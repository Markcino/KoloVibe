"""D11-007 / FR-015: every creator change leaves immutable evidence in its own transaction and reaches Audit."""

import io
import json
from unittest.mock import patch
from uuid import uuid4

from django.core.management import CommandError, call_command
from django.db import DatabaseError, transaction
from django.test import RequestFactory, TestCase, TransactionTestCase
from django.utils import timezone

from service import security_audit
from service.models import AuditDelivery, AuditEvent, CreatorProfile
from service.onboarding import onboarding
from service.profiles import own_profile


class Response:
    status = 201

    def __init__(self, body=b'{"status":"ok"}'):
        self.body = body

    def read(self, size):
        return self.body[:size]

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


BASELINE = set()


def new():
    # Only this test's evidence: the PostgreSQL foundations run shares a database with committed fixtures.
    return AuditEvent.objects.exclude(pk__in=BASELINE)


def kinds():
    return list(new().order_by("occurred_at").values_list("kind", "subject_type"))


class CreatorAuditEvidenceTests(TestCase):
    def setUp(self):
        self.admin, self.applicant = uuid4(), uuid4()
        BASELINE.clear()
        BASELINE.update(AuditEvent.objects.values_list("pk", flat=True))

    def call(self, operation, actor, role, data=None):
        request = RequestFactory().post("/internal/creators/onboarding/" + operation, {
            "actor_id": str(actor), "role": role, "data": data or {}}, content_type="application/json")
        request.service_caller = "gateway"
        return onboarding(request, operation)

    def onboard(self):
        self.assertEqual(self.call("invite", self.admin, "administrator", {"account_id": str(self.applicant)}).status_code, 201)
        self.assertEqual(self.call("submit", self.applicant, "viewer", {
            "handle": "pilot_one", "adult_attested": True, "rights_attested": True}).status_code, 201)

    def test_invitation_application_and_approval_each_record_one_event_with_a_delivery(self):
        self.onboard()
        self.assertEqual(self.call("review", self.admin, "administrator",
                                   {"account_id": str(self.applicant), "decision": "approved"}).status_code, 200)
        self.assertEqual(kinds(), [("creator.invited", "account"), ("creator.application_submitted", "creator"),
                                   ("creator.approved", "account")])
        self.assertEqual(AuditDelivery.objects.filter(event__in=new(), delivered_at__isnull=True).count(), 3)
        submitted = new().get(kind="creator.application_submitted")
        self.assertEqual((submitted.actor_id, submitted.subject_id),
                         (self.applicant, CreatorProfile.objects.get(user_id=self.applicant).id))
        approved = new().get(kind="creator.approved")
        self.assertEqual((approved.actor_id, approved.subject_id), (self.admin, self.applicant))

    def test_rejection_revocation_and_reinvitation_are_recorded_and_repeats_add_nothing(self):
        other = uuid4()
        self.call("invite", self.admin, "administrator", {"account_id": str(other)})
        self.call("revoke", self.admin, "administrator", {"account_id": str(other)})
        self.call("revoke", self.admin, "administrator", {"account_id": str(other)})
        self.call("invite", self.admin, "administrator", {"account_id": str(other)})
        self.onboard()
        self.call("review", self.admin, "moderator", {"account_id": str(self.applicant), "decision": "rejected"})
        self.call("review", self.admin, "moderator", {"account_id": str(self.applicant), "decision": "rejected"})
        self.assertEqual([kind for kind, _ in kinds()], [
            "creator.invited", "creator.invitation_revoked", "creator.invited", "creator.invited",
            "creator.application_submitted", "creator.rejected"])

    def test_refused_actions_record_nothing(self):
        self.assertEqual(self.call("invite", self.admin, "viewer", {"account_id": str(self.applicant)}).status_code, 403)
        self.assertEqual(self.call("invite", self.admin, "administrator", {"account_id": str(self.admin)}).status_code, 403)
        self.assertEqual(self.call("submit", self.applicant, "viewer", {
            "handle": "pilot_one", "adult_attested": True, "rights_attested": True}).status_code, 403)
        self.assertFalse(new().exists())

    def test_own_profile_edit_records_profile_updated_but_a_read_records_nothing(self):
        owner = uuid4()
        profile = CreatorProfile.objects.create(user_id=owner, handle="original", status="active", reviewed_at=timezone.now())

        def call(operation, data):
            request = RequestFactory().post("/internal/creators/me", {
                "actor_id": str(owner), "role": "creator", "operation": operation, "data": data},
                content_type="application/json")
            request.service_caller = "gateway"
            return own_profile(request)
        self.assertEqual(call("get", {}).status_code, 200)
        self.assertFalse(new().exists())
        self.assertEqual(call("patch", {"bio": "Stories from Monrovia"}).status_code, 200)
        event = new().get()
        self.assertEqual((event.kind, event.actor_id, event.subject_type, event.subject_id),
                         ("creator.profile_updated", owner, "creator", profile.id))
        self.assertNotIn("Monrovia", json.dumps(new().values().get(), default=str))

    def test_evidence_needs_its_transaction_a_known_kind_and_rolls_back_with_the_change(self):
        with self.assertRaises(RuntimeError), transaction.atomic():
            security_audit.record("creator.deleted", self.admin, "account", self.applicant)
        try:
            with transaction.atomic():
                security_audit.record("creator.approved", self.admin, "account", self.applicant)
                raise ValueError("work failed")
        except ValueError:
            pass
        self.assertFalse(new().exists())

    def test_events_are_append_only_and_carry_identifiers_only(self):
        self.onboard()
        self.assertEqual({field.name for field in AuditEvent._meta.fields},
                         {"id", "kind", "actor_id", "occurred_at", "subject_type", "subject_id"})
        with self.assertRaises(DatabaseError), transaction.atomic():
            new().update(kind="creator.approved")
        with self.assertRaises(DatabaseError), transaction.atomic():
            new()._raw_delete(AuditEvent.objects.db)

    def test_vocabulary_matches_what_the_audit_service_accepts(self):
        from pathlib import Path
        source = (Path(__file__).resolve().parents[2] / "audit/service/events.py").read_text()
        for kind in security_audit.KINDS:
            self.assertIn(f'"{kind}"', source)


