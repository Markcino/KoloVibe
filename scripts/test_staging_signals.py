"""Health-signal emission and its job wiring, without Django or a database (#145)."""
import json
import sys
import unittest
from io import StringIO
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services"))
from staging_runtime import roles, signals  # noqa: E402


def emitted(names, measure, environ=None):
    out, err = StringIO(), StringIO()
    signals.emit("points", names, measure=measure, environ=environ or {}, out=out, err=err)
    return [json.loads(line.removeprefix("KOLOVIBE_SIGNAL ")) for line in out.getvalue().splitlines()], err.getvalue()


class SignalTests(unittest.TestCase):
    def test_without_an_approved_threshold_the_value_is_reported_and_nothing_alerts(self):
        records, err = emitted(["audit_backlog"], {"audit_backlog": lambda: {"pending": 11, "oldest_age_seconds": 86400,
                                                                            "max_attempts": 40}})
        self.assertEqual(records, [{"signal": "audit_backlog", "service": "points", "pending": 11,
                                    "oldest_age_seconds": 86400, "max_attempts": 40, "available": True,
                                    "thresholds": {}, "alert": None}])
        self.assertEqual(err, "")

    def test_each_approved_threshold_is_compared_and_a_breach_is_repeated_on_stderr(self):
        measure = {"audit_backlog": lambda: {"pending": 11, "oldest_age_seconds": 120, "max_attempts": 1}}
        for environ, alert in (({"KOLOVIBE_ALERT_AUDIT_MAX_PENDING": "10"}, True),
                               ({"KOLOVIBE_ALERT_AUDIT_MAX_PENDING": "11"}, False),
                               ({"KOLOVIBE_ALERT_AUDIT_MAX_AGE_SECONDS": "60"}, True),
                               ({"KOLOVIBE_ALERT_AUDIT_MAX_AGE_SECONDS": "600",
                                 "KOLOVIBE_ALERT_AUDIT_MAX_PENDING": "100"}, False)):
            with self.subTest(environ):
                records, err = emitted(["audit_backlog"], measure, environ)
                self.assertIs(records[0]["alert"], alert)
                self.assertEqual(err.startswith("KOLOVIBE_ALERT "), alert)

    def test_an_empty_backlog_has_no_age_and_never_breaches_an_age_threshold(self):
        records, _ = emitted(["audit_backlog"], {"audit_backlog": lambda: {"pending": 0, "oldest_age_seconds": None,
                                                                          "max_attempts": 0}},
                             {"KOLOVIBE_ALERT_AUDIT_MAX_AGE_SECONDS": "0"})
        self.assertIs(records[0]["alert"], False)

    def test_there_are_no_default_thresholds_and_a_malformed_one_is_refused(self):
        for name in signals.THRESHOLDS:
            self.assertEqual(signals.approved_thresholds(name, {}), {})
        for value in ("-1", "5m", "1.5", " 3"):
            with self.subTest(value), self.assertRaises(RuntimeError):
                signals.approved_thresholds("queue_depth", {"KOLOVIBE_ALERT_QUEUE_MAX_DEPTH": value})

    def test_an_unmeasurable_signal_says_so_without_the_cause(self):
        def boom():
            raise RuntimeError("amqps://user:pw@broker")  # pragma: allowlist secret

        records, err = emitted(["queue_depth"], {"queue_depth": boom}, {"KOLOVIBE_ALERT_QUEUE_MAX_DEPTH": "0"})
        self.assertEqual(records, [{"signal": "queue_depth", "service": "points", "available": False, "alert": None}])
        self.assertEqual(err, "")


class JobWiringTests(unittest.TestCase):
    def test_every_audit_delivery_job_reports_its_backlog_and_only_listed_roles_emit(self):
        self.assertTrue(set(roles.ROLE_SIGNALS) <= set(roles.ROLES))
        for (service, role), (_, kind, target, _) in roles.ROLES.items():
            if target in ("deliver_audit_events", "deliver_security_audit"):
                self.assertIn("audit_backlog", roles.signals_for(service, role), (service, role))
        self.assertEqual(roles.signals_for("content", "requeue-media"), ("media_stalled", "queue_depth"))
        self.assertEqual(roles.signals_for("content", "media-worker"), ())
        for names in roles.ROLE_SIGNALS.values():
            self.assertTrue(set(names) <= set(signals.SIGNALS))

    def test_signals_follow_every_batch_including_failures_and_the_final_exit(self):
        emits, outcome = [], iter([None, RuntimeError("x")] + [RuntimeError("x")] * 5)

        def call(*a):
            result = next(outcome)
            if result:
                raise result

        with self.assertRaises(SystemExit):
            roles.run_job("deliver_audit_events", 30, 10, call=call, sleep=lambda s: None, stop=lambda: False,
                          signals=("audit_backlog",), service="points", emit=lambda *a: emits.append(a))
        self.assertEqual(emits, [("points", ("audit_backlog",))] * 6)

    def test_a_malformed_threshold_stops_the_job_before_its_first_batch(self):
        import os
        from unittest.mock import patch

        calls = []
        with patch.dict(os.environ, {"KOLOVIBE_ALERT_AUDIT_MAX_PENDING": "lots"}), self.assertRaises(RuntimeError):
            roles.run_job("deliver_audit_events", 30, 10, call=lambda *a: calls.append(a), stop=lambda: False,
                          signals=("audit_backlog",), service="points", emit=lambda *a: None)
        self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()
