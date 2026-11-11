import json
import uuid

from django.db import IntegrityError, transaction
from django.test import RequestFactory, TestCase
from django.urls import reverse
from django.utils import timezone

from service.models import CreatorProfile
from service.profiles import internal_profile, internal_search


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


    def test_search_filters_profiles_and_paginates(self):
        for index in range(21):
            CreatorProfile.objects.create(
                id=uuid.UUID(int=index + 1), user_id=uuid.uuid4(),
                handle=f"river-{index}", status=CreatorProfile.Status.ACTIVE,
                reviewed_at=timezone.now(),
            )
        CreatorProfile.objects.create(user_id=uuid.uuid4(), handle="river-pending")
        CreatorProfile.objects.create(
            user_id=uuid.uuid4(), handle="river-restricted",
            status=CreatorProfile.Status.RESTRICTED, restricted_at=timezone.now(),
            reviewed_at=timezone.now(),
        )

        def search(data):
            request = RequestFactory().post("/internal/creators/search",
                json.dumps(data), content_type="application/json")
            return internal_search(request)

        first = json.loads(search({"q": "RIVER"}).content)
        self.assertEqual(len(first["items"]), 20)
        second = json.loads(search({"q": "river", "cursor": first["next_cursor"]}).content)
        self.assertEqual([item["handle"] for item in second["items"]], ["river-20"])
        self.assertIsNone(second["next_cursor"])
        self.assertEqual(search({"q": "ocean", "cursor": first["next_cursor"]}).status_code, 400)
        self.assertEqual(self.client.post(reverse("internal-search"),
            data=json.dumps({"q": "river"}), content_type="application/json").status_code, 403)
