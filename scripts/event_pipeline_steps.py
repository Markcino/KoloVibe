"""Child-process steps for scripts/verify_event_pipeline.py: run one service's real code against its own database.

Usage: python scripts/event_pipeline_steps.py <engagement|points> <step> '<json arguments>'
The parent supplies the service's disposable PostgreSQL environment. Each step prints one JSON line. Two services
cannot share a process (both are the Python package `service`), which is also how they run in production, so the
messages the steps exchange are plain JSON, exactly as Celery would carry them.
"""

from datetime import UTC, timedelta
import traceback
import json
import os
import sys
import threading
import uuid
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def setup(service):
    directory = ROOT / "services" / service
    sys.path[:0] = [str(directory), str(ROOT / "services")]
    os.chdir(directory)
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "service.settings")
    # The worker module only validates the URI at import; nothing connects. It must look like the approved form.
    import secrets

    os.environ.setdefault("KOLOVIBE_RABBITMQ_URL", f"amqps://worker:{secrets.token_urlsafe(12)}@broker.invalid:5671/")
    os.environ["KOLOVIBE_LOCAL_POINTS_ENABLED"] = "1"
    import django

    django.setup()


class RecordingPublisher:
    """Stands in for the Celery app: records exactly what would be published, and can simulate a broker outage."""

    def __init__(self, fail_times=0):
        self.messages, self.fail_times = [], fail_times

    def send_task(self, name, **kwargs):
        if self.fail_times:
            self.fail_times -= 1
            raise ConnectionError("simulated broker interruption")
        queue = kwargs.get("queue")
        self.messages.append({
            "name": name, "args": kwargs["args"], "task_id": kwargs["task_id"],
            "delivery_mode": kwargs.get("delivery_mode"), "exchange": kwargs.get("exchange"),
            "routing_key": kwargs.get("routing_key"),
            "queue": getattr(queue, "name", queue),
            "queue_exchange": getattr(getattr(queue, "exchange", None), "name", None),
            "queue_no_declare": getattr(queue, "no_declare", None),
            "exchange_no_declare": getattr(getattr(queue, "exchange", None), "no_declare", None),
        })


def engagement_qualify(arguments):
    """Create `count` qualified views through the real watch API (distinct viewers and videos)."""
    from django.db import connection
    from django.utils import timezone
    from service.watch import progress, start

    now = timezone.now()
    created = []
    for _ in range(arguments["count"]):
        data = {"account_id": uuid.uuid4(), "video_id": uuid.uuid4(), "creator_user_id": arguments.get("creator") and
                uuid.UUID(arguments["creator"]) or uuid.uuid4(), "duration_ms": 3000, "revision": 1}
        with patch("service.watch.timezone.now", return_value=now):
            session = uuid.UUID(json.loads(start(data).content)["session_id"])
        sample = data | {"session_id": session, "position_ms": 2500}
        with patch("service.watch.timezone.now", return_value=now + timedelta(seconds=3)):
            for _ in range(2):
                assert json.loads(progress(sample).content) == {"qualified": True}
        created.append(str(data["creator_user_id"]))
    with connection.cursor() as cursor:
        cursor.execute("SELECT count(*) FROM event_outbox WHERE published_at IS NULL")
        return {"unpublished": cursor.fetchone()[0], "creators": created}


def engagement_dispatch(arguments):
    from django.db import connection
    from service import events

    publisher = RecordingPublisher(fail_times=arguments.get("fail_times", 0))
    failures = 0
    while True:
        try:
            if not events.dispatch_one(publisher):
                break
        except ConnectionError:
            failures += 1
            if failures > arguments.get("max_failures", 5):
                break
    with connection.cursor() as cursor:
        cursor.execute("SELECT count(*), count(published_at), coalesce(sum(attempts), 0) FROM event_outbox")
        total, published, attempts = cursor.fetchone()
    return {"messages": publisher.messages, "failures": failures, "outbox_total": total,
            "outbox_published": published, "attempts": int(attempts)}


def _wire(message):
    """Celery's JSON serializer round trip."""
    return json.loads(json.dumps(message["args"]))


