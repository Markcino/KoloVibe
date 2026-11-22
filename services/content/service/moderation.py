"""Apply authenticated moderation decisions in the Content transaction."""

import json
from uuid import UUID

from django.db import DatabaseError, transaction
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import ModerationReceipt, Video, RightsEvent, OriginalityAttestation
from .copyright import audit, claim
from . import media_storage as storage


TRANSITIONS = {
    "publish": (Video.State.REVIEW, Video.State.PUBLISHED),
    "reject": (Video.State.REVIEW, Video.State.REJECTED),
    "remove": (Video.State.PUBLISHED, Video.State.REMOVED),
    "restore": (Video.State.REMOVED, Video.State.PUBLISHED),
}


def _error(detail, status):
    return JsonResponse({"detail": detail}, status=status)


def _apply(video_id, action_id, action, revision, *, copyright=False, actor_id=None, reason="", report_id=None):
    if not isinstance(action, str) or action not in TRANSITIONS or type(revision) is not int or revision < 0:
        raise ValueError("Invalid moderation transition")
    if type(copyright) is not bool or not copyright and (actor_id is not None or reason or report_id is not None):
        raise ValueError("Invalid copyright metadata")
    if report_id is not None and (not isinstance(report_id, str) or str(UUID(report_id)) != report_id):
        raise ValueError("Invalid copyright report")
    with transaction.atomic():
        video = Video.objects.select_for_update().filter(pk=video_id, deleted_at__isnull=True).first()
        if video is None:
            return _error("Video not found", 404)
        receipt = ModerationReceipt.objects.filter(pk=action_id).first()
        if receipt:
            if (receipt.video_id, receipt.action, receipt.previous_revision) != (video_id, action, revision):
                return _error("Moderation action conflict", 409)
            evidence = RightsEvent.objects.filter(pk=action_id).first()
            if copyright:
                if evidence is None or (str(evidence.actor_id), evidence.reason, evidence.event, evidence.payload) != (actor_id, reason, "copyright_" + action, {"report_id": report_id}):
                    return _error("Copyright action conflict", 409)
            elif evidence is not None:
                return _error("Copyright action conflict", 409)
            return JsonResponse({"applied": True})

        previous, new_state = TRANSITIONS[action]
        prior_visibility = Video.Visibility.PUBLIC if action == "remove" else Video.Visibility.PRIVATE
        if (video.moderation_revision != revision or video.state != previous
                or video.visibility != prior_visibility):
            return _error("Video state changed", 409)
        if new_state == Video.State.PUBLISHED:
            if action == "publish" and video.rights_status in {"claimed", "removed"}:
                return _error("Copyright review required", 409)
            if not video.provider_asset_id:
                return _error("Processed video asset required", 409)
            now = timezone.now()
            video.moderation_approved_at = now
            # Reviewer approval does not make a new video public. Restoration
            # of a previously public removal is a separate moderated action.
            if action == "restore":
                video.published_at = video.published_at or now
        if copyright:
            if action not in {"remove", "restore"} or not isinstance(reason, str) or not 10 <= len(reason.strip()) <= 2000 or len(reason) > 2000:
                raise ValueError("Copyright action reason required")
            actor = UUID(actor_id)
            if action == "restore" and report_id:
                claim(video, UUID(report_id), False)
            if action == "remove":
                video.rights_status = "removed"
            else:
                from .models import CopyrightClaimState
                video.rights_status = "claimed" if CopyrightClaimState.objects.filter(video=video, active=True).exists() else "restored"
            audit(video, "copyright_" + action, reason, actor=actor, ident=action_id, payload={"report_id": report_id})
        elif action == "publish" and video.rights_status == "flagged" and OriginalityAttestation.objects.filter(video=video).exists():
            video.rights_status = "attested"
        video.state = new_state
        video.visibility = Video.Visibility.PUBLIC if action == "restore" else Video.Visibility.PRIVATE
        video.moderation_revision += 1
        if not copyright and action in ("remove", "restore"):
            video.rights_status = Video.RightsStatus.REMOVED if action == "remove" else Video.RightsStatus.RESTORED
        video.save(update_fields=[
            "state", "visibility", "moderation_revision", "moderation_approved_at", "published_at", "rights_status",
        ])
        ModerationReceipt.objects.create(action_id=action_id, video_id=video_id,
                                         action=action, previous_revision=revision)
    return JsonResponse({"applied": True})


