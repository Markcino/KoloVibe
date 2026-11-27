"""Mandate 3.3b: Creators assembles one account's own creator records for an access export, once."""
import json
import uuid

from django.db import connection, transaction
from django.test import TestCase

from service import privacy
from service.models import AuditEvent, CreatorProfile, CreatorRestriction, RestrictionAppeal
from . import test_privacy_erasure


def delivered(self):
    with connection.cursor() as cur:
        cur.execute("SELECT event_type, payload FROM event_outbox")
        rows = cur.fetchall()
    self.assertEqual(len(rows), 1)
    self.assertEqual(rows[0][0], "privacy.export_delivered")
    part = json.loads(rows[0][1])
    json.dumps(part, allow_nan=False)
    return part


def export_twice(self, payload):
    event = str(uuid.uuid4())
    with transaction.atomic():
        self.assertTrue(privacy.export(event, payload))
    with transaction.atomic():
        self.assertFalse(privacy.export(event, payload), "a repeat delivery sends nothing more")
    return delivered(self)


class CreatorsExportTests(TestCase):
    setUp = test_privacy_erasure.CreatorsErasureTests.setUp
    payload = test_privacy_erasure.CreatorsErasureTests.payload

    def test_assembles_only_this_account_and_carries_the_profile_id(self):
        profile = self.profiles[self.person]
        measure = CreatorRestriction.objects.create(id=uuid.uuid4(), creator=profile, kind="warning",
                                                    reason_code="SPAM", policy_version="v1", reason="Repeated spam",
                                                    issued_by=self.admin)
        RestrictionAppeal.objects.create(id=uuid.uuid4(), restriction=measure, appellant_id=self.person,
                                         reason="It was not spam")
        AuditEvent.objects.create(kind="creator.warned", actor_id=self.admin, subject_type="creator",
                                  subject_id=profile.pk)
        part = export_twice(self, self.payload())
        self.assertEqual(set(part), {"request_id", "account_id", "service", "creator_id", "data", "withheld",
                                     "truncated"})
        self.assertEqual(part["creator_id"], str(profile.pk))
        self.assertEqual({name: len(rows) for name, rows in part["data"].items()},
                         {"profile": 1, "application": 1, "onboarding_events": 1, "measures": 1, "appeals": 1})
        self.assertEqual(part["data"]["profile"][0]["handle"], "person_creator")
        self.assertEqual(part["data"]["appeals"][0]["reason"], "It was not spam")
        self.assertEqual(part["withheld"], ["copyright_review_grant", "audit_events"])
        self.assertNotIn("other_creator", json.dumps(part), "another account's rows never appear")
        self.assertTrue(CreatorProfile.objects.filter(user_id=self.person).exists(), "an export changes nothing")

    def test_someone_who_was_never_a_creator_gets_empty_categories_and_no_profile_id(self):
        part = export_twice(self, self.payload(account_id=str(uuid.uuid4())))
        self.assertIsNone(part["creator_id"])
        self.assertEqual((set(map(len, part["data"].values())), part["withheld"]), ({0}, []))

    def test_malformed_requests_are_refused(self):
        for bad in (self.payload(service="moderation"), self.payload(account_id="nope"), self.payload(extra=1)):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                privacy.export(str(uuid.uuid4()), bad)
