"""Bounded local MP4 validation and encoding for the pilot worker."""

import json
import math
import os
import subprocess

from .media_storage import MAX_BYTES, MAX_POSTER_BYTES


MAX_DURATION = 300
PROBE_TIMEOUT = 15
ENCODE_TIMEOUT = 120
POSTER_TIMEOUT = 15
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
    rendition_duration = _probe(destination)
    if abs(rendition_duration - duration) > 1:
        raise InvalidMedia
    return max(1, math.floor(rendition_duration * 1000))


def render_poster(source, destination, cover_time_ms, duration_ms):
    if (type(cover_time_ms) is not int or not 0 <= cover_time_ms <= duration_ms
            or not 0 < duration_ms <= MAX_DURATION * 1000):
        raise InvalidMedia
    # An inclusive cover at the duration boundary uses the last decodable frame.
    seek_ms = min(cover_time_ms, max(0, duration_ms - 100))
    _run([
        "ffmpeg", "-v", "error", "-nostdin", "-max_alloc", "67108864",
        "-filter_threads", "1", "-protocol_whitelist", "file,pipe", "-f", "mov", "-enable_drefs", "0",
        "-threads", "1", "-i", str(source), "-ss", f"{seek_ms / 1000:.3f}",
        "-map", "0:v:0", "-map_metadata", "-1", "-frames:v", "1", "-an",
        "-vf", r"scale=w=min(640\,iw):h=min(640\,ih):force_original_aspect_ratio=decrease",
        "-c:v", "mjpeg", "-q:v", "3", "-threads", "1", "-fs", str(MAX_POSTER_BYTES),
        "-f", "image2", str(destination),
    ], POSTER_TIMEOUT)
    if not destination.is_file() or not 0 < destination.stat().st_size <= MAX_POSTER_BYTES:
        raise InvalidMedia
    with destination.open("rb") as image:
        if image.read(2) != b"\xff\xd8":
            raise InvalidMedia


MAX_MUTE_SEGMENTS = 20
AUDIO_TIMEOUT = 30
FRAME_TIMEOUT = 30


def has_audio(source):
    response = _run([
        "ffprobe", "-v", "error", "-protocol_whitelist", "file,pipe", "-select_streams", "a:0",
        "-show_entries", "stream=codec_type", "-of", "csv=p=0", str(source),
    ], PROBE_TIMEOUT, output=True)
    return response.stdout.strip() == b"audio"


def extract_audio(source, destination, start_ms=0, length_ms=None):
    """Write mono 16-bit PCM WAV (the format fingerprinters expect); the caller must check `has_audio` first."""
    if type(start_ms) is not int or start_ms < 0 or (length_ms is not None and (type(length_ms) is not int or length_ms <= 0)):
        raise InvalidMedia
    args = ["ffmpeg", "-v", "error", "-nostdin", "-max_alloc", "67108864", "-protocol_whitelist", "file,pipe",
            "-threads", "1", "-ss", f"{start_ms / 1000:.3f}"]
    if length_ms is not None:
        args += ["-t", f"{length_ms / 1000:.3f}"]
    args += ["-i", str(source), "-map", "0:a:0", "-vn", "-ac", "1", "-ar", "11025", "-c:a", "pcm_s16le",
             "-f", "wav", str(destination)]
    _run(args, AUDIO_TIMEOUT)
    if not destination.is_file() or destination.stat().st_size <= 44:
        raise InvalidMedia


def extract_frames(source, directory, duration_ms, count=5):
    """Evenly spaced JPEG frames; never reads past the validated duration."""
    if type(count) is not int or not 0 < count <= 10 or not 0 < duration_ms <= MAX_DURATION * 1000:
        raise InvalidMedia
    frames = []
    for index in range(count):
        at = min(duration_ms * (2 * index + 1) // (2 * count), max(0, duration_ms - 100))
        frame = directory / f"frame-{index}.jpg"
        _run([
            "ffmpeg", "-v", "error", "-nostdin", "-max_alloc", "67108864", "-protocol_whitelist", "file,pipe",
            "-threads", "1", "-ss", f"{at / 1000:.3f}", "-i", str(source), "-map", "0:v:0", "-frames:v", "1",
            "-an", "-vf", r"scale=w=min(512\,iw):h=min(512\,ih):force_original_aspect_ratio=decrease",
            "-c:v", "mjpeg", "-q:v", "3", "-f", "image2", str(frame),
        ], FRAME_TIMEOUT)
        if frame.is_file() and frame.stat().st_size > 0:
            frames.append(frame)
    if not frames:
        raise InvalidMedia
    return frames


def mute_segments(source, destination, segments, duration_ms):
    """Silence the given [start_ms, end_ms) spans while copying the video stream untouched."""
    if (not isinstance(segments, (list, tuple)) or not 0 < len(segments) <= MAX_MUTE_SEGMENTS
            or type(duration_ms) is not int or duration_ms <= 0):
        raise InvalidMedia
    clauses = []
    for segment in segments:
        try:
            start, end = segment
        except (TypeError, ValueError):
            raise InvalidMedia from None
        if type(start) is not int or type(end) is not int or not 0 <= start < end <= duration_ms:
            raise InvalidMedia
        clauses.append(f"volume=enable='between(t,{start / 1000:.3f},{end / 1000:.3f})':volume=0")
    _run([
        "ffmpeg", "-v", "error", "-nostdin", "-max_alloc", "67108864", "-protocol_whitelist", "file,pipe",
        "-f", "mp4", "-threads", "1", "-i", str(source), "-map", "0:v:0", "-map", "0:a:0",
        "-map_metadata", "-1", "-map_chapters", "-1", "-c:v", "copy", "-af", ",".join(clauses),
        "-c:a", "aac", "-ac", "2", "-movflags", "+faststart", "-fs", str(MAX_BYTES), "-f", "mp4",
        str(destination),
    ], ENCODE_TIMEOUT)
    if not destination.is_file() or not 0 < destination.stat().st_size <= MAX_BYTES:
        raise InvalidMedia
    if abs(_probe(destination) - duration_ms / 1000) > 1:
        raise InvalidMedia
