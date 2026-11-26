"""Decision C slice 2b: Moderation erases one account's data and confirms it."""
import json
import uuid
from datetime import timedelta
from unittest.mock import patch

from django.db import connection, transaction
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from service import events, privacy
from service.models import (Appeal, CopyrightNotice, CounterNotice, ModerationAction, ModeratorAssignment, Report,
                            ReviewerPreview, RightsHolder)


def report(reporter, details="It is harmful", **fields):
    return Report.objects.create(id=uuid.uuid4(), video_id=uuid.uuid4(), reporter_id=reporter, reason="harm",
                                 details=details, **fields)


class ModerationErasureTests(TestCase):
    def setUp(self):
        self.person, self.other, self.admin, self.reviewer = (str(uuid.uuid4()) for _ in range(4))
        self.profile = str(uuid.uuid4())  # the person's creator profile id, which Identity passes on from Creators
        self.request_id = str(uuid.uuid4())
        self.plain = report(self.person)
        self.cited = report(self.person, details="Evidence cited by a decision")
        ModerationAction.objects.create(id=uuid.uuid4(), video_id=self.cited.video_id, reviewer_id=self.reviewer,
                                        action="remove", reason="Removed", status="applied", report=self.cited)
        self.theirs = report(self.other)

    def payload(self, **changes):
        return {"request_id": self.request_id, "account_id": self.person, "service": "moderation",
                "creator_id": self.profile} | changes

    def confirmation(self):
        with connection.cursor() as cur:
            cur.execute("SELECT event_type, payload FROM event_outbox")
            rows = cur.fetchall()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][0], "privacy.erasure_confirmed")
        return json.loads(rows[0][1])

    def test_reports_are_de_identified_and_uncited_details_cleared(self):
        self.assertTrue(privacy.erase(str(uuid.uuid4()), self.payload()))
        self.plain.refresh_from_db()
        self.cited.refresh_from_db()
        self.assertNotEqual(str(self.plain.reporter_id), self.person)
        self.assertEqual(self.plain.reporter_id, self.cited.reporter_id, "one tombstone per erasure")
        self.assertEqual((self.plain.details, self.cited.details), ("", "Evidence cited by a decision"))
        self.assertFalse(Report.objects.filter(reporter_id=self.person).exists())
        self.assertTrue(Report.objects.filter(reporter_id=self.other, details="It is harmful").exists())
        self.assertEqual(self.confirmation(), {
            "request_id": self.request_id, "account_id": self.person, "service": "moderation",
            "counts": {"reports_deidentified": 2, "rights_holder_revoked": 0, "reviewer_previews": 0,
                       "assignments_deactivated": 0},
            "retained": ["cited_report_details"]})

    def test_copyright_claims_counter_notices_and_appeals_are_retained(self):
        claim = Report.objects.create(
            id=uuid.uuid4(), video_id=uuid.uuid4(), reporter_id=self.person, reason="copyright", details="My work")
        CopyrightNotice.objects.create(report=claim, work_reference="https://example.test/work")
        removal = ModerationAction.objects.create(id=uuid.uuid4(), video_id=uuid.uuid4(), reviewer_id=self.reviewer,
                                                  creator_id=self.profile, action="remove", reason="Copyright",
                                                  status="applied", copyright=True)
        appeal = Appeal.objects.create(removal=removal, appellant_id=self.person, reason="It is mine")
        CounterNotice.objects.create(appeal=appeal, request_id=uuid.uuid4(), account_id=self.person)
        privacy.erase(str(uuid.uuid4()), self.payload())
        claim.refresh_from_db()
        self.assertEqual((str(claim.reporter_id), claim.details), (self.person, "My work"),
                         "copyright evidence is never changed")
        self.assertEqual(self.confirmation()["retained"],
                         ["copyright_claims", "cited_report_details", "counter_notices", "appeals", "decisions"])

    def test_rights_holder_is_revoked_and_staff_grants_end(self):
        RightsHolder.objects.create(account_id=self.person, organisation="Label", evidence="Passport checked",
                                    verified_by=self.admin)
        ModeratorAssignment.objects.create(moderator_id=self.person, queue_scope="reports", target_id=uuid.uuid4())
        ReviewerPreview.objects.create(actor_id=self.person, queue_scope="reports", target_id=uuid.uuid4(),
                                       video_id=uuid.uuid4(), expires_at=timezone.now() + timedelta(minutes=5))
        ModerationAction.objects.create(id=uuid.uuid4(), video_id=uuid.uuid4(), reviewer_id=self.person,
                                        action="remove", reason="Staff decision", status="applied")
        privacy.erase(str(uuid.uuid4()), self.payload())
        holder = RightsHolder.objects.get(account_id=self.person)
        self.assertEqual((holder.evidence, str(holder.revoked_by)), (privacy.ERASED_EVIDENCE, self.request_id))
        self.assertIsNotNone(holder.revoked_at)
        self.assertFalse(ModeratorAssignment.objects.filter(active=True).exists())
        self.assertFalse(ReviewerPreview.objects.exists())
        confirmation = self.confirmation()
        self.assertEqual((confirmation["counts"]["rights_holder_revoked"], confirmation["counts"]["reviewer_previews"],
                          confirmation["counts"]["assignments_deactivated"]), (1, 1, 1))
        self.assertIn("staff_decisions", confirmation["retained"])

    def test_decisions_are_found_by_the_creator_profile_not_the_account(self):
        ModerationAction.objects.create(id=uuid.uuid4(), video_id=uuid.uuid4(), reviewer_id=self.reviewer,
                                        creator_id=self.profile, action="remove", reason="Safety", status="applied")
        privacy.erase(str(uuid.uuid4()), self.payload(creator_id=None))
        self.assertNotIn("decisions", self.confirmation()["retained"], "someone never a creator has no decisions")
        with connection.cursor() as cur:
            cur.execute("DELETE FROM event_outbox")
        privacy.erase(str(uuid.uuid4()), self.payload())
        self.assertIn("decisions", self.confirmation()["retained"])

    def test_a_repeat_delivery_changes_nothing(self):
        event = str(uuid.uuid4())
        privacy.erase(event, self.payload())
        late = report(self.person)
        self.assertFalse(privacy.erase(event, self.payload()))
        late.refresh_from_db()
        self.assertEqual(str(late.reporter_id), self.person)

    def test_malformed_requests_are_refused_before_any_change(self):
        for bad in (self.payload(service="creators"), self.payload(request_id="nope"), self.payload(extra=1),
                    self.payload(creator_id="nope"), {"account_id": self.person},
                    {"request_id": self.request_id, "account_id": self.person, "service": "moderation"}):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                privacy.erase(str(uuid.uuid4()), bad)
        self.assertEqual(Report.objects.filter(reporter_id=self.person).count(), 2)

    def test_only_confirmations_may_enter_the_outbox(self):
        with transaction.atomic():
            for kind, payload in (("privacy.erasure_requested", {"service": "moderation"}),
                                  ("privacy.erasure_confirmed", {"service": "creators"})):
                with self.subTest(kind=kind), self.assertRaises(ValueError):
                    events.record_event(kind, payload)


