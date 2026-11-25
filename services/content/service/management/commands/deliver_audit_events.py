"""Bounded delivery; retry indefinitely across invocations without losing evidence."""
from datetime import timedelta
import json
import logging

from django.core.management.base import BaseCommand, CommandError
from django.db import DatabaseError, transaction
from django.utils import timezone

from service.internal_client import signed_internal_request
from service.models import AuditDelivery

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Deliver up to 100 due video events with bounded timeout/backoff"

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=100)

    def handle(self, *args, **options):
        if not 1 <= options["limit"] <= 1000:
            raise CommandError("Audit batch must be between 1 and 1000")
        failures = 0
        try:
            ids = list(AuditDelivery.objects.filter(delivered_at__isnull=True,
                       next_attempt_at__lte=timezone.now()).order_by("event__occurred_at", "event_id")
                       .values_list("event_id", flat=True)[:options["limit"]])
            for ident in ids:
                with transaction.atomic():
                    delivery = AuditDelivery.objects.select_for_update(of=("self",)).select_related("event").get(event_id=ident)
                    if delivery.delivered_at is not None or delivery.next_attempt_at > timezone.now():
                        continue
                    event = delivery.event
                    payload = {"id": str(event.id), "actor_id": str(event.actor_id) if event.actor_id else None, "kind": event.kind,
                               "occurred_at": event.occurred_at.isoformat(), "subject_type": event.subject_type,
                               "subject_id": str(event.subject_id)}
                    delivery.attempts += 1
                    try:
                        with signed_internal_request("audit", "/internal/security-events", method="POST",
                             payload=json.dumps(payload, separators=(",", ":")).encode(), timeout=2) as response:
                            raw = response.read(101)
                            if response.status not in (200, 201) or len(raw) > 100 or json.loads(raw) != {"status": "ok"}:
                                raise ValueError("Invalid audit acknowledgment")
                    except (OSError, ValueError, UnicodeError, KeyError, TypeError, RuntimeError):
                        failures += 1
                        delivery.next_attempt_at = timezone.now() + timedelta(seconds=min(3600, 2 ** min(delivery.attempts, 12)))
                        logger.error("Content audit delivery failed; evidence retained")
                    else:
                        delivery.delivered_at = timezone.now()
                    delivery.save(update_fields=["attempts", "delivered_at", "next_attempt_at"])
        except DatabaseError:
            raise CommandError("Content audit database unavailable") from None
        if failures:
            raise CommandError(f"{failures} content audit events await retry")
        self.stdout.write("Content audit batch acknowledged")