@require_POST
def moderation_video(request, operation):
    if getattr(request, "service_caller", None) != "moderation":
        return _error("Forbidden", 403)
    try:
        if len(request.body) > 48000:
            raise ValueError("Request too large")
        data = json.loads(request.body)
        fields = {"inspect": {"video_id"}, "apply": {"video_id", "action_id", "action", "revision"},
                  "queue": {"cursor"}, "detail": {"video_id"}, "preview": {"video_id"}, "totals": {"scope_ids"},
                  "rights": {"video_id", "command_id", "report_id", "event", "actor_id", "reason"}}
        if (operation not in fields or not isinstance(data, dict) or not fields[operation] <= set(data)
                or set(data) - fields[operation] - ({"scope_ids", "status"} if operation == "queue" else {"copyright", "actor_id", "reason", "report_id"} if operation == "apply" else set())):
            raise ValueError("Invalid moderation request")
        if operation in {"queue", "totals"}:
            states = {"review", "published", "rejected", "removed"}
            state = data.get("status", "review")
            if not isinstance(state, str) or state not in states:
                raise ValueError("Unsupported status")
            videos = Video.objects.filter(deleted_at__isnull=True).order_by("id")
            ids = data.get("scope_ids")
            if ids is not None:
                if not isinstance(ids, list) or len(ids) > 1000 or any(not isinstance(item, str) for item in ids):
                    raise ValueError("Invalid assignment scope")
                videos = videos.filter(id__in=[UUID(item) for item in ids])
            if operation == "totals":
                return JsonResponse({status: videos.filter(state=status).count() for status in sorted(states)})
            videos = videos.filter(state=state)
            if data["cursor"] is not None:
                videos = videos.filter(id__gt=UUID(data["cursor"]))
            page = list(videos[:21])
            items = [{"id": str(video.id), "title": video.title} for video in page[:20]]
            return JsonResponse({"items": items, "next_cursor": items[-1]["id"] if len(page) > 20 else None})
        video_id = UUID(data["video_id"])
        if operation == "rights":
            if data["event"] not in {"claim", "dismiss"} or not isinstance(data["reason"], str) or not 1 <= len(data["reason"]) <= 2000:
                raise ValueError("Rights reason required")
            command, report, actor = UUID(data["command_id"]), UUID(data["report_id"]), UUID(data["actor_id"])
            with transaction.atomic():
                video = Video.objects.select_for_update().filter(pk=video_id, deleted_at__isnull=True).first()
                if video is None:
                    return _error("Video not found", 404)
                prior = RightsEvent.objects.filter(pk=command).first()
                event = "copyright_" + data["event"]
                if prior:
                    if (prior.video_id, prior.actor_id, prior.event, prior.reason, prior.payload) != (video_id, actor, event, data["reason"], {"report_id": str(report)}):
                        return _error("Rights command conflict", 409)
                else:
                    claim(video, report, data["event"] == "claim")
                    audit(video, event, data["reason"], actor=actor, ident=command, payload={"report_id": str(report)})
            return JsonResponse({"applied": True})
        if operation == "apply":
            return _apply(video_id, UUID(data["action_id"]), data["action"], data["revision"],
                          **{name: data[name] for name in ("copyright", "actor_id", "reason", "report_id") if name in data})
        video = Video.objects.filter(pk=video_id, deleted_at__isnull=True).first()
        if video is None:
            return _error("Video not found", 404)
        if operation == "detail":
            return JsonResponse({"id": str(video.id), "title": video.title, "description": video.description,
                "state": video.state, "duration_seconds": video.duration_seconds,
                "rights_status": video.rights_status, "preview_available": bool(video.provider_asset_id
                    and video.provider_asset_id.startswith("playback/"))})
        if operation == "preview":
            if not video.provider_asset_id or not video.provider_asset_id.startswith("playback/"):
                return _error("Preview unavailable", 404)
            response = HttpResponse(storage.read_preview(video.provider_asset_id), content_type="video/mp4")
            response["Cache-Control"] = "private, no-store"
            return response
        return JsonResponse({"creator_id": str(video.creator_id), "state": video.state,
                             "visibility": video.visibility, "revision": video.moderation_revision})
    except (ValueError, TypeError, AttributeError):
        return _error("Invalid moderation request", 400)
    except (storage.StorageUnavailable, storage.ObjectMissing):
        return _error("Preview unavailable", 503)
    except DatabaseError:
        return _error("Video service unavailable", 503)
