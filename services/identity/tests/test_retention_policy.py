"""An owner-approved retention policy decides which retained evidence a completed erasure may keep (ADR-020)."""
import json
import os
import uuid
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.test import SimpleTestCase, TestCase, override_settings

from service import erasure, events, retention_policy
from service.models import PrivacyRequest
from . import test_erasure

# A clearly labelled SANDBOX fixture for tests only. It is not a retention decision, and the loader refuses it outside
# local development and tests.
SANDBOX = {"policy_id": "SANDBOX-TEST-ONLY", "status": "sandbox", "approved_by": "test fixture",
           "approved_on": "2026-11-27", "reference": "tests only; not an owner decision",
           "compatible": {"creators": ["appeals", "audit_events"], "moderation": ["appeals"]}}


class PolicyFileTests(SimpleTestCase):
    def parse(self, policy, environment="local"):
        return retention_policy.parse(json.dumps(policy), environment=environment)

    def test_a_valid_policy_names_only_each_services_own_evidence(self):
        self.assertEqual(self.parse(SANDBOX)["compatible"]["creators"], frozenset({"appeals", "audit_events"}))
        for bad in (SANDBOX | {"extra": 1}, SANDBOX | {"status": "draft"}, SANDBOX | {"policy_id": "has space"},
                    SANDBOX | {"approved_on": "27 Nov"}, SANDBOX | {"approved_by": " "},
                    SANDBOX | {"compatible": {"identity": ["audit_events"]}},
                    SANDBOX | {"compatible": {"creators": ["apeals"]}},
                    SANDBOX | {"compatible": {"business": ["business_ownership"]}},
                    SANDBOX | {"compatible": {"content": ["untracked_media"]}},
                    SANDBOX | {"compatible": {"creators": ["appeals", "appeals"]}},
                    SANDBOX | {"compatible": ["creators"]}):
            with self.subTest(bad), self.assertRaises(retention_policy.InvalidPolicy):
                self.parse(bad)
        with self.assertRaises(retention_policy.InvalidPolicy):
            retention_policy.parse("{", environment="local")

    def test_a_sandbox_policy_is_refused_on_staging_and_an_approved_one_is_accepted(self):
        with self.assertRaises(retention_policy.InvalidPolicy):
            self.parse(SANDBOX, environment="staging")
        self.assertEqual(self.parse(SANDBOX | {"status": "approved"}, environment="staging")["policy_id"],
                         "SANDBOX-TEST-ONLY")

    def test_nothing_configured_or_a_broken_file_means_nothing_is_compatible(self):
        with patch.dict(os.environ, {"KOLOVIBE_ERASURE_RETENTION_POLICY_FILE": ""}):
            self.assertEqual(retention_policy.current(), retention_policy.EMPTY)
        with TemporaryDirectory() as directory, self.assertLogs("service.retention_policy", "ERROR"):
            path = Path(directory) / "policy.json"
            path.write_text(json.dumps(SANDBOX | {"compatible": {"creators": ["nope"]}}))
            with patch.dict(os.environ, {"KOLOVIBE_ERASURE_RETENTION_POLICY_FILE": str(path)}):
                self.assertEqual(retention_policy.current(), retention_policy.EMPTY)

    def test_unfinished_work_always_blocks_and_unknown_categories_block(self):
        policy = {"policy_id": "p", "compatible": {"business": frozenset({"reviews"}),
                                                   "content": frozenset({"attestations"})}}
        self.assertEqual(retention_policy.blocking("business", ["reviews", "business_ownership"], policy),
                         ["business_ownership"])
        self.assertEqual(retention_policy.blocking("content", ["attestations", "untracked_media", "new_kind"], policy),
                         ["untracked_media", "new_kind"])
        self.assertEqual(retention_policy.blocking("creators", ["appeals"], retention_policy.EMPTY), ["appeals"])


@override_settings(STAGING_PRIVILEGED=True, PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class PolicyCompletionTests(TestCase):
    _base = test_erasure.ErasureTests
    setUp, token, call = _base.setUp, _base.token, _base.call
    approve, confirmation = _base.approve, _base.confirmation

    def with_policy(self, policy):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / "policy.json"
        path.write_text(json.dumps(policy))
        self.enterContext(patch.dict(os.environ, {"KOLOVIBE_ERASURE_RETENTION_POLICY_FILE": str(path)}))

    def confirm_each(self, retained):
        for service in events.ERASURE_SERVICES:
            extra = {"creator_id": None} if service == "creators" else {}
            erasure.confirm(str(uuid.uuid4()), self.confirmation(service=service, counts={"rows": 1},
                                                                 retained=retained.get(service, []), **extra))

    def test_approved_evidence_completes_the_request_and_records_the_policy(self):
        self.with_policy(SANDBOX)
        self.approve()
        self.confirm_each({"creators": ["appeals", "audit_events"], "moderation": ["appeals"]})
        self.deletion.refresh_from_db()
        self.assertEqual((self.deletion.status, self.deletion.completed_under_policy), ("completed", "SANDBOX-TEST-ONLY"))
        self.person.refresh_from_db()
        self.assertFalse(self.person.has_usable_password())

    def test_evidence_the_policy_does_not_name_keeps_the_request_processing(self):
        self.with_policy(SANDBOX)
        self.approve()
        self.confirm_each({"creators": ["appeals", "measures"]})
        self.deletion.refresh_from_db()
        self.assertEqual(self.deletion.status, "processing")
        self.person.refresh_from_db()
        self.assertEqual(self.person.email, "person@example.test", "nothing is de-identified early")

    def test_without_a_policy_a_retained_category_keeps_the_request_processing(self):
        self.approve()
        self.confirm_each({"moderation": ["appeals"]})
        self.deletion.refresh_from_db()
        self.assertEqual(self.deletion.status, "processing")

    def test_a_clean_completion_records_no_policy(self):
        self.with_policy(SANDBOX)
        self.approve()
        self.confirm_each({})
        self.deletion.refresh_from_db()
        self.assertEqual((self.deletion.status, self.deletion.completed_under_policy), ("completed", ""))
        self.assertTrue(PrivacyRequest.objects.filter(pk=self.deletion.pk, status="completed").exists())
