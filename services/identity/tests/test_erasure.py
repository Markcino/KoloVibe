"""Decision C slices 2a and 2b: erasure jobs open with an approval, and confirmations apply once."""
import json
import uuid
from io import StringIO
from unittest.mock import patch

from django.db import connection
from django.test import SimpleTestCase, TestCase, override_settings

from service import erasure, events
from service.models import ErasureJob, PrivacyRequest, SecurityEvent
from .test_privacy_review import PrivacyReviewTests


@override_settings(STAGING_PRIVILEGED=True, PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class ErasureTests(TestCase):
    """Reuses the review fixture: an administrator with MFA, a person, and their requests."""
    setUp, token, call = PrivacyReviewTests.setUp, PrivacyReviewTests.token, PrivacyReviewTests.call

    def approve(self):
        target = str(self.deletion.id)
        self.call("start-review", id=target)
        status, row = self.call("approve-deletion", id=target)
        self.assertEqual(status, 200)
        return target

    def outbox(self):
        with connection.cursor() as cur:
            cur.execute("SELECT event_type, payload FROM event_outbox ORDER BY created_at")
            return [(kind, json.loads(payload)) for kind, payload in cur.fetchall()]

    def confirmation(self, **changes):
        return {"request_id": str(self.deletion.id), "account_id": str(self.person.id), "service": "engagement",
                "counts": {"likes": 3, "follows": 1}, "retained": ["qualified_watches"]} | changes

    def test_approval_opens_one_job_and_one_event_per_service(self):
        target = self.approve()
        self.assertEqual(set(ErasureJob.objects.values_list("service", flat=True)),
                         {"engagement", "creators", "moderation", "content", "business"})
        self.assertEqual(sorted(self.outbox(), key=lambda row: row[1]["service"]),
                         [("privacy.erasure_requested", {"request_id": target, "account_id": str(self.person.id),
                                                         "service": service})
                          for service in ("business", "creators", "engagement")],
                         "Moderation and Content wait for Creators")
        self.call("approve-deletion", id=target)
        self.assertEqual(len(self.outbox()), 3, "repeating the approval opens nothing more")

    def test_creators_confirmation_sends_moderation_its_request_with_the_profile_id(self):
        target = self.approve()
        profile = str(uuid.uuid4())
        creators = self.confirmation(service="creators", creator_id=profile, counts={"profile": 1}, retained=[])
        event = str(uuid.uuid4())
        self.assertTrue(erasure.confirm(event, creators))
        self.assertEqual(sorted(self.outbox()[3:], key=lambda row: row[1]["service"]), [
            ("privacy.erasure_requested", {"request_id": target, "account_id": str(self.person.id),
                                           "service": service, "creator_id": profile})
            for service in ("content", "moderation")])
        self.assertFalse(erasure.confirm(event, creators))
        self.assertEqual(len(self.outbox()), 5, "a repeated confirmation sends nothing more")
        self.assertIsNone(ErasureJob.objects.get(service="moderation").confirmed_at)

    def test_a_person_who_was_never_a_creator_still_reaches_moderation(self):
        self.approve()
        erasure.confirm(str(uuid.uuid4()), self.confirmation(service="creators", creator_id=None, retained=[]))
        self.assertIsNone(self.outbox()[-1][1]["creator_id"])

    def test_a_refused_approval_opens_nothing(self):
        self.call("start-review", id=str(self.deletion.id))
        self.call("hold-place", account_id=str(self.person.id), reason_code="LEGAL_CLAIM", note="Open dispute")
        self.assertEqual(self.call("approve-deletion", id=str(self.deletion.id))[0], 409)
        self.assertEqual((ErasureJob.objects.count(), self.outbox()), (0, []))

    def test_a_confirmation_applies_once_and_never_completes_the_request(self):
        self.approve()
        event = str(uuid.uuid4())
        self.assertTrue(erasure.confirm(event, self.confirmation()))
        job = ErasureJob.objects.get(service="engagement")
        self.assertIsNotNone(job.confirmed_at)
        self.assertEqual((job.counts, job.retained), ({"likes": 3, "follows": 1}, ["qualified_watches"]))
        self.assertFalse(erasure.confirm(event, self.confirmation()), "the same event is applied once")
        self.assertEqual(SecurityEvent.objects.filter(kind="account.privacy_erasure_confirmed").count(), 1)
        self.deletion.refresh_from_db()
        self.assertEqual(self.deletion.status, "processing")

    def test_confirmations_that_match_no_open_job_are_refused(self):
        self.approve()
        for bad in (self.confirmation(account_id=str(uuid.uuid4())), self.confirmation(request_id=str(uuid.uuid4()))):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                erasure.confirm(str(uuid.uuid4()), bad)
        self.assertFalse(ErasureJob.objects.filter(confirmed_at__isnull=False).exists())

    def test_malformed_confirmations_are_refused(self):
        for bad in (self.confirmation(service="points"), self.confirmation(counts={"Likes": 1}),
                    self.confirmation(counts={"likes": -1}), self.confirmation(counts={"likes": True}),
                    self.confirmation(retained=["a", "a"]), self.confirmation(extra=1),
                    self.confirmation(counts={"email": "person@example.test"}),
                    self.confirmation(creator_id=str(uuid.uuid4())), self.confirmation(service="creators"),
                    self.confirmation(service="creators", creator_id="nope")):
            with self.subTest(bad=bad):
                self.assertFalse(erasure.valid_confirmation(bad))

    def confirm_all(self, retained=(), creator_id=None):
        for service in events.ERASURE_SERVICES:
            extra = {"creator_id": creator_id} if service == "creators" else {}
            erasure.confirm(str(uuid.uuid4()), self.confirmation(service=service, counts={"rows": 1},
                                                                 retained=list(retained), **extra))

    def test_completion_waits_for_every_service_and_then_de_identifies_the_account(self):
        from service.models import Account, LoginSession, NotificationPreferences, TotpFactor
        self.approve()
        NotificationPreferences.objects.create(account=self.person)
        TotpFactor.objects.create(account=self.person, encrypted_secret="x")
        for service in events.ERASURE_SERVICES[:-1]:
            extra = {"creator_id": None} if service == "creators" else {}
            erasure.confirm(str(uuid.uuid4()), self.confirmation(service=service, retained=[], **extra))
        self.deletion.refresh_from_db()
        self.assertEqual(self.deletion.status, "processing", "one service has not confirmed yet")
        erasure.confirm(str(uuid.uuid4()), self.confirmation(service=events.ERASURE_SERVICES[-1], retained=[]))
        self.deletion.refresh_from_db()
        self.assertEqual(self.deletion.status, "completed")
        person = Account.objects.get(pk=self.person.pk)
        self.assertEqual((person.email, person.display_name, person.is_active, person.role),
                         (f"erased-{person.id.hex}@invalid", "", False, "viewer"))
        self.assertFalse(person.has_usable_password())
        for model in (LoginSession, NotificationPreferences, TotpFactor):
            self.assertFalse(model.objects.filter(account=person).exists(), model.__name__)
        self.assertTrue(PrivacyRequest.objects.filter(account=person).exists(), "the evidence row stays")
        self.assertEqual(SecurityEvent.objects.filter(kind="account.privacy_erasure_completed").count(), 1)

    def test_a_retained_category_keeps_the_request_processing_until_a_later_confirmation_clears_it(self):
        self.approve()
        self.confirm_all(retained=["appeals"])
        self.deletion.refresh_from_db()
        self.assertEqual(self.deletion.status, "processing")
        self.person.refresh_from_db()
        self.assertEqual(self.person.email, "person@example.test", "nothing is de-identified early")
        self.confirm_all()  # e.g. re-applied once a retention decision let every service erase the rest
        self.deletion.refresh_from_db()
        self.assertEqual(self.deletion.status, "completed")

    def test_reapply_sends_every_service_its_request_again_with_the_stored_profile_id(self):
        from io import StringIO
        from django.core.management import call_command
        self.approve()
        profile = str(uuid.uuid4())
        self.confirm_all(retained=["appeals"], creator_id=profile)
        before = len(self.outbox())
        out = StringIO()
        call_command("reapply_erasures", "--all", stdout=out)
        sent = self.outbox()[before:]
        self.assertEqual(sorted(row[1]["service"] for row in sent), sorted(events.ERASURE_SERVICES))
        self.assertTrue(all(row[1].get("creator_id") == profile for row in sent
                            if row[1]["service"] in events.AFTER_CREATORS))
        self.assertIn("Re-applied 1 erasures (5 service requests)", out.getvalue())
        self.assertNotIn(str(self.person.id), out.getvalue())
        self.assertEqual(SecurityEvent.objects.filter(kind="account.privacy_erasure_reapplied").count(), 1)

    def test_reapply_skips_requests_creators_has_not_answered_and_completed_ones_accept_confirmations(self):
        from django.core.management import call_command
        self.approve()
        before = len(self.outbox())
        call_command("reapply_erasures", "--request", str(self.deletion.id), stdout=StringIO())
        self.assertEqual(len(self.outbox()), before, "Creators' first answer releases the rest")
        self.confirm_all()
        self.deletion.refresh_from_db()
        self.assertEqual(self.deletion.status, "completed")
        again = self.confirmation(service="engagement", retained=[])
        self.assertTrue(erasure.confirm(str(uuid.uuid4()), again), "a re-applied erasure is accepted")
        self.assertEqual(SecurityEvent.objects.filter(kind="account.privacy_erasure_completed").count(), 1)

    def test_only_erasure_requests_may_enter_the_outbox(self):
        from django.db import transaction
        with transaction.atomic():
            with self.assertRaises(ValueError):
                events.record_event("privacy.erasure_requested", {"service": "points"})
            with self.assertRaises(ValueError):
                events.record_event("account.registered", {"service": "engagement"})


class OutsideTransactionTests(SimpleTestCase):
    def test_an_event_needs_the_business_transaction(self):
        with self.assertRaises(RuntimeError):
            events.record_event("privacy.erasure_requested", {"service": "engagement"})


class DispatchRoutingTests(TestCase):
    def test_requests_go_to_the_service_queue_through_its_named_exchange(self):
        task_name, queue, options = events._destination({"service": "content"})
        self.assertEqual((task_name, queue.name), ("kolovibe.content.event", "kolovibe.content.media"),
                         "Content erases on its media worker")
        task_name, queue, options = events._destination({"service": "engagement"})
        self.assertEqual(task_name, "kolovibe.engagement.event")
        self.assertEqual(options, {"exchange": "kolovibe.engagement", "routing_key": "kolovibe.engagement"})
        self.assertTrue(queue.no_declare)
        with self.assertRaises(ValueError):
            events._destination({"service": "identity"})

    def test_worker_rejects_anything_but_a_confirmation(self):
        with patch.dict("os.environ", {"KOLOVIBE_ENV": "local",
                                       "KOLOVIBE_RABBITMQ_URL": "amqps://u:p@localhost:5671/kv"}):
            from service import celery_app
        with self.assertRaises(ValueError):
            celery_app.receive_event.run(str(uuid.uuid4()), "privacy.erasure_requested", {})
        with patch("service.erasure.confirm", return_value=True) as confirm:
            self.assertTrue(celery_app.receive_event.run("e", "privacy.erasure_confirmed", {"a": 1}))
        confirm.assert_called_once_with("e", {"a": 1})
