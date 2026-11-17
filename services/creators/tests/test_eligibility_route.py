"""Staging `media` capability: only the exact eligibility route is registered, never the other operations."""
import importlib
import json
from uuid import uuid4

from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings
from django.urls import Resolver404, resolve

from service import urls as service_urls
from service.models import CreatorApplication, CreatorProfile
from service.onboarding import POLICY_VERSION, eligibility, ownership

BASE = "/internal/creators/onboarding/"
OTHERS = ("invite", "review", "pending", "submit", "status", "standing")


def staging_urls(**settings_values):
    """Re-evaluate the URL table as a staging service (not `local`) with the given settings."""
    with override_settings(ENVIRONMENT="staging", **settings_values):
        return importlib.reload(service_urls)


class RouteRegistrationTests(SimpleTestCase):
    def tearDown(self):
        importlib.reload(service_urls)  # restore the local table for other tests

    def names(self, module):
        return {p.name for p in module.urlpatterns}

    def test_media_registers_only_the_exact_eligibility_and_ownership_routes(self):
        module = staging_urls(STAGING_CAPABILITIES=frozenset({"media"}), STAGING_CREATOR_ONBOARDING=False)
        self.assertIn("internal-eligibility", self.names(module))
        self.assertIn("internal-ownership", self.names(module))
        self.assertNotIn("internal-onboarding", self.names(module))
        with override_settings(ROOT_URLCONF=module):
            self.assertEqual(resolve(BASE + "eligibility").url_name, "internal-eligibility")
            self.assertEqual(resolve(BASE + "ownership").url_name, "internal-ownership")
            for operation in OTHERS + ("", "eligibility/", "eligibility2", "Eligibility", "ownership/",
                                       "ownership2", "Ownership", "ownership/x"):
                with self.subTest(operation=operation), self.assertRaises(Resolver404):
                    resolve(BASE + operation)

    def test_no_media_no_onboarding_registers_nothing(self):
        for caps in (frozenset(), frozenset({"points"})):
            module = staging_urls(STAGING_CAPABILITIES=caps, STAGING_CREATOR_ONBOARDING=False)
            with self.subTest(caps=caps), override_settings(ROOT_URLCONF=module):
                self.assertFalse({"internal-eligibility", "internal-ownership", "internal-onboarding"}
                                 & self.names(module))
                for operation in ("eligibility", "ownership"):
                    with self.assertRaises(Resolver404):
                        resolve(BASE + operation)

    def test_approved_onboarding_keeps_its_full_route(self):
        for caps in (frozenset(), frozenset({"media"})):
            module = staging_urls(STAGING_CAPABILITIES=caps, STAGING_CREATOR_ONBOARDING=True)
            with self.subTest(caps=caps), override_settings(ROOT_URLCONF=module):
                self.assertIn("internal-onboarding", self.names(module))
                self.assertFalse({"internal-eligibility", "internal-ownership"} & self.names(module))
                for operation in OTHERS + ("eligibility", "ownership"):
                    self.assertEqual(resolve(BASE + operation).url_name, "internal-onboarding")


class EligibilityHandlerTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.account = uuid4()

    def call(self, role="creator", caller="gateway", method="post", body=None):
        body = {"actor_id": str(self.account), "role": role, "data": {}} if body is None else body
        request = self.factory.generic(method.upper(), BASE + "eligibility", json.dumps(body),
                                       content_type="application/json")
        if caller is not None:
            request.service_caller = caller
        return eligibility(request)

    def make(self, application_status="approved", **profile_extra):
        profile_fields = dict(user_id=self.account, handle="pilot_one", display_name="p",
                              status=CreatorProfile.Status.ACTIVE, reviewed_at="2026-01-01T00:00:00Z")
        profile_fields.update(profile_extra)
        profile = CreatorProfile.objects.create(**profile_fields)
        return CreatorApplication.objects.create(account_id=self.account, invited_by=uuid4(), profile=profile, status=application_status,
                                                 attestation_version=POLICY_VERSION)

    def test_approved_creator_is_eligible(self):
        application = self.make()
        response = self.call()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(response.content),
                         {"upload_eligible": True, "creator_id": str(application.profile_id)})

    def test_viewer_role_is_accepted_like_the_onboarding_handler(self):
        self.make()
        self.assertEqual(self.call(role="viewer").status_code, 200)

    def test_unapproved_or_missing_creators_are_not_eligible(self):
        self.assertEqual(json.loads(self.call().content), {"upload_eligible": False, "creator_id": None})
        for status in ("invited", "pending", "rejected"):
            CreatorApplication.objects.all().delete()
            CreatorProfile.objects.all().delete()
            self.make(application_status=status)
            with self.subTest(status=status):
                self.assertEqual(json.loads(self.call().content), {"upload_eligible": False, "creator_id": None})

    def test_dec004_conditions_each_deny(self):
        cases = {
            "restricted": dict(status=CreatorProfile.Status.SUSPENDED, restricted_at="2026-01-02T00:00:00Z"),
            "suspended": dict(status=CreatorProfile.Status.SUSPENDED),
            "pending profile": dict(status=CreatorProfile.Status.PENDING, reviewed_at=None),
        }
        for label, extra in cases.items():
            CreatorApplication.objects.all().delete()
            CreatorProfile.objects.all().delete()
            self.make(**extra)
            with self.subTest(label):
                self.assertFalse(json.loads(self.call().content)["upload_eligible"])
        CreatorApplication.objects.all().delete()
        CreatorProfile.objects.all().delete()
        self.make()
        CreatorApplication.objects.update(attestation_version="old")
        self.assertFalse(json.loads(self.call().content)["upload_eligible"])

    def test_only_the_gateway_service_caller_is_accepted(self):
        self.make()
        for caller in (None, "", "moderation", "identity", "content"):
            with self.subTest(caller=caller):
                self.assertEqual(self.call(caller=caller).status_code, 403)

    def test_invalid_roles_are_forbidden(self):
        self.make()
        for role in ("moderator", "administrator", "root", ""):
            with self.subTest(role=role):
                self.assertEqual(self.call(role=role).status_code, 403)
        self.assertEqual(self.call(role=7).status_code, 400)

    def test_envelope_is_validated(self):
        actor = str(self.account)
        for body in ({"actor_id": actor, "role": "creator"},
                     {"actor_id": actor, "role": "creator", "data": {"x": 1}},
                     {"actor_id": actor, "role": "creator", "data": {}, "extra": 1},
                     {"actor_id": "nope", "role": "creator", "data": {}},
                     {"actor_id": actor, "role": "creator", "data": []}, []):
            with self.subTest(body=body):
                self.assertEqual(self.call(body=body).status_code, 400)

    def test_only_post_is_allowed(self):
        for method in ("get", "put", "patch", "delete"):
            with self.subTest(method=method):
                self.assertEqual(self.call(method=method).status_code, 405)

    def test_operation_cannot_be_chosen_by_the_caller(self):
        """The pinned view ignores any operation smuggled in the body; the envelope has no such field."""
        self.make()
        body = {"actor_id": str(self.account), "role": "creator", "data": {}, "operation": "invite"}
        self.assertEqual(self.call(body=body).status_code, 400)