def points_consume(arguments):
    """Deliver messages to the real Celery task body, `times` each, optionally from concurrent workers."""
    from django.db import connection
    from service.celery_app import receive_event

    deliveries = [_wire(message) for message in arguments["messages"] for _ in range(arguments.get("times", 1))]
    results, errors = [], []

    def deliver(args):
        try:
            # `.run` is the task body. Production workers are separate processes; Task.__call__ keeps per-process
            # request state and is not meant to be shared by threads.
            results.append(receive_event.run(*args) if arguments.get("concurrent") else receive_event(*args))
        except Exception as error:  # reported as a type name only
            errors.append(type(error).__name__ + ": " + traceback.format_exc().splitlines()[-3][-90:])
        finally:
            connection.close()

    if arguments.get("concurrent"):
        threads = [threading.Thread(target=deliver, args=(args,)) for args in deliveries]
        [thread.start() for thread in threads]
        [thread.join() for thread in threads]
    else:
        for args in deliveries:
            deliver(args)
    return {"applied": sum(1 for item in results if item is True), "results": len(results), "errors": errors}


def points_crash_then_recover(arguments):
    """The worker dies after the receipt commits but before the award posts; a redelivery completes it."""
    from service.celery_app import receive_event
    from service.models import PointsEntry, QualificationReceipt

    args = _wire(arguments["message"])
    with patch("service.pilot_points.audit_record", side_effect=RuntimeError("worker killed")):
        try:
            receive_event(*args)
            crashed = False
        except RuntimeError:
            crashed = True
    during = {"receipt": QualificationReceipt.objects.get(pk=args[0]).status,
              "entries": PointsEntry.objects.filter(source_decision_id=args[0]).count()}
    applied = receive_event(*args)
    after = {"receipt": QualificationReceipt.objects.get(pk=args[0]).status,
             "entries": PointsEntry.objects.filter(source_decision_id=args[0]).count()}
    return {"crashed": crashed, "during": during, "applied_on_redelivery": applied, "after": after}


def points_seed_cap(arguments):
    from django.utils import timezone
    from service.models import DailyAwardCount

    DailyAwardCount.objects.update_or_create(
        creator_user_id=uuid.UUID(arguments["creator"]), day=timezone.now().astimezone(UTC).date(),
        defaults={"awards": arguments["awards"]})
    return {}


def points_state(arguments):
    from service.models import AuditDelivery, AuditEvent, DailyAwardCount, PointsEntry, QualificationReceipt
    from django.db import connection

    creators = [uuid.UUID(item) for item in arguments["creators"]]
    receipts = QualificationReceipt.objects.filter(creator_user_id__in=creators)
    with connection.cursor() as cursor:
        cursor.execute("SELECT count(*) FROM event_inbox")
        inbox = cursor.fetchone()[0]
    return {
        "entries": PointsEntry.objects.filter(creator_user_id__in=creators).count(),
        "balance": sum(PointsEntry.objects.filter(creator_user_id__in=creators).values_list("delta", flat=True)),
        "receipts": {status: receipts.filter(status=status).count() for status in ("pending", "posted", "withheld")},
        "inbox": inbox,
        "audit": {kind: AuditEvent.objects.filter(kind=kind).count() for kind in ("points.awarded", "points.withheld")},
        "deliveries_pending": AuditDelivery.objects.filter(delivered_at__isnull=True).count(),
        "awards_today": sum(DailyAwardCount.objects.filter(creator_user_id__in=creators).values_list("awards", flat=True)),
    }


def points_deliver_audit(arguments):
    """Run the real audit delivery command against a stand-in Audit service that can fail first."""
    from django.core.management import call_command, CommandError
    from io import StringIO

    sent, remaining_failures = [], [arguments.get("fail_first", 0)]

    class Ack:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def read(self, limit):
            return b'{"status":"ok"}'

    def fake(audience, path, *, method, payload, timeout):
        if remaining_failures[0]:
            remaining_failures[0] -= 1
            raise OSError("audit unavailable")
        sent.append({"audience": audience, "path": path, "payload": json.loads(payload)})
        return Ack()

    outcome = "ok"
    with patch("service.management.commands.deliver_audit_events.signed_internal_request", fake):
        try:
            call_command("deliver_audit_events", stdout=StringIO())
        except CommandError:
            outcome = "retry"
    return {"outcome": outcome, "sent": sent}


