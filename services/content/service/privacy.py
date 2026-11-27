"""Decision C slice 2c: Content erases one creator's videos (docs/privacy/account-erasure-plan-PROPOSED.md).

Identity sends this request only after Creators confirmed, with the creator profile id Content keys videos by
(null for someone who was never a creator). It runs on the media worker, the only Content process with R2 access.

1. A repeated delivery is recognised from the inbox before anything else, so R2 is never touched twice for it.
2. Every object Content knows for those videos is removed from R2 first: the original upload, the playback rendition
   and the poster. Already-missing objects count as removed. A storage outage raises, nothing is recorded, and the
   task retries. Older renditions and posters that a re-encode or cover change left behind have no row pointing at
   them, so the worker then lists each upload's `playback/<upload>/` and each video's `posters/<video>/` prefix and
   removes every object there too. Only if a listed object has a name the worker may not delete (outside the reviewed
   key pattern) is `untracked_media` reported as retained, so the request cannot complete with an object left.
3. Then, in one transaction with the inbox entry and the confirmation event:
   - deleted: metadata revisions (proposed titles and descriptions) and upload records;
   - each video row is kept, because originality attestations, prescreening, copyright claim states and screening
     records point at it (`PROTECT`) and are evidence. The row is emptied instead: no title, description, tags,
     category, cover or storage keys, `removed`, private and marked deleted, so it never shows again;
   - retained, decision pending: attestations, prescreen results, copyright claim states, rights events,
     fingerprints, screening records, source digests, moderation receipts and the append-only audit trail.
No constraint or append-only trigger is disabled. Nothing here reads another service's database.
"""
import re
import uuid

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from . import media_storage
from .events import ERASURE_CONFIRMED, ERASURE_REQUESTED, SERVICE, accept_once, already_accepted, record_event
from .models import (AuditEvent, CopyrightClaimState, Fingerprint, MediaUpload, MetadataRevision, ModerationReceipt,
                     OriginalityAttestation, PrescreenResult, RightsEvent, ScreeningRecord, SourceDigest, Video)


def _request(payload):
    if (not isinstance(payload, dict) or set(payload) != {"request_id", "account_id", "service", "creator_id"}
            or payload["service"] != SERVICE):
        raise ValueError("Invalid erasure request")
    for key in ("request_id", "account_id", "creator_id"):
        if key == "creator_id" and payload[key] is None:
            continue
        if not isinstance(payload[key], str) or str(uuid.UUID(payload[key])) != payload[key]:
            raise ValueError("Invalid erasure request")
    return payload["request_id"], payload["account_id"], payload["creator_id"]


def _keys(video_ids):
    """Every R2 key a row names for these videos, plus the original of every upload Content recorded, and the
    prefixes under which superseded renditions and posters of those uploads and videos can remain."""
    keys = set()
    for provider, poster in Video.objects.filter(pk__in=video_ids).values_list("provider_asset_id", "poster_asset_id"):
        keys.update(key for key in (provider, poster) if key)
    uploads = set(MediaUpload.objects.filter(video_id__in=video_ids).values_list("id", flat=True))
    uploads |= set(OriginalityAttestation.objects.filter(video_id__in=video_ids).values_list("upload_id", flat=True))
    uploads |= set(PrescreenResult.objects.filter(video_id__in=video_ids).values_list("upload_id", flat=True))
    keys.update(f"originals/{upload}.mp4" for upload in uploads)
    prefixes = [f"playback/{upload}/" for upload in sorted(map(str, uploads))]
    prefixes += [f"posters/{video}/" for video in sorted(map(str, video_ids))]
    return sorted(keys), prefixes


def _remove_untracked(prefixes, removed):
    """Remove what remains under each prefix; False if something there cannot be removed by this worker."""
    complete = True
    for prefix in prefixes:
        for key in media_storage.list_keys(prefix):  # StorageUnavailable propagates, like a failed delete
            if key in removed:
                continue
            if not re.fullmatch(media_storage.KEY, key):
                complete = False
                continue
            media_storage.delete_object(key)
            removed.add(key)
    return complete


def _retained(account_id, video_ids):
    checks = {
        "attestations": OriginalityAttestation.objects.filter(Q(account_id=account_id) | Q(video_id__in=video_ids)),
        "prescreen_results": PrescreenResult.objects.filter(video_id__in=video_ids),
        "copyright_claims": CopyrightClaimState.objects.filter(video_id__in=video_ids),
        "rights_events": RightsEvent.objects.filter(Q(video_id__in=video_ids) | Q(actor_id=account_id)),
        "fingerprints": Fingerprint.objects.filter(video_id__in=video_ids),
        "screening_records": ScreeningRecord.objects.filter(video_id__in=video_ids),
        "source_digests": SourceDigest.objects.filter(first_video_id__in=video_ids),
        "moderation_receipts": ModerationReceipt.objects.filter(video_id__in=video_ids),
        "audit_events": AuditEvent.objects.filter(Q(actor_id=account_id) | Q(subject_id__in=video_ids)),
    }
    return [name for name, rows in checks.items() if rows.exists()]


def erase(event_id, payload):
    """Erase once and record the confirmation; a repeated delivery changes nothing and returns False."""
    request_id, account_id, creator_id = _request(payload)
    if already_accepted(event_id):
        return False
    video_ids = list(Video.objects.filter(creator_id=creator_id).values_list("id", flat=True)) if creator_id else []
    keys, prefixes = _keys(video_ids)
    for key in keys:
        media_storage.delete_object(key)  # StorageUnavailable propagates: nothing is recorded and the task retries
    removed = set(keys)
    untracked_removed = _remove_untracked(prefixes, removed)
    with transaction.atomic():
        if not accept_once(event_id, ERASURE_REQUESTED):
            return False
        # A video created while the objects were being removed is left for the retry of a later request; this
        # request covers the videos that existed when it started.
        counts = {"media_objects": len(removed)}
        counts["metadata_revisions"], _ = MetadataRevision.objects.filter(video_id__in=video_ids).delete()
        counts["upload_records"], _ = MediaUpload.objects.filter(video_id__in=video_ids).delete()
        counts["videos_emptied"] = Video.objects.filter(pk__in=video_ids).update(
            title="", description="", tags=[], category=None, cover_time_ms=None, poster_asset_id=None,
            provider_asset_id=None, failure_reason=None, state=Video.State.REMOVED,
            visibility=Video.Visibility.PRIVATE, deleted_at=timezone.now())
        retained = _retained(account_id, video_ids)
        if not untracked_removed:
            retained.append("untracked_media")
        record_event(ERASURE_CONFIRMED, {"request_id": request_id, "account_id": account_id, "service": SERVICE,
                                         "counts": counts, "retained": retained})
        return True
