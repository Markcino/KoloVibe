import json
import os
import secrets
import tempfile
import uuid
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

import pyotp
from cryptography.fernet import Fernet
from django.test import RequestFactory, TestCase, override_settings
from django.utils import timezone

from service import accounts, events, privacy_review
from service.models import Account, AccountHold, ErasureJob, LoginSession, PrivacyRequest, SecurityEvent, TotpFactor


@override_settings(STAGING_PRIVILEGED=True, PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class PrivacyReviewTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.now = timezone.now().replace(microsecond=0)
        clock = patch("django.utils.timezone.now", return_value=self.now)
        clock.start()
        self.addCleanup(clock.stop)
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        key = Fernet.generate_key()
        path = Path(temporary.name) / "mfa-key"
        path.touch(mode=0o600)
        path.write_bytes(key)
        environment = patch.dict(os.environ, {"KOLOVIBE_MFA_ENCRYPTION_KEY_FILE": str(path)})
        environment.start()
        self.addCleanup(environment.stop)
        self.admin = Account.objects.create_user("admin@example.test", secrets.token_urlsafe(32), "Administrator")
        self.admin.role = Account.Role.ADMINISTRATOR
        self.admin.save()
        TotpFactor.objects.create(account=self.admin, encrypted_secret=Fernet(key).encrypt(
            pyotp.random_base32().encode()).decode())
        self.access = self.token(self.admin, "administrator", mfa=self.now)
        self.person = Account.objects.create_user("person@example.test", secrets.token_urlsafe(32), "Person")
        self.person_session = LoginSession.objects.create(
            account=self.person, expires_at=self.now + timedelta(days=1), refresh_digest=secrets.token_hex(32))
        self.deletion = PrivacyRequest.objects.create(account=self.person, kind="deletion")
        self.access_request = PrivacyRequest.objects.create(account=self.person, kind="access")

    def token(self, account, role, mfa=None):
        session = LoginSession.objects.create(account=account, authenticated_role=role, mfa_verified_at=mfa,
                                              expires_at=self.now + timedelta(minutes=15),
                                              refresh_digest=secrets.token_hex(32))
        return accounts._issue(session)["access_token"]

    def call(self, operation, access=None, **fields):
        response = privacy_review.administer(self.factory.post(
            "/internal/auth/privacy-review",
            json.dumps({"access_token": access or self.access, "operation": operation, **fields}),
            content_type="application/json"))
        return response.status_code, json.loads(response.content)

    def test_only_an_administrator_with_mfa_may_review(self):
        moderator = Account.objects.create_user("mod@example.test", secrets.token_urlsafe(32), "Moderator")
        moderator.role = Account.Role.MODERATOR
        moderator.save()
        for access in (self.token(moderator, "moderator", mfa=self.now), self.token(self.admin, "administrator")):
            # Identity refuses these sessions outright (401) or the role (403); never 200.
            self.assertIn(self.call("list", access)[0], {401, 403})
        stale = self.token(self.admin, "administrator", mfa=self.now - timedelta(minutes=10))
        self.assertEqual(self.call("list", stale)[0], 200, "reading needs MFA, not a fresh sign-in")
        self.assertEqual(self.call("start-review", stale, id=str(self.deletion.id))[0], 403)
        self.assertEqual(self.call("list", "not-a-token")[0], 401)
        self.assertTrue(SecurityEvent.objects.filter(kind="account.privacy_review_denied").exists(),
                        "the stale write was recorded")

    def test_invalid_shapes_are_refused_before_any_lookup(self):
        for operation, fields in [("list", {"status": "deleted"}), ("decline", {"id": str(self.deletion.id)}),
                                  ("decline", {"id": str(self.deletion.id), "decline_code": "BECAUSE"}),
                                  ("start-review", {"id": "nope"}), ("erase", {}),
                                  ("hold-place", {"account_id": str(self.person.id), "reason_code": "LEGAL_CLAIM",
                                                  "note": "x"}),
                                  ("list", {"extra": 1})]:
            with self.subTest(operation=operation, fields=fields):
                self.assertEqual(self.call(operation, **fields)[0], 400)

    def test_list_pages_newest_first_and_filters_by_status(self):
        status, page = self.call("list")
        self.assertEqual(status, 200)
        self.assertEqual({item["kind"] for item in page["items"]}, {"access", "deletion"})
        self.assertIsNone(page["next_cursor"])
        item = page["items"][0]
        self.assertEqual(set(item), {"id", "account_id", "kind", "status", "created_at", "review_started_at",
                                     "decided_at", "decline_code", "held", "erasure", "export"})
        self.assertEqual((item["erasure"], item["export"]), ([], None))
        self.assertEqual(self.call("list", status="declined")[1]["items"], [])
        self.assertEqual(self.call("list", cursor=str(uuid.uuid4()))[0], 400)

    def test_review_then_decline_with_a_fixed_code(self):
        target = str(self.access_request.id)
        self.assertEqual(self.call("decline", id=target, decline_code="WITHDRAWN")[0], 409, "review first")
        status, row = self.call("start-review", id=target)
        self.assertEqual((status, row["status"]), (200, "in_review"))
        self.assertEqual(self.call("start-review", id=target)[1]["status"], "in_review", "repeat answers the same")
        status, row = self.call("decline", id=target, decline_code="WITHDRAWN")
        self.assertEqual((status, row["status"], row["decline_code"]), (200, "declined", "WITHDRAWN"))
        self.assertEqual(self.call("decline", id=target, decline_code="WITHDRAWN")[0], 200)
        self.assertEqual(self.call("decline", id=target, decline_code="DUPLICATE_REQUEST")[0], 409)
        self.assertEqual(self.call("approve-deletion", id=target)[0], 409)
        self.person.refresh_from_db()
        self.assertTrue(self.person.is_active, "declining never deactivates")

    def test_an_access_request_cannot_be_approved_as_a_deletion_nor_the_reverse(self):
        target = str(self.access_request.id)
        self.call("start-review", id=target)
        status, body = self.call("approve-deletion", id=target)
        self.assertEqual((status, body["code"]), (409, "request_not_deletion"))
        self.call("start-review", id=str(self.deletion.id))
        status, body = self.call("approve-access", id=str(self.deletion.id))
        self.assertEqual((status, body["code"]), (409, "request_not_access"))

    def test_approving_a_deletion_deactivates_and_revokes_but_never_claims_completion(self):
        target = str(self.deletion.id)
        self.assertEqual(self.call("approve-deletion", id=target)[0], 409, "review first")
        self.call("start-review", id=target)
        status, row = self.call("approve-deletion", id=target)
        self.assertEqual((status, row["status"]), (200, "processing"))
        self.assertEqual(row["erasure"], [{"service": service, "confirmed": False, "retained": []}
                                          for service in events.ERASURE_SERVICES])
        ErasureJob.objects.filter(request=self.deletion, service="creators").update(
            confirmed_at=timezone.now(), counts={"profile": 1}, retained=["measures"])
        listed = next(item for item in self.call("list", status="processing")[1]["items"] if item["id"] == target)
        self.assertIn({"service": "creators", "confirmed": True, "retained": ["measures"]}, listed["erasure"])
        self.assertNotIn("counts", listed["erasure"][1])
        self.person.refresh_from_db()
        self.assertFalse(self.person.is_active)
        self.assertFalse(LoginSession.objects.filter(account=self.person, revoked_at__isnull=True).exists())
        self.assertEqual(self.call("approve-deletion", id=target)[1]["status"], "processing")
        self.assertEqual(SecurityEvent.objects.filter(kind="account.deactivated", actor_id=self.person.id).count(), 1)
        self.assertFalse(PrivacyRequest.objects.filter(status="completed").exists())
        # The person can no longer use the app: the old access token stops working.
        person_access = accounts._issue(self.person_session)["access_token"]
        self.assertIsNone(accounts._session_for_access(person_access))

    def test_a_hold_blocks_approval_until_released(self):
        target = str(self.deletion.id)
        self.call("start-review", id=target)
        status, hold = self.call("hold-place", account_id=str(self.person.id), reason_code="LEGAL_CLAIM",
                                 note="Open dispute about uploaded content")
        self.assertEqual(status, 201)
        self.assertEqual(self.call("hold-place", account_id=str(self.person.id), reason_code="LEGAL_CLAIM",
                                   note="Again")[1]["id"], hold["id"], "one open hold per reason")
        self.assertTrue(self.call("list")[1]["items"][0]["held"])
        status, body = self.call("approve-deletion", id=target)
        self.assertEqual((status, body["code"]), (409, "account_on_hold"))
        self.person.refresh_from_db()
        self.assertTrue(self.person.is_active)
        self.assertEqual(self.call("holds", account_id=str(self.person.id))[1]["items"][0]["id"], hold["id"])
        status, released = self.call("hold-release", id=hold["id"])
        self.assertEqual(status, 200)
        self.assertIsNotNone(released["released_at"])
        self.assertEqual(self.call("approve-deletion", id=target)[1]["status"], "processing")
        self.assertEqual(self.call("holds", account_id=str(uuid.uuid4()))[0], 404)

    def test_an_administrator_cannot_approve_their_own_deletion(self):
        own = PrivacyRequest.objects.create(account=self.admin, kind="deletion")
        self.call("start-review", id=str(own.id))
        self.assertEqual(self.call("approve-deletion", id=str(own.id))[1]["code"], "own_account")

    def test_a_processing_request_still_counts_as_open(self):
        self.call("start-review", id=str(self.access_request.id))
        PrivacyRequest.objects.filter(pk=self.access_request.pk).update(status="processing")
        self.assertTrue(PrivacyRequest.objects.filter(account=self.person, kind="access",
                                                      status__in=PrivacyRequest.OPEN).exists())
        from django.db import IntegrityError, transaction
        with self.assertRaises(IntegrityError), transaction.atomic():
            PrivacyRequest.objects.create(account=self.person, kind="access")

    def test_holds_need_a_known_account_and_a_declined_request_needs_a_code(self):
        self.assertEqual(self.call("hold-place", account_id=str(uuid.uuid4()), reason_code="LEGAL_CLAIM",
                                   note="Unknown account")[0], 404)
        from django.db import IntegrityError, transaction
        with self.assertRaises(IntegrityError), transaction.atomic():
            PrivacyRequest.objects.filter(pk=self.deletion.pk).update(status="declined")
        self.assertEqual(AccountHold.objects.count(), 0)
