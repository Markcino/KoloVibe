"""A malformed task message must be rejected, not kill the worker (Phase 11 D11-001).

Celery's `on_task_received` handles only InvalidTaskError, ContentDisallowed and DecodeError around the task strategy. Any other
exception raised while the strategy reads a malformed envelope (for example KeyError('id')) is "unrecoverable" for the whole worker
process; with late acknowledgement the broker redelivers the message after every restart, so the consumer crash-loops. The shared
worker entry point (`staging_runtime.roles.run_celery`) therefore installs a guard that turns those exceptions into
InvalidTaskError, which Celery rejects without requeue.
"""

from pathlib import Path
import sys
import unittest
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services"))

from celery import Celery  # noqa: E402
from celery.exceptions import InvalidTaskError  # noqa: E402
from celery.worker import strategy as celery_strategy  # noqa: E402

from staging_runtime import roles  # noqa: E402

TASK = "kolovibe.points.event"
MALFORMED = (([1, 2, 3], {"task": TASK}), ({"id": "x"}, {"task": TASK}), ("garbage", {"task": TASK}), ({"args": [], "kwargs": {}}, {"task": TASK}))


def app_with_task():
    app = Celery("poison-test", broker="memory://")

    @app.task(name=TASK)
    def receive(event_id, event_type, payload):
        return None

    return app


def message(body, headers):
    msg = MagicMock()
    msg.headers, msg.payload, msg.body, msg.content_type, msg.properties, msg.delivery_info = headers, body, body, "application/json", {}, {}
    return msg


def deliver(handler, body, headers):
    # A real consumer passes no pre-decoded payload for protocol-2 messages (the body is decoded later, in the pool).
    return handler(message(body, headers), None, MagicMock(), MagicMock(), [])


def outcome(handler, body, headers):
    try:
        deliver(handler, body, headers)
        return "accepted"
    except InvalidTaskError:
        return "rejected"
    except Exception as error:  # an exception Celery's consumer does not handle: it would kill the worker
        return "ESCAPES:" + type(error).__name__


class PoisonMessageTests(unittest.TestCase):
    def consumer(self, app):
        consumer = MagicMock()
        consumer.app, consumer.event_dispatcher, consumer.hub = app, MagicMock(), None
        return consumer

    def unguarded(self):
        app = app_with_task()
        return celery_strategy.default(app.tasks[TASK], app, self.consumer(app))

    def guarded(self):
        app = app_with_task()
        roles.guard_malformed_messages(app)
        return roles.resolve_strategy(app)(app.tasks[TASK], app, self.consumer(app))

    def test_celery_lets_some_malformed_messages_escape_as_unrecoverable_errors(self):
        """Canary for the upstream behaviour the guard exists for. If Celery fixes this, this test fails and the guard can be reviewed."""
        results = {repr(body): outcome(self.unguarded(), body, headers) for body, headers in MALFORMED}
        self.assertTrue([r for r in results.values() if r.startswith("ESCAPES")], f"nothing escaped Celery's own handling: {results}")

    def test_the_guard_leaves_no_malformed_message_able_to_escape(self):
        handler = self.guarded()
        for body, headers in MALFORMED:
            self.assertIn(outcome(handler, body, headers), ("accepted", "rejected"), repr(body))

    def test_every_message_that_escaped_unguarded_is_rejected_by_the_guard(self):
        plain, guarded = self.unguarded(), self.guarded()
        for body, headers in MALFORMED:
            if outcome(plain, body, headers).startswith("ESCAPES"):
                self.assertEqual(outcome(guarded, body, headers), "rejected", repr(body))

    def test_a_message_without_an_id_header_is_rejected_not_fatal(self):
        self.assertEqual(outcome(self.guarded(), [1, 2, 3], {"task": TASK}), "rejected")

    def test_run_celery_installs_the_guard_before_the_worker_starts(self):
        app = app_with_task()
        order = []
        app.worker_main = lambda argv: order.append(("worker", roles.resolve_strategy(app).__name__))
        module = MagicMock()
        module.app = app
        with patch.dict(sys.modules, {"fake_worker_module": module}):
            roles.run_celery("fake_worker_module:app", "kolovibe.points")
        self.assertEqual(order, [("worker", "guarded_strategy")], "the worker must start with the guarded strategy in place")


if __name__ == "__main__":
    unittest.main()
