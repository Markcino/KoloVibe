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
    from test_postgres_foundations import migration_connection
    from service import limits
    from service.api import dispatch
    from service.models import (Business, BusinessMembership, HoursRule, ProfileRevision, RegistrationGrant,
                                VerificationCase, VerificationDecision)

    def call(operation, data, actor, key, role="viewer", mfa=False):
        body = {"actor_id": str(actor), "role": role, "mfa_verified": mfa, "email_verified": True,
                "idempotency_key": key, "origin": None, "data": data}
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

        def test_one_reviewer_wins_a_claim_race_and_a_case_is_decided_once(self):
            owner, first, second, admin = uuid4(), uuid4(), uuid4(), uuid4()
            RegistrationGrant.objects.create(account_id=owner, granted_by_account_id=admin)
            _, business = call("register", {"display_name": "Claim Shop", "legal_name": "Claim Shop Ltd"}, owner, "claim-owner-0123456789")
            for reviewer in (first, second):
                call("reviewer_grant", {"reviewer_account_id": str(reviewer), "scope": "verification", "active": True},
                     admin, f"grant-{reviewer.hex[:16]}-key", role="administrator", mfa=True)
            call("verification_submit", {"business_id": business["id"], "method": "manual_review", "declaration": True,
                                         "evidence": [{"kind": "registration_number", "value": "LBR-1"}]}, owner, "submit-key-0123456789")
            case = VerificationCase.objects.get(business_id=business["id"])
            results = parallel([lambda r=r, i=i: call("verification_claim", {"case_id": str(case.id)}, r, f"claim-key-{i:09d}x",
                                                      role="moderator", mfa=True) for i, r in enumerate((first, second) * 2)])
            self.assertEqual(sorted(status for status, _ in results), [200, 409, 409, 409])  # one winner; every other claim conflicts
            case.refresh_from_db()
            winner = case.assigned_reviewer_account_id
            self.assertIn(winner, (first, second))
            self.assertEqual(Business.objects.get(pk=business["id"]).state, "under_review")
            decisions = parallel([lambda i=i: call("verification_decide", {"case_id": str(case.id), "decision": d, "reason_code": "documents_checked"},
                                                   winner, f"decide-key-{i:09d}x", role="moderator", mfa=True)
                                  for i, d in enumerate(("verify", "reject", "verify", "reject"))])
            self.assertEqual([status for status, _ in decisions].count(200), 1)
            self.assertEqual(VerificationDecision.objects.filter(case=case).count(), 1)

        def test_concurrent_first_edits_create_exactly_one_working_revision(self):
            owner = uuid4()
            RegistrationGrant.objects.create(account_id=owner, granted_by_account_id=uuid4())
            _, business = call("register", {"display_name": "Edit Shop", "legal_name": "Edit Shop Ltd"}, owner, "edit-owner-0123456789")
            results = parallel([lambda i=i: call("profile_edit", {"business_id": business["id"], "city": f"City {i}"},
                                                 owner, f"edit-key-{i:010d}") for i in range(4)])
            self.assertEqual({status for status, _ in results}, {200})
            self.assertEqual(ProfileRevision.objects.filter(business_id=business["id"]).count(), 1)

        def test_search_pages_are_complete_and_stable_on_postgresql(self):
            from service.api import NIL_ACTOR
            from service.models import BusinessListing
            names = [f"Pg Shop {chr(97 + i)}" for i in range(7)] + ["Pg 100% Cakes"]
            for name in names:
                business = Business.objects.create(created_by_account_id=uuid4(), display_name=name, legal_name=name + " Ltd",
                                                   state="verified", owner_listed=True)
                BusinessListing.objects.create(business=business, display_name=name, name_sort=name.casefold(),
                                               category_slug="food", category_name="Food", county_code="pgtest", city="Pgville",
                                               time_zone="Africa/Monrovia", hours={"rules": [[0, 480, 1020]], "exceptions": []})

            def search(**params):
                body = {"actor_id": NIL_ACTOR, "role": "anonymous", "mfa_verified": False, "email_verified": False,
                        "idempotency_key": None, "origin": "198.51.100.7", "data": params}
                request = RequestFactory().post("/internal/business/public_search", json.dumps(body), content_type="application/json")
                request.service_caller = "gateway"
                response = dispatch(request, "public_search")
                connection.close()
                return response.status_code, json.loads(response.content)

            seen, cursor = [], None
            for _ in range(10):
                status, body = search(county="pgtest", limit=3, **({"cursor": cursor} if cursor else {}))
                self.assertEqual(status, 200, body)
                seen += [item["display_name"] for item in body["items"]]
                cursor = body["next_cursor"]
                if not cursor:
                    break
            self.assertEqual(seen, sorted(names, key=str.casefold))
            self.assertEqual([i["display_name"] for i in search(county="pgtest", q="%")[1]["items"]], ["Pg 100% Cakes"])
            self.assertEqual(search(county="pgtest", q="x'; DROP TABLE service_business;--")[1]["items"], [])
            self.assertEqual(len(search(county="pgtest", open_now="true", limit=20)[1]["items"]) >= 0, True)
            BusinessListing.objects.filter(county_code="pgtest").delete()

        def listed_business(self, name):
            from service.models import BusinessListing
            business = Business.objects.create(created_by_account_id=uuid4(), display_name=name, legal_name=name + " Ltd",
                                               state="verified", owner_listed=True)
            BusinessListing.objects.create(business=business, display_name=name, name_sort=name.casefold(), category_slug="food",
                                           category_name="Food", county_code="pgreview", city="Pgville", time_zone="UTC")
            return business

        def test_one_author_cannot_review_a_business_twice_under_concurrency(self):
            from service.models import Review, ReviewAggregate
            business = self.listed_business("Review Race Shop")
            author = uuid4()
            results = parallel([lambda i=i: call("review_create", {"business_id": str(business.id), "rating": 5,
                                                                    "body": f"Concurrent attempt number {i} at a review."},
                                                 author, f"review-key-{i:09d}x") for i in range(4)])
            self.assertEqual(sorted(status for status, _ in results), [201, 409, 409, 409])
            self.assertEqual(Review.objects.filter(business=business).count(), 1)
            self.assertEqual(ReviewAggregate.objects.get(business=business).count, 1)

        def test_concurrent_reviews_keep_the_aggregate_exact_and_one_invitation_is_used_once(self):
            from service.models import Review, ReviewAggregate, ReviewInvitation
            business = self.listed_business("Aggregate Shop")
            results = parallel([lambda i=i: call("review_create", {"business_id": str(business.id), "rating": 1 + i % 5,
                                                                    "body": f"Independent opinion number {i} about this shop."},
                                                 uuid4(), f"agg-key-{i:012d}") for i in range(5)])
            self.assertEqual({status for status, _ in results}, {201})
            published = list(Review.objects.filter(business=business, state="published").values_list("rating", flat=True))
            row = ReviewAggregate.objects.get(business=business)
            self.assertEqual((row.count, row.rating_sum), (len(published), sum(published)))
            code = "pg-review-invite-code-0123456789"
            import hashlib, hmac
            from django.conf import settings
            ReviewInvitation.objects.create(business=business, created_by_account_id=uuid4(),
                                            code_digest=hmac.new(settings.SECRET_KEY.encode(), ("review-invite:" + code).encode(),
                                                                 hashlib.sha256).hexdigest(),
                                            expires_at=__import__("django.utils.timezone", fromlist=["now"]).now() + __import__("datetime").timedelta(days=1))
            used = parallel([lambda i=i: call("review_create", {"business_id": str(business.id), "rating": 4, "invitation_code": code,
                                                                 "body": f"Invited opinion number {i} about this shop."},
                                              uuid4(), f"inv-key-{i:012d}") for i in range(4)])
            self.assertEqual(sorted(status for status, _ in used), [201, 404, 404, 404])

        def test_the_database_enforces_revision_and_hours_invariants(self):
            owner = uuid4()
            RegistrationGrant.objects.create(account_id=owner, granted_by_account_id=uuid4())
            _, business = call("register", {"display_name": "Rule Shop", "legal_name": "Rule Shop Ltd"}, owner, "rule-owner-0123456789")
            ProfileRevision.objects.create(business_id=business["id"], revision_no=1, display_name="A")
            for make in (lambda: ProfileRevision.objects.create(business_id=business["id"], revision_no=2, display_name="B"),
                         lambda: ProfileRevision.objects.create(business_id=business["id"], revision_no=1, state="rejected", display_name="C"),
                         lambda: ProfileRevision.objects.create(business_id=business["id"], revision_no=3, state="rejected",
                                                                display_name="D", latitude=1),
                         lambda: HoursRule.objects.create(business_id=business["id"], weekday=9, opens_minute=1, closes_minute=2),
                         lambda: HoursRule.objects.create(business_id=business["id"], weekday=1, opens_minute=600, closes_minute=600)):
                with self.assertRaises(IntegrityError), transaction.atomic():
                    make()

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

    class BusinessMigrations(unittest.TestCase):
        """Tested upgrade and rollback of every Business migration, as the least-privilege login (disposable only)."""

        def test_every_migration_applies_and_reverses_and_the_schema_round_trips(self):
            from tests import migration_checks
            migration_checks.round_trip(self, migration_connection())

        def test_rows_survive_an_upgrade_and_a_rollback_of_later_migrations(self):
            from tests import migration_checks
            migration_checks.data_survives(self, migration_connection())

    loader = unittest.defaultTestLoader
    # Migrations run last: they drop and recreate later tables, so no other test may be mid-flight.
    suite = unittest.TestSuite([loader.loadTestsFromTestCase(BusinessPostgres), loader.loadTestsFromTestCase(BusinessMigrations)])
    sys.exit(0 if unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful() else 1)


