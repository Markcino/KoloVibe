import json
from uuid import uuid4
from django.test import RequestFactory, TestCase
from django.utils import timezone
from service.models import CreatorApplication, CreatorProfile
from service.onboarding import onboarding, POLICY_VERSION


class CreatorStandingTests(TestCase):
    def setUp(self): self.actor = uuid4()

    def call(self, actor=None, caller="gateway"):
        request = RequestFactory().post("/internal/creators/onboarding/standing",
                  {"actor_id": str(actor or self.actor), "role": "creator", "data": {}}, content_type="application/json")
        request.service_caller = caller
        return onboarding(request, "standing")

    def test_standing_includes_restricted_suspended_and_actual_publishing_eligibility(self):
        profile = CreatorProfile.objects.create(user_id=self.actor, handle="standing_creator", status="active", reviewed_at=timezone.now())
        self.assertFalse(json.loads(self.call().content)["publishing_allowed"])
        CreatorApplication.objects.create(account_id=self.actor, invited_by=uuid4(), profile=profile,
                      status="approved", attestation_version=POLICY_VERSION)
        self.assertTrue(json.loads(self.call().content)["publishing_allowed"])
        for status in ("restricted", "suspended"):
            profile.status = status
            profile.save(update_fields=["status"])
            result = json.loads(self.call().content)
            self.assertEqual((result["creator_status"], result["creator_id"], result["publishing_allowed"]), (status, str(profile.id), False))

    def test_absent_profile_has_null_status_and_cannot_read_foreign_account(self):
        CreatorProfile.objects.create(user_id=uuid4(), handle="foreign_standing")
        self.assertEqual(json.loads(self.call().content), {"creator_id": None, "creator_status": None, "publishing_allowed": False})
        self.assertEqual(self.call(caller="moderation").status_code, 403)
