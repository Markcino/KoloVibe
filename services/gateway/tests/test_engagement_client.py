from io import BytesIO
import json
from unittest.mock import patch
from urllib.error import HTTPError
from uuid import UUID, uuid4

from django.test import SimpleTestCase

from service import engagement_client as client
from .test_accounts import Response


class EngagementClientTests(SimpleTestCase):
    def test_like_counts_are_signed_bounded_exact_and_zero_preserving(self):
        ids = [str(uuid4()), str(uuid4())]
        expected = {ids[0]: 4, ids[1]: 0}
        with patch("service.engagement_client.signed_internal_request", return_value=Response(200, json.dumps({"counts": expected}).encode())) as peer:
            self.assertEqual(client.like_counts(ids), expected)
            self.assertEqual(peer.call_args.args, ("engagement", "/internal/engagement/like-counts"))
            self.assertEqual(json.loads(peer.call_args.kwargs["payload"]), {"video_ids": ids})
            self.assertEqual(peer.call_args.kwargs["timeout"], 2)
            peer.reset_mock()
            self.assertEqual(client.like_counts([]), {})
            for invalid in (None, "id", [True], ["bad"], [str(uuid4()) for _ in range(51)]):
                self.assertIsNone(client.like_counts(invalid))
            peer.assert_not_called()

    def test_counts_reject_wrong_keys_booleans_negative_numbers_and_service_failures(self):
        ident = str(uuid4())
        with patch("service.engagement_client.signed_internal_request") as peer:
            for result in ({"counts": {}}, {"counts": {ident: True}}, {"counts": {ident: -1}},
                           {"counts": {ident: 1.5}}, {"counts": {ident: 1}, "extra": 1}, []):
                peer.return_value = Response(200, json.dumps(result).encode())
                self.assertIsNone(client.like_counts([ident]))
            for body in (b"invalid-json", b"x" * 8193):
                peer.return_value = Response(200, body)
                self.assertIsNone(client.like_counts([ident]))
            peer.return_value = Response(201, json.dumps({"counts": {ident: 0}}).encode())
            self.assertIsNone(client.like_counts([ident]))
            for error in (TimeoutError(), OSError(), RuntimeError(), HTTPError("https://engagement.invalid", 503, "", {}, BytesIO(b"private detail"))):
                peer.side_effect = error
                self.assertIsNone(client.like_counts([ident]))

    def test_follower_count_validates_identity_and_nonnegative_integer(self):
        ident = str(uuid4())
        with patch("service.engagement_client.signed_internal_request") as peer:
            peer.return_value = Response(200, json.dumps({"creator_id": ident, "follower_count": 0}).encode())
            self.assertEqual(client.follower_count(ident), 0)
            for result in ({"creator_id": str(uuid4()), "follower_count": 1}, {"creator_id": ident, "follower_count": True},
                           {"creator_id": ident, "follower_count": -1}, {"creator_id": ident, "follower_count": 1, "extra": 1}):
                peer.return_value = Response(200, json.dumps(result).encode())
                self.assertIsNone(client.follower_count(ident))
            peer.reset_mock()
            self.assertIsNone(client.follower_count("bad-id"))
            peer.assert_not_called()

    def test_trending_skips_hidden_candidates_before_applying_limit(self):
        ids = [str(UUID(int=index + 1)) for index in range(51)]
        first = {"items": [{"video_id": value, "qualified_plays": 10} for value in ids[:50]], "next_cursor": "signed-cursor"}
        second = {"items": [{"video_id": ids[-1], "qualified_plays": 9}], "next_cursor": None}
        with patch("service.engagement_client._post", side_effect=[first, second]) as peer, \
                patch("service.engagement_client.lookup_public_videos", side_effect=[[], [{"id": ids[-1]}]]) as content:
            self.assertEqual(client.trending_video_ids(20), [ids[-1]])
            self.assertEqual(peer.call_args_list[1].args[1]["cursor"], "signed-cursor")
            self.assertEqual(content.call_args_list[0].args, (ids[:50],))

    def test_trending_preserves_rank_and_deterministic_ties(self):
        ids = [str(UUID(int=value)) for value in (1, 2, 3)]
        data = {"items": [{"video_id": value, "qualified_plays": 4 if index < 2 else 3} for index, value in enumerate(ids)], "next_cursor": None}
        with patch("service.engagement_client._post", return_value=data), \
                patch("service.engagement_client.lookup_public_videos", return_value=[{"id": value} for value in ids]):
            self.assertEqual(client.trending_video_ids(2), ids[:2])

    def test_trending_rejects_unavailable_invalid_reordered_or_repeated_rankings(self):
        ids = [str(UUID(int=value)) for value in (1, 2)]
        invalid = (None, {"items": [], "next_cursor": "cursor"},
                   {"items": [{"video_id": ids[0], "qualified_plays": True}], "next_cursor": None},
                   {"items": [{"video_id": value, "qualified_plays": 1} for value in reversed(ids)], "next_cursor": None},
                   {"items": [{"video_id": ids[0], "qualified_plays": 1}] * 2, "next_cursor": None})
        with patch("service.engagement_client._post") as peer, patch("service.engagement_client.lookup_public_videos") as content:
            for data in invalid:
                peer.return_value = data
                self.assertIsNone(client.trending_video_ids())
            content.assert_not_called()
            peer.return_value = {"items": [], "next_cursor": None}
            content.return_value = None
            self.assertIsNone(client.trending_video_ids())
            self.assertIsNone(client.trending_video_ids(True))
            self.assertIsNone(client.trending_video_ids(51))

    def test_trending_deadline_returns_unavailable_instead_of_a_partial_ranking(self):
        data = {"items": [{"video_id": str(uuid4()), "qualified_plays": 1}], "next_cursor": None}
        with patch("service.engagement_client._post", return_value=data), \
                patch("service.engagement_client.time.monotonic", side_effect=[0, 9]), \
                patch("service.engagement_client.lookup_public_videos") as content:
            self.assertIsNone(client.trending_video_ids())
            content.assert_not_called()
