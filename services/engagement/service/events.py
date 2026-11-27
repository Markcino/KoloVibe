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
ERASURE_CONFIRMED = "privacy.erasure_confirmed"
EXPORT_DELIVERED = "privacy.export_delivered"
PRIVACY_REPLIES = (ERASURE_CONFIRMED, EXPORT_DELIVERED)
NEXT_EVENT = ("SELECT id,event_type,payload FROM event_outbox WHERE published_at IS NULL "
              "ORDER BY created_at FOR UPDATE SKIP LOCKED LIMIT 1")
NEXT_PRIVACY_EVENT = ("SELECT id,event_type,payload FROM event_outbox WHERE published_at IS NULL "
                      "AND event_type IN (%s, %s) "
                      "ORDER BY created_at FOR UPDATE SKIP LOCKED LIMIT 1")

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


def _destination(event_type):
    """The pre-provisioned queue an event travels to: (task name, Queue, publish options). Nothing is declared here.

    A qualified view goes to Points; every other event goes to Engagement's own queue. In both cases the message is published
    to the destination's NAMED exchange with an explicit routing key and without declaring the queue or exchange. The
    owning worker creates and binds them. A producer-side declaration needs READ on the exchange, and since the exchange and
    queue share a name, that right would also let the Engagement account consume the Points queue. Publishing through the
    default exchange is not an option either: it routes by queue name to ANY queue, so granting it would let this account
    write to Points directly. Celery selects the default exchange for a bare queue name, hence the explicit options.
    """
    from kombu import Exchange, Queue

    if event_type == QUALIFIED_VIEW:
        task_name, name = "kolovibe.points.event", "kolovibe.points"
    elif event_type in PRIVACY_REPLIES:  # Decision C: confirmations and export parts go back to Identity's own queue
        task_name, name = "kolovibe.identity.event", "kolovibe.identity"
    else:
        task_name, name = TASK_NAME, f"kolovibe.{SERVICE}"
    queue = Queue(
        name,
        exchange=Exchange(name, type="direct", durable=True, no_declare=True),
        routing_key=name,
        durable=True,
        no_declare=True,
    )
    return task_name, queue, {"exchange": name, "routing_key": name}

def dispatch_one(celery_app, privacy_only=False):
    """At-least-once dispatch: publishing may succeed before DB acknowledgment.

    privacy_only limits the batch to erasure confirmations, which must flow even where local points are disabled.
    """
    with transaction.atomic():
        with connection.cursor() as cur:
            if privacy_only:
                cur.execute(NEXT_PRIVACY_EVENT, list(PRIVACY_REPLIES))
            else:
                cur.execute(NEXT_EVENT)
            row = cur.fetchone()
            if row is None:
                return False
            ident, event_type, payload = row
            if isinstance(payload, str):
                payload = json.loads(payload)
            task_name, queue, publish_options = _destination(event_type)
            celery_app.send_task(
                task_name,
                args=[str(ident), event_type, payload],
                queue=queue,
                task_id=str(ident),
                delivery_mode=2,
                **publish_options,
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
