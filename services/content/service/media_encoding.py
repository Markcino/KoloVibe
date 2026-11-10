"""Bounded local MP4 validation and encoding for the pilot worker."""

import json
import math
import os
import subprocess

from .media_storage import MAX_BYTES


MAX_DURATION = 300
PROBE_TIMEOUT = 15
ENCODE_TIMEOUT = 120
SAFE_ENV = {"PATH": os.defpath, "LANG": "C"}


class InvalidMedia(Exception):
    pass


class EncoderUnavailable(Exception):
    pass


def _run(args, timeout, *, output=False):
    try:
        return subprocess.run(args, stdin=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                              stdout=subprocess.PIPE if output else subprocess.DEVNULL,
                              env=SAFE_ENV, check=True, timeout=timeout)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        raise InvalidMedia from None
    except OSError:
        raise EncoderUnavailable from None


def _probe(path):
    response = _run([
        "ffprobe", "-v", "error", "-max_alloc", "67108864",
        "-protocol_whitelist", "file,pipe", "-f", "mov", "-enable_drefs", "0",
        "-select_streams", "v:0", "-show_entries", "stream=width,height:format=duration",
        "-of", "json", str(path),
    ], PROBE_TIMEOUT, output=True)
    try:
        if len(response.stdout) > 4096:
            raise ValueError("Media probe exceeded its response budget")
        info = json.loads(response.stdout)
        width, height = info["streams"][0]["width"], info["streams"][0]["height"]
        duration = float(info["format"]["duration"])
        if not 0 < duration <= MAX_DURATION or min(width, height) <= 0:
            raise ValueError("Invalid duration or dimensions")
        if max(width, height) > 1920 or min(width, height) > 1080:
            raise ValueError("Video dimensions exceed the pilot limit")
        return duration
    except (ValueError, IndexError, KeyError, TypeError):
        raise InvalidMedia from None


def encode(source, destination):
    duration = _probe(source)
    _run([
        "ffmpeg", "-v", "error", "-nostdin", "-max_alloc", "67108864",
        "-filter_threads", "1", "-protocol_whitelist", "file,pipe", "-f", "mov", "-enable_drefs", "0",
        "-threads", "1", "-i", str(source), "-map", "0:v:0", "-map", "0:a:0?",
        "-map_metadata", "-1", "-map_chapters", "-1",
        "-vf", r"scale=w=min(1280\,iw):h=min(720\,ih):force_original_aspect_ratio=decrease:force_divisible_by=2",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "veryfast",
        "-c:a", "aac", "-ac", "2", "-threads", "1", "-movflags", "+faststart",
        "-fs", str(MAX_BYTES), "-f", "mp4", str(destination),
    ], ENCODE_TIMEOUT)
    if not destination.is_file() or not 0 < destination.stat().st_size <= MAX_BYTES:
        raise InvalidMedia
    if abs(_probe(destination) - duration) > 1:
        raise InvalidMedia
    return math.ceil(duration)