class OwnershipHandlerTests(TestCase):
    """The pinned ownership view: the account is the envelope's authenticated actor, nothing else."""

    def setUp(self):
        self.factory = RequestFactory()
        self.account = uuid4()

    def call(self, role="creator", caller="gateway", method="post", body=None):
        body = {"actor_id": str(self.account), "role": role, "data": {}} if body is None else body
        request = self.factory.generic(method.upper(), BASE + "ownership", json.dumps(body),
                                       content_type="application/json")
        if caller is not None:
            request.service_caller = caller
        return ownership(request)

    def profile(self, user_id=None, **extra):
        fields = dict(user_id=user_id or self.account, handle=f"h{uuid4().hex[:8]}", display_name="p")
        fields.update(extra)
        return CreatorProfile.objects.create(**fields)

    def test_owner_gets_their_own_creator_id(self):
        profile = self.profile(status=CreatorProfile.Status.ACTIVE, reviewed_at="2026-01-01T00:00:00Z")
        response = self.call()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(response.content), {"creator_id": str(profile.id)})

    def test_viewer_and_creator_roles_are_accepted(self):
        self.profile()
        for role in ("viewer", "creator"):
            with self.subTest(role=role):
                self.assertEqual(self.call(role=role).status_code, 200)

    def test_another_accounts_profile_is_never_returned(self):
        other = self.profile(user_id=uuid4())
        mine = self.profile()
        self.assertEqual(json.loads(self.call().content), {"creator_id": str(mine.id)})
        self.assertNotEqual(str(other.id), str(mine.id))

    def test_missing_profile_is_not_found(self):
        self.profile(user_id=uuid4())
        response = self.call()
        self.assertEqual(response.status_code, 404)
        self.assertEqual(json.loads(response.content), {"detail": "Creator profile not found"})

    def test_client_supplied_account_id_is_rejected(self):
        other = self.profile(user_id=uuid4())
        self.profile()
        body = {"actor_id": str(self.account), "role": "creator", "data": {"account_id": str(other.user_id)}}
        self.assertEqual(self.call(body=body).status_code, 400)
        body = {"actor_id": str(self.account), "role": "creator", "data": {}, "account_id": str(other.user_id)}
        self.assertEqual(self.call(body=body).status_code, 400)

    def test_invalid_roles_are_forbidden(self):
        self.profile()
        for role in ("moderator", "administrator", "root", ""):
            with self.subTest(role=role):
                self.assertEqual(self.call(role=role).status_code, 403)
        self.assertEqual(self.call(role=7).status_code, 400)

    def test_only_the_gateway_service_caller_is_accepted(self):
        self.profile()
        for caller in (None, "", "moderation", "identity", "content"):
            with self.subTest(caller=caller):
                self.assertEqual(self.call(caller=caller).status_code, 403)

    def test_envelope_is_validated(self):
        actor = str(self.account)
        for body in ({"actor_id": actor, "role": "creator"}, {"actor_id": "nope", "role": "creator", "data": {}},
                     {"actor_id": actor, "role": "creator", "data": []}, []):
            with self.subTest(body=body):
                self.assertEqual(self.call(body=body).status_code, 400)

    def test_only_post_is_allowed(self):
        for method in ("get", "put", "patch", "delete"):
            with self.subTest(method=method):
                self.assertEqual(self.call(method=method).status_code, 405)

    def test_operation_cannot_be_chosen_by_the_caller(self):
        self.profile()
        body = {"actor_id": str(self.account), "role": "creator", "data": {}, "operation": "invite"}
        self.assertEqual(self.call(body=body).status_code, 400)
