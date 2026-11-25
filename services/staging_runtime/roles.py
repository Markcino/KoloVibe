"""Worker and scheduled-job roles for the shared image (Celery is the approved execution mechanism).

A role is an explicit (service, role) pair that needs one approved capability. Nothing is selected by
default and nothing is shell-evaluated: a role maps to a fixed Celery application and queue, or to one
named Django management command that a bounded loop runs on a fixed interval. The service's own staging
configuration (TLS, secrets, capabilities) is loaded first, so a role cannot start on a service that has
not been approved for the capability.
"""

import os
import signal
import sys
import time

# role -> (capability the settings must carry, kind, target, extra)
ROLES = {
    ("content", "media-worker"): ("media", "celery", "service.media_tasks:app", "kolovibe.content.media"),
    ("engagement", "consumer"): ("engagement", "celery", "service.celery_app:app", "kolovibe.engagement"),
    ("points", "consumer"): ("points", "celery", "service.celery_app:app", "kolovibe.points"),
    ("engagement", "dispatch-events"): ("points", "job", "dispatch_engagement_events", None),
    ("points", "deliver-audit"): ("points", "job", "deliver_audit_events", None),
    ("moderation", "deliver-audit"): ("moderation", "job", "deliver_audit_events", None),
    ("identity", "deliver-security-audit"): ("privileged", "job", "deliver_security_audit", None),
}

MIN_INTERVAL, MAX_INTERVAL = 5, 3600
MAX_CONSECUTIVE_FAILURES = 5


def resolve(service, role):
    try:
        return ROLES[(service, role)]
    except KeyError:
        raise RuntimeError("Unsupported worker role for this service") from None


def require_capability(settings, capability):
    approved = settings.STAGING_PRIVILEGED if capability == "privileged" else capability in settings.STAGING_CAPABILITIES
    if settings.ENVIRONMENT != "staging" or not approved:
        raise RuntimeError("The worker role is not approved for this service")


# One process, one task at a time, recycled before it can grow without bound: the media worker runs
# FFmpeg on untrusted uploads in a memory-constrained node. Gossip and mingle stay off; heartbeats stay on.
CELERY_WORKER_OPTIONS = ("--concurrency=1", "--prefetch-multiplier=1", "--loglevel=WARNING",
                         "--max-tasks-per-child=20", "--max-memory-per-child=262144",
                         "--without-gossip", "--without-mingle", "--without-heartbeat")


def celery_argv(queue):
    return ["worker", "-Q", queue, *CELERY_WORKER_OPTIONS]


GUARDED_STRATEGY = "staging_runtime.roles:guarded_strategy"


def guarded_strategy(task, app, consumer, **kwargs):
    """Celery's default task strategy, with malformed task envelopes turned into InvalidTaskError.

    Celery's `on_task_received` handles only InvalidTaskError, ContentDisallowed and DecodeError around the strategy. Any other
    exception while the strategy reads a malformed envelope (a `task` header with a list body, a missing `id`) is "unrecoverable"
    for the whole worker; with late acknowledgement the broker redelivers the message after every restart, so the consumer
    crash-loops until someone purges the queue (Phase 11 D11-001). InvalidTaskError is Celery's own path: it logs the message and
    rejects it without requeue.
    """
    from celery.exceptions import InvalidTaskError
    from celery.worker.strategy import default
    from kombu.exceptions import ContentDisallowed, DecodeError

    handler = default(task, app, consumer, **kwargs)

    def guarded(message, body, ack, reject, callbacks, *args, **kw):
        try:
            return handler(message, body, ack, reject, callbacks, *args, **kw)
        except (InvalidTaskError, ContentDisallowed, DecodeError):
            raise  # Celery already rejects these
        except (KeyError, TypeError, ValueError, AttributeError, UnicodeError) as error:
            raise InvalidTaskError("Malformed task message (" + type(error).__name__ + ")") from error

    return guarded


def guard_malformed_messages(app):
    app.Task.Strategy = GUARDED_STRATEGY


def resolve_strategy(app):
    from kombu.utils.imports import symbol_by_name

    return symbol_by_name(app.Task.Strategy)


def run_celery(target, queue, argv_hook=None):
    import importlib

    module, _, attribute = target.partition(":")
    app = getattr(importlib.import_module(module), attribute)
    # Remote control (the `celery.pidbox` exchange and the per-node reply queue) is not used and the broker
    # accounts are not granted configure access to it. It must be off before the worker is built, because the
    # Pidbox/Control bootsteps are chosen from this setting at construction time.
    app.conf.worker_enable_remote_control = False
    guard_malformed_messages(app)
    app.worker_main(celery_argv(queue))


def run_job(command, interval, limit, *, sleep=time.sleep, clock=time.monotonic, call=None, stop=None):
    """Run one management command in a bounded loop; exit non-zero after repeated failure so Swarm restarts it."""
    if not MIN_INTERVAL <= interval <= MAX_INTERVAL or not 1 <= limit <= 1000:
        raise RuntimeError("Job interval or batch limit is out of range")
    if call is None:
        from django.core.management import call_command as call
    state = {"stop": False}
    if stop is None:
        for number in (signal.SIGTERM, signal.SIGINT):
            signal.signal(number, lambda n, f: state.update(stop=True))
    failures = 0
    while not (stop() if stop else state["stop"]):
        started = clock()
        try:
            call(command, "--limit", str(limit))
            failures = 0
        except Exception as exc:  # noqa: BLE001 - never print the cause: it may carry configuration
            failures += 1
            if command == "dispatch_engagement_events":
                # Only trusted exception type names: never render str(exc), repr(exc), or tracebacks.
                # A wrapped AMQP refusal may be visible only in __cause__.
                cause = exc.__cause__ or exc.__context__
                print(
                    f"Engagement dispatch failure type={type(exc).__name__} "
                    f"cause_type={type(cause).__name__ if cause is not None else 'none'}",
                    file=sys.stderr,
                    flush=True,
                )
            print("Job failed; will retry", file=sys.stderr)
            if failures >= MAX_CONSECUTIVE_FAILURES:
                raise SystemExit(1) from None
        sleep(max(1, interval - (clock() - started)))
    return 0
