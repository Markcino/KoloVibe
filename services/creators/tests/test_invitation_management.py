"""Outstanding-invitation listing and revocation: authorization, state transitions and the onboarding event trail."""

import json
from uuid import uuid4

from django.test import RequestFactory, TestCase

from service.models import CreatorApplication, CreatorProfile, OnboardingEvent
from service.onboarding import onboarding


class InvitationManagementTests(TestCase):
    def setUp(self):
        self.admin = uuid4()
        self.account = uuid4()
        self.attestations = {"handle": "pilot_one", "adult_attested": True, "rights_attested": True}

    def call(self, operation, actor, role, data=None, caller="gateway"):
        request = RequestFactory().post("/internal/creators/onboarding/" + operation, {
            "actor_id": str(actor), "role": role, "data": data or {}}, content_type="application/json")
        request.service_caller = caller
        return onboarding(request, operation)

    def invite(self, role="administrator", account=None):
        return self.call("invite", self.admin, role, {"account_id": str(account or self.account)})

    def revoke(self, role="administrator", actor=None, account=None):
        return self.call("revoke", actor or self.admin, role, {"account_id": str(account or self.account)})

    def outstanding(self, role="administrator", cursor=None, caller="gateway"):
        return self.call("outstanding", self.admin, role, {"cursor": cursor}, caller=caller)

    def actions(self):
        return list(OnboardingEvent.objects.order_by("created_at").values_list("action", flat=True))

    def test_only_administrators_list_or_revoke_and_only_through_the_gateway(self):
        self.invite()
        for role in ("viewer", "creator", "moderator"):
            self.assertEqual(self.outstanding(role).status_code, 403, role)
            self.assertEqual(self.revoke(role).status_code, 403, role)
        self.assertEqual(self.outstanding(caller="content").status_code, 403)
        self.assertEqual(self.revoke().status_code, 200)  # positive control: the refusals were about the role
        self.assertEqual(CreatorApplication.objects.get().status, "revoked")

    def test_listing_shows_only_invited_accounts_with_exact_fields_and_pages_by_cursor(self):
        ids = sorted(uuid4() for _ in range(24))
        for account in ids:
            self.invite(account=account)
        CreatorApplication.objects.filter(account_id=ids[0]).update(status="pending")
        CreatorApplication.objects.filter(account_id=ids[1]).update(status="revoked")
        first = json.loads(self.outstanding().content)
        self.assertEqual(len(first["items"]), 20)
        self.assertEqual(set(first["items"][0]), {"account_id", "status", "creator_id", "invited_at"})
        self.assertTrue(all(item["status"] == "invited" for item in first["items"]))
        self.assertEqual(first["next_cursor"], first["items"][-1]["account_id"])
        second = json.loads(self.outstanding(cursor=first["next_cursor"]).content)
        self.assertEqual(len(second["items"]), 2)
        self.assertIsNone(second["next_cursor"])
        listed = {item["account_id"] for item in first["items"]}
        self.assertNotIn(str(ids[0]), listed)
        self.assertNotIn(str(ids[1]), listed)

    def test_revoke_is_repeat_safe_records_one_event_and_removes_the_invitation(self):
        self.invite()
        self.assertEqual(self.revoke().status_code, 200)
        self.assertEqual(self.revoke().status_code, 200)
        self.assertEqual(self.actions(), ["invited", "revoked"])
        self.assertEqual(json.loads(self.outstanding().content)["items"], [])
        event = OnboardingEvent.objects.get(action="revoked")
        self.assertEqual((event.account_id, event.actor_id), (self.account, self.admin))

    def test_only_an_outstanding_invitation_can_be_revoked(self):
        self.assertEqual(self.revoke().status_code, 404)
        self.invite()
        self.assertEqual(self.revoke(actor=self.account).status_code, 403)  # no self-revocation
        self.call("submit", self.account, "viewer", self.attestations)
        self.assertEqual(self.revoke().status_code, 409)  # pending: decide it by review
        self.call("review", self.admin, "administrator", {"account_id": str(self.account), "decision": "approved"})
        self.assertEqual(self.revoke().status_code, 409)  # approved: never undone here
        self.assertEqual(CreatorApplication.objects.get().status, "approved")
        self.assertEqual(self.actions(), ["invited", "approved"])

    def test_a_revoked_account_cannot_apply_and_sees_no_invitation(self):
        self.invite()
        self.revoke()
        self.assertEqual(self.call("submit", self.account, "viewer", self.attestations).status_code, 403)
        self.assertFalse(CreatorProfile.objects.exists())
        self.assertEqual(self.call("status", self.account, "viewer").status_code, 404)
        eligibility = json.loads(self.call("eligibility", self.account, "viewer").content)
        self.assertEqual(eligibility, {"upload_eligible": False, "creator_id": None})

    def test_reinviting_a_revoked_account_is_administrator_only_and_restores_the_invitation(self):
        self.invite()
        self.revoke()
        self.assertEqual(self.invite(role="moderator").status_code, 403)
        self.assertEqual(CreatorApplication.objects.get().status, "revoked")
        other_admin = uuid4()
        response = self.call("invite", other_admin, "administrator", {"account_id": str(self.account)})
        self.assertEqual(response.status_code, 200)
        application = CreatorApplication.objects.get()
        self.assertEqual((application.status, application.invited_by), ("invited", other_admin))
        self.assertIsNone(application.reviewed_by)
        self.assertEqual(self.actions(), ["invited", "revoked", "reinvited"])
        self.assertEqual(self.call("submit", self.account, "viewer", self.attestations).status_code, 201)

    def test_invalid_requests_are_refused(self):
        self.assertEqual(self.call("revoke", self.admin, "administrator", {}).status_code, 400)
        self.assertEqual(self.call("revoke", self.admin, "administrator", {"account_id": "x"}).status_code, 400)
        self.assertEqual(self.call("outstanding", self.admin, "administrator", {"cursor": "x"}).status_code, 400)
        self.assertEqual(self.call("outstanding", self.admin, "administrator",
                                   {"cursor": None, "extra": 1}).status_code, 400)

    def test_review_decisions_are_recorded_once(self):
        self.invite()
        self.call("submit", self.account, "viewer", self.attestations)
        decision = {"account_id": str(self.account), "decision": "rejected"}
        self.call("review", self.admin, "administrator", decision)
        self.call("review", self.admin, "administrator", decision)
        self.assertEqual(self.actions(), ["invited", "rejected"])
