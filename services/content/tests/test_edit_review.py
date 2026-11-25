"""Decision A (RV2-01): edits to a published video's text wait for review; the approved text stays live."""

import json
from uuid import uuid4

from django.db import IntegrityError, transaction
from django.test import RequestFactory, TestCase
from django.utils import timezone

from service.media_api import media_api
from service.models import AuditEvent, MetadataRevision, Video
from service.moderation import moderation_video
from service.videos import _public_videos


class EditReviewTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.creator = uuid4()
        now = timezone.now()
        self.video = Video.objects.create(
            creator_id=self.creator, title="Original", description="Live text", category="hipco", tags=["monrovia"],
            state="published", visibility="public", provider_asset_id=f"playback/{uuid4()}/{uuid4()}.mp4",
            moderation_approved_at=now, published_at=now, duration_ms=2000, duration_seconds=2)
        self.owner = {"creator_id": str(self.creator), "video_id": str(self.video.id)}

    def media(self, operation, fields=None):
        request = self.factory.post("/internal/videos/media/" + operation, self.owner | (fields or {}),
                                    content_type="application/json")
        request.service_caller = "gateway"
        return media_api(request, operation)

    def moderation(self, operation, data, caller="moderation"):
        request = self.factory.post("/internal/videos/moderation/" + operation, data, content_type="application/json")
        request.service_caller = caller
        return moderation_video(request, operation)

    def edit(self, **fields):
        result = self.media("edit", fields)
        self.assertEqual(result.status_code, 200, result.content)
        return json.loads(result.content)

    def decide(self, revision_id, action, decision_id=None, reason_code=None):
        return self.moderation("edit-apply", {"revision_id": str(revision_id), "action_id": str(decision_id or uuid4()),
                                              "action": action, "reason_code": reason_code})

    def kinds(self):
        return list(AuditEvent.objects.filter(subject_id=self.video.id).order_by("occurred_at").values_list("kind", flat=True))

    def public_titles(self):
        return [item.title for item in _public_videos()]

    def test_material_edit_is_held_and_live_text_unchanged(self):
        data = self.edit(title="Changed", tags=["#New"])
        self.assertEqual((data["title"], data["tags"]), ("Original", ["monrovia"]))
        review = data["edit_review"]
        self.assertEqual(review["status"], "pending")
        self.assertEqual(review["proposed"], {"title": "Changed", "description": "Live text", "category": "hipco",
                                              "tags": ["new"]})
        self.assertIsNone(review["decided_at"])
        self.video.refresh_from_db()
        self.assertEqual((self.video.title, self.video.tags, self.video.moderation_revision), ("Original", ["monrovia"], 0))
        self.assertEqual(self.public_titles(), ["Original"])
        self.assertEqual(self.kinds(), ["video.edit_submitted"])

    def test_repeated_edits_supersede_and_merge_without_skipping_review(self):
        first = self.edit(title="One")["edit_review"]
        self.assertEqual(self.edit(title="One")["edit_review"]["id"], first["id"])  # a duplicate is a no-op
        second = self.edit(description="Two")["edit_review"]
        self.assertNotEqual(second["id"], first["id"])
        self.assertEqual(second["proposed"]["title"], "One")  # the partial edit keeps the pending title
        self.assertEqual(second["proposed"]["description"], "Two")
        statuses = dict(MetadataRevision.objects.values_list("id", "status"))
        self.assertEqual(sorted(statuses.values()), ["pending", "superseded"])
        # The superseded proposal can no longer be approved.
        self.assertEqual(self.decide(first["id"], "approve").status_code, 409)
        self.video.refresh_from_db()
        self.assertEqual(self.video.title, "Original")

    def test_returning_to_live_text_withdraws_the_proposal(self):
        self.edit(title="Temporary")
        data = self.edit(title="Original")
        self.assertIsNone(data["edit_review"])
        self.assertEqual(MetadataRevision.objects.get().status, "withdrawn")
        self.assertEqual(self.kinds(), ["video.edit_submitted", "video.edit_withdrawn"])

    def test_cover_still_applies_at_once_beside_a_held_edit(self):
        data = self.edit(title="Held", cover_time_ms=1000)
        self.assertEqual((data["title"], data["cover_time_ms"]), ("Original", 1000))
        self.video.refresh_from_db()
        self.assertEqual(self.video.moderation_revision, 1)

    def test_unpublished_states_still_edit_directly(self):
        Video.objects.filter(pk=self.video.pk).update(state="rejected", visibility="private")
        data = self.edit(title="Fixed")
        self.assertEqual((data["title"], data["edit_review"]), ("Fixed", None))
        self.assertFalse(MetadataRevision.objects.exists())

    def test_approval_makes_the_proposal_live_and_replays_safely(self):
        revision = self.edit(title="Approved title", category="comedy")["edit_review"]["id"]
        decision = uuid4()
        self.assertEqual(self.decide(revision, "approve", decision).status_code, 200)
        self.assertEqual(self.decide(revision, "approve", decision).status_code, 200)  # a lost answer replays
        self.assertEqual(self.decide(revision, "reject", decision).status_code, 409)
        self.assertEqual(self.decide(revision, "reject").status_code, 409)
        self.video.refresh_from_db()
        self.assertEqual((self.video.title, self.video.category, self.video.moderation_revision), ("Approved title", "comedy", 1))
        self.assertEqual(self.public_titles(), ["Approved title"])
        review = json.loads(self.media("detail").content)["edit_review"]
        self.assertEqual((review["status"], review["proposed"]), ("approved", None))
        self.assertIsNotNone(review["decided_at"])
        self.assertEqual(self.kinds(), ["video.edit_submitted", "video.edit_approved"])

    def test_rejection_keeps_live_text_and_tells_the_creator(self):
        revision = self.edit(title="Spam title")["edit_review"]["id"]
        self.assertEqual(self.decide(revision, "reject", reason_code="REVIEWED_REJECT").status_code, 200)
        self.video.refresh_from_db()
        self.assertEqual(self.video.title, "Original")
        request = self.factory.post("/internal/videos/media/library", {"creator_id": str(self.creator), "cursor": None},
                                    content_type="application/json")
        request.service_caller = "gateway"
        library = json.loads(media_api(request, "library").content)
        review = library["items"][0]["edit_review"]
        self.assertEqual((review["status"], review["reason_code"]), ("rejected", "REVIEWED_REJECT"))
        # A fresh edit after a rejection opens a new review.
        self.assertEqual(self.edit(title="Second try")["edit_review"]["status"], "pending")

    def test_one_pending_revision_per_video_is_enforced_by_the_database(self):
        self.edit(title="Pending")
        with self.assertRaises(IntegrityError), transaction.atomic():
            MetadataRevision.objects.create(video=self.video, proposed={"title": "Race"})

    def test_reviewer_queue_detail_and_scope(self):
        revision = self.edit(title="Queued")["edit_review"]["id"]
        other = Video.objects.create(creator_id=uuid4(), title="Other")
        queue = json.loads(self.moderation("edits", {"cursor": None}).content)
        self.assertEqual(queue["items"], [{"id": revision, "video_id": str(self.video.id), "title": "Queued",
                                           "submitted_at": queue["items"][0]["submitted_at"]}])
        scoped = json.loads(self.moderation("edits", {"cursor": None, "scope_ids": [str(other.id)]}).content)
        self.assertEqual(scoped["items"], [])
        detail = json.loads(self.moderation("edit-detail", {"revision_id": revision}).content)
        self.assertEqual((detail["live"]["title"], detail["proposed"]["title"], detail["status"], detail["video_state"]),
                         ("Original", "Queued", "pending", "published"))
        self.assertEqual(self.moderation("edit-detail", {"revision_id": str(uuid4())}).status_code, 404)

    def test_only_moderation_may_read_or_decide(self):
        revision = self.edit(title="Guarded")["edit_review"]["id"]
        for operation, data in (("edits", {"cursor": None}), ("edit-detail", {"revision_id": revision}),
                                ("edit-apply", {"revision_id": revision, "action_id": str(uuid4()),
                                                "action": "approve", "reason_code": None})):
            self.assertEqual(self.moderation(operation, data, caller="gateway").status_code, 403)
        self.assertEqual(self.decide(revision, "publish").status_code, 400)
        self.assertEqual(self.moderation("edits", {"cursor": None, "status": "pending"}).status_code, 400)

    def test_deleted_video_hides_its_pending_edit(self):
        revision = self.edit(title="Gone")["edit_review"]["id"]
        self.assertEqual(self.media("delete").status_code, 200)
        self.assertEqual(json.loads(self.moderation("edits", {"cursor": None}).content)["items"], [])
        self.assertEqual(self.decide(revision, "approve").status_code, 404)

    def test_removal_still_restricts_immediately_while_an_edit_waits(self):
        revision = self.edit(title="Waiting")["edit_review"]["id"]
        removal = self.moderation("apply", {"video_id": str(self.video.id), "action_id": str(uuid4()),
                                            "action": "remove", "revision": 0})
        self.assertEqual(removal.status_code, 200)
        self.assertEqual(self.public_titles(), [])
        self.assertEqual(self.decide(revision, "reject").status_code, 200)
