"""Screening providers. Heavy or licensed dependencies are imported lazily, so an unavailable one fails closed."""

from collections import Counter, defaultdict
import hashlib
import http.client
import json
import os
from pathlib import Path
import secrets
import ssl
import statistics
import subprocess

from django.db.models import Q

from . import media_encoding, media_storage
from .models import Fingerprint, Video
from .screening import DUPLICATE, MUSIC, NSFW, Finding, ProviderResult

MAX_CANDIDATES = 100_000
PDQ_MIN_QUALITY = 50
PDQ_SCORE_BITS = 64  # score = 1 - distance / 64, so distance 0 -> 1.0 and 32 -> 0.5
FRAME_COUNT = 8
CHROMA_ITEM_MS = 123.8
CHROMA_MIN_OVERLAP = 40
CHROMA_PREFIX_SHIFT = 14
CHROMA_REPORT_FLOOR = 0.3
CHROMA_MAX_REFERENCES = 200
CHROMA_EXTEND_STEP = 4
CHROMA_EXTEND_RATE = 0.25
MUSIC_WINDOW_MS = 12_000
MUSIC_MAX_WINDOWS = 25  # covers the 300 s upload limit
EXPLICIT_CLASSES = {"FEMALE_BREAST_EXPOSED", "FEMALE_GENITALIA_EXPOSED", "MALE_GENITALIA_EXPOSED",
                    "BUTTOCKS_EXPOSED", "ANUS_EXPOSED"}
SAFE_ENV = {"PATH": os.defpath, "LANG": "C"}


def _frames(media):
    directory = media.workdir / "frames"
    if not directory.exists():
        directory.mkdir()
        media_encoding.extract_frames(media.playback, directory, media.duration_ms, FRAME_COUNT)
    return sorted(directory.glob("frame-*.jpg"))


def _audio(media):
    """Path to the mono WAV of the playback audio, or None when the video has no audio track."""
    path = media.workdir / "audio.wav"
    if not path.exists():
        if not media_encoding.has_audio(media.playback):
            return None
        media_encoding.extract_audio(media.playback, path)
    return path


def _reference_prints(media, kind):
    """Confirmed-takedown prints plus other creators' live videos; a creator is never matched against themselves."""
    others = Q(video__deleted_at__isnull=True, video__state__in=[Video.State.REVIEW, Video.State.PUBLISHED]) \
        & ~Q(video__creator_id=media.creator_id)
    return Fingerprint.objects.filter(kind=kind).filter(Q(blocked=True) | others).exclude(video_id=media.video_id)


class ExactHashProvider:
    name = "exact_hash"

    def screen(self, media):
        digest = hashlib.sha256()
        with media.source.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1 << 20), b""):
                digest.update(chunk)
        value = digest.hexdigest()
        result = ProviderResult(fingerprints=[(Fingerprint.Kind.SHA256, value)])
        matches = _reference_prints(media, Fingerprint.Kind.SHA256).filter(value=value)
        if matches.filter(blocked=True).exists():
            result.findings.append(Finding(self.name, DUPLICATE, 1.0, "exact_blocked"))
        elif matches.exists():
            result.findings.append(Finding(self.name, DUPLICATE, 1.0, "exact_duplicate"))
        return result


def _pdq_hashes(frames):
    import numpy
    import pdqhash
    from PIL import Image

    hashes = []
    for frame in frames:
        with Image.open(frame) as image:
            vector, quality = pdqhash.compute(numpy.asarray(image.convert("RGB")))
        if quality >= PDQ_MIN_QUALITY:
            hashes.append(int("".join("1" if bit else "0" for bit in vector), 2))
    return hashes


class PdqProvider:
    """Perceptual frame hashes (Meta PDQ); the video score is the median best-frame similarity."""
    name = "pdq"

    def __init__(self, hasher=_pdq_hashes):
        self.hasher = hasher

    def screen(self, media):
        hashes = self.hasher(_frames(media))
        result = ProviderResult(fingerprints=[(Fingerprint.Kind.PDQ, f"{value:064x}") for value in hashes])
        if not hashes:
            return result
        references = [int(value, 16) for value in
                      _reference_prints(media, Fingerprint.Kind.PDQ).values_list("value", flat=True)[:MAX_CANDIDATES]]
        if references:
            best = [max(max(0.0, 1 - (value ^ other).bit_count() / PDQ_SCORE_BITS) for other in references)
                    for value in hashes]
            score = statistics.median(best)
            if score >= 0.3:
                result.findings.append(Finding(self.name, DUPLICATE, score, "pdq_similar"))
        return result


def _fpcalc(wav):
    try:
        done = subprocess.run(["fpcalc", "-raw", "-json", "-length", str(media_encoding.MAX_DURATION), str(wav)],
                              stdin=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdout=subprocess.PIPE,
                              env=SAFE_ENV, check=True, timeout=30)
        fingerprint = json.loads(done.stdout)["fingerprint"]
    except (OSError, subprocess.SubprocessError, ValueError, KeyError, TypeError):
        raise RuntimeError("fpcalc unavailable") from None
    if isinstance(fingerprint, str):
        fingerprint = fingerprint.split(",")
    return [int(item) & 0xFFFFFFFF for item in fingerprint]


def _usable(prints):
    return len(prints) >= CHROMA_MIN_OVERLAP and len(set(prints)) >= 0.2 * len(prints)


