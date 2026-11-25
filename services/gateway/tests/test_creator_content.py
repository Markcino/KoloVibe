from io import BytesIO
import json
from unittest.mock import patch
from urllib.error import HTTPError
from uuid import uuid4

from django.http import JsonResponse
from django.test import RequestFactory, SimpleTestCase

from service import content_client, creators, media, videos
from service.routes import catalog, creator_studio
from service.video_validation import valid_video
from .test_accounts import Response
from .video_fixtures import metadata


class CreatorContentGatewayTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.actor, self.creator, self.video = str(uuid4()), str(uuid4()), str(uuid4())
        self.profile = {"id": self.creator, "user_id": self.actor, "handle": "creator_name", "bio": "",
                        "display_name": "Creator", "location": "Monrovia", "status": "active"}

    def video_item(self, owned=False, **changes):
        return {"id": self.video, "creator_id": self.creator, "title": "Original hipco", "description": "Monrovia",
                "state": "published", "created_at": "2026-11-11T12:00:00Z", **metadata(owned=owned),
                "category": "hipco", **changes}

    def test_owner_profile_get_patch_forward_only_actor_owned_fields(self):
        with patch("service.creators.authenticated_actor", return_value=(self.actor, "creator")), \
                patch("service.creators.signed_internal_request") as call:
            call.return_value = Response(200, json.dumps(self.profile).encode())
            response = creators.own_creator(self.factory.get("/api/v1/creators/me"))
            self.assertEqual(response.status_code, 200)
            self.assertIn("no-store", response["Cache-Control"])
            self.assertEqual(json.loads(call.call_args.kwargs["payload"]), {
                "actor_id": self.actor, "role": "creator", "operation": "get", "data": {}})
            fields = {"display_name": "Updated", "location": "Buchanan", "handle": "new_creator"}
            call.return_value = Response(200, json.dumps(self.profile | fields).encode())
            response = creators.own_creator(self.factory.patch("/api/v1/creators/me", fields, content_type="application/json"))
            self.assertEqual(response.status_code, 200)
            self.assertEqual(json.loads(call.call_args.kwargs["payload"])["data"], fields)
            call.reset_mock()
            for fields in ({"handle": "Upper"}, {"handle": "bad-handle"}, {"location": "x" * 81},
                           {"display_name": "x" * 81}, {"bio": "x" * 501}, {"user_id": self.actor}, {}):
                self.assertEqual(creators.own_creator(self.factory.patch("/api/v1/creators/me", fields,
                    content_type="application/json")).status_code, 400)
            call.assert_not_called()

    def test_owner_profile_role_restriction_and_handle_conflict_code(self):
        request = self.factory.patch("/api/v1/creators/me", {"handle": "taken_name"}, content_type="application/json")
        with patch("service.creators.authenticated_actor", return_value=(self.actor, "viewer")), \
                patch("service.creators.signed_internal_request") as call:
            self.assertEqual(creators.own_creator(request).status_code, 403)
            call.assert_not_called()
        with patch("service.creators.authenticated_actor", return_value=(self.actor, "creator")), \
                patch("service.creators.signed_internal_request") as call:
            call.side_effect = HTTPError("https://creators.invalid", 409, "", {}, BytesIO(
                b'{"detail":"Creator handle is unavailable","code":"handle_taken"}'))
            result = creators.own_creator(request)
            self.assertEqual(result.status_code, 409)
            self.assertEqual(json.loads(result.content)["code"], "handle_taken")
            call.side_effect = HTTPError("https://creators.invalid", 403, "", {}, BytesIO(b'{"detail":"Creator unavailable"}'))
            self.assertEqual(creators.own_creator(request).status_code, 403)

    def test_public_creator_composes_content_count_and_nullable_follower_count(self):
        with patch("service.creators.read_creator", return_value=JsonResponse(self.profile)), \
                patch("service.content_client.published_video_count", return_value=7) as content_count, \
                patch("service.engagement_client.follower_count", return_value=None) as followers:
            response = creators.creator_detail(self.factory.get("/creator"), self.creator)
            public = {key: value for key, value in self.profile.items() if key != "user_id"}
            self.assertEqual(json.loads(response.content), public | {"published_video_count": 7, "follower_count": None})
            self.assertNotIn("user_id", json.loads(response.content))
            content_count.assert_called_once_with(self.creator)
            followers.assert_called_once_with(self.creator)
            followers.return_value = 12
            self.assertEqual(json.loads(creators.creator_detail(self.factory.get("/creator"), self.creator).content)["follower_count"], 12)
            followers.return_value = True
            self.assertEqual(creators.creator_detail(self.factory.get("/creator"), self.creator).status_code, 503)
            followers.return_value = None
            content_count.return_value = None
            self.assertEqual(creators.creator_detail(self.factory.get("/creator"), self.creator).status_code, 503)

    def test_public_listing_category_and_batch_like_counts_include_unknown_as_null(self):
        item = self.video_item()
        request = self.factory.get("/api/v1/videos", {"category": "hipco", "q": " original "})
        with patch("service.videos.signed_internal_request", return_value=Response(200, json.dumps({"items": [item], "next_cursor": None}).encode())) as call, \
                patch("service.engagement_client.like_counts", return_value={self.video: 42}) as counts:
            result = videos.list_videos(request)
            self.assertEqual(result.status_code, 200)
            self.assertEqual(json.loads(result.content)["items"][0]["like_count"], 42)
            self.assertEqual(json.loads(call.call_args.kwargs["payload"]), {"category": "hipco", "q": "original"})
            counts.assert_called_once_with([self.video])
            counts.return_value = None
            self.assertIsNone(json.loads(videos.list_videos(request).content)["items"][0]["like_count"])
            counts.return_value = {self.video: True}
            self.assertEqual(videos.list_videos(request).status_code, 503)
            counts.return_value = None
            call.return_value = Response(200, json.dumps({"items": [item | {"category": "comedy"}], "next_cursor": None}).encode())
            self.assertEqual(videos.list_videos(request).status_code, 503)

    def test_play_count_is_attached_to_public_items_and_null_when_unavailable(self):
        item = self.video_item()
        request = self.factory.get("/api/v1/videos")
        with patch("service.videos.signed_internal_request", return_value=Response(200, json.dumps({"items": [item], "next_cursor": None}).encode())), \
                patch("service.engagement_client.like_counts", return_value={self.video: 1}), \
                patch("service.engagement_client.play_counts", return_value={self.video: 0}) as plays:
            body = json.loads(videos.list_videos(request).content)["items"][0]
            self.assertEqual((body["like_count"], body["play_count"]), (1, 0))
            self.assertEqual(set(body) - set(item), {"like_count", "play_count"})
            plays.assert_called_once_with([self.video])
            plays.return_value = None
            self.assertIsNone(json.loads(videos.list_videos(request).content)["items"][0]["play_count"])
            plays.return_value = {self.video: -1}
            self.assertEqual(videos.list_videos(request).status_code, 503)
            plays.return_value = {self.video: 2, "other": 1}
            self.assertEqual(videos.list_videos(request).status_code, 503)

    def test_creator_popular_ranks_public_videos_by_qualified_plays_with_a_stable_tiebreak(self):
        newest, middle, oldest, quiet = (self.video_item(id=str(uuid4()), title=name) for name in ("N", "M", "O", "Q"))
        page = {"items": [newest, middle, oldest, quiet], "next_cursor": None}
        counts = {newest["id"]: 3, middle["id"]: 9, oldest["id"]: 3, quiet["id"]: 0}
        request = self.factory.get("/api/v1/videos", {"creator_id": self.creator, "sort": "popular"})
        with patch("service.videos.signed_internal_request", return_value=Response(200, json.dumps(page).encode())) as call, \
                patch("service.engagement_client.like_counts", return_value=None), \
                patch("service.engagement_client.play_counts", side_effect=lambda ids: {i: counts[i] for i in ids}):
            result = videos.list_videos(request)
            self.assertEqual(result.status_code, 200)
            body = json.loads(result.content)
            self.assertEqual([i["title"] for i in body["items"]], ["M", "N", "O", "Q"])
            self.assertEqual([i["play_count"] for i in body["items"]], [9, 3, 3, 0])
            self.assertIsNone(body["next_cursor"])
            self.assertIn("no-store", result["Cache-Control"])
            self.assertEqual(json.loads(call.call_args.kwargs["payload"]), {"creator_id": self.creator})
            # Same input, same order: the tie-break is newest first, not random.
            again = json.loads(videos.list_videos(request).content)
            self.assertEqual([i["id"] for i in again["items"]], [i["id"] for i in body["items"]])

    def test_creator_popular_only_ranks_what_content_says_is_public_and_fails_closed(self):
        item = self.video_item()
        request = self.factory.get("/api/v1/videos", {"creator_id": self.creator, "sort": "popular"})
        with patch("service.videos.signed_internal_request") as call, \
                patch("service.engagement_client.like_counts", return_value=None), \
                patch("service.engagement_client.play_counts", return_value={self.video: 1}):
            # A private or removed video from Content is rejected by validation rather than ranked.
            call.return_value = Response(200, json.dumps({"items": [item | {"visibility": "private"}], "next_cursor": None}).encode())
            self.assertEqual(videos.list_videos(request).status_code, 503)
            # Another creator's item is never ranked under this creator.
            call.return_value = Response(200, json.dumps({"items": [item | {"creator_id": str(uuid4())}], "next_cursor": None}).encode())
            self.assertEqual(videos.list_videos(request).status_code, 503)
            # Without a trustworthy aggregate there is no popularity order to show.
            call.return_value = Response(200, json.dumps({"items": [item], "next_cursor": None}).encode())
            with patch("service.engagement_client.play_counts", return_value=None):
                self.assertEqual(videos.list_videos(request).status_code, 503)

    def test_creator_popular_requires_exactly_a_creator_and_never_relabels_trending(self):
        with patch("service.videos.signed_internal_request") as call, patch("service.engagement_client.trending_video_ids") as trending:
            for query in ({"sort": "popular"}, {"sort": "popular", "creator_id": "bad"},
                          {"sort": "popular", "creator_id": self.creator, "q": "x"},
                          {"sort": "popular", "creator_id": self.creator, "cursor": self.video},
                          {"sort": "popular", "creator_id": self.creator, "category": "hipco"}):
                self.assertEqual(videos.list_videos(self.factory.get("/api/v1/videos", query)).status_code, 400, query)
            call.assert_not_called()
            trending.assert_not_called()

    def test_creator_popular_fails_closed_above_the_ranking_limit(self):
        items = [self.video_item(id=str(uuid4())) for _ in range(20)]
        page = {"items": items, "next_cursor": items[-1]["id"]}
        request = self.factory.get("/api/v1/videos", {"creator_id": self.creator, "sort": "popular"})
        with patch("service.videos.signed_internal_request", return_value=Response(200, json.dumps(page).encode())) as call, \
                patch("service.engagement_client.like_counts", return_value=None), \
                patch("service.engagement_client.play_counts", return_value={}):
            self.assertEqual(videos.list_videos(request).status_code, 503)
            self.assertEqual(call.call_count, videos.POPULAR_PAGES)

    def test_trending_lookup_preserves_order_applies_filters_and_has_no_cursor(self):
        first, second = self.video_item(), self.video_item(id=str(uuid4()), category="comedy")
        ids = [second["id"], first["id"]]
        with patch("service.engagement_client.trending_video_ids", return_value=ids) as trending, \
                patch("service.content_client.lookup_public_videos", return_value=[second, first]) as lookup, \
                patch("service.engagement_client.like_counts", return_value=None):
            request = self.factory.get("/api/v1/videos", {"sort": "trending"})
            result = json.loads(videos.list_videos(request).content)
            self.assertEqual([item["id"] for item in result["items"]], ids)
            self.assertIsNone(result["next_cursor"])
            trending.assert_called_once_with(20)
            lookup.assert_called_once_with(ids)
            request = self.factory.get("/api/v1/videos", {"sort": "trending", "category": "hipco",
                                                         "creator_id": self.creator, "q": "monrovia"})
            self.assertEqual([item["id"] for item in json.loads(videos.list_videos(request).content)["items"]], [self.video])
            trending.return_value = None
            self.assertEqual(videos.list_videos(request).status_code, 503)
            trending.return_value = ids
            lookup.return_value = None
            self.assertEqual(videos.list_videos(request).status_code, 503)

    def test_bad_category_sort_and_trending_cursor_do_not_call_services(self):
        for fields in ({"category": "unknown"}, {"sort": "bad"}, {"sort": "trending", "cursor": self.video}):
            with patch("service.videos.signed_internal_request") as call, patch("service.engagement_client.trending_video_ids") as trending:
                self.assertEqual(videos.list_videos(self.factory.get("/api/v1/videos", fields)).status_code, 400)
                call.assert_not_called(); trending.assert_not_called()

    def test_content_lookup_is_bounded_public_only_and_rejects_reordered_responses(self):
        first, second = self.video_item(), self.video_item(id=str(uuid4()))
        with patch("service.content_client.signed_internal_request") as call:
            call.return_value = Response(200, json.dumps({"items": [second, first]}).encode())
            self.assertEqual(content_client.lookup_public_videos([second["id"], first["id"]]), [second, first])
            self.assertEqual(json.loads(call.call_args.kwargs["payload"]), {"ids": [second["id"], first["id"]]})
            self.assertIsNone(content_client.lookup_public_videos([first["id"], second["id"]]))
            call.return_value = Response(200, json.dumps({"items": [first | {"visibility": "private"}]}).encode())
            self.assertIsNone(content_client.lookup_public_videos([first["id"]]))
            call.reset_mock()
            self.assertIsNone(content_client.lookup_public_videos([str(uuid4()) for _ in range(51)]))
            self.assertIsNone(content_client.lookup_public_videos([first["id"], first["id"]]))
            call.assert_not_called()

    def test_every_new_video_field_is_strictly_validated(self):
        valid = self.video_item(duration_ms=2000, duration_seconds=2)
        self.assertTrue(valid_video(valid, public=True))
        for changes in ({"category": "other"}, {"tags": ["UPPER"]}, {"tags": ["a"] * 6},
                        {"tags": ["same", "same"]}, {"cover_time_ms": True}, {"cover_time_ms": 2001},
                        {"poster_url": "https://evil.invalid/frame.jpg?signature=test"},
                        {"poster_url": "http://" + "a" * 32 + ".r2.cloudflarestorage.com/frame.jpg?signature=test"},
                        {"published_at": "invalid"}, {"visibility": "private"}, {"duration_ms": 0},
                        {"unexpected": "secret"}):
            self.assertFalse(videos._valid_item(valid | changes))

    def test_owner_edits_normalize_tags_and_verify_returned_metadata(self):
        result = self.video_item(owned=True, title="Updated", tags=["monrovia"], visibility="public")
        with patch("service.media._owned_creator", return_value=(self.creator, None)), \
                patch("service.media.signed_internal_request", return_value=Response(200, json.dumps(result).encode())) as call:
            request = self.factory.patch("/api/v1/videos/id", {"title": " Updated ", "tags": ["#Monrovia"]},
                                         content_type="application/json")
            self.assertEqual(media.manage_own_video(request, self.video).status_code, 200)
            self.assertEqual(json.loads(call.call_args.kwargs["payload"]), {
                "creator_id": self.creator, "video_id": self.video, "title": "Updated", "tags": ["monrovia"]})
            call.return_value = Response(200, json.dumps(result | {"tags": ["wrong"]}).encode())
            self.assertEqual(media.manage_own_video(request, self.video).status_code, 503)

    def test_restricted_creator_cannot_create_or_republish_and_unpublish_needs_only_ownership(self):
        eligibility = JsonResponse({"upload_eligible": False, "creator_id": None})
        with patch("service.media._owned_creator", return_value=(self.creator, None)), \
                patch("service.media.creator_eligibility", return_value=eligibility), \
                patch("service.media.signed_internal_request") as call:
            self.assertEqual(media.create_video_draft(self.factory.post("/api/v1/videos", {
                "title": "Original", "category": "hipco"}, content_type="application/json")).status_code, 403)
            self.assertEqual(media.video_visibility(self.factory.generic("POST", "/publish"), self.video, "publish").status_code, 403)
            call.assert_not_called()
            call.return_value = Response(200, json.dumps(self.video_item(owned=True, visibility="private")).encode())
            self.assertEqual(media.video_visibility(self.factory.generic("POST", "/unpublish"), self.video, "unpublish").status_code, 200)

    def test_publish_review_required_code_and_upload_failure_status_are_preserved(self):
        with patch("service.media._owned_creator", return_value=(self.creator, None)), \
                patch("service.media._eligible_creator", return_value=(self.creator, None)), \
                patch("service.media.signed_internal_request") as call:
            call.side_effect = HTTPError("https://content.invalid", 409, "", {}, BytesIO(
                b'{"detail":"Moderation approval required","code":"review_required"}'))
            result = media.video_visibility(self.factory.generic("POST", "/publish"), self.video, "publish")
            self.assertEqual(result.status_code, 409)
            self.assertEqual(json.loads(result.content)["code"], "review_required")
            call.side_effect = None
            status = {"video_id": self.video, "state": "failed", "failure_reason": "invalid_media", "retryable": True}
            call.return_value = Response(200, json.dumps(status).encode())
            self.assertEqual(media.video_upload_status(self.factory.get("/status"), self.video).status_code, 200)
            call.return_value = Response(200, json.dumps(status | {"retryable": "true"}).encode())
            self.assertEqual(media.video_upload_status(self.factory.get("/status"), self.video).status_code, 503)

    def test_owner_library_state_query_and_response_filter_are_checked(self):
        item = self.video_item(owned=True, state="processing", visibility="private")
        with patch("service.media._owned_creator", return_value=(self.creator, None)), \
                patch("service.media.signed_internal_request", return_value=Response(200, json.dumps({"items": [item], "next_cursor": None}).encode())) as call:
            request = self.factory.get("/creators/me/videos", {"state": "in_progress"})
            self.assertEqual(media.own_video_library(request).status_code, 200)
            self.assertEqual(json.loads(call.call_args.kwargs["payload"])["state"], "in_progress")
            self.assertEqual(media.own_video_library(self.factory.get("/creators/me/videos", {"state": "published"})).status_code, 503)
            call.reset_mock()
            self.assertEqual(media.own_video_library(self.factory.get("/creators/me/videos", {"state": "uploading"})).status_code, 400)
            call.assert_not_called()

    def test_owner_library_search_is_validated_forwarded_trimmed_and_checked_in_the_response(self):
        item = self.video_item(owned=True, title="River Song", description="a short film")
        page = json.dumps({"items": [item], "next_cursor": None}).encode()
        with patch("service.media._owned_creator", return_value=(self.creator, None)), \
                patch("service.media.signed_internal_request", return_value=Response(200, page)) as call:
            result = media.own_video_library(self.factory.get("/creators/me/videos", {"q": "  river  ", "state": "all"}))
            self.assertEqual(result.status_code, 200)
            self.assertEqual(json.loads(call.call_args.kwargs["payload"])["q"], "river")
            # Upstream returning a video that does not match the search is refused, not forwarded.
            result = media.own_video_library(self.factory.get("/creators/me/videos", {"q": "unrelated"}))
            self.assertEqual(result.status_code, 503)
            call.reset_mock()
            for bad in ({"q": ""}, {"q": "   "}, {"q": "x" * 101}, {"q": "bad\x01"}, {"q": "a", "extra": "1"}):
                with self.subTest(bad=bad):
                    self.assertEqual(media.own_video_library(self.factory.get("/creators/me/videos", bad)).status_code, 400)
            self.assertEqual(media.own_video_library(self.factory.get("/creators/me/videos?q=a&q=b")).status_code, 400)
            call.assert_not_called()

    def test_new_write_routes_are_media_gated_and_public_listing_stays_on(self):
        with patch("service.routes.creator_studio.enabled", return_value=False):
            self.assertEqual(creator_studio.patterns(), [])
        with patch("service.routes.creator_studio.enabled", side_effect=lambda name: name == "media"):
            routes = creator_studio.patterns()
            names = {route.name for route in routes}
            self.assertTrue({"api-own-creator", "api-video-publish", "api-video-unpublish"} <= names)
        with patch("service.routes.catalog.enabled", return_value=False):
            self.assertTrue(any(route.name == "api-videos" and route.callback is videos.list_videos for route in catalog.patterns()))

    def test_maximum_unicode_metadata_pages_fit_the_bounded_response_budget(self):
        items = [self.video_item(owned=True, id=str(uuid4()), title="🎥" * 160, description="🎥" * 2000) for _ in range(20)]
        body = json.dumps({"items": items, "next_cursor": None}).encode()
        self.assertGreater(len(body), 500000)
        with patch("service.media._owned_creator", return_value=(self.creator, None)), \
                patch("service.media.signed_internal_request", return_value=Response(200, body)):
            result = media.own_video_library(self.factory.get("/library"))
            self.assertEqual(result.status_code, 200)
            self.assertEqual(len(json.loads(result.content)["items"]), 20)
