"""Django database contract tests for the outbox and inbox primitives."""
from contextlib import nullcontext
from unittest.mock import MagicMock, patch
from uuid import UUID

from django.test import SimpleTestCase
from service import events

class EventContractTests(SimpleTestCase):
    def test_record_requires_atomic_business_transaction(self):
        with self.assertRaises(RuntimeError):
            events.record_event("engagement.received", {})
    def test_accept_requires_atomic_transaction(self):
        with self.assertRaises(RuntimeError):
            events.accept_once("2a31e65b-fb55-4f8f-ae99-f5b67a5617cb", "accepted")
    def test_event_payload_validation_requires_transaction_first(self):
        with self.assertRaises(RuntimeError):
            events.record_event("content.created", {"sample": True})


class OutboxPublishPermissionTests(SimpleTestCase):
    def dispatch(self, event_type):
        app = MagicMock()
        db = MagicMock()
        cursor = db.cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value = (
            UUID("d37b09c2-934f-4b69-ad5f-d41f4a3d8096"),
            event_type,
            {"video_id": "test-video"},
        )
        with patch.object(events, "connection", db), patch.object(
            events.transaction, "atomic", return_value=nullcontext()
        ):
            self.assertTrue(events.dispatch_one(app))
        return app, cursor

    def test_qualified_view_uses_preexisting_points_binding(self):
        app, cursor = self.dispatch(events.QUALIFIED_VIEW)
        options = app.send_task.call_args.kwargs
        queue = options["queue"]
        self.assertEqual(app.send_task.call_args.args[0], "kolovibe.points.event")
        self.assertEqual(queue.name, "kolovibe.points")
        self.assertEqual(queue.exchange.name, "kolovibe.points")
        self.assertEqual(queue.routing_key, "kolovibe.points")
        self.assertEqual(options["exchange"], "kolovibe.points")
        self.assertEqual(options["routing_key"], "kolovibe.points")
        self.assertEqual(queue.exchange.type, "direct")
        self.assertTrue(queue.no_declare)
        self.assertTrue(queue.exchange.no_declare)
        self.assertEqual(options["delivery_mode"], 2)
        self.assertEqual(options["task_id"], "d37b09c2-934f-4b69-ad5f-d41f4a3d8096")
        self.assertIn("published_at = now()", cursor.execute.call_args_list[-1].args[0])

    def test_qualified_view_actual_celery_publish_uses_named_exchange(self):
        """Exercise Celery's actual routing; a Queue object's metadata is not enough."""
        from celery import Celery
        from kombu.transport import memory

        app = Celery("kolovibe-publish-route-test", broker="memory://")
        app.conf.update(
            task_default_queue="kolovibe.engagement",
            task_serializer="json",
            task_ignore_result=True,
            result_backend=None,
        )
        db = MagicMock()
        cursor = db.cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value = (
            UUID("d37b09c2-934f-4b69-ad5f-d41f4a3d8096"),
            events.QUALIFIED_VIEW,
            {"creator_user_id": "test", "qualified_at": "test"},
        )
        published = []

        def reject_declaration(*args, **kwargs):
            raise AssertionError("Publisher must not declare or bind broker resources")

        def capture_publish(channel, message, **kwargs):
            published.append((kwargs.get("exchange"), kwargs.get("routing_key")))

        with (
            patch.object(events, "connection", db),
            patch.object(events.transaction, "atomic", return_value=nullcontext()),
            patch.object(memory.Channel, "queue_bind", new=reject_declaration),
            patch.object(memory.Channel, "exchange_declare", new=reject_declaration),
            patch.object(memory.Channel, "basic_publish", new=capture_publish),
        ):
            self.assertTrue(events.dispatch_one(app))

        self.assertEqual(published, [("kolovibe.points", "kolovibe.points")])

    def test_engagement_queue_routing_unchanged(self):
        app, _ = self.dispatch("engagement.received")
        options = app.send_task.call_args.kwargs
        self.assertEqual(app.send_task.call_args.args[0], events.TASK_NAME)
        self.assertEqual(options["queue"], "kolovibe.engagement")

    def test_failed_publish_does_not_acknowledge_outbox(self):
        app = MagicMock()
        app.send_task.side_effect = RuntimeError("broker publish rejected")
        db = MagicMock()
        cursor = db.cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value = (
            UUID("d37b09c2-934f-4b69-ad5f-d41f4a3d8096"),
            events.QUALIFIED_VIEW,
            {},
        )
        with patch.object(events, "connection", db), patch.object(
            events.transaction, "atomic", return_value=nullcontext()
        ):
            with self.assertRaises(RuntimeError):
                events.dispatch_one(app)
        self.assertEqual(cursor.execute.call_count, 1)
