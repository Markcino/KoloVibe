"""Decision C slice 2d: Business erases only what needs no pending decision, and confirms it."""
import json
import uuid
from unittest.mock import patch

from django.db import connection, transaction
from django.test import SimpleTestCase, override_settings

from service import events, privacy
from service.models import (BusinessMembership, InquiryThread, RegistrationGrant, ReviewerGrant, StaffInvitation)

from .support import BusinessTestCase


class BusinessErasureTests(BusinessTestCase):
    def setUp(self):
        super().setUp()
        self.owner, business = self.register()
        self.business_id = business["id"]
        self.person = self.add_staff(self.owner, self.business_id)
        self.request_id = str(uuid.uuid4())

    def payload(self, account=None, **changes):
        return {"request_id": self.request_id, "account_id": str(account or self.person), "service": "business"} | changes

    def confirmation(self):
        with connection.cursor() as cur:
            cur.execute("SELECT event_type, payload FROM event_outbox")
            rows = cur.fetchall()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][0], "privacy.erasure_confirmed")
        return json.loads(rows[0][1])

    def test_staff_membership_and_grants_end_and_the_business_is_untouched(self):
        RegistrationGrant.objects.create(account_id=self.person, granted_by_account_id=uuid.uuid4())
        ReviewerGrant.objects.create(reviewer_account_id=self.person, scope="verification",
                                     granted_by_account_id=uuid.uuid4())
        self.assertTrue(privacy.erase(str(uuid.uuid4()), self.payload()))
        membership = BusinessMembership.objects.get(account_id=self.person)
        self.assertEqual(membership.status, "revoked")
        self.assertIsNotNone(membership.revoked_at)
        self.assertFalse(RegistrationGrant.objects.filter(account_id=self.person).exists())
        self.assertFalse(ReviewerGrant.objects.filter(active=True).exists())
        self.assertTrue(BusinessMembership.objects.filter(account_id=self.owner, status="active").exists())
        self.assertEqual(self.confirmation(), {
            "request_id": self.request_id, "account_id": str(self.person), "service": "business",
            "counts": {"registration_grant": 1, "staff_memberships_revoked": 1, "invitations_revoked": 0,
                       "reviewer_grants_deactivated": 1},
            "retained": ["audit_events"]}, "redeeming the invitation is on the audit trail")

    def test_an_owner_keeps_the_business_pending_dr_bz_08(self):
        status, invitation = self.call("staff_invite", {"business_id": self.business_id, "label": "Baker"},
                                       actor=self.owner)
        self.assertEqual(status, 201)
        privacy.erase(str(uuid.uuid4()), self.payload(self.owner))
        self.assertTrue(BusinessMembership.objects.filter(account_id=self.owner, role="owner",
                                                          status="active").exists(), "the last owner is never removed")
        self.assertIsNotNone(StaffInvitation.objects.get(pk=invitation["id"]).revoked_at, "open invitations end")
        confirmation = self.confirmation()
        self.assertEqual(confirmation["counts"]["invitations_revoked"], 1)
        self.assertIn("business_ownership", confirmation["retained"])
        self.assertIn("audit_events", confirmation["retained"])

    def test_customer_inquiries_are_retained_pending_dr_bz_25(self):
        InquiryThread.objects.create(business_id=self.business_id, customer_account_id=self.person,
                                     customer_label="Customer 1", subject_code="general")
        privacy.erase(str(uuid.uuid4()), self.payload())
        self.assertIn("inquiries", self.confirmation()["retained"])
        self.assertTrue(InquiryThread.objects.filter(customer_account_id=self.person).exists())

    def test_a_repeat_delivery_changes_nothing(self):
        event = str(uuid.uuid4())
        privacy.erase(event, self.payload())
        RegistrationGrant.objects.create(account_id=self.person, granted_by_account_id=uuid.uuid4())
        self.assertFalse(privacy.erase(event, self.payload()))
        self.assertTrue(RegistrationGrant.objects.filter(account_id=self.person).exists())

    def test_malformed_requests_are_refused_before_any_change(self):
        for bad in (self.payload(service="creators"), self.payload(account_id="nope"), self.payload(creator_id=None),
                    {"request_id": self.request_id}):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                privacy.erase(str(uuid.uuid4()), bad)
        self.assertEqual(BusinessMembership.objects.filter(status="active").count(), 2)

    def test_only_confirmations_may_enter_the_outbox(self):
        with transaction.atomic():
            for kind, payload in (("privacy.erasure_requested", {"service": "business"}),
                                  ("privacy.erasure_confirmed", {"service": "content"})):
                with self.subTest(kind=kind), self.assertRaises(ValueError):
                    events.record_event(kind, payload)


@override_settings(ERASURE_BROKER_URL="amqps://u:p@localhost:5671/kv")
class BusinessWorkerTests(SimpleTestCase):
    def test_confirmations_go_to_identity_through_its_named_exchange(self):
        task_name, queue, options = events._destination()
        self.assertEqual((task_name, options), ("kolovibe.identity.event",
                                                {"exchange": "kolovibe.identity", "routing_key": "kolovibe.identity"}))
        self.assertTrue(queue.no_declare)

    def test_worker_accepts_only_erasure_requests_and_stays_off_staging(self):
        from service import celery_app
        with self.assertRaises(ValueError):
            celery_app.receive_event.run(str(uuid.uuid4()), "privacy.erasure_confirmed", {})
        with patch("service.privacy.erase", return_value=True) as erase:
            self.assertTrue(celery_app.receive_event.run("e", "privacy.erasure_requested", {"a": 1}))
        erase.assert_called_once_with("e", {"a": 1})
        with override_settings(ENVIRONMENT="staging"), self.assertRaises(RuntimeError):
            celery_app.build_app()
