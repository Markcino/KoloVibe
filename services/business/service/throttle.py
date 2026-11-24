"""DB-backed budgets with hashed keys (pattern: Identity's LoginThrottle); raw identifiers are never stored."""
import hashlib
import hmac

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .limits import BUDGETS
from .models import ThrottleCounter


def _key(name, actor_id):
    return hmac.new(settings.SECRET_KEY.encode(), f"{name}\0{actor_id}".encode(), hashlib.sha256).hexdigest()


def allow(name, actor_id):
    """Count one attempt; False when the actor is over budget for the window."""
    limit, window = BUDGETS[name]
    now = timezone.now()
    with transaction.atomic():
        row, _ = ThrottleCounter.objects.select_for_update().get_or_create(
            key=_key(name, actor_id), defaults={"window_started_at": now})
        if now - row.window_started_at >= window:
            row.count, row.window_started_at = 0, now
        if row.count >= limit:
            return False
        row.count += 1
        row.save(update_fields=["count", "window_started_at"])
    return True
