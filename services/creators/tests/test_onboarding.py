import json
from uuid import uuid4

from django.test import RequestFactory, TestCase

from service.models import CreatorApplication, CreatorProfile
from service.onboarding import onboarding


class CreatorOnboardingTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.applicant = uuid4()
        self.reviewer = uuid4()
        self.attestations = {"handle": "Pilot_One", "adult_attested": True, "rights_attested": True}

    def call(self, operation, actor, role, data=None, caller="gateway"):
        request = self.factory.post("/internal/creators/onboarding/" + operation, {
            "actor_id": str(actor), "role": role, "data": data or {},
        }, content_type="application/json")
        request.service_caller = caller
        return onboarding(request, operation)

    def invite(self):
        return self.call("invite", self.reviewer, "moderator", {"account_id": str(self.applicant)})

    def submit(self):
        return self.call("submit", self.applicant, "viewer", self.attestations)

    def eligibility(self):
        response = self.call("eligibility", self.applicant, "viewer")
        self.assertEqual(response.status_code, 200)
        return json.loads(response.content)

    def test_invitation_and_approval_grant_only_creator_eligibility(self):
        self.assertEqual(self.submit().status_code, 403)
        self.assertEqual(self.invite().status_code, 201)
        self.assertEqual(self.invite().status_code, 200)
        self.assertEqual(self.submit().status_code, 201)
        self.assertEqual(self.submit().status_code, 200)
        self.assertFalse(self.eligibility()["upload_eligible"])
        queue = self.call("pending", self.reviewer, "moderator", {"cursor": None})
        self.assertEqual(json.loads(queue.content)["items"][0]["account_id"], str(self.applicant))
        decision = {"account_id": str(self.applicant), "decision": "approved"}
        self.assertEqual(self.call("review", self.applicant, "moderator", decision).status_code, 403)
        self.assertEqual(self.call("review", self.reviewer, "moderator", decision).status_code, 200)
        self.assertEqual(self.call("review", self.reviewer, "moderator", decision).status_code, 200)
        application = CreatorApplication.objects.get()
        self.assertEqual(application.invited_by, self.reviewer)
        self.assertEqual(application.reviewed_by, self.reviewer)
        self.assertIsNotNone(application.reviewed_at)
        self.assertTrue(self.eligibility()["upload_eligible"])

        profile = CreatorProfile.objects.get()
        profile.status = CreatorProfile.Status.SUSPENDED
        profile.save(update_fields=["status"])
        self.assertEqual(self.eligibility(), {"upload_eligible": False, "creator_id": None})

    def test_denies_unauthorized_review_and_requires_both_attestations(self):
        data = {"account_id": str(self.applicant)}
        self.assertEqual(self.call("invite", self.reviewer, "viewer", data).status_code, 403)
        self.assertEqual(self.call("invite", self.reviewer, "moderator", data, caller="content").status_code, 403)
        self.assertEqual(self.invite().status_code, 201)
        for field in ("adult_attested", "rights_attested"):
            response = self.call("submit", self.applicant, "viewer", self.attestations | {field: False})
            self.assertEqual(response.status_code, 400)
        self.assertFalse(CreatorProfile.objects.exists())
        self.assertEqual(self.submit().status_code, 201)
        decision = data | {"decision": "rejected"}
        self.assertEqual(self.call("review", self.reviewer, "administrator", decision).status_code, 200)
        self.assertEqual(self.call("review", self.reviewer, "administrator",
                                   decision | {"decision": "approved"}).status_code, 409)
        self.assertFalse(self.eligibility()["upload_eligible"])

    def test_legacy_public_profile_is_not_pilot_eligibility(self):
        from django.utils import timezone

        CreatorProfile.objects.create(user_id=self.applicant, handle="pilot_one", status="active",
                                      reviewed_at=timezone.now())
        self.assertFalse(self.eligibility()["upload_eligible"])
        self.assertEqual(self.invite().status_code, 201)
        self.assertEqual(self.submit().status_code, 201)
        self.assertEqual(CreatorProfile.objects.count(), 1)
