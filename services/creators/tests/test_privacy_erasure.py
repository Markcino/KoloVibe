"""Decision C slice 2b: Creators erases one account's creator data and confirms it."""
import json
import uuid
from unittest.mock import patch

from django.db import connection, transaction
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from service import events, privacy
from service.models import (AuditEvent, CopyrightReviewPolicy, CreatorApplication, CreatorProfile, CreatorRestriction,
                            OnboardingEvent, RestrictionAppeal)


class CreatorsErasureTests(TestCase):
    def setUp(self):
        self.person, self.other, self.admin = (str(uuid.uuid4()) for _ in range(3))
        self.request_id = str(uuid.uuid4())
        self.profiles = {}
        for account, handle in ((self.person, "person_creator"), (self.other, "other_creator")):
            profile = CreatorProfile.objects.create(user_id=account, handle=handle, display_name="Ada Example",
                                                    location="Lagos", bio="My channel", status="active",
                                                    reviewed_at=timezone.now())
            CreatorApplication.objects.create(account_id=account, invited_by=self.admin, profile=profile,
                                              status="approved", attestation_version="v1")
            OnboardingEvent.objects.create(account_id=account, actor_id=self.admin, action="approved")
            self.profiles[account] = profile
        CopyrightReviewPolicy.objects.create(creator=self.profiles[self.person], active=True, approved_by=self.admin,
                                             approved_at=timezone.now(), version="v1", reason="Trusted")

    def payload(self, **changes):
        return {"request_id": self.request_id, "account_id": self.person, "service": "creators"} | changes

    def confirmation(self):
        with connection.cursor() as cur:
            cur.execute("SELECT event_type, payload FROM event_outbox")
            rows = cur.fetchall()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][0], "privacy.erasure_confirmed")
        return json.loads(rows[0][1])

    def test_without_measures_the_profile_and_application_are_deleted(self):
        profile_id = str(self.profiles[self.person].id)
        self.assertTrue(privacy.erase(str(uuid.uuid4()), self.payload()))
        self.assertFalse(CreatorProfile.objects.filter(user_id=self.person).exists())
        self.assertFalse(CreatorApplication.objects.filter(account_id=self.person).exists())
        self.assertFalse(CopyrightReviewPolicy.objects.exists())
        self.assertFalse(OnboardingEvent.objects.filter(account_id=self.person).exists())
        self.assertEqual(OnboardingEvent.objects.count(), 2, "onboarding history keeps its count")
        self.assertTrue(CreatorProfile.objects.filter(user_id=self.other, display_name="Ada Example").exists())
        self.assertEqual(self.confirmation(), {
            "request_id": self.request_id, "account_id": self.person, "service": "creators",
            "creator_id": profile_id, "counts": {"application": 1, "profile": 1, "profile_deidentified": 0, "copyright_review_grant": 1,
                       "onboarding_events_deidentified": 1},
            "retained": []})

    def test_with_measures_the_profile_is_kept_but_de_identified(self):
        profile = self.profiles[self.person]
        measure = CreatorRestriction.objects.create(id=uuid.uuid4(), creator=profile, kind="warning", reason_code="X1",
                                                    policy_version="v1", reason="Private reason", issued_by=self.admin)
        RestrictionAppeal.objects.create(id=uuid.uuid4(), restriction=measure, appellant_id=self.person,
                                         reason="I disagree")
        with transaction.atomic():
            AuditEvent.objects.create(kind="creator.restricted", actor_id=self.admin, subject_type="creator",
                                      subject_id=profile.id)
        privacy.erase(str(uuid.uuid4()), self.payload())
        profile.refresh_from_db()
        self.assertEqual((profile.handle, profile.display_name, profile.location, profile.bio, profile.status),
                         (f"erased-{profile.id.hex}", "", "", "", "suspended"))
        self.assertTrue(CreatorRestriction.objects.filter(pk=measure.pk).exists(), "enforcement evidence is retained")
        confirmation = self.confirmation()
        self.assertEqual((confirmation["counts"]["profile"], confirmation["counts"]["profile_deidentified"]), (0, 1))
        self.assertEqual(confirmation["retained"], ["measures", "appeals", "audit_events"])

    def test_a_repeat_delivery_changes_nothing(self):
        event = str(uuid.uuid4())
        privacy.erase(event, self.payload())
        CreatorProfile.objects.create(user_id=self.person, handle="came_back", status="pending")
        self.assertFalse(privacy.erase(event, self.payload()))
        self.assertTrue(CreatorProfile.objects.filter(handle="came_back").exists())

    def test_an_account_with_no_creator_data_still_confirms(self):
        privacy.erase(str(uuid.uuid4()), self.payload(account_id=str(uuid.uuid4())))
        self.assertEqual(set(self.confirmation()["counts"].values()), {0})
        self.assertIsNone(self.confirmation()["creator_id"])

    def test_malformed_requests_are_refused_before_any_change(self):
        for bad in (self.payload(service="engagement"), self.payload(account_id="nope"), self.payload(extra=1),
                    {"request_id": self.request_id}, [self.request_id]):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                privacy.erase(str(uuid.uuid4()), bad)
        self.assertEqual(CreatorProfile.objects.count(), 2)

    def test_only_confirmations_may_enter_the_outbox(self):
        with transaction.atomic():
            for kind, payload in (("privacy.erasure_requested", {"service": "creators"}),
                                  ("privacy.erasure_confirmed", {"service": "engagement"})):
                with self.subTest(kind=kind), self.assertRaises(ValueError):
                    events.record_event(kind, payload)


class CreatorsWorkerTests(SimpleTestCase):
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
        with patch.dict("os.environ", {"KOLOVIBE_ENV": "staging", "KOLOVIBE_STAGING_CAPABILITIES": "media"}):
            with self.assertRaises(RuntimeError):
                celery_app.build_app()
