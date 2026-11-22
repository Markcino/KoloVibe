"""Content-owned rights evidence and deterministic pre-screen routing."""
import hashlib
import hmac
import json
import re

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .models import (CopyrightClaimState, OriginalityAttestation, Fingerprint,
                     PrescreenResult, RightsEvent, SourceDigest, Video, ScreeningRecord)

ATTESTATION_VERSION = "R1-originality-v1"
RIGHTS = {value for value, _ in Video.RightsStatus.choices}


def audit(video, event, reason, *, actor=None, ident=None, payload=None):
    if not transaction.get_connection().in_atomic_block:
        raise RuntimeError("Rights evidence requires its owning transaction")
    values = {"video_id": video.id, "actor_id": actor, "event": event, "reason": reason,
              "payload": payload or {}}
    if ident is None:
        return RightsEvent.objects.create(**values)
    row, created = RightsEvent.objects.get_or_create(id=ident, defaults=values)
    if not created and any(getattr(row, key) != value for key, value in values.items()):
        raise ValueError("Rights event conflict")
    return row


def analyze(source, *, media=None, audio_provider=None):
    from uuid import UUID
    from .screening import Media, MUSIC
    from .screening_providers import ChromaprintProvider, ExactHashProvider
    media = media or Media(UUID(int=0), UUID(int=0), source, source, 300_000, source.parent)
    exact = ExactHashProvider().screen(media)
    digest = next(value for kind, value in exact.fingerprints if kind == "sha256")
    fingerprints = list(exact.fingerprints)
    try:
        audio_result = (audio_provider or ChromaprintProvider()).screen(media)
        fingerprints.extend(audio_result.fingerprints)
        audio = "matched" if any(item.kind == MUSIC for item in audio_result.findings) else "clear"
    except Exception:
        # Existing provider adapters fail closed for absent tools/invalid media/service failure.
        audio = "unavailable"
    audio_prints = [value for kind, value in fingerprints if kind == "chromaprint"]
    fingerprint = hashlib.sha256(audio_prints[0].encode()).hexdigest() if audio_prints else ""
    return {"sha256": digest, "fingerprint": fingerprint, "audio": audio,
            "fingerprints": fingerprints, "duplicate": bool(exact.findings)}


def route(video, upload, result):
    """Called only under the worker's locked, current lease transaction."""
    first, _ = SourceDigest.objects.get_or_create(sha256=result["sha256"], defaults={"first_video_id": video.id})
    reasons = []
    if first.first_video_id != video.id or result.get("duplicate"):
        reasons.append("exact_duplicate")
    if result["audio"] != "clear":
        reasons.append("audio_" + result["audio"])
    attestation = OriginalityAttestation.objects.filter(upload_id=upload.id, video=video).first()
    if attestation is None:
        reasons.append("missing_attestation")
    if video.rights_status in {"claimed", "removed"}:
        reasons.append("active_copyright_case")
    if result.get("safety_hold"):
        reasons.append("safety_review")
    policy = attestation.review_policy if attestation else {}
    trusted = policy.get("trusted") is True
    rate = policy.get("sample_percent", 100)
    # A trust snapshot cannot authorize delayed/retried jobs after the reservation expires.
    if upload.expires_at <= timezone.now():
        trusted = False
    bucket = int.from_bytes(hmac.new(settings.SECRET_KEY.encode(), upload.id.bytes, hashlib.sha256).digest()[:8], "big") % 100
    sampled = bucket < rate
    auto = not reasons and trusted and not sampled
    disposition = "flagged" if reasons else "sampled" if trusted and sampled else "auto_approved" if auto else "untrusted"
    for kind, value in result.get("fingerprints", []):
        Fingerprint.objects.get_or_create(video=video, kind=kind, value=value, blocked=False)
    PrescreenResult.objects.create(upload_id=upload.id, video=video, source_sha256=result["sha256"],
        fingerprint_sha256=result["fingerprint"], reasons=reasons, disposition=disposition)
    # Do not overwrite a claim or takedown that arrived while the worker was encoding.
    if video.rights_status not in {"claimed", "removed"}:
        video.rights_status = "flagged" if reasons else "attested"
    if video.rights_status in {"claimed", "removed"}:
        auto = False
    ScreeningRecord.objects.create(video=video, provider="copyright_gate", kind="decision", score=0,
        action="publish" if auto else "review", reason=disposition)
    audit(video, "prescreen_completed", ",".join(reasons) or disposition,
          payload={"upload_id": str(upload.id), "disposition": disposition, "policy_version": policy.get("policy_version")})
    return auto


def claim(video, report_id, active):
    row, _ = CopyrightClaimState.objects.select_for_update().get_or_create(report_id=report_id, defaults={"video": video})
    if row.video_id != video.id:
        raise ValueError("Claim conflict")
    row.active = active
    row.save(update_fields=["active"])
    if video.rights_status != "removed":
        if CopyrightClaimState.objects.filter(video=video, active=True).exists():
            video.rights_status = "claimed"
        else:
            screen = PrescreenResult.objects.filter(video=video).order_by("-created_at").first()
            video.rights_status = "flagged" if screen is None or screen.reasons else "attested"
    video.save(update_fields=["rights_status"])