def points_make_available(arguments):
    from django.utils import timezone
    from service.models import AuditDelivery

    AuditDelivery.objects.update(next_attempt_at=timezone.now() - timedelta(seconds=1))
    return {}


def points_ledger_rules(arguments):
    """Reversal behaviour the schema enforces today (no write path creates reversals; none was invented)."""
    from django.db import DatabaseError, IntegrityError, transaction
    from service.models import PointsEntry

    creator = uuid.uuid4()
    award = PointsEntry.objects.create(creator_user_id=creator, source_decision_id=uuid.uuid4(), delta=1,
                                       entry_type="AWARD", rule_version="t", reason_code="T")
    outcomes = {}

    def attempt(name, action):
        try:
            with transaction.atomic():
                action()
            outcomes[name] = "accepted"
        except (IntegrityError, DatabaseError, ValueError) as error:
            outcomes[name] = type(error).__name__

    attempt("positive_reversal", lambda: PointsEntry.objects.create(
        creator_user_id=creator, delta=1, entry_type="REVERSAL", reversal_of=award, rule_version="t", reason_code="T"))
    attempt("reversal_without_target", lambda: PointsEntry.objects.create(
        creator_user_id=creator, delta=-1, entry_type="REVERSAL", rule_version="t", reason_code="T"))
    attempt("zero_delta", lambda: PointsEntry.objects.create(
        creator_user_id=creator, delta=0, entry_type="ADJUSTMENT", rule_version="t", reason_code="T"))
    attempt("valid_reversal", lambda: PointsEntry.objects.create(
        creator_user_id=creator, delta=-1, entry_type="REVERSAL", reversal_of=award, rule_version="t", reason_code="T"))
    attempt("second_reversal_of_same_award", lambda: PointsEntry.objects.create(
        creator_user_id=creator, delta=-1, entry_type="REVERSAL", reversal_of=award, rule_version="t", reason_code="T"))
    attempt("update_entry", lambda: PointsEntry.objects.filter(pk=award.pk).update(delta=5))
    attempt("delete_entry", lambda: PointsEntry.objects.filter(pk=award.pk).delete())
    attempt("orm_save_existing", lambda: (setattr(award, "delta", 9), award.save()))
    return {"outcomes": outcomes, "balance": sum(PointsEntry.objects.filter(
        creator_user_id=creator).values_list("delta", flat=True))}


def _outbox_counts():
    from django.db import connection

    with connection.cursor() as cursor:
        cursor.execute("SELECT count(*), count(published_at), coalesce(sum(attempts), 0) FROM event_outbox")
        total, published, attempts = cursor.fetchone()
    return {"outbox_total": total, "outbox_published": published, "attempts": int(attempts)}


# --- steps for scripts/verify_event_pipeline_broker.py: the same code, against a real RabbitMQ ----------------------

def engagement_dispatch_real(arguments):
    """Publish through the service's own Celery app (real AMQPS connection, real account permissions)."""
    from service import events
    from service.celery_app import app

    errors, detail = [], ""
    for _ in range(arguments.get("limit", 50)):
        try:
            if not events.dispatch_one(app):
                break
        except Exception as error:  # a type name and the broker's own refusal text; the outbox must keep the event
            errors.append(type(error).__name__)
            detail = str(error)[:200]
            break
    return {"errors": errors, "detail": detail if errors else "", **_outbox_counts()}


def engagement_reset_outbox(arguments):
    """Make every published event unpublished again: the broker then sees the same event id a second time."""
    from django.db import connection

    with connection.cursor() as cursor:
        cursor.execute("UPDATE event_outbox SET published_at = NULL")
    return _outbox_counts()


def engagement_record_other(arguments):
    """An outbox event that is not a qualified view: it travels to Engagement's own queue."""
    from django.db import transaction
    from service import events

    with transaction.atomic():
        return {"event_id": events.record_event(arguments.get("event_type", "foundation.ping"), {"n": 1})}


def points_worker(arguments):
    """The production worker entry point (queue and options exactly as the shared image runs them). Blocks."""
    from staging_runtime import roles

    roles.run_celery("service.celery_app:app", "kolovibe.points")
    return {}


if __name__ == "__main__":
    service, step = sys.argv[1], sys.argv[2]
    setup(service)
    print("RESULT " + json.dumps(globals()[f"{service}_{step}"](json.loads(sys.argv[3]))))
