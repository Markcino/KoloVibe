"""Decision A (RV2-01): edits to a published video's text are reviewed before they show.

Title, description, category and tags are material: on a published video an edit to any of them becomes a
pending `MetadataRevision` and the approved values stay live. The cover frame comes from media that was
already reviewed, so it still applies at once. Moderation decides through `apply`, which is idempotent per
decision id; the creator reads the outcome on their own video (`review_state`).
"""

from uuid import UUID

from django.db import transaction
from django.utils import timezone

from . import security_audit
from .models import MetadataRevision, Video

MATERIAL = ("title", "description", "category", "tags")
ACTIONS = {"approve": MetadataRevision.Status.APPROVED, "reject": MetadataRevision.Status.REJECTED}
VISIBLE = (MetadataRevision.Status.PENDING, MetadataRevision.Status.APPROVED, MetadataRevision.Status.REJECTED)


def live(video):
    return {name: getattr(video, name) for name in MATERIAL}


def _render(revision):
    if revision is None:
        return None
    pending = revision.status == MetadataRevision.Status.PENDING
    return {"id": str(revision.id), "status": revision.status, "submitted_at": revision.created_at.isoformat(),
            "decided_at": revision.decided_at.isoformat() if revision.decided_at else None,
            "reason_code": revision.reason_code, "proposed": dict(revision.proposed) if pending else None}


def review_states(videos):
    """The newest pending or decided revision for each video, in one query (owner views only)."""
    ids = [video.id for video in videos]
    latest = {}
    for revision in MetadataRevision.objects.filter(video_id__in=ids, status__in=VISIBLE).order_by("-created_at", "-id"):
        latest.setdefault(revision.video_id, revision)
    return {video_id: _render(latest.get(video_id)) for video_id in ids}


def pending(video, *, lock=False):
    rows = MetadataRevision.objects.filter(video=video, status=MetadataRevision.Status.PENDING)
    return (rows.select_for_update() if lock else rows).first()


def submit(video, requested):
    """Hold a material edit to a published video. The caller holds the video row lock.

    The proposal is the live text, then any pending proposal, then this request, so a partial edit keeps the
    rest of the pending change. Returning to the live text withdraws the proposal; repeating it is a no-op.
    """
    current = pending(video, lock=True)
    desired = live(video) | (dict(current.proposed) if current else {}) | requested
    if current is not None and desired == current.proposed:
        return False
    now = timezone.now()
    if current is not None:
        current.status = (MetadataRevision.Status.WITHDRAWN if desired == live(video)
                          else MetadataRevision.Status.SUPERSEDED)
        current.decided_at = now
        current.save(update_fields=["status", "decided_at"])
    if desired == live(video):
        if current is not None:
            security_audit.record("video.edit_withdrawn", video.id)
        return current is not None
    MetadataRevision.objects.create(video=video, proposed=desired, created_at=now)
    security_audit.record("video.edit_submitted", video.id)
    return True


def queue(cursor, scope_ids=None):
    rows = MetadataRevision.objects.filter(status=MetadataRevision.Status.PENDING,
                                           video__deleted_at__isnull=True).order_by("id")
    if scope_ids is not None:
        rows = rows.filter(video_id__in=scope_ids)
    if cursor is not None:
        rows = rows.filter(id__gt=cursor)
    page = list(rows[:21])
    items = [{"id": str(row.id), "video_id": str(row.video_id), "title": row.proposed["title"],
              "submitted_at": row.created_at.isoformat()} for row in page[:20]]
    return {"items": items, "next_cursor": items[-1]["id"] if len(page) > 20 else None}


def detail(revision_id):
    revision = MetadataRevision.objects.select_related("video").filter(
        pk=revision_id, video__deleted_at__isnull=True).first()
    if revision is None:
        return None
    video = revision.video
    return {"id": str(revision.id), "video_id": str(video.id), "creator_id": str(video.creator_id),
            "status": revision.status, "submitted_at": revision.created_at.isoformat(),
            "video_state": video.state, "live": live(video), "proposed": dict(revision.proposed)}


class Conflict(Exception):
    pass


def apply(revision_id, decision_id, action, reason_code):
    """Approve or reject one pending revision. Replaying the same decision id answers the same outcome."""
    if action not in ACTIONS:
        raise ValueError("Invalid edit decision")
    if reason_code is not None and (not isinstance(reason_code, str) or not 2 <= len(reason_code) <= 64):
        raise ValueError("Invalid reason code")
    with transaction.atomic():
        head = MetadataRevision.objects.filter(pk=revision_id).values_list("video_id", flat=True).first()
        if head is None:
            return None
        video = Video.objects.select_for_update().filter(pk=head, deleted_at__isnull=True).first()
        if video is None:
            return None
        revision = MetadataRevision.objects.select_for_update().get(pk=revision_id)
        if revision.decision_id is not None:
            if revision.decision_id != decision_id or revision.status != ACTIONS[action]:
                raise Conflict
            return revision
        if revision.status != MetadataRevision.Status.PENDING:
            raise Conflict
        if MetadataRevision.objects.filter(decision_id=decision_id).exists():
            raise Conflict
        revision.status, revision.decided_at = ACTIONS[action], timezone.now()
        revision.decision_id, revision.reason_code = decision_id, reason_code
        revision.save(update_fields=["status", "decided_at", "decision_id", "reason_code"])
        if action == "approve":
            changed = [name for name in MATERIAL if getattr(video, name) != revision.proposed[name]]
            for name in changed:
                setattr(video, name, revision.proposed[name])
            video.moderation_revision += 1
            video.save(update_fields=[*changed, "moderation_revision"])
        security_audit.record("video.edit_approved" if action == "approve" else "video.edit_rejected", video.id)
    return revision


def parse_scope(ids):
    if ids is None:
        return None
    if not isinstance(ids, list) or len(ids) > 1000 or any(not isinstance(item, str) for item in ids):
        raise ValueError("Invalid assignment scope")
    return [UUID(item) for item in ids]