class ModerationWorkerTests(SimpleTestCase):
    def test_confirmations_go_to_identity_through_its_named_exchange(self):
        task_name, queue, options = events._destination()
        self.assertEqual((task_name, options), ("kolovibe.identity.event",
                                                {"exchange": "kolovibe.identity", "routing_key": "kolovibe.identity"}))
        self.assertTrue(queue.no_declare)

    def test_worker_accepts_only_erasure_requests(self):
        with patch.dict("os.environ", {"KOLOVIBE_ENV": "local", "KOLOVIBE_RABBITMQ_URL": "amqps://u:p@localhost:5671/kv"}):
            from service import celery_app
        with self.assertRaises(ValueError):
            celery_app.receive_event.run(str(uuid.uuid4()), "privacy.erasure_confirmed", {})
        with patch("service.privacy.erase", return_value=True) as erase:
            self.assertTrue(celery_app.receive_event.run("e", "privacy.erasure_requested", {"a": 1}))
        erase.assert_called_once_with("e", {"a": 1})

    def test_staging_stays_blocked_without_an_approved_capability(self):
        with patch.dict("os.environ", {"KOLOVIBE_ENV": "local", "KOLOVIBE_RABBITMQ_URL": "amqps://u:p@localhost:5671/kv"}):
            from service import celery_app
        with patch.dict("os.environ", {"KOLOVIBE_ENV": "staging", "KOLOVIBE_STAGING_CAPABILITIES": "moderation"}):
            with self.assertRaises(RuntimeError):
                celery_app.build_app()
