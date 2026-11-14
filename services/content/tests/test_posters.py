from pathlib import Path
import shutil
import subprocess
from tempfile import TemporaryDirectory
from unittest import skipUnless
from unittest.mock import patch
from uuid import uuid4

from django.test import SimpleTestCase

from service import media_encoding, media_storage


class PosterBoundaryTests(SimpleTestCase):
    def test_frame_extraction_has_timeout_size_threads_protocol_and_metadata_limits(self):
        with TemporaryDirectory() as directory:
            destination = Path(directory) / "poster.jpg"
            def render(args, timeout):
                destination.write_bytes(b"\xff\xd8fixture\xff\xd9")
            with patch("service.media_encoding._run", side_effect=render) as run:
                media_encoding.render_poster(Path(directory) / "source.mp4", destination, 1000, 2000)
            args, timeout = run.call_args.args
            self.assertEqual(timeout, media_encoding.POSTER_TIMEOUT)
            self.assertEqual(args[args.index("-protocol_whitelist") + 1], "file,pipe")
            self.assertEqual(args[args.index("-frames:v") + 1], "1")
            self.assertEqual(args[args.index("-fs") + 1], str(media_storage.MAX_POSTER_BYTES))
            self.assertEqual(args[args.index("-map_metadata") + 1], "-1")
            self.assertEqual(args[args.index("-threads") + 1], "1")

    def test_missing_invalid_oversized_or_out_of_range_poster_is_rejected(self):
        with TemporaryDirectory() as directory:
            source, destination = Path(directory) / "source.mp4", Path(directory) / "poster.jpg"
            with patch("service.media_encoding._run"):
                for content in (None, b"invalid jpeg", b"x" * (media_storage.MAX_POSTER_BYTES + 1)):
                    if content is not None:
                        destination.write_bytes(content)
                    with self.assertRaises(media_encoding.InvalidMedia):
                        media_encoding.render_poster(source, destination, 0, 1000)
                with self.assertRaises(media_encoding.InvalidMedia):
                    media_encoding.render_poster(source, destination, 1001, 1000)

    def test_poster_put_has_jpeg_private_cache_and_conditional_headers(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "poster.jpg"
            path.write_bytes(b"\xff\xd8fixture\xff\xd9")
            key = f"playback/{uuid4()}/{uuid4()}.jpg"
            with patch("service.media_storage._request") as request:
                media_storage.put_poster(key, path)
            method, actual_key, headers, body = request.call_args.args
            self.assertEqual((method, actual_key), ("PUT", key))
            self.assertEqual(headers, {"Content-Type": "image/jpeg", "Content-Length": str(path.stat().st_size),
                                       "Cache-Control": "private, no-store", "If-None-Match": "*"})

    def test_ffmpeg_timeout_is_an_invalid_media_failure(self):
        with patch("service.media_encoding.subprocess.run", side_effect=subprocess.TimeoutExpired("ffmpeg", 15)):
            with self.assertRaises(media_encoding.InvalidMedia):
                media_encoding._run(["ffmpeg"], 15)

    # The encoder deliberately runs with a fixed, minimal PATH (media_encoding.SAFE_ENV), so the guard
    # looks for the binaries exactly where the runtime will: a Homebrew install under /usr/local/bin
    # must not turn into a spurious failure, and the sandbox PATH must not be widened to hide it.
    @skipUnless(shutil.which("ffmpeg", path=media_encoding.SAFE_ENV["PATH"])
                and shutil.which("ffprobe", path=media_encoding.SAFE_ENV["PATH"]),
                "FFmpeg and ffprobe are required on the sandbox PATH")
    def test_real_bounded_encoding_and_jpeg_render_for_short_and_longer_clips(self):
        with TemporaryDirectory() as directory:
            for index, duration in enumerate((0.4, 1.6)):
                source = Path(directory) / f"source-{index}.mp4"
                destination = Path(directory) / f"playback-{index}.mp4"
                poster = Path(directory) / f"poster-{index}.jpg"
                # Source filters in a filtergraph (not the lavfi device), so the minimal production FFmpeg can run
                # this: a short blue clip with a silent audio track exercises the video and the audio path.
                subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-filter_complex",
                                f"color=c=blue:s=64x64:r=25:d={duration}[v];anullsrc=r=44100:cl=mono:d={duration}[a]",
                                "-map", "[v]", "-map", "[a]", "-threads", "1",
                                "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(source)],
                               check=True, timeout=15, stdin=subprocess.DEVNULL, capture_output=True)
                duration_ms = media_encoding.encode(source, destination)
                self.assertGreater(duration_ms, 0)
                cover = 1000 if duration_ms > 1000 else 0
                media_encoding.render_poster(destination, poster, cover, duration_ms)
                self.assertEqual(poster.read_bytes()[:2], b"\xff\xd8")
                self.assertLessEqual(poster.stat().st_size, media_storage.MAX_POSTER_BYTES)
                # The inclusive endpoint is supported even at the end of a clip.
                last = Path(directory) / f"last-{index}.jpg"
                media_encoding.render_poster(destination, last, duration_ms, duration_ms)
                self.assertGreater(last.stat().st_size, 0)
