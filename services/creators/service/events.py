"""PostgreSQL-backed outbox and idempotent inbox for Creators (Decision C erasure).

The same primitives as Engagement and Identity; the tables come from infra/postgres/schema_isolation.sql. Creators only
sends one kind of event, `privacy.erasure_confirmed`, to Identity's named exchange with an explicit routing key, and
never declares anything. Its broker account therefore needs write access to `kolovibe.identity` and its own queue
only (generate_r1_secrets.PROPOSED_BROKER_PERMISSIONS).
"""
import json
import uuid

from django.db import connection, transaction

SERVICE = "creators"
QUEUE = "kolovibe.creators"
ERASURE_REQUESTED = "privacy.erasure_requested"
ERASURE_CONFIRMED = "privacy.erasure_confirmed"
INSERT_POSTGRES = "INSERT INTO event_outbox (id,event_type,payload) VALUES (%s,%s,%s::jsonb)"
INSERT_SQLITE = "INSERT INTO event_outbox (id,event_type,payload) VALUES (%s,%s,%s)"  # the test fixture has no jsonb


def record_event(event_type, payload):
    if not connection.in_atomic_block:
        raise RuntimeError("Record the event in the same transaction as the business change")
    if event_type != ERASURE_CONFIRMED or not isinstance(payload, dict) or payload.get("service") != SERVICE:
        raise ValueError("Invalid event")
    ident = uuid.uuid4()
    with connection.cursor() as cur:
        cur.execute(INSERT_POSTGRES if connection.vendor == "postgresql" else INSERT_SQLITE,
                    [str(ident), event_type, json.dumps(payload, separators=(",", ":"), allow_nan=False)])
    return str(ident)


def _destination():
    from kombu import Exchange, Queue

    name = "kolovibe.identity"
    queue = Queue(name, exchange=Exchange(name, type="direct", durable=True, no_declare=True), routing_key=name,
                  durable=True, no_declare=True)
    return "kolovibe.identity.event", queue, {"exchange": name, "routing_key": name}


def dispatch_one(celery_app):
    """At-least-once dispatch: publishing may succeed before the database acknowledges it."""
    with transaction.atomic():
        with connection.cursor() as cur:
            cur.execute("SELECT id,event_type,payload FROM event_outbox WHERE published_at IS NULL "
                        "ORDER BY created_at FOR UPDATE SKIP LOCKED LIMIT 1")
            row = cur.fetchone()
            if row is None:
                return False
            ident, event_type, payload = row
            if event_type != ERASURE_CONFIRMED:
                raise ValueError("Unexpected outbox event")
            if isinstance(payload, str):
                payload = json.loads(payload)
            task_name, queue, options = _destination()
            celery_app.send_task(task_name, args=[str(ident), event_type, payload], queue=queue,
                                 task_id=str(ident), delivery_mode=2, **options)
            cur.execute("UPDATE event_outbox SET published_at = now(), attempts = attempts + 1 WHERE id = %s", [ident])
    return True


def accept_once(event_id, event_type):
    """Call within the SAME transaction as every resulting change."""
    uuid.UUID(str(event_id))
    if not connection.in_atomic_block:
        raise RuntimeError("Idempotent event processing requires an atomic transaction")
    with connection.cursor() as cur:
        cur.execute("INSERT INTO event_inbox (id,event_type) VALUES (%s,%s) ON CONFLICT DO NOTHING",
                    [str(event_id), event_type])
        return cur.rowcount == 1
