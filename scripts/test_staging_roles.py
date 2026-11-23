"""Worker and scheduled-job roles: explicit, capability-gated, bounded."""

from pathlib import Path
import sys
import types
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services"))

from staging_runtime import roles  # noqa: E402


def settings(**kw):
    base = dict(ENVIRONMENT="staging", STAGING_CAPABILITIES=frozenset(), STAGING_PRIVILEGED=False)
    return types.SimpleNamespace(**(base | kw))


class RoleTests(unittest.TestCase):
    def test_only_the_listed_service_role_pairs_exist(self):
        self.assertEqual(set(roles.ROLES), {
            ("content", "media-worker"), ("engagement", "consumer"), ("points", "consumer"),
            ("engagement", "dispatch-events"), ("points", "deliver-audit"), ("moderation", "deliver-audit"),
            ("identity", "deliver-security-audit")})
        for service, role in (("gateway", "consumer"), ("audit", "media-worker"), ("content", "consumer"),
                              ("content", "bash"), ("points", "../x")):
            with self.subTest(service, role=role), self.assertRaises(RuntimeError):
                roles.resolve(service, role)

    def test_every_job_names_a_real_management_command(self):
        for (service, role), (_, kind, target, _) in roles.ROLES.items():
            if kind == "job":
                self.assertTrue((ROOT / "services" / service / "service/management/commands" / (target + ".py")).is_file(),
                                f"{service}/{role}")
            else:
                module = target.partition(":")[0].replace(".", "/") + ".py"
                self.assertTrue((ROOT / "services" / service / module).is_file(), f"{service}/{role}")

    def test_a_role_runs_only_with_its_approved_capability_in_staging(self):
        roles.require_capability(settings(STAGING_CAPABILITIES=frozenset({"media"})), "media")
        roles.require_capability(settings(STAGING_PRIVILEGED=True), "privileged")
        for bad in (settings(), settings(STAGING_CAPABILITIES=frozenset({"points"})),
                    settings(ENVIRONMENT="local", STAGING_CAPABILITIES=frozenset({"media"}))):
            with self.assertRaises(RuntimeError):
                roles.require_capability(bad, "media")
        with self.assertRaises(RuntimeError):
            roles.require_capability(settings(), "privileged")

    def test_job_interval_and_batch_are_bounded(self):
        for interval, limit in ((1, 100), (4, 100), (3601, 100), (30, 0), (30, 1001)):
            with self.subTest(interval, limit=limit), self.assertRaises(RuntimeError):
                roles.run_job("x", interval, limit, call=lambda *a: None, stop=lambda: True)

    def test_job_runs_repeatedly_with_the_fixed_batch_and_sleeps_the_remainder(self):
        calls, sleeps, ticks = [], [], iter(range(0, 1000, 2))
        runs = {"n": 0}

        def stop():
            runs["n"] += 1
            return runs["n"] > 3

        roles.run_job("deliver_audit_events", 30, 7, call=lambda *a: calls.append(a), sleep=sleeps.append,
                      clock=lambda: next(ticks), stop=stop)
        self.assertEqual(calls, [("deliver_audit_events", "--limit", "7")] * 3)
        self.assertEqual(sleeps, [28, 28, 28])

    def test_a_job_that_keeps_failing_exits_nonzero_without_printing_the_cause(self):
        def boom(*a):
            raise RuntimeError("database password=hunter2")

        with self.assertRaises(SystemExit) as raised:
            roles.run_job("x", 30, 10, call=boom, sleep=lambda s: None, stop=lambda: False)
        self.assertEqual(raised.exception.code, 1)

    def test_engagement_dispatch_reports_only_exception_type_names(self):
        from contextlib import redirect_stderr
        from io import StringIO

        def boom(*args):
            try:
                raise PermissionError("amqps://publisher:private-password@rabbitmq")
            except PermissionError as exc:
                raise RuntimeError("database password=private-password") from exc

        output = StringIO()
        with redirect_stderr(output), self.assertRaises(SystemExit) as raised:
            roles.run_job("dispatch_engagement_events", 30, 10, call=boom,
                          sleep=lambda value: None, stop=lambda: False)

        self.assertEqual(raised.exception.code, 1)
        text = output.getvalue()
        self.assertIn("Engagement dispatch failure type=RuntimeError cause_type=PermissionError", text)
        self.assertEqual(text.count("Engagement dispatch failure type="), roles.MAX_CONSECUTIVE_FAILURES)
        self.assertNotIn("private-password", text)
        self.assertNotIn("amqps://", text)
        self.assertNotIn("database password=", text)

    def test_a_single_failure_is_retried_and_success_resets_the_count(self):
        outcome = iter([False, True] * 4)

        def flaky(*a):
            if next(outcome):
                raise RuntimeError("x")

        runs = {"n": 0}

        def stop():
            runs["n"] += 1
            return runs["n"] > 8

        roles.run_job("x", 30, 10, call=flaky, sleep=lambda s: None, stop=stop)


if __name__ == "__main__":
    unittest.main()
