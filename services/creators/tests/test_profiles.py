import json
import uuid

from django.db import IntegrityError, transaction
from django.test import RequestFactory, TestCase
from django.urls import reverse
from django.utils import timezone

from service.models import CreatorProfile
from service.profiles import internal_profile


class PublicCreatorTests(TestCase):
    def test_only_reviewed_active_profile_is_public(self):
        profile = CreatorProfile.objects.create(user_id=uuid.uuid4(), handle="original-voice")
        request = RequestFactory().post("/internal/creators/profile",
            json.dumps({"creator_id": str(profile.id)}), content_type="application/json")
        self.assertEqual(internal_profile(request).status_code, 404)
        self.assertEqual(self.client.post(reverse("internal-profile"),
            data=json.dumps({"creator_id": str(profile.id)}),
            content_type="application/json").status_code, 403)
        profile.reviewed_at = timezone.now()
        profile.status = CreatorProfile.Status.ACTIVE
        profile.save(update_fields=["reviewed_at", "status"])
        result = json.loads(internal_profile(request).content)
        self.assertEqual(result["handle"], "original-voice")
        self.assertEqual(result["status"], "active")

    def test_database_rejects_unreviewed_active_profile(self):
        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                CreatorProfile.objects.create(user_id=uuid.uuid4(), handle="unreviewed",
                    status=CreatorProfile.Status.ACTIVE)

    def test_invalid_identifier_is_rejected(self):
        request = RequestFactory().post("/internal/creators/profile",
            json.dumps({"creator_id": "bad"}), content_type="application/json")
        self.assertEqual(internal_profile(request).status_code, 400)
