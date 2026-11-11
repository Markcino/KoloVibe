import json
from .video_fixtures import metadata
from unittest.mock import patch
from uuid import UUID

from django.http import JsonResponse
from django.test import SimpleTestCase
from django.urls import reverse

from service.following import following_videos


class Response:
    status = 200

    def __init__(self, body):
        self.body = json.dumps(body).encode()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return None

    def read(self, limit):
        return self.body[:limit]


class FollowingFeedTests(SimpleTestCase):
    account_id = "00000000-0000-4000-8000-000000000100"
    creator_id = "00000000-0000-4000-8000-000000000200"

    def video(self, index):
        return {"id": str(UUID(int=index + 1)), "creator_id": self.creator_id,
                "title": "Original", "description": "", "state": "published",
                "created_at": "2026-11-11T00:00:00+00:00", **metadata()}

    def test_requires_session(self):
        self.assertEqual(self.client.get(reverse("api-following-videos")).status_code, 401)

    def test_uses_bounded_catalog_scan_and_membership(self):
        calls = []

        def peer(audience, path, *, payload, **_):
            body = json.loads(payload)
            calls.append((audience, path, body))
            if audience == "content":
                if body:
                    return Response({"items": [self.video(20)], "next_cursor": None})
                return Response({"items": [self.video(i) for i in range(20)],
                                 "next_cursor": self.video(19)["id"]})
            return Response({"creator_ids": [self.creator_id]})

        account = JsonResponse({"id": self.account_id, "roles": ["viewer"]})
        with patch("service.following.current_account", return_value=account), \
             patch("service.following.signed_internal_request", side_effect=peer):
            result = self.client.get(reverse("api-following-videos"))
        self.assertEqual(result.status_code, 200)
        self.assertEqual(len(result.json()["items"]), 20)
        self.assertEqual(result.json()["next_cursor"], self.video(19)["id"])
        self.assertEqual(calls[1], ("engagement", "/internal/follows/membership",
                                    {"account_id": self.account_id,
                                     "creator_ids": [self.creator_id]}))

    def test_rejects_untrusted_membership_response(self):
        account = JsonResponse({"id": self.account_id, "roles": ["viewer"]})
        def peer(audience, path, **_):
            if audience == "content":
                return Response({"items": [self.video(0)], "next_cursor": None})
            return Response({"creator_ids": ["00000000-0000-4000-8000-000000000999"]})
        with patch("service.following.current_account", return_value=account), \
             patch("service.following.signed_internal_request", side_effect=peer):
            self.assertEqual(self.client.get(reverse("api-following-videos")).status_code, 503)

    def test_empty_scanned_page_advances_cursor_until_a_match(self):
        account = JsonResponse({"id": self.account_id, "roles": ["viewer"]})
        scans = []

        def peer(audience, path, *, payload, **_):
            body = json.loads(payload)
            if audience == "content":
                scans.append(body)
                if not body:
                    return Response({"items": [self.video(i) for i in range(20)],
                                     "next_cursor": self.video(19)["id"]})
                return Response({"items": [self.video(20)], "next_cursor": None})
            if len(scans) == 1:
                return Response({"creator_ids": []})
            return Response({"creator_ids": [self.creator_id]})

        with patch("service.following.current_account", return_value=account), \
             patch("service.following.signed_internal_request", side_effect=peer):
            result = self.client.get(reverse("api-following-videos"))
        self.assertEqual([item["id"] for item in result.json()["items"]],
                         [self.video(20)["id"]])
        self.assertEqual(scans[1], {"cursor": self.video(19)["id"]})
