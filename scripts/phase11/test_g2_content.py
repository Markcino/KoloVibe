"""Phase 11, test group 2: creator and content. Real FFmpeg and ffprobe on crafted files, and the creator API.

Real Cloudflare R2 upload and playback are BLOCKED (no credentials, no network authorization); storage is the only part
that is not exercised. The encoder and validator below are the production code (`service.media_encoding`).
"""

import json
import os
import secrets
import shutil
import subprocess
import sys
import tempfile
import unittest
import uuid
from pathlib import Path

import lib

CONTENT = lib.ROOT / "services" / "content"


def S():
    return lib.CURRENT


def ffmpeg(*args, timeout=120):
    return subprocess.run(["ffmpeg", "-v", "error", "-y", *args], capture_output=True, timeout=timeout)


def probe(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,codec_name,width,height:format=duration,size:format_tags",
                          "-of", "json", str(path)], capture_output=True, text=True, timeout=30)
    return json.loads(out.stdout or "{}")


def run_encode(source, destination, poster=None):
    """The production validator and encoder, in its own process exactly as the worker would load it."""
    code = ("import json,sys,pathlib;sys.path.insert(0,sys.argv[1]);from service import media_encoding as m\n"
            "try:\n r=m.encode(pathlib.Path(sys.argv[2]),pathlib.Path(sys.argv[3]));print(json.dumps({'ok':True,'ms':r}))\n"
            "except Exception as e:\n print(json.dumps({'ok':False,'error':type(e).__name__}))\n")
    result = subprocess.run([sys.executable, "-c", code, str(CONTENT), str(source), str(destination)], capture_output=True, text=True, timeout=200,
                            env={"PATH": os.environ["PATH"]})
    return json.loads(result.stdout.strip().splitlines()[-1])


