import json
import logging
from urllib.error import URLError

from django.core.management.base import BaseCommand, CommandError
from django.db import DatabaseError, transaction
from django.utils import timezone

from service.internal_client import signed_internal_request
from service.models import AuditDelivery

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Deliver a bounded batch of immutable identity events; failed events remain retryable"

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=100)

    def handle(self, *args, **options):
        if not 1 <= options["limit"] <= 1000:
            raise CommandError("Audit delivery batch must be between 1 and 1000")
        failures = 0
        deliveries = AuditDelivery.objects.filter(delivered_at__isnull=True).order_by(
            "event__occurred_at", "event_id").values_list("event_id", flat=True)[:options["limit"]]
        for event_id in list(deliveries):
            try:
                with transaction.atomic():
                    delivery = AuditDelivery.objects.select_for_update().select_related("event").get(
                        event_id=event_id)
                    if delivery.delivered_at is not None:
                        continue
                    delivery.attempts += 1
                    event = delivery.event
                    payload = json.dumps({
                        "id": str(event.id), "actor_id": str(event.actor_id) if event.actor_id else None,
                        "kind": event.kind, "occurred_at": event.occurred_at.isoformat(),
                    }, separators=(",", ":")).encode()
                    try:
                        with signed_internal_request("audit", "/internal/security-events",
                                                     method="POST", payload=payload, timeout=2) as response:
                            if response.status not in (200, 201) or json.loads(
                                    response.read(100)) != {"status": "ok"}:
                                raise ValueError("Invalid audit acknowledgment")
                    except (URLError, OSError, ValueError, UnicodeError, KeyError, TypeError, RuntimeError):
                        logger.error("Security audit delivery failed; event retained for retry")
                        failures += 1
                    else:
                        delivery.delivered_at = timezone.now()
                    delivery.save(update_fields=["attempts", "delivered_at"])
            except DatabaseError:
                raise CommandError("Security audit delivery database unavailable") from None
        if failures:
            raise CommandError(f"{failures} security events await retry")
        self.stdout.write("Security audit batch acknowledged")
