"""Automated copyright/safety pre-screen for processed uploads.

Providers only report findings; `decide` turns findings into one action using configurable thresholds, so the policy
is testable without media. Anything uncertain, failing or unavailable is held for a human (fail closed).
"""

from dataclasses import dataclass, field
import os
from pathlib import Path
import random
from uuid import UUID

DUPLICATE, MUSIC, NSFW, ERROR = "duplicate", "music", "nsfw", "error"
PUBLISH, MUTE, REVIEW, HIDE = "publish", "mute", "review", "hide"
DEFAULT_SCREENERS = "exact_hash,pdq,chromaprint,nsfw"


@dataclass(frozen=True)
class Finding:
    provider: str
    kind: str
    score: float
    reason: str = ""
    segments: tuple = ()  # ((start_ms, end_ms), ...) for audio matches


@dataclass
class ProviderResult:
    findings: list = field(default_factory=list)
    fingerprints: list = field(default_factory=list)  # [(kind, value)] stored for later duplicate checks


@dataclass(frozen=True)
class Media:
    video_id: UUID
    creator_id: UUID
    source: Path
    playback: Path
    duration_ms: int
    workdir: Path


@dataclass(frozen=True)
class Config:
    enabled: bool = False
    screeners: tuple = ()
    duplicate_hide: float = 0.85
    duplicate_review: float = 0.5
    nsfw_hide: float = 0.85
    nsfw_review: float = 0.5
    music_mute: float = 0.6
    music_review: float = 0.4
    max_mute_ratio: float = 0.8
    sample_rate: float = 0.05


@dataclass(frozen=True)
class Decision:
    action: str
    rights_status: str
    reason: str
    mute_segments: tuple = ()


@dataclass
class Outcome:
    decision: Decision
    findings: list
    fingerprints: list

    def hold(self, reason):
        """Replace the decision with a human hold, e.g. when muting itself failed."""
        return Outcome(Decision(REVIEW, "flagged", reason), self.findings, self.fingerprints)


def _fraction(environ, name, default):
    raw = environ.get(name)
    if raw is None or raw == "":
        return default
    value = float(raw)
    if not 0.0 <= value <= 1.0:
        raise ValueError(name)
    return value


def load_config(environ=None):
    """Read thresholds from the environment. Screening is off unless KOLOVIBE_AUTO_SCREENING=1."""
    environ = os.environ if environ is None else environ
    if environ.get("KOLOVIBE_AUTO_SCREENING") != "1":
        return Config()
    names = tuple(name.strip() for name in environ.get("KOLOVIBE_SCREENERS", DEFAULT_SCREENERS).split(",")
                  if name.strip())
    if not names:
        raise ValueError("KOLOVIBE_SCREENERS")
    values = {key: _fraction(environ, "KOLOVIBE_SCREEN_" + key.upper(), default)
              for key, default in (("duplicate_hide", 0.85), ("duplicate_review", 0.5), ("nsfw_hide", 0.85),
                                   ("nsfw_review", 0.5), ("music_mute", 0.6), ("music_review", 0.4),
                                   ("max_mute_ratio", 0.8), ("sample_rate", 0.05))}
    for hide, review in (("duplicate_hide", "duplicate_review"), ("nsfw_hide", "nsfw_review"),
                         ("music_mute", "music_review")):
        if values[review] > values[hide]:
            raise ValueError(review)
    return Config(enabled=True, screeners=names, **values)


def _merge(segments):
    merged = []
    for start, end in sorted(segments):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return tuple(merged)


def decide(findings, duration_ms, config, rng=random.SystemRandom()):
    """Highest-risk finding wins: hide > human review > mute > publish (with random human sampling)."""
    hide = review = None
    segments = []
    for finding in findings:
        if finding.kind == ERROR:
            review = review or "screener_failed:" + finding.provider
        elif finding.kind in (DUPLICATE, NSFW):
            hide_at, review_at = ((config.duplicate_hide, config.duplicate_review) if finding.kind == DUPLICATE
                                  else (config.nsfw_hide, config.nsfw_review))
            if finding.score >= hide_at:
                hide = hide or finding.kind + "_match"
            elif finding.score >= review_at:
                review = review or finding.kind + "_uncertain"
        elif finding.kind == MUSIC:
            if finding.score >= config.music_mute:
                segments.extend(finding.segments or ((0, duration_ms),))
            elif finding.score >= config.music_review:
                review = review or "music_uncertain"
    muted = _merge(segments)
    if sum(end - start for start, end in muted) > config.max_mute_ratio * duration_ms:
        hide = hide or "music_dominant"
    if hide:
        return Decision(HIDE, "hidden", hide)
    if review:
        return Decision(REVIEW, "flagged", review, muted)
    if config.sample_rate and rng.random() < config.sample_rate:
        return Decision(REVIEW, "muted" if muted else "attested", "sampled", muted)
    if muted:
        return Decision(MUTE, "muted", "music_match", muted)
    return Decision(PUBLISH, "attested", "clean")


def providers(names):
    from . import screening_providers

    return [screening_providers.build(name) for name in names]


def evaluate(media, config, screeners=None):
    """Run every configured provider; a provider or configuration failure becomes an `error` finding."""
    findings, fingerprints = [], []
    try:
        screeners = providers(config.screeners) if screeners is None else screeners
    except Exception:
        findings.append(Finding("configuration", ERROR, 1.0, "provider_unavailable"))
        screeners = []
    if not screeners and not findings:
        findings.append(Finding("configuration", ERROR, 1.0, "no_screeners"))
    for screener in screeners:
        try:
            result = screener.screen(media)
        except Exception:
            findings.append(Finding(screener.name, ERROR, 1.0, "provider_failed"))
            continue
        findings.extend(result.findings)
        fingerprints.extend(result.fingerprints)
    return Outcome(decide(findings, media.duration_ms, config), findings, fingerprints)