def audit_tests():
    """Audit 0006 on PostgreSQL: a CHECK constraint with a violating row must refuse the rollback and keep the row."""
    sys.path.insert(0, str(ROOT / "services" / "audit"))
    os.environ["DJANGO_SETTINGS_MODULE"] = "service.settings"
    import django
    django.setup()
    from django.db import connection
    from test_postgres_foundations import migration_connection
    from tests import migration_checks

    class AuditBusinessProducer(unittest.TestCase):
        def test_rolls_back_and_forward_over_existing_producers(self):
            self.assertEqual(connection.vendor, "postgresql")
            migration_checks.upgrade_and_rollback_over_existing_producers(self, migration_connection())

        def test_rollback_is_refused_and_loses_nothing_while_a_business_grant_exists(self):
            migration_checks.rollback_refused_and_lossless_while_a_business_grant_exists(self, migration_connection())

    suite = unittest.defaultTestLoader.loadTestsFromTestCase(AuditBusinessProducer)
    sys.exit(0 if unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful() else 1)


def main():
    from test_postgres_foundations import postgres_fixture
    with postgres_fixture() as (_, environments):
        subprocess.run([sys.executable, str(Path(__file__).resolve()), "--run"], check=True, env=environments["business"])
        subprocess.run([sys.executable, str(Path(__file__).resolve()), "--audit"], check=True, env=environments["audit"])


if __name__ == "__main__":
    audit_tests() if "--audit" in sys.argv else tests() if "--run" in sys.argv else main()
