import json
from datetime import timedelta
from unittest.mock import patch
from uuid import uuid4
from django.test import TestCase, RequestFactory
from django.utils import timezone
from service.models import ModeratorAssignment, ReviewerPreview, AuditEvent, Report
from service.workflow import moderation_workflow


class ReviewerTests(TestCase):
    def setUp(self):
        self.actor, self.other, self.video = uuid4(), uuid4(), uuid4()
        self.grant = ModeratorAssignment.objects.create(moderator_id=self.actor, queue_scope="videos", target_id=self.video)
        self.metadata = {"id": str(self.video), "title": "<script>title</script>", "description": "Private description",
                         "state": "review", "duration_seconds": 20, "rights_status": "flagged", "preview_available": True}

    def call(self, operation, data, actor=None, role="moderator", mfa=True):
        request = RequestFactory().post("/internal/moderation/" + operation, {
            "actor_id": str(actor or self.actor), "role": role, "mfa_verified": mfa, "data": data}, content_type="application/json")
        request.service_caller = "gateway"
        return moderation_workflow(request, operation)

    @patch("service.workflow._content")
    def test_detail_is_scoped_audited_and_has_no_storage_locations(self, content):
        content.side_effect = lambda *args: dict(self.metadata)
        Report.objects.create(id=uuid4(), video_id=self.video, reporter_id=uuid4(), reason="spam", details="private report")
        response = self.call("video_detail", {"target_id": str(self.video)})
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data["reports"], [])
        self.assertEqual(data["video"]["rights_status"], "flagged")
        self.assertEqual(data["preview"]["url"], "/api/v1/moderation/previews/" + data["preview"]["id"])
        self.assertNotIn(b"playback/", response.content)
        self.assertTrue(AuditEvent.objects.filter(kind="moderation.reviewer_read", actor_id=self.actor).exists())
        self.assertEqual(self.call("video_detail", {"target_id": str(uuid4())}).status_code, 403)
        self.assertEqual(self.call("video_detail", {"target_id": str(self.video)}, actor=self.other).status_code, 403)
        self.assertEqual(AuditEvent.objects.filter(kind="moderation.assignment_denied").count(), 2)

    @patch("service.reviewer.signed_internal_request")
    def test_preview_requires_owner_assignment_mfa_and_unexpired_lease(self, peer):
        lease = ReviewerPreview.objects.create(actor_id=self.actor, queue_scope="videos", target_id=self.video,
                                               video_id=self.video, expires_at=timezone.now() + timedelta(seconds=60))
        data = {"preview_id": str(lease.id)}
        for actor, role, mfa in ((self.other, "moderator", True), (self.actor, "viewer", True), (self.actor, "moderator", False)):
            self.assertEqual(self.call("preview", data, actor=actor, role=role, mfa=mfa).status_code, 403)
        peer.assert_not_called()
        response = peer.return_value.__enter__.return_value
        response.status, response.headers = 200, {"Content-Type": "video/mp4"}
        response.read.return_value = b"test-mp4"
        result = self.call("preview", data)
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.content, b"test-mp4")
        self.assertIn("no-store", result["Cache-Control"])
        self.assertTrue(AuditEvent.objects.filter(kind="moderation.preview_read").exists())
        self.grant.active = False
        self.grant.save()
        self.assertEqual(self.call("preview", data).status_code, 403)
        lease.expires_at = timezone.now() - timedelta(seconds=1)
        lease.save()
        self.assertEqual(self.call("preview", data, role="administrator").status_code, 403)