class Media(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if shutil.which("ffmpeg") is None:
            raise unittest.SkipTest("ffmpeg is not installed")
        cls.dir = Path(tempfile.mkdtemp(prefix="p11-media-"))
        d = cls.dir
        common = ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac"]
        ffmpeg("-f", "lavfi", "-i", "testsrc=size=640x360:rate=15:duration=2", "-f", "lavfi", "-i", "sine=duration=2", *common, "-shortest", str(d / "valid.mp4"))
        ffmpeg("-f", "lavfi", "-i", "testsrc=size=1920x1080:rate=10:duration=1", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(d / "fullhd.mp4"))
        ffmpeg("-f", "lavfi", "-i", "testsrc=size=3840x2160:rate=5:duration=1", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(d / "uhd.mp4"))
        ffmpeg("-f", "lavfi", "-i", "color=c=black:size=64x64:rate=1:duration=301", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(d / "long.mp4"))
        ffmpeg("-f", "lavfi", "-i", "sine=duration=2", "-c:a", "aac", str(d / "audio_only.mp4"))
        ffmpeg("-f", "lavfi", "-i", "testsrc=size=641x361:rate=10:duration=1", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-vf", "scale=640:360", str(d / "odd.mp4"))
        ffmpeg("-f", "lavfi", "-i", "testsrc=size=320x180:rate=10:duration=1", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-metadata", "title=SECRET-TITLE",
               "-metadata", "location=+06.30-010.80/", "-metadata", "comment=PRIVATE-NOTE", str(d / "metadata.mp4"))
        data = (d / "valid.mp4").read_bytes()
        (d / "truncated.mp4").write_bytes(data[: len(data) // 2])
        (d / "empty.mp4").write_bytes(b"")
        (d / "text.mp4").write_text("this is not a video\n" * 200)
        (d / "polyglot.mp4").write_bytes(data + b"PK\x03\x04" + secrets.token_bytes(500) + b"<?php system($_GET['c']); ?>")
        (d / "playlist.mp4").write_text("#EXTM3U\n#EXT-X-VERSION:3\n#EXTINF:1,\nfile:///etc/hostname\n#EXT-X-ENDLIST\n")
        (d / "concat.mp4").write_text("ffconcat version 1.0\nfile '/etc/passwd'\n")
        (d / "junk_header.mp4").write_bytes(b"\x00\x00\x00\x18ftypmp42" + secrets.token_bytes(4000))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.dir, ignore_errors=True)

    def encode(self, name):
        out = self.dir / (name + ".out.mp4")
        return run_encode(self.dir / name, out), out

    def test_T2_01_a_valid_video_is_converted_to_a_clean_h264_aac_mp4(self):
        result, out = self.encode("valid.mp4")
        self.assertTrue(result["ok"], result)
        info = probe(out)
        codecs = {s["codec_type"]: s["codec_name"] for s in info["streams"]}
        self.assertEqual(codecs, {"video": "h264", "audio": "aac"})
        self.assertAlmostEqual(float(info["format"]["duration"]), 2.0, delta=1.0)
        self.assertAlmostEqual(result["ms"] / 1000, float(info["format"]["duration"]), delta=0.5)

    def test_T2_02_a_full_hd_upload_is_scaled_down_and_dimensions_are_even(self):
        result, out = self.encode("fullhd.mp4")
        self.assertTrue(result["ok"], result)
        video = next(s for s in probe(out)["streams"] if s["codec_type"] == "video")
        self.assertLessEqual(video["width"], 1280)
        self.assertLessEqual(video["height"], 720)
        self.assertEqual((video["width"] % 2, video["height"] % 2), (0, 0))

    def test_T2_03_oversized_dimensions_are_refused(self):
        self.assertEqual(self.encode("uhd.mp4")[0], {"ok": False, "error": "InvalidMedia"})

    def test_T2_04_a_video_longer_than_five_minutes_is_refused(self):
        self.assertEqual(self.encode("long.mp4")[0], {"ok": False, "error": "InvalidMedia"})

    def test_T2_05_files_that_are_not_valid_videos_are_refused(self):
        for name in ("empty.mp4", "text.mp4", "truncated.mp4", "audio_only.mp4", "junk_header.mp4"):
            self.assertEqual(self.encode(name)[0], {"ok": False, "error": "InvalidMedia"}, name)

    def test_T2_06_playlists_and_concat_files_cannot_make_ffmpeg_read_local_files_or_the_network(self):
        for name in ("playlist.mp4", "concat.mp4"):
            result, out = self.encode(name)
            self.assertFalse(result["ok"], f"{name} was accepted")
            self.assertFalse(out.exists(), f"{name} produced output")

    def test_T2_07_appended_data_in_a_polyglot_file_does_not_survive_conversion(self):
        result, out = self.encode("polyglot.mp4")
        if result["ok"]:
            data = out.read_bytes()
            self.assertNotIn(b"<?php", data)
            self.assertNotIn(b"PK\x03\x04", data[-2000:])
        else:
            self.assertEqual(result["error"], "InvalidMedia")

    def test_T2_08_metadata_such_as_titles_and_gps_is_stripped(self):
        result, out = self.encode("metadata.mp4")
        self.assertTrue(result["ok"], result)
        raw = out.read_bytes()
        for marker in (b"SECRET-TITLE", b"PRIVATE-NOTE", b"+06.30-010.80"):
            self.assertNotIn(marker, raw)

    def test_T2_09_the_rendition_is_streamable_and_within_the_size_limit(self):
        result, out = self.encode("valid.mp4")
        self.assertTrue(result["ok"], result)
        data = out.read_bytes()
        self.assertLessEqual(len(data), 50 * 1024 * 1024)
        self.assertLess(data.find(b"moov"), data.find(b"mdat"), "faststart: the index must come before the media data")

    def test_T2_10_a_corrupted_header_in_the_middle_of_a_valid_file_does_not_hang_or_crash_the_encoder(self):
        broken = bytearray((self.dir / "valid.mp4").read_bytes())
        for i in range(0, 400):
            broken[100 + i] = secrets.randbelow(256)
        (self.dir / "bitflip.mp4").write_bytes(bytes(broken))
        result, out = self.encode("bitflip.mp4")
        self.assertIn(result.get("error", "ok"), ("ok", "InvalidMedia"), result)


class CreatorApi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.creator_user, tokens = S().signed_in()
        cls.account = tokens["user"]["id"]
        S().arm_fixture_videos(cls.account)
        cls.token = S().login(cls.creator_user)["access_token"]
        cls.viewer = S().signed_in()[1]["access_token"]

    def draft(self, token=None, **overrides):
        body = {"title": "My original", "category": "comedy", **overrides}
        return S().post("/videos", body, token=token or self.token, key=secrets.token_urlsafe(16))

    def test_T2_20_a_viewer_cannot_create_videos(self):
        self.assertIn(self.draft(self.viewer)[0], (403, 404))

    def test_T2_21_a_creator_can_create_a_draft_and_it_starts_private(self):
        status, body = self.draft()
        self.assertEqual(status, 201, body)
        self.assertEqual(body.get("state"), "draft")
        self.assertNotEqual(body.get("visibility"), "public")
        listing = S().get("/videos")[1]["items"]
        self.assertNotIn(body["id"], [v["id"] for v in listing], "a draft must not be in public discovery")

    def test_T2_22_draft_input_is_validated(self):
        for overrides in ({"title": ""}, {"title": "x" * 500}, {"category": "not-a-category"}, {"tags": ["a"] * 100}, {"cover_time_ms": -5}, {"extra": 1}):
            self.assertEqual(self.draft(**overrides)[0], 400, overrides)

    def test_T2_23_upload_intents_enforce_size_limits_and_the_originality_attestation(self):
        video = self.draft()[1]["id"]
        base = {"originality_attestation": {"version": "R1-originality-v1", "accepted": True}}
        for size in (0, -1, 50 * 1024 * 1024 + 1, 10**12, "100", 1.5, None, True):
            status, body = S().post(f"/videos/{video}/upload-intents", {**base, "size_bytes": size}, token=self.token, key=secrets.token_urlsafe(16))
            self.assertIn(status, (400, 409, 503), (size, status, body))
        status, body = S().post(f"/videos/{video}/upload-intents", {"size_bytes": 1000}, token=self.token, key=secrets.token_urlsafe(16))
        self.assertIn(status, (400, 409, 503), "without the originality attestation no upload may start")
        for bad in (True, {"version": "R1-originality-v1", "accepted": False}, {"version": "old", "accepted": True}, {"accepted": True}, "yes"):
            status, body = S().post(f"/videos/{video}/upload-intents", {"originality_attestation": bad, "size_bytes": 1000}, token=self.token, key=secrets.token_urlsafe(16))
            self.assertEqual(status, 400, (bad, status, body))

    def test_T2_24_one_creator_cannot_touch_anothers_videos(self):
        mine = self.draft()[1]["id"]
        other_user, tokens = S().signed_in()
        other_id = tokens["user"]["id"]
        S().approve_creator(other_id)
        other = S().login(other_user)["access_token"]
        for method, path, body in (("GET", f"/creators/me/videos/{mine}", None), ("GET", f"/videos/{mine}/upload-status", None),
                                   ("POST", f"/videos/{mine}/upload-intents", {"originality_attestation": {"version": "R1-originality-v1", "accepted": True}, "size_bytes": 1000}),
                                   ("POST", f"/videos/{mine}/publish", None), ("POST", f"/videos/{mine}/unpublish", None),
                                   ("GET", f"/creators/me/videos/{mine}/analytics", None)):
            key = secrets.token_urlsafe(16) if method == "POST" else None
            status, answer = S().call(method, path, body, token=other, key=key)
            control = S().call(method, path.replace(mine, str(uuid.uuid4())), body, token=other, key=key)
            self.assertIn(status, (403, 404), f"{method} {path} -> {status}")
            self.assertEqual((status, answer), control, f"{method}: another creator's video answers differently from a missing video (existence leak)")
        self.assertEqual(S().get(f"/creators/me/videos/{mine}", token=self.token)[0], 200, "the owner is unaffected")

    def test_T2_25_a_draft_without_a_finished_upload_cannot_be_published(self):
        video = self.draft()[1]["id"]
        status, body = S().post(f"/videos/{video}/publish", {}, token=self.token, key=secrets.token_urlsafe(16))
        self.assertIn(status, (400, 409), (status, body))
        self.assertNotIn(video, [v["id"] for v in S().get("/videos")[1]["items"]])

    def test_T2_26_an_unpublished_or_unknown_video_has_no_playback(self):
        video = self.draft()[1]["id"]
        self.assertIn(S().get(f"/videos/{video}/playback", token=self.viewer)[0], (403, 404))
        self.assertEqual(S().get(f"/videos/{uuid.uuid4()}/playback", token=self.viewer)[0], 404)

    def test_T2_27_published_playback_returns_a_short_lived_signed_url_only_for_signed_in_viewers(self):
        video = S().video_ids[0]
        self.assertEqual(S().get(f"/videos/{video}/playback")[0], 401)
        status, body = S().get(f"/videos/{video}/playback", token=self.viewer)
        self.assertEqual(status, 200, body)
        url = body["playback_url"]
        self.assertIn("X-Amz-Signature", url)
        self.assertIn("X-Amz-Expires=", url)
        expires = int(url.split("X-Amz-Expires=")[1].split("&")[0])
        self.assertLessEqual(expires, 300, "playback links must be short lived")
        self.assertNotIn(S().environments["content"]["KOLOVIBE_R2_SECRET_KEY_FILE"] if "KOLOVIBE_R2_SECRET_KEY_FILE" in S().environments["content"] else "no-secret", url)
