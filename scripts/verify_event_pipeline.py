"""Engagement outbox -> broker message -> Points inbox -> receipt -> append-only ledger, across the real services.

Runs the real Engagement and Points code in separate processes against the disposable TLS PostgreSQL used by CI, one
database role per service, exchanging only JSON exactly as Celery would carry it (scripts/event_pipeline_steps.py).
The broker itself is replaced by a recording publisher: the message, exchange, routing key and no-declare flags are
asserted, but RabbitMQ permission behaviour is NOT exercised here and remains an owner staging check.

Run from the repository root with PostgreSQL tools on PATH:  python scripts/verify_event_pipeline.py
"""

import json
from pathlib import Path
import subprocess
import sys
import unittest
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_postgres_foundations import postgres_fixture  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
STEPS = ROOT / "scripts" / "event_pipeline_steps.py"
QUALIFIED_VIEW = "dec003.qualified_view"


class EventPipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.context = postgres_fixture()
        cls.base, cls.environments = cls.context.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.context.__exit__(None, None, None)

    def step(self, service, name, **arguments):
        result = subprocess.run([sys.executable, str(STEPS), service, name, json.dumps(arguments)],
                                env=dict(self.environments[service]), capture_output=True, text=True, timeout=120)
        self.assertEqual(result.returncode, 0, result.stderr[-1500:])
        line = next(line for line in result.stdout.splitlines() if line.startswith("RESULT "))
        return json.loads(line[len("RESULT "):])

    def publish(self, count, creator=None, **dispatch):
        created = self.step("engagement", "qualify", count=count, **({"creator": creator} if creator else {}))
        self.assertEqual(created["unpublished"], count)
        sent = self.step("engagement", "dispatch", **dispatch)
        return created["creators"], sent

    def state(self, creators):
        return self.step("points", "state", creators=creators)

    # --- the boundary contract -------------------------------------------------------------------

    def test_a_qualified_view_travels_from_the_outbox_to_exactly_one_ledger_entry(self):
        creators, sent = self.publish(1)
        self.assertEqual(len(sent["messages"]), 1)
        message = sent["messages"][0]
        # Verified routing: the pre-provisioned Points exchange and key, nothing declared or bound by Engagement.
        self.assertEqual(message["name"], "kolovibe.points.event")
        self.assertEqual((message["exchange"], message["routing_key"]), ("kolovibe.points", "kolovibe.points"))
        self.assertEqual((message["queue"], message["queue_exchange"]), ("kolovibe.points", "kolovibe.points"))
        self.assertIs(message["queue_no_declare"], True)
        self.assertIs(message["exchange_no_declare"], True)
        self.assertEqual(message["delivery_mode"], 2)
        event_id, event_type, payload = message["args"]
        self.assertEqual((event_id, event_type), (message["task_id"], QUALIFIED_VIEW))
        self.assertEqual(set(payload), {"creator_user_id", "qualified_at"})
        self.assertEqual(payload["creator_user_id"], creators[0])
        uuid.UUID(event_id)
        self.assertEqual(self.step("points", "consume", messages=sent["messages"])["applied"], 1)
        state = self.state(creators)
        self.assertEqual((state["entries"], state["balance"]), (1, 1))
        self.assertEqual(state["receipts"], {"pending": 0, "posted": 1, "withheld": 0})
        self.assertEqual(state["audit"]["points.awarded"] >= 1, True)

    def test_a_broker_interruption_keeps_the_event_and_the_retry_delivers_it_once(self):
        creators, sent = self.publish(2, fail_times=1)
        self.assertEqual(sent["failures"], 1, "the first publish attempt failed")
        self.assertEqual(len(sent["messages"]), 2, "after recovery every event was published")
        self.assertEqual(self.step("points", "consume", messages=sent["messages"])["applied"], 2)
        self.assertEqual(self.state(creators)["entries"], 2)

    # --- at-least-once delivery, exactly-once effect ----------------------------------------------

    def test_duplicate_deliveries_have_one_business_effect(self):
        creators, sent = self.publish(1)
        outcome = self.step("points", "consume", messages=sent["messages"], times=4)
        self.assertEqual((outcome["applied"], outcome["results"], outcome["errors"]), (1, 4, []))
        state = self.state(creators)
        self.assertEqual((state["entries"], state["inbox"] >= 1), (1, True))
        self.assertEqual(state["receipts"], {"pending": 0, "posted": 1, "withheld": 0})

    def test_concurrent_redelivery_from_several_workers_has_one_business_effect(self):
        creators, sent = self.publish(1)
        outcome = self.step("points", "consume", messages=sent["messages"], times=6, concurrent=True)
        self.assertEqual(outcome["errors"], [])
        self.assertEqual(outcome["applied"], 1)
        self.assertEqual(self.state(creators)["entries"], 1)

    def test_a_worker_killed_before_posting_is_recovered_by_redelivery(self):
        creators, sent = self.publish(1)
        recovery = self.step("points", "crash_then_recover", message=sent["messages"][0])
        self.assertTrue(recovery["crashed"])
        self.assertEqual(recovery["during"], {"receipt": "pending", "entries": 0}, "an honest pending record, no award")
        self.assertTrue(recovery["applied_on_redelivery"])
        self.assertEqual(recovery["after"], {"receipt": "posted", "entries": 1})
        self.assertEqual(self.state(creators)["balance"], 1)

    # --- withheld awards and the daily limit ------------------------------------------------------

    def test_the_daily_cap_withholds_without_posting_and_replays_change_nothing(self):
        creator = str(uuid.uuid4())
        self.step("points", "seed_cap", creator=creator, awards=99)
        creators, sent = self.publish(3, creator=creator)
        self.assertEqual(self.step("points", "consume", messages=sent["messages"])["applied"], 1)
        state = self.state([creator])
        self.assertEqual((state["entries"], state["balance"], state["awards_today"]), (1, 1, 100))
        self.assertEqual(state["receipts"], {"pending": 0, "posted": 1, "withheld": 2})
        self.step("points", "consume", messages=sent["messages"], times=2)
        self.assertEqual(self.state([creator]), state, "replays of posted and withheld events change nothing")

    # --- audit evidence delivery ------------------------------------------------------------------

    def test_audit_evidence_is_retained_on_failure_and_delivered_without_identifiers(self):
        creators, sent = self.publish(1)
        self.step("points", "consume", messages=sent["messages"])
        failed = self.step("points", "deliver_audit", fail_first=1000)
        self.assertEqual(failed["outcome"], "retry")
        self.assertEqual(failed["sent"], [])
        self.assertGreater(self.state(creators)["deliveries_pending"], 0, "evidence retained for retry")
        self.step("points", "make_available")
        delivered = self.step("points", "deliver_audit")
        self.assertEqual(delivered["outcome"], "ok")
        self.assertTrue(delivered["sent"])
        for item in delivered["sent"]:
            self.assertEqual((item["audience"], item["path"]), ("audit", "/internal/security-events"))
            self.assertEqual(set(item["payload"]), {"id", "actor_id", "kind", "occurred_at", "subject_type", "subject_id"})
            self.assertIn(item["payload"]["kind"], {"points.awarded", "points.withheld"})
            self.assertNotIn(creators[0], json.dumps(item["payload"]), "evidence carries no creator identifier")
        self.assertEqual(self.state(creators)["deliveries_pending"], 0)

    # --- the append-only ledger and reversal rules the schema enforces ------------------------------

    def test_the_ledger_is_append_only_and_reversals_are_constrained(self):
        rules = self.step("points", "ledger_rules")
        outcomes = rules["outcomes"]
        for rejected in ("positive_reversal", "reversal_without_target", "zero_delta", "second_reversal_of_same_award",
                         "update_entry", "delete_entry", "orm_save_existing"):
            self.assertNotEqual(outcomes[rejected], "accepted", f"{rejected} must be refused")
        self.assertEqual(outcomes["valid_reversal"], "accepted", "a negative reversal of an award is representable")
        self.assertEqual(rules["balance"], 0, "award plus its single reversal; nothing else changed the ledger")


if __name__ == "__main__":
    unittest.main()