class OutsideTransactionTests(TransactionTestCase):
    def test_evidence_is_refused_outside_its_owning_transaction(self):
        with self.assertRaises(RuntimeError):
            security_audit.record("creator.approved", uuid4(), "account", uuid4())
        self.assertFalse(new().exists())


class CreatorAuditDeliveryTests(TestCase):
    def setUp(self):
        AuditDelivery.objects.update(delivered_at=timezone.now())  # isolate from committed fixtures (rolled back)
        with transaction.atomic():
            self.event = security_audit.record("creator.approved", uuid4(), "account", uuid4())

    def run_command(self, **options):
        out = io.StringIO()
        call_command("deliver_audit_events", stdout=out, **options)
        return out.getvalue()

    def test_delivers_the_exact_signed_payload_once(self):
        calls = []

        def send(audience, path, **kwargs):
            calls.append((audience, path, kwargs))
            return Response()
        with patch("service.management.commands.deliver_audit_events.signed_internal_request", side_effect=send):
            self.assertIn("acknowledged", self.run_command())
            self.run_command()
        self.assertEqual(len(calls), 1)
        audience, path, kwargs = calls[0]
        self.assertEqual((audience, path, kwargs["method"], kwargs["timeout"]),
                         ("audit", "/internal/security-events", "POST", 2))
        payload = json.loads(kwargs["payload"])
        self.assertEqual(set(payload), {"id", "actor_id", "kind", "occurred_at", "subject_type", "subject_id"})
        self.assertEqual((payload["id"], payload["kind"], payload["subject_type"], payload["subject_id"]),
                         (str(self.event.id), "creator.approved", "account", str(self.event.subject_id)))
        self.assertIsNotNone(AuditDelivery.objects.get(event=self.event).delivered_at)

    def test_failure_or_a_bad_acknowledgement_keeps_the_evidence_and_backs_off(self):
        for outcome in (OSError(), Response(b'{"status":"maybe"}')):
            AuditDelivery.objects.filter(event=self.event).update(next_attempt_at=timezone.now())
            with patch("service.management.commands.deliver_audit_events.signed_internal_request",
                       side_effect=[outcome] if isinstance(outcome, Exception) else None,
                       return_value=outcome):
                with self.assertRaises(CommandError):
                    self.run_command()
            delivery = AuditDelivery.objects.get(event=self.event)
            self.assertIsNone(delivery.delivered_at)
            self.assertGreater(delivery.next_attempt_at, timezone.now())
        self.assertEqual(AuditDelivery.objects.get(event=self.event).attempts, 2)

    def test_batch_limit_is_bounded(self):
        for limit in (0, 1001):
            with self.assertRaises(CommandError):
                self.run_command(limit=limit)
