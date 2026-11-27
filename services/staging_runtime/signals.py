"""Read-only health signals for audit delivery, stuck media and broker queues (#145, mandate item 2.3).

A job role that owns one of these backlogs emits its signal after every batch, so no extra process is needed. Each
signal is one JSON line on stdout, prefixed `KOLOVIBE_SIGNAL `, holding only names and counts: never an identifier,
payload, credential or exception message. When the owner has approved a threshold for the signal (an environment
value; there are no defaults, and this module invents none), the line also says whether the threshold is breached,
and a breach is repeated on stderr prefixed `KOLOVIBE_ALERT ` for the log pipeline to forward. Without an approved
threshold the line carries `"alert": null`.

What this does not do: it does not notify anyone. Choosing the monitoring platform, the notification channel and
the on-call path is an owner decision (OD-08, ADR-017). A job that is not running emits nothing, so detecting a
missing signal needs that platform too.
"""

import json
import os
import sys

# signal name -> {threshold field: environment variable holding the owner-approved value}
THRESHOLDS = {
    "audit_backlog": {"oldest_age_seconds": "KOLOVIBE_ALERT_AUDIT_MAX_AGE_SECONDS",
                      "pending": "KOLOVIBE_ALERT_AUDIT_MAX_PENDING"},
    "media_stalled": {"stalled": "KOLOVIBE_ALERT_MEDIA_MAX_STALLED"},
    "queue_depth": {"messages": "KOLOVIBE_ALERT_QUEUE_MAX_DEPTH"},
}
MEDIA_QUEUE = "kolovibe.content.media"


def _now():
    from django.utils import timezone

    return timezone.now()


def audit_backlog(now=None):
    """Undelivered audit evidence held by this service: count, oldest age and the highest retry count."""
    from django.db.models import Max, Min
    from service.models import AuditDelivery

    now = now or _now()
    pending = AuditDelivery.objects.filter(delivered_at__isnull=True)
    summary = pending.aggregate(oldest=Min("event__occurred_at"), attempts=Max("attempts"))
    oldest = summary["oldest"]
    return {"pending": pending.count(),
            "oldest_age_seconds": None if oldest is None else max(0, int((now - oldest).total_seconds())),
            "max_attempts": summary["attempts"] or 0}


def media_stalled(now=None):
    """Processing videos the requeue job considers stalled (its reviewed 15-minute rule), and the oldest one's age."""
    from service.management.commands.requeue_stalled_media import stalled_uploads

    now = now or _now()
    stalled = stalled_uploads(now)
    first = stalled.values_list("expires_at", flat=True).first()
    return {"stalled": stalled.count(),
            "oldest_age_seconds": None if first is None else max(0, int((now - first).total_seconds()))}


def queue_depth(queue=MEDIA_QUEUE):
    """Ready messages and consumers on one queue, by a passive declare that never creates or changes the queue."""
    from service.media_tasks import app

    with app.connection_for_read() as connection:
        _, messages, consumers = connection.default_channel.queue_declare(queue=queue, passive=True)
    return {"queue": queue, "messages": int(messages), "consumers": int(consumers)}


SIGNALS = {"audit_backlog": audit_backlog, "media_stalled": media_stalled, "queue_depth": queue_depth}


def approved_thresholds(name, environ=None):
    """{field: limit} for the thresholds the owner has set; a malformed value is refused, never guessed."""
    environ = os.environ if environ is None else environ
    limits = {}
    for field, variable in THRESHOLDS[name].items():
        value = environ.get(variable, "")
        if value == "":
            continue
        if not value.isdigit():
            raise RuntimeError("Alert threshold must be a whole number: " + variable)
        limits[field] = int(value)
    return limits


def evaluate(name, values, limits):
    """None without an approved threshold, else whether any measured value exceeds its limit."""
    if not limits:
        return None
    return any(values.get(field) is not None and values[field] > limit for field, limit in limits.items())


def emit(service, names, *, measure=None, environ=None, out=None, err=None):
    """Measure and print each named signal; a signal that cannot be measured says so, without the cause."""
    measure = SIGNALS if measure is None else measure
    out, err = out or sys.stdout, err or sys.stderr
    for name in names:
        limits = approved_thresholds(name, environ)
        try:
            values = measure[name]()
        except Exception:  # noqa: BLE001 - never print the cause: it may carry configuration
            values = None
        record = {"signal": name, "service": service}
        if values is None:
            record.update(available=False, alert=None)
        else:
            record.update(values, available=True, thresholds=limits, alert=evaluate(name, values, limits))
        line = json.dumps(record, sort_keys=True, separators=(",", ":"))
        print("KOLOVIBE_SIGNAL " + line, file=out, flush=True)
        if record["alert"]:
            print("KOLOVIBE_ALERT " + line, file=err, flush=True)
