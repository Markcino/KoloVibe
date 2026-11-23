"""Creator draft -> R2 upload -> FFmpeg -> review -> moderation -> publication -> authorized playback, in one chain.

Content's real code and database run the whole journey. The R2 bucket is an in-memory stand-in (private objects keyed
exactly as production keys them) and, when FFmpeg is present, the encoder and poster renderer are the real ones. The
asserted rule at every step is that bytes only become reachable after the step that is meant to allow it.
"""
import json
from pathlib import Path
import shutil
import subprocess
from tempfile import TemporaryDirectory
from unittest.mock import patch
from urllib.parse import urlsplit
from uuid import uuid4

from django.test import RequestFactory, TestCase
from django.utils import timezone

from service import media_encoding, media_storage
from service.media_api import media_api
from service.media_processing import process
from service.models import MediaUpload, Video
from service.moderation import moderation_video

FFMPEG = bool(shutil.which("ffmpeg", path=media_encoding.SAFE_ENV["PATH"])
              and shutil.which("ffprobe", path=media_encoding.SAFE_ENV["PATH"]))


def make_clip(directory):
    path = Path(directory) / "creator-original.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-filter_complex",
                    "color=c=blue:s=64x64:r=25:d=1.6[v];anullsrc=r=44100:cl=mono:d=1.6[a]", "-map", "[v]", "-map", "[a]",
                    "-threads", "1", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(path)],
                   check=True, timeout=30, stdin=subprocess.DEVNULL, capture_output=True)
    return path.read_bytes()


class PrivateBucket:
    """Private object store: nothing is readable without a signed grant, and every grant is recorded."""

    def __init__(self):
        self.objects, self.signed = {}, []

    def sign_upload(self, key, size, seconds):
        self.signed.append(("PUT", key, seconds))
        return f"https://bucket.invalid/{key}?signature=test"

    def inspect_upload(self, key):
        if key not in self.objects:
            raise media_storage.ObjectMissing
        return len(self.objects[key]), media_storage.CONTENT_TYPE, '"etag-original"'

    def download_upload(self, key, etag, expected, destination):
        if key not in self.objects:
            raise media_storage.ObjectMissing
        if etag != '"etag-original"' or len(self.objects[key]) != expected:
            raise media_storage.ObjectChanged
        destination.write_bytes(self.objects[key])

    def put_playback(self, key, path):
        self.objects[key] = Path(path).read_bytes()

    def put_poster(self, key, path):
        self.objects[key] = Path(path).read_bytes()

    def sign_playback(self, key, seconds):
        self.signed.append(("GET", key, seconds))
        return f"https://bucket.invalid/{key}?signature=test"


def stand_in_encode(source, destination):
    Path(destination).write_bytes(b"\x00\x00\x00\x18ftypmp42" + b"rendition")
    return 1900


def stand_in_poster(source, destination, cover_time_ms, duration_ms):
    Path(destination).write_bytes(b"\xff\xd8poster\xff\xd9")


