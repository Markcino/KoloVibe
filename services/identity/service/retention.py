"""Bounded removal of expired, single-purpose security rows.

Several tables only matter for a short time (throttle windows, one-time codes, MFA challenges, refresh-replay
markers, finished sessions) yet were never deleted, and `LoginThrottle` rows are created by anonymous login attempts,
so they grew without limit. Each entry below names the column that ends the row's usefulness and how long to keep the
row afterwards. Rows are only removed once that grace has passed, so nothing the service still consults is touched:

* a throttle window older than a day is simply reset the next time its key is seen;
* a refresh-replay marker is consulted only while its session could still refresh (`expires_at`);
* sessions are kept for a month after expiry or revocation for investigation, then removed with their children.

Accounts, security events, audit deliveries, moderator invitations, privacy requests and factors are never touched:
their retention is a policy decision (ADR-020, OD-08) and is not made here.
"""
from datetime import timedelta
import logging
import time

from django.db import DatabaseError, transaction
from django.db.models import Q
from django.utils import timezone

from .models import (EmailVerification, LoginSession, LoginThrottle, MfaChallenge, PasswordReset,
                     ReauthenticationToken, StepUpProof, UsedRefreshToken)

logger = logging.getLogger(__name__)

BATCH = 1000
INTERVAL = 300.0  # seconds between opportunistic purges, per process
_state = {"at": None}


def _rules(now):
    day = timedelta(days=1)
    return (
        ("login_throttle", LoginThrottle.objects.filter(window_started_at__lt=now - day)),
        ("refresh_replay_markers", UsedRefreshToken.objects.filter(expires_at__lt=now - day)),
        ("reauthentication_tokens", ReauthenticationToken.objects.filter(expires_at__lt=now - day)),
        ("step_up_proofs", StepUpProof.objects.filter(expires_at__lt=now - day)),
        ("mfa_challenges", MfaChallenge.objects.filter(expires_at__lt=now - day)),
        ("email_verifications", EmailVerification.objects.filter(expires_at__lt=now - 7 * day)),
        ("password_resets", PasswordReset.objects.filter(expires_at__lt=now - 7 * day)),
        ("sessions", LoginSession.objects.filter(
            Q(expires_at__lt=now - 30 * day) | Q(revoked_at__lt=now - 30 * day))),
    )


def purge_expired(now=None, batch=BATCH):
    """Delete at most `batch` expired rows per table; return how many of each were removed (counts only)."""
    if not isinstance(batch, int) or not 1 <= batch <= 10_000:
        raise ValueError("Invalid purge batch")
    now = now or timezone.now()
    removed = {}
    for name, queryset in _rules(now):
        with transaction.atomic():
            keys = list(queryset.values_list("pk", flat=True)[:batch])
            if keys:
                queryset.model.objects.filter(pk__in=keys).delete()
        removed[name] = len(keys)
    return removed


def maybe_purge():
    """Opportunistic purge at most every few minutes per process; never fails the caller."""
    current = time.monotonic()
    if _state["at"] is not None and current - _state["at"] < INTERVAL:
        return
    _state["at"] = current
    try:
        removed = purge_expired()
    except DatabaseError:
        logger.error("Identity retention purge unavailable")
        return
    if any(removed.values()):
        logger.info("Identity retention purge removed %s", ", ".join(f"{k}={v}" for k, v in removed.items() if v))
