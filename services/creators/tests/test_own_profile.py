import json
from uuid import uuid4

from django.db import IntegrityError, transaction
from django.test import RequestFactory, TestCase
from django.utils import timezone

from service.models import CreatorProfile
from service.profiles import own_profile, internal_profile, internal_search


class OwnCreatorProfileTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.owner = uuid4()
        self.profile = CreatorProfile.objects.create(
            user_id=self.owner, handle="original_creator", status="active", reviewed_at=timezone.now())

    def call(self, fields=None, *, role="creator", actor=None, caller="gateway"):
        request = self.factory.post("/internal/creators/me", {
            "actor_id": str(actor or self.owner), "role": role,
            "operation": "patch" if fields is not None else "get", "data": fields if fields is not None else {},
        }, content_type="application/json")
        request.service_caller = caller
        return own_profile(request)

    def test_get_and_patch_return_only_owned_profile_and_persist_all_fields(self):
        self.assertEqual(self.call().status_code, 200)
        fields = {"handle": "new_creator", "display_name": "New Creator", "bio": "Original stories",
                  "location": "Monrovia"}
        response = self.call(fields)
        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.content)
        self.assertEqual(set(payload), {"id", "user_id", "handle", "display_name", "location", "bio", "status"})
        self.assertTrue(all(payload[name] == value for name, value in fields.items()))
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.location, "Monrovia")
        self.assertEqual(self.call(actor=uuid4()).status_code, 404)

    def test_restricted_suspended_pending_noncreator_and_other_callers_are_denied(self):
        for role in ("viewer", "moderator", "administrator"):
            self.assertEqual(self.call(role=role).status_code, 403)
        self.assertEqual(self.call(caller="content").status_code, 403)
        for status in ("restricted", "suspended", "pending"):
            CreatorProfile.objects.filter(pk=self.profile.pk).update(status=status)
            self.assertEqual(self.call().status_code, 403)
            self.assertEqual(self.call({"display_name": "Changed"}).status_code, 403)

    def test_strict_limits_partial_updates_and_client_controlled_status_are_rejected(self):
        for fields in ({}, {"handle": "ab"}, {"handle": "UPPER"}, {"handle": "with-hyphen"},
                       {"handle": "a" * 31}, {"display_name": "x" * 81}, {"bio": "x" * 501},
                       {"location": "x" * 81}, {"status": "active"}, {"user_id": str(uuid4())},
                       {"bio": None}):
            with self.subTest(fields=fields):
                self.assertEqual(self.call(fields).status_code, 400)
        self.assertEqual(self.call({"display_name": "x" * 80, "bio": "x" * 500, "location": "x" * 80}).status_code, 200)
        self.assertEqual(self.call({"handle": "a" * 30}).status_code, 200)

    def test_handle_conflicts_are_case_insensitive_in_http_and_database(self):
        CreatorProfile.objects.create(user_id=uuid4(), handle="Taken_Name")
        response = self.call({"handle": "taken_name"})
        self.assertEqual(response.status_code, 409)
        self.assertEqual(json.loads(response.content)["code"], "handle_taken")
        with self.assertRaises(IntegrityError), transaction.atomic():
            CreatorProfile.objects.create(user_id=uuid4(), handle="taken_name")
        self.assertEqual(self.call({"handle": self.profile.handle}).status_code, 200)

    def test_public_detail_and_search_include_names_and_locations(self):
        self.call({"display_name": "Coastal storyteller", "location": "Buchanan"})
        request = self.factory.post("/internal/creators/profile", {"creator_id": str(self.profile.id)},
                                    content_type="application/json")
        data = json.loads(internal_profile(request).content)
        self.assertEqual((data["display_name"], data["location"]), ("Coastal storyteller", "Buchanan"))
        request = self.factory.post("/internal/creators/search", {"q": "storyteller"}, content_type="application/json")
        self.assertEqual(json.loads(internal_search(request).content)["items"][0]["id"], str(self.profile.id))