class UploadToPlaybackJourneyTests(TestCase):
    """Uses the real encoder and poster renderer when FFmpeg is on the sandbox PATH (the media image, CI); otherwise
    deterministic stand-ins, so every other boundary in the chain is still exercised."""

    def setUp(self):
        self.factory = RequestFactory()
        self.creator, self.account = uuid4(), uuid4()
        self.bucket = PrivateBucket()
        for name in ("sign_upload", "inspect_upload", "download_upload", "put_playback", "put_poster", "sign_playback"):
            patcher = patch(f"service.media_storage.{name}", getattr(self.bucket, name))
            patcher.start()
            self.addCleanup(patcher.stop)
        if not FFMPEG:
            for name, replacement in (("encode", stand_in_encode), ("render_poster", stand_in_poster)):
                patcher = patch(f"service.media_encoding.{name}", replacement)
                patcher.start()
                self.addCleanup(patcher.stop)

    def call(self, operation, data, view=media_api, caller="gateway"):
        request = self.factory.post(f"/internal/videos/media/{operation}", json.dumps(data), content_type="application/json")
        request.service_caller = caller
        return view(request, operation)

    def test_every_step_opens_only_what_that_step_allows(self):
        if FFMPEG:
            with TemporaryDirectory() as directory:
                clip = make_clip(directory)
        else:
            clip = b"synthetic creator original " * 40

        # 1. Draft: metadata only; no bytes, no playback.
        draft = self.call("draft", {"creator_id": str(self.creator), "title": "Journey original", "category": "hipco"})
        self.assertEqual(draft.status_code, 201)
        video_id = json.loads(draft.content)["id"]
        owner = {"creator_id": str(self.creator), "video_id": video_id}
        self.assertEqual(self.call("playback", {"video_id": video_id}).status_code, 404)

        # 2. Upload initiation: a size-bound, create-only grant for a private original; attestation and policy required.
        intent = owner | {"size_bytes": len(clip), "idempotency_key": "journey-upload-0001", "account_id": str(self.account),
                          "originality_attestation": {"version": "R1-originality-v1", "accepted": True},
                          "review_policy": {"trusted": False, "sample_percent": 100, "policy_version": None}}
        granted = json.loads(self.call("intent", intent).content)
        self.assertEqual(granted["upload_headers"], {"Content-Type": "video/mp4", "Content-Length": str(len(clip)),
                                                     "If-None-Match": "*"})
        source_key = urlsplit(granted["upload_url"]).path.lstrip("/")
        self.assertEqual(source_key, f"originals/{granted['upload_id']}.mp4")
        self.assertEqual(self.bucket.signed[0][0], "PUT")
        self.assertEqual(self.call("intent", intent | {"originality_attestation": {"version": "x", "accepted": True}}).status_code, 400)

        # 3. Completion needs the bytes to exist and match the reservation; only then does processing queue.
        with patch("service.media_api._enqueue") as enqueue:
            self.assertEqual(self.call("complete", owner).status_code, 409)
            enqueue.assert_not_called()
            self.bucket.objects[source_key] = clip[:-1]  # truncated upload
            self.assertEqual(self.call("complete", owner).status_code, 409)
            self.bucket.objects[source_key] = clip
            self.assertEqual(self.call("complete", owner).status_code, 202)
            enqueue.assert_called_once()
        self.assertEqual(Video.objects.get(pk=video_id).state, Video.State.PROCESSING)
        self.assertEqual(self.call("playback", {"video_id": video_id}).status_code, 404)

        # 4. FFmpeg processing (real encoder and poster when available): output private, in review, not playable.
        process(video_id)
        video = Video.objects.get(pk=video_id)
        self.assertEqual((video.state, video.visibility), ("review", "private"))
        self.assertGreater(video.duration_ms, 1000)
        self.assertTrue(video.provider_asset_id.startswith("playback/"))
        self.assertEqual(self.bucket.objects[video.poster_asset_id][:2], b"\xff\xd8")
        self.assertIn(b"ftyp", self.bucket.objects[video.provider_asset_id][:16], "an MP4 rendition was stored")
        self.assertEqual(self.call("playback", {"video_id": video_id}).status_code, 404)
        self.assertEqual(self.call("watch-check", {"video_id": video_id}).status_code, 404)
        self.assertEqual([entry for entry in self.bucket.signed if entry[0] == "GET"], [], "no playback grant yet")
        upload = MediaUpload.objects.get(video_id=video_id)
        self.assertIsNone(upload.lease_id, "the worker released its lease")

        # 5. Publishing without approval is refused; the creator cannot skip moderation.
        self.assertEqual(self.call("publish", owner).status_code, 409)

        # 6. Moderation approval: only the Moderation caller, against the current revision, and still private.
        action = {"video_id": video_id, "action": "publish", "revision": video.moderation_revision, "action_id": str(uuid4())}
        self.assertEqual(self.call("apply", action, moderation_video, caller="gateway").status_code, 403)
        self.assertEqual(self.call("apply", action, moderation_video, caller="moderation").status_code, 200)
        self.assertEqual(self.call("apply", action, moderation_video, caller="moderation").status_code, 200, "idempotent")
        video.refresh_from_db()
        self.assertEqual((video.state, video.visibility), ("published", "private"))
        self.assertEqual(self.call("playback", {"video_id": video_id}).status_code, 404, "approved is not yet public")

        # 7. Creator publication makes it public; playback is a short-lived signed grant, tracked playback has the facts
        #    Engagement needs (creator, duration, revision) without any URL.
        self.assertEqual(self.call("publish", owner).status_code, 200)
        playback = json.loads(self.call("playback", {"video_id": video_id}).content)
        self.assertTrue(playback["playback_url"].startswith("https://bucket.invalid/playback/"))
        self.assertEqual(self.bucket.signed[-1], ("GET", Video.objects.get(pk=video_id).provider_asset_id, 300))
        facts = json.loads(self.call("watch-check", {"video_id": video_id}).content)
        self.assertEqual(set(facts), {"creator_id", "duration_ms", "revision"})
        self.assertEqual(facts["creator_id"], str(self.creator))
        self.assertEqual(facts["duration_ms"], Video.objects.get(pk=video_id).duration_ms)
        self.assertGreaterEqual(facts["revision"], 2)

        # 8. Unpublishing closes playback again; the object itself stays private and unreachable without a grant.
        self.assertEqual(self.call("unpublish", owner).status_code, 200)
        self.assertEqual(self.call("playback", {"video_id": video_id}).status_code, 404)
        self.assertEqual(self.call("watch-check", {"video_id": video_id}).status_code, 404)

        # 9. Another creator can do none of it.
        stranger = {"creator_id": str(uuid4()), "video_id": video_id}
        for operation in ("publish", "unpublish", "complete", "detail", "status"):
            self.assertEqual(self.call(operation, stranger).status_code, 404, operation)
