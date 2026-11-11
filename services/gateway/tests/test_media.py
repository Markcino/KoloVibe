import json
from unittest.mock import patch
from uuid import uuid4

from django.http import JsonResponse
from django.test import RequestFactory, SimpleTestCase

from service.media import (issue_video_upload, manage_own_video, own_video_library, own_video_detail,
                           video_item, video_playback, video_upload_status)
from .test_videos import Response
from .video_fixtures import metadata


class MediaGatewayTests(SimpleTestCase):
    @patch("service.media.signed_internal_request")
    @patch("service.media.creator_ownership")
    @patch("service.media.authenticated_actor")
    def test_owned_detail_verifies_creator_and_revision(self, actor, ownership, content):
        creator_id, video_id = uuid4(), uuid4()
        actor.return_value = (str(uuid4()), "creator")
        ownership.return_value = JsonResponse({"creator_id": str(creator_id)})
        content.return_value = Response(json.dumps({
            "id": str(video_id), "creator_id": str(creator_id), "title": "Removed video",
            "description": "", "state": "removed", "created_at": "2026-11-10T20:00:00+00:00",
            "revision": 2, **metadata("private"),
        }).encode())
        response = own_video_detail(RequestFactory().get("/api/v1/creators/me/videos/id"), video_id)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(response.content)["revision"], 2)
        self.assertEqual(content.call_args.args, ("content", "/internal/videos/media/detail"))
        self.assertEqual(json.loads(content.call_args.kwargs["payload"]),
                         {"creator_id": str(creator_id), "video_id": str(video_id)})
        actor.return_value = JsonResponse({"detail": "Unauthorized"}, status=401)
        content.reset_mock()
        self.assertEqual(own_video_detail(RequestFactory().get("/api/v1/creators/me/videos/id"), video_id)
                         .status_code, 401)
        content.assert_not_called()

    @patch("service.media.signed_internal_request")
    @patch("service.media.creator_ownership")
    @patch("service.media.authenticated_actor")
    def test_library_and_draft_edits_bind_to_authenticated_creator(self, actor, ownership, content):
        creator_id, video_id = uuid4(), uuid4()
        actor.return_value = (str(uuid4()), "creator")
        ownership.return_value = JsonResponse({"creator_id": str(creator_id)})
        content.return_value = Response(json.dumps({"items": [], "next_cursor": None}).encode())
        result = own_video_library(RequestFactory().get("/creators/me/videos"))
        self.assertEqual(result.status_code, 200)
        self.assertEqual(json.loads(content.call_args.kwargs["payload"])["creator_id"], str(creator_id))
        content.return_value = Response(json.dumps({
            "id": str(video_id), "creator_id": str(creator_id), "title": "Edited",
            "description": "Story", "state": "draft", "created_at": "2026-11-10T20:00:00+00:00",
            **metadata("private"),
        }).encode())
        request = RequestFactory().patch("/videos", json.dumps({"title": "Edited", "description": "Story"}),
                                         content_type="application/json")
        self.assertEqual(video_item(request, video_id).status_code, 200)
        self.assertEqual(json.loads(content.call_args.kwargs["payload"])["video_id"], str(video_id))
        actor.return_value = JsonResponse({"detail": "Unauthorized"}, status=401)
        content.reset_mock()
        self.assertEqual(manage_own_video(request, video_id).status_code, 401)
        content.assert_not_called()

    @patch("service.media.signed_internal_request")
    @patch("service.media.creator_eligibility")
    def test_upload_is_bound_to_the_approved_creator(self, eligibility, content):
        video_id, creator_id = uuid4(), uuid4()
        request = RequestFactory().post("/upload", {"size_bytes": 1234}, content_type="application/json",
                                        HTTP_IDEMPOTENCY_KEY="local-test-media-001")
        eligibility.return_value = JsonResponse({"upload_eligible": False, "creator_id": None})
        self.assertEqual(issue_video_upload(request, video_id).status_code, 403)
        content.assert_not_called()
        eligibility.return_value = JsonResponse({"upload_eligible": True, "creator_id": str(creator_id)})
        content.return_value = Response(json.dumps({
            "video_id": str(video_id), "upload_id": str(uuid4()),
            "upload_url": "https://" + "a" * 32 + ".r2.cloudflarestorage.com/local-fixture/originals/object.mp4?signature=test",
            "upload_headers": {"Content-Type": "video/mp4", "Content-Length": "1234", "If-None-Match": "*"},
            "expires_at": "2026-11-10T20:00:00+00:00", "max_bytes": 52428800,
        }).encode())
        response = issue_video_upload(request, video_id)
        self.assertEqual(response.status_code, 200)
        self.assertIn("no-store", response["Cache-Control"])
        self.assertEqual(json.loads(content.call_args.kwargs["payload"])["creator_id"], str(creator_id))

    @patch("service.media.signed_internal_request")
    def test_anonymous_completion_and_playback_do_not_reach_content(self, content):
        video_id = uuid4()
        self.assertEqual(video_playback(RequestFactory().get("/playback"), video_id).status_code, 401)
        self.assertEqual(video_upload_status(RequestFactory().post("/status"), video_id).status_code, 401)
        content.assert_not_called()
