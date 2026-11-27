"""Mandate 3.3b: Moderation assembles one account's own moderation records for an access export, once."""
import json
import uuid

from django.db import connection, transaction
from django.test import TestCase

from service import privacy
from service.models import Appeal, CopyrightNotice, CopyrightStrike, ModerationAction, RightsHolder
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


class ModerationExportTests(TestCase):
    setUp = test_privacy_erasure.ModerationErasureTests.setUp
    payload = test_privacy_erasure.ModerationErasureTests.payload

    def test_assembles_the_persons_reports_and_the_decisions_on_their_profile(self):
        claim = test_privacy_erasure.report(self.person, details="My song")
        CopyrightNotice.objects.create(report=claim, work_reference="ISRC-1", version="v1", organisation="Label")
        removal = ModerationAction.objects.create(id=uuid.uuid4(), video_id=uuid.uuid4(), reviewer_id=self.reviewer,
                                                  action="remove", reason="Copyright", status="applied",
                                                  creator_id=self.profile, copyright=True)
        CopyrightStrike.objects.create(removal=removal, creator_id=self.profile)
        Appeal.objects.create(removal=removal, appellant_id=self.person, reason="I own it")
        ModerationAction.objects.create(id=uuid.uuid4(), video_id=uuid.uuid4(), reviewer_id=self.person,
                                        action="approve", reason="Fine", status="applied")
        RightsHolder.objects.create(account_id=self.person, organisation="Label", evidence="Private note",
                                    verified_by=self.reviewer)
        part = export_twice(self, self.payload())
        counts = {name: len(rows) for name, rows in part["data"].items()}
        self.assertEqual(counts, {"reports": 2, "copyright_claims": 1, "appeals": 1, "counter_notices": 0,
                                  "decisions": 1, "edit_decisions": 0, "strikes": 1, "rights_holder": 1})
        self.assertEqual(part["data"]["copyright_claims"][0]["report_video_id"], str(claim.video_id))
        self.assertEqual(set(part["withheld"]), {"staff_decisions", "rights_holder_evidence"})
        text = json.dumps(part)
        self.assertNotIn("Private note", text, "the administrator's evidence note is never exported")
        self.assertNotIn(str(self.theirs.id), text)
        self.assertNotIn(str(self.theirs.video_id), text, "another account's report never appears")

    def test_someone_who_was_never_a_creator_gets_no_decisions(self):
        part = export_twice(self, self.payload(creator_id=None))
        self.assertEqual((len(part["data"]["reports"]), part["data"]["decisions"]), (2, []))

    def test_malformed_requests_are_refused(self):
        for bad in (self.payload(creator_id="nope"), self.payload(extra=1),
                    {k: v for k, v in self.payload().items() if k != "creator_id"}):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                privacy.export(str(uuid.uuid4()), bad)
