"""PostgreSQL-backed outbox and idempotent inbox for at-least-once Celery delivery.

These primitives are not a business-rule processor. Business effects must be
committed in the same transaction as accept_once().
"""
import json
import uuid
from django.db import connection, transaction

SERVICE = "engagement"
TASK_NAME = f"kolovibe.{SERVICE}.event"
QUALIFIED_VIEW = "dec003.qualified_view"

def record_event(event_type, payload):
    if not connection.in_atomic_block:
        raise RuntimeError("Record the event in the same transaction as the business change")
    if not isinstance(event_type, str) or len(event_type) > 100 or not isinstance(payload, dict):
        raise ValueError("Invalid event")
    ident = uuid.uuid4()
    with connection.cursor() as cur:
        cur.execute(
            "INSERT INTO event_outbox (id,event_type,payload) VALUES (%s,%s,%s::jsonb)",
            [str(ident), event_type, json.dumps(payload, separators=(",",":"), allow_nan=False)],
        )
    return str(ident)

def dispatch_one(celery_app):
    """At-least-once dispatch: publishing may succeed before DB acknowledgment."""
    with transaction.atomic():
        with connection.cursor() as cur:
            cur.execute(
                "SELECT id,event_type,payload FROM event_outbox "
                "WHERE published_at IS NULL ORDER BY created_at "
                "FOR UPDATE SKIP LOCKED LIMIT 1"
            )
            row = cur.fetchone()
            if row is None:
                return False
            ident, event_type, payload = row
            if isinstance(payload, str):
                payload = json.loads(payload)
            if event_type == QUALIFIED_VIEW:
                from kombu import Exchange, Queue

                task_name = "kolovibe.points.event"
                # The Points worker owns this pre-provisioned durable queue and its binding.
                # A producer-side Queue declaration tries queue.bind and requires READ on
                # the Points exchange. Since the exchange and queue share a name, granting
                # that READ right would also permit the Engagement user to consume points.
                # Publish to the existing binding without re-declaring broker resources.
                queue = Queue(
                    "kolovibe.points",
                    exchange=Exchange("kolovibe.points", type="direct", durable=True, no_declare=True),
                    routing_key="kolovibe.points",
                    durable=True,
                    no_declare=True,
                )
            else:
                task_name, queue = TASK_NAME, f"kolovibe.{SERVICE}"
            celery_app.send_task(
                task_name,
                args=[str(ident), event_type, payload],
                queue=queue,
                task_id=str(ident),
                delivery_mode=2,
            )
            cur.execute(
                "UPDATE event_outbox SET published_at = now(), attempts = attempts + 1 "
                "WHERE id = %s", [ident]
            )
    return True

def accept_once(event_id, event_type):
    """Call within the SAME DB transaction as every resulting business mutation."""
    uuid.UUID(str(event_id))
    if not connection.in_atomic_block:
        raise RuntimeError("Idempotent event processing requires an atomic transaction")
    with connection.cursor() as cur:
        cur.execute(
            "INSERT INTO event_inbox (id,event_type) VALUES (%s,%s) "
            "ON CONFLICT DO NOTHING", [str(event_id), event_type]
        )
        return cur.rowcount == 1
