import json
from unittest.mock import patch
from uuid import uuid4
from django.test import SimpleTestCase, RequestFactory
from django.http import JsonResponse
from service.moderation import moderation_endpoint
from service.reviewer_contracts import valid_detail
from .test_videos import Response


class ReviewerGatewayTests(SimpleTestCase):
    def test_detail_requires_live_mfa_and_forwards_only_bound_actor(self):
        actor, target = str(uuid4()), str(uuid4())
        with patch("service.moderation.authenticated_actor", return_value=(actor, "moderator")), \
             patch("service.standing.identity_context", return_value={"account_id": actor, "mfa_verified": False}), \
             patch("service.moderation._forward") as forward:
            response = moderation_endpoint(RequestFactory().get("/detail"), "video_detail", target_id=target)
            self.assertEqual(response.status_code, 403)
            forward.assert_not_called()
        with patch("service.moderation.authenticated_actor", return_value=(actor, "moderator")), \
             patch("service.standing.identity_context", return_value={"account_id": actor, "mfa_verified": True}), \
             patch("service.moderation._forward", return_value=JsonResponse({})) as forward:
            moderation_endpoint(RequestFactory().get("/detail"), "video_detail", target_id=target)
            forward.assert_called_once_with("video_detail", actor, "moderator", {"target_id": target}, mfa_verified=True)
            self.assertEqual(moderation_endpoint(RequestFactory().get("/detail", {"actor_id": str(uuid4())}),
                                                "video_detail", target_id=target).status_code, 400)

    def test_detail_validator_rejects_raw_storage_url_and_unknown_records(self):
        video = str(uuid4())
        detail = {"record": {"id": video, "title": "Title"}, "video": {"id": video, "title": "Title", "description": "",
            "state": "review", "duration_seconds": 30, "rights_status": "flagged"}, "preview": None,
            "reports": [], "decisions": [], "history_truncated": {"reports": False, "decisions": False}}
        self.assertTrue(valid_detail(detail))
        for state in ("attested", "flagged", "claimed", "removed", "restored"):
            detail["video"]["rights_status"] = state
            self.assertTrue(valid_detail(detail))
        detail["video"]["rights_status"] = "not_recorded"
        self.assertFalse(valid_detail(detail))
        detail["video"]["rights_status"] = "flagged"
        detail["preview"] = {"id": video, "url": "https://storage.invalid/raw-key", "expires_at": "2026-11-21T10:00:00Z"}
        self.assertFalse(valid_detail(detail))
