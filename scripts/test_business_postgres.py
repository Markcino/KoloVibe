"""Business concurrency and constraint behaviour on a disposable, TLS-only PostgreSQL.

Reuses the foundations fixture (migrations under the service's own least-privilege role). Run as an unprivileged
OS user with PostgreSQL tools on PATH, as in CI.  SQLite cannot show row-lock or unique-index races; this can.
"""
import json
import os
import subprocess
import sys
import threading
import unittest
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


def tests():
    sys.path.insert(0, str(ROOT / "services" / "business"))
    os.environ["DJANGO_SETTINGS_MODULE"] = "service.settings"
    import django
    django.setup()
    from django.db import IntegrityError, connection, transaction
    from django.test import RequestFactory
    from service import limits
    from service.api import dispatch
    from service.models import Business, BusinessMembership, RegistrationGrant

    def call(operation, data, actor, key, role="viewer"):
        body = {"actor_id": str(actor), "role": role, "mfa_verified": False, "email_verified": True,
                "idempotency_key": key, "data": data}
        request = RequestFactory().post("/internal/business/" + operation, json.dumps(body), content_type="application/json")
        request.service_caller = "gateway"
        response = dispatch(request, operation)
        connection.close()
        return response.status_code, json.loads(response.content)

    def parallel(jobs):
        results = [None] * len(jobs)

        def run(index, job):
            results[index] = job()
        threads = [threading.Thread(target=run, args=(i, job)) for i, job in enumerate(jobs)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(30)
        return results

    class BusinessPostgres(unittest.TestCase):
        def test_runs_on_postgresql_with_the_service_schema(self):
            with connection.cursor() as cursor:
                cursor.execute("SELECT current_schema()")
                self.assertEqual(connection.vendor, "postgresql")
                self.assertEqual(cursor.fetchone()[0], "business")

        def test_concurrent_identical_registrations_create_one_business(self):
            account = uuid4()
            RegistrationGrant.objects.create(account_id=account, granted_by_account_id=uuid4())
            data = {"display_name": "Race Foods", "legal_name": "Race Foods Ltd"}
            results = parallel([lambda: call("register", data, account, "same-key-0123456789")] * 5)  # five attempts fit the daily registration budget
            self.assertEqual({status for status, _ in results}, {201})
            self.assertEqual(len({body["id"] for _, body in results}), 1)
            self.assertEqual(Business.objects.filter(created_by_account_id=account).count(), 1)
            self.assertEqual(BusinessMembership.objects.filter(account_id=account, role="owner").count(), 1)

        def test_concurrent_distinct_registrations_cannot_exceed_the_account_cap(self):
            account = uuid4()
            RegistrationGrant.objects.create(account_id=account, granted_by_account_id=uuid4())
            jobs = [(lambda i=i: call("register", {"display_name": f"Shop {i}", "legal_name": f"Shop {i} Ltd"},
                                      account, f"distinct-key-{i:08d}")) for i in range(limits.MAX_BUSINESSES_PER_ACCOUNT + 2)]
            results = parallel(jobs)
            created = [r for r in results if r[0] == 201]
            self.assertEqual(len(created), limits.MAX_BUSINESSES_PER_ACCOUNT)
            self.assertEqual(Business.objects.filter(created_by_account_id=account).count(),
                             limits.MAX_BUSINESSES_PER_ACCOUNT)

        def test_one_code_is_redeemed_at_most_once_under_concurrency(self):
            owner = uuid4()
            RegistrationGrant.objects.create(account_id=owner, granted_by_account_id=uuid4())
            _, business = call("register", {"display_name": "Code Shop", "legal_name": "Code Shop Ltd"}, owner, "owner-key-0123456789")
            _, invitation = call("staff_invite", {"business_id": business["id"], "label": "Till"}, owner, "invite-key-0123456789")
            jobs = [(lambda i=i: call("staff_redeem", {"code": invitation["code"]}, uuid4(), f"redeem-key-{i:08d}x")) for i in range(6)]
            results = parallel(jobs)
            self.assertEqual(sorted(status for status, _ in results), [200] + [404] * 5)
            self.assertEqual(BusinessMembership.objects.filter(business_id=business["id"], role="staff").count(), 1)

        def test_the_database_refuses_a_second_active_membership_and_a_bad_role(self):
            owner = uuid4()
            RegistrationGrant.objects.create(account_id=owner, granted_by_account_id=uuid4())
            _, business = call("register", {"display_name": "Dup Shop", "legal_name": "Dup Shop Ltd"}, owner, "dup-key-01234567890")
            with self.assertRaises(IntegrityError), transaction.atomic():
                BusinessMembership.objects.create(business_id=business["id"], account_id=owner, role="staff",
                                                  granted_by_account_id=owner)
            with self.assertRaises(IntegrityError), transaction.atomic():
                BusinessMembership.objects.create(business_id=business["id"], account_id=uuid4(), role="admin",
                                                  granted_by_account_id=owner)

    suite = unittest.defaultTestLoader.loadTestsFromTestCase(BusinessPostgres)
    sys.exit(0 if unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful() else 1)


def main():
    from test_postgres_foundations import postgres_fixture
    with postgres_fixture() as (_, environments):
        subprocess.run([sys.executable, str(Path(__file__).resolve()), "--run"], check=True, env=environments["business"])


if __name__ == "__main__":
    tests() if "--run" in sys.argv else main()
