"""Anonymous responses carry only allow-listed fields, and a misbehaving upstream is refused, never forwarded."""

import json
import uuid
from unittest.mock import patch

from django.test import SimpleTestCase
from django.urls import reverse

from .test_creators import Response
from .video_fixtures import metadata

# Fields that belong to Content, Moderation, Identity or Engagement and must never reach an anonymous caller.
INTERNAL_FIELDS = {
    "source_object_key": "originals/secret-source.mp4", "storage_key": "private/bucket-key", "r2_etag": "etag-secret",
    "moderation_reason": "internal-reason", "moderation_revision": 7, "report_count": 3, "fraud_hold": True,
    "account_id": "00000000-0000-4000-8000-00000000aaaa", "user_id": "00000000-0000-4000-8000-00000000bbbb",
    "email": "person@example.test", "role": "administrator", "reviewer_id": "00000000-0000-4000-8000-00000000cccc",
}
SECRET_VALUES = ("secret-source", "bucket-key", "etag-secret", "internal-reason", "person@example.test",
                 "00000000-0000-4000-8000-00000000")


def public_video(**overrides):
    return {"id": str(uuid.uuid4()), "creator_id": str(uuid.uuid4()), "title": "Original", "description": "",
            "state": "published", "created_at": "2026-10-31T00:00:00+00:00", **metadata()} | overrides


def public_creator(**overrides):
    return {"id": str(uuid.uuid4()), "handle": "original-voice", "bio": "", "status": "active",
            "display_name": "Voice", "location": ""} | overrides


class PublicVideoMinimisationTests(SimpleTestCase):
    def setUp(self):
        self.enterContext(patch("service.engagement_client.like_counts", return_value=None))
        self.enterContext(patch("service.engagement_client.play_counts", return_value=None))

    def get_list(self, item):
        page = {"items": [item], "next_cursor": None}
        with patch("service.videos.signed_internal_request", return_value=Response(json.dumps(page).encode())):
            return self.client.get(reverse("api-videos"))

    def get_detail(self, item):
        with patch("service.videos.signed_internal_request", return_value=Response(json.dumps(item).encode())):
            return self.client.get(reverse("api-video-detail", args=[item["id"]]))

    def test_allow_listed_record_is_served_with_only_public_aggregates(self):
        item = public_video()
        for response in (self.get_list(item), self.get_detail(item)):
            self.assertEqual(response.status_code, 200)
        self.assertEqual(self.get_detail(item).json(), item | {"like_count": None, "play_count": None})

    def test_any_internal_field_from_content_is_refused_not_forwarded(self):
        for field, value in INTERNAL_FIELDS.items():
            item = public_video(**{field: value})
            for label, response in (("list", self.get_list(item)), ("detail", self.get_detail(item))):
                with self.subTest(field=field, endpoint=label):
                    self.assertEqual(response.status_code, 503)
                    body = response.content.decode()
                    self.assertEqual(response.json(), {"detail": response.json()["detail"]})
                    for secret in SECRET_VALUES:
                        self.assertNotIn(secret, body)

    def test_nonpublic_records_are_refused(self):
        for overrides in ({"state": "draft"}, {"state": "review"}, {"state": "removed"}, {"state": "rejected"},
                          {"visibility": "private"}, {"visibility": "unlisted"}):
            item = public_video(**overrides)
            for label, response in (("list", self.get_list(item)), ("detail", self.get_detail(item))):
                with self.subTest(overrides=overrides, endpoint=label):
                    self.assertEqual(response.status_code, 503)

    def test_upstream_failure_text_is_not_reflected(self):
        for error in (OSError("db.internal.example:5432 password=hunter2"), ValueError("trace /srv/app/models.py")):
            with self.subTest(type(error).__name__), \
                    patch("service.videos.signed_internal_request", side_effect=error):
                response = self.client.get(reverse("api-videos"))
                self.assertEqual(response.status_code, 503)
                self.assertNotIn("internal.example", response.content.decode())
                self.assertNotIn("hunter2", response.content.decode())
                self.assertNotIn("/srv/app", response.content.decode())


class PublicCreatorMinimisationTests(SimpleTestCase):
    def setUp(self):
        self.enterContext(patch("service.engagement_client.follower_count", return_value=None))
        self.enterContext(patch("service.content_client.published_video_count", return_value=0))

    def detail(self, upstream):
        with patch("service.creators.signed_internal_request", return_value=Response(json.dumps(upstream).encode())):
            return self.client.get(reverse("api-creator-detail", args=[upstream["id"]]))

    def search(self, item):
        page = {"items": [item], "next_cursor": None}
        with patch("service.creators.signed_internal_request", return_value=Response(json.dumps(page).encode())):
            return self.client.get(reverse("api-creator-search"), {"q": "voice"})

    def test_detail_never_returns_the_account_identifier(self):
        account = str(uuid.uuid4())
        response = self.detail(public_creator(user_id=account))
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("user_id", response.json())
        self.assertNotIn(account, response.content.decode())

    def test_extra_upstream_fields_are_refused_for_detail_and_search(self):
        for field in ("email", "role", "reviewer_id", "moderation_reason", "account_id"):
            for label, call in (("detail", lambda item: self.detail(item | {"user_id": str(uuid.uuid4())})),
                                ("search", self.search)):
                with self.subTest(field=field, endpoint=label):
                    response = call(public_creator(**{field: "person@example.test"}))
                    self.assertEqual(response.status_code, 503)
                    self.assertNotIn("person@example.test", response.content.decode())

    def test_inactive_profiles_are_refused(self):
        for status in ("pending", "restricted", "suspended"):
            with self.subTest(status):
                self.assertEqual(self.detail(public_creator(status=status, user_id=str(uuid.uuid4()))).status_code, 503)
                self.assertEqual(self.search(public_creator(status=status)).status_code, 503)