def align(candidate, reference):
    """Best (bit-error-rate, first, last) overlap of two raw Chromaprint sequences, or None."""
    if not _usable(candidate) or not _usable(reference):
        return None
    index = defaultdict(list)
    for position, value in enumerate(reference):
        index[value >> CHROMA_PREFIX_SHIFT].append(position)
    votes = Counter()
    for position, value in enumerate(candidate):
        for other in index.get(value >> CHROMA_PREFIX_SHIFT, ()):
            votes[position - other] += 1
    best = None
    for offset, _ in votes.most_common(3):
        first, last = max(0, offset), min(len(candidate), len(reference) + offset)
        errors = [(candidate[i] ^ reference[i - offset]).bit_count() for i in range(first, last)]
        if len(errors) < CHROMA_MIN_OVERLAP:
            continue
        # Only part of the overlap may be reused audio: take the best window, then grow it while it stays similar.
        width = CHROMA_MIN_OVERLAP
        low = min(range(len(errors) - width + 1), key=lambda start: sum(errors[start:start + width]))
        high = low + width
        step = CHROMA_EXTEND_STEP
        while low - step >= 0 and sum(errors[low - step:low]) <= 32 * step * CHROMA_EXTEND_RATE:
            low -= step
        while high + step <= len(errors) and sum(errors[high:high + step]) <= 32 * step * CHROMA_EXTEND_RATE:
            high += step
        rate = sum(errors[low:high]) / (32 * (high - low))
        if best is None or rate < best[0]:
            best = (rate, first + low, first + high)
    return best


class ChromaprintProvider:
    """Match audio against our own takedown blocklist. score = 1 - 2 * bit-error-rate."""
    name = "chromaprint"

    def __init__(self, fingerprinter=_fpcalc):
        self.fingerprinter = fingerprinter

    def screen(self, media):
        wav = _audio(media)
        if wav is None:
            return ProviderResult()
        prints = self.fingerprinter(wav)
        result = ProviderResult(fingerprints=[(Fingerprint.Kind.CHROMAPRINT, ",".join(map(str, prints)))])
        blocked = Fingerprint.objects.filter(kind=Fingerprint.Kind.CHROMAPRINT, blocked=True) \
            .exclude(video_id=media.video_id).values_list("value", flat=True)[:CHROMA_MAX_REFERENCES]
        for value in blocked:
            match = align(prints, [int(item) for item in value.split(",")])
            if match is None:
                continue
            rate, first, last = match
            score = max(0.0, 1 - 2 * rate)
            if score >= CHROMA_REPORT_FLOOR:
                end = min(media.duration_ms, int(last * CHROMA_ITEM_MS) + 1)
                start = min(int(first * CHROMA_ITEM_MS), end - 1)
                result.findings.append(Finding(self.name, MUSIC, score, "chromaprint_match", ((start, end),)))
        return result


_detector = None


def _nude_scores(frames):
    global _detector
    if _detector is None:
        from nudenet import NudeDetector

        _detector = NudeDetector()
    return [max([item["score"] for item in _detector.detect(str(frame)) if item["class"] in EXPLICIT_CLASSES],
                default=0.0) for frame in frames]


class NudeNetProvider:
    name = "nsfw"

    def __init__(self, scorer=_nude_scores):
        self.scorer = scorer

    def screen(self, media):
        score = max(self.scorer(_frames(media)), default=0.0)
        return ProviderResult([Finding(self.name, NSFW, float(score), "nudenet_explicit")] if score else [])


class AuddClient:
    """Sends short audio windows to AudD over verified TLS. Enabled only by configuration and a private token file."""
    host = "api.audd.io"

    def identify(self, wav):
        token = media_storage._secret("KOLOVIBE_AUDD_TOKEN_FILE")
        boundary = secrets.token_hex(16)
        parts = [f'--{boundary}\r\nContent-Disposition: form-data; name="api_token"\r\n\r\n{token}\r\n'.encode(),
                 (f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="clip.wav"\r\n'
                  "Content-Type: audio/wav\r\n\r\n").encode(), Path(wav).read_bytes(),
                 f"\r\n--{boundary}--\r\n".encode()]
        connection = http.client.HTTPSConnection(self.host, timeout=20, context=ssl.create_default_context())
        try:
            connection.request("POST", "/", b"".join(parts),
                               {"Content-Type": f"multipart/form-data; boundary={boundary}"})
            response = connection.getresponse()
            raw = response.read(65537)
        finally:
            connection.close()
        if response.status != 200 or len(raw) > 65536:
            raise RuntimeError("Music identification unavailable")
        document = json.loads(raw)
        if not isinstance(document, dict) or document.get("status") != "success":
            raise RuntimeError("Music identification unavailable")
        return document.get("result") is not None


class MusicIdProvider:
    """Commercial-music identification through an injected client; each matched window becomes a mute segment."""
    name = "music_id"

    def __init__(self, client=None):
        self.client = client

    def screen(self, media):
        if _audio(media) is None:
            return ProviderResult()
        client = self.client or AuddClient()
        segments = []
        for index in range(min(MUSIC_MAX_WINDOWS, -(-media.duration_ms // MUSIC_WINDOW_MS))):
            start = index * MUSIC_WINDOW_MS
            end = min(media.duration_ms, start + MUSIC_WINDOW_MS)
            clip = media.workdir / f"music-{index}.wav"
            media_encoding.extract_audio(media.playback, clip, start, end - start)
            if client.identify(clip):
                segments.append((start, end))
        return ProviderResult([Finding(self.name, MUSIC, 1.0, "music_id_match", tuple(segments))] if segments else [])


_FACTORIES = {"exact_hash": ExactHashProvider, "pdq": PdqProvider, "chromaprint": ChromaprintProvider,
              "nsfw": NudeNetProvider, "music_id": MusicIdProvider}


def build(name):
    if name not in _FACTORIES:
        raise ValueError("Unknown screener")
    return _FACTORIES[name]()
