import uuid
import json

from django.db import IntegrityError
from django.test import TestCase
from django.test import RequestFactory
from django.urls import reverse
from django.utils import timezone

from service.models import Video
from service.videos import internal_list_videos, internal_video_detail


class PublicVideoTests(TestCase):
    def make_video(self, **changes):
        values = {
            "creator_id": uuid.uuid4(),
            "title": "An original work",
            "state": Video.State.DRAFT,
            "visibility": Video.Visibility.PRIVATE,
        }
        values.update(changes)
        return Video.objects.create(**values)

    def test_empty_feed_contains_no_fixtures(self):
        self.assertEqual(
            self.client.get(reverse("videos")).json(),
            {"items": [], "next_cursor": None},
        )

    def test_only_approved_public_published_video_is_visible(self):
        private = self.make_video()
        public = self.make_video(
            state=Video.State.PUBLISHED,
            visibility=Video.Visibility.PUBLIC,
            provider_asset_id=str(uuid.uuid4()),
            moderation_approved_at=timezone.now(),
        )
        response = self.client.get(reverse("videos"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual([item["id"] for item in response.json()["items"]], [str(public.id)])
        self.assertEqual(self.client.get(reverse("video_detail", args=[private.id])).status_code, 404)
        self.assertEqual(self.client.get(reverse("video_detail", args=[public.id])).status_code, 200)

    def test_search_matches_description_without_exposing_private_videos(self):
        self.make_video(title="River")
        public = self.make_video(
            description="A river story",
            state=Video.State.PUBLISHED,
            visibility=Video.Visibility.PUBLIC,
            provider_asset_id=str(uuid.uuid4()),
            moderation_approved_at=timezone.now(),
        )
        request = RequestFactory().post(
            "/internal/videos", data=json.dumps({"q": " RIVER "}),
            content_type="application/json",
        )
        response = internal_list_videos(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [item["id"] for item in json.loads(response.content)["items"]],
            [str(public.id)],
        )
        response = self.client.get(reverse("videos"), {"q": " "})
        self.assertEqual(response.status_code, 400)

    def test_database_rejects_publication_without_approval_and_media(self):
        with self.assertRaises(IntegrityError):
            self.make_video(state=Video.State.PUBLISHED, visibility=Video.Visibility.PUBLIC)

    def test_unlisted_video_does_not_appear_in_public_reads(self):
        video = self.make_video(
            state=Video.State.PUBLISHED,
            visibility=Video.Visibility.UNLISTED,
            provider_asset_id=str(uuid.uuid4()),
            moderation_approved_at=timezone.now(),
        )
        self.assertEqual(self.client.get(reverse("videos")).json()["items"], [])
        self.assertEqual(self.client.get(reverse("video_detail", args=[video.id])).status_code, 404)

    def test_internal_read_requires_service_signature(self):
        response = self.client.post(
            reverse("internal-videos"),
            data=json.dumps({}), content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)

    def test_internal_handler_has_same_empty_result_after_authentication(self):
        request = RequestFactory().post(
            "/internal/videos", data=json.dumps({}), content_type="application/json"
        )
        response = internal_list_videos(request)
        self.assertEqual(json.loads(response.content), {"items": [], "next_cursor": None})

    def test_internal_detail_never_returns_private_video(self):
        video = self.make_video()
        request = RequestFactory().post(
            "/internal/videos/detail", data=json.dumps({"video_id": str(video.id)}),
            content_type="application/json")
        self.assertEqual(internal_video_detail(request).status_code, 404)
        self.assertEqual(self.client.post(reverse("internal-video-detail"),
            data=json.dumps({"video_id": str(video.id)}),
            content_type="application/json").status_code, 403)

    def test_invalid_query_inputs_are_rejected(self):
        for query in ("?cursor=invalid", "?creator_id=invalid", "?unknown=1",
                      "?cursor=" + str(uuid.uuid4()),
                      "?creator_id=" + str(uuid.uuid4()) + "&creator_id=" + str(uuid.uuid4())):
            self.assertEqual(self.client.get(reverse("videos") + query).status_code, 400)

    def test_post_cannot_create_content(self):
        self.assertEqual(self.client.post(reverse("videos"), data={}).status_code, 405)

    def test_cursor_paginates_without_repeating_items(self):
        for _ in range(21):
            self.make_video(
                state=Video.State.PUBLISHED,
                visibility=Video.Visibility.PUBLIC,
                provider_asset_id=str(uuid.uuid4()),
                moderation_approved_at=timezone.now(),
            )
        first = self.client.get(reverse("videos")).json()
        self.assertEqual(len(first["items"]), 20)
        second = self.client.get(reverse("videos") + "?cursor=" + first["next_cursor"]).json()
        self.assertEqual(len(second["items"]), 1)
        self.assertNotIn(second["items"][0]["id"], {item["id"] for item in first["items"]})

    def test_cursor_must_belong_to_requested_creator(self):
        video = self.make_video(
            state=Video.State.PUBLISHED, visibility=Video.Visibility.PUBLIC,
            provider_asset_id=str(uuid.uuid4()), moderation_approved_at=timezone.now())
        self.assertEqual(self.client.get(reverse("videos"), {
            "creator_id": str(uuid.uuid4()), "cursor": str(video.id)}).status_code, 400)
