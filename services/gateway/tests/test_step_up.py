"""Decision G at the edge: the Gateway obtains and consumes Identity step-up proofs; it never decides them."""
import json
import secrets
from unittest.mock import patch
from uuid import uuid4

from django.http import JsonResponse
from django.test import RequestFactory, SimpleTestCase

from service import accounts
from service.business import business_endpoint
from .test_videos import Response

ACTOR = str(uuid4())
BUSINESS = str(uuid4())
MEMBER = str(uuid4())
PROOF = "p" * 64
PASSWORD = secrets.token_urlsafe(16)


class NoContent(Response):
    status = 204


def identity_ok(path, payload, statuses):
    return JsonResponse({"account_id": ACTOR, "purpose": payload["purpose"], "resource_id": payload["resource_id"]})


class StepUpIssueTests(SimpleTestCase):
    def post(self, body, token="t" * 40):
        headers = {"HTTP_AUTHORIZATION": f"Bearer {token}"} if token else {}
        return accounts.step_up(RequestFactory().post("/api/v1/me/step-up", json.dumps(body),
                                                      content_type="application/json", **headers))

    @patch("service.accounts._invoke")
    def test_the_request_is_bounded_and_forwarded_with_the_callers_token(self, identity):
        identity.return_value = JsonResponse({"step_up_token": PROOF, "purpose": "business.member_remove",
                                              "expires_at": "2026-11-25T16:00:00+00:00"})
        response = self.post({"current_password": PASSWORD, "purpose": "business.member_remove", "resource_id": BUSINESS})
        self.assertEqual(response.status_code, 200)
        path, payload, _ = identity.call_args.args
        self.assertEqual(path, "/internal/auth/step-up")
        self.assertEqual(payload, {"access_token": "t" * 40, "current_password": PASSWORD,
                                   "purpose": "business.member_remove", "resource_id": BUSINESS})

    @patch("service.accounts._invoke")
    def test_malformed_requests_and_answers_never_pass(self, identity):
        self.assertEqual(self.post({"current_password": PASSWORD, "purpose": "x.y"}, token=None).status_code, 401)
        for body in ({"purpose": "business.member_remove"}, {"current_password": PASSWORD},
                     {"current_password": PASSWORD, "purpose": "business.member_remove", "resource_id": "nope"},
                     {"current_password": PASSWORD, "purpose": "business.member_remove", "audience": "finance"}):
            with self.subTest(body):
                self.assertEqual(self.post(body).status_code, 400)
        identity.assert_not_called()
        identity.return_value = JsonResponse({"step_up_token": PROOF, "purpose": "other.purpose",
                                              "expires_at": "2026-11-25T16:00:00+00:00"})
        self.assertEqual(self.post({"current_password": PASSWORD, "purpose": "business.member_remove"}).status_code, 503)


class BusinessStepUpTests(SimpleTestCase):
    def call(self, operations, method, headers, **ids):
        request = RequestFactory().generic(method, "/api/v1/x", "", content_type="application/json",
                                           HTTP_AUTHORIZATION="Bearer " + "t" * 40, **headers)
        return business_endpoint(request, operations, **ids)

    @patch("service.business.signed_internal_request")
    @patch("service.business._invoke", side_effect=identity_ok)
    @patch("service.business.authenticated_actor", return_value=(ACTOR, "viewer"))
    def test_a_proof_is_consumed_for_the_business_in_the_path_and_attested(self, actor, identity, peer):
        peer.return_value = NoContent(b"")
        response = self.call({"DELETE": "member_remove"}, "DELETE", {"HTTP_X_STEP_UP_TOKEN": PROOF,
                                                                    "HTTP_IDEMPOTENCY_KEY": "k" * 20},
                             business_id=BUSINESS, member_id=MEMBER)
        self.assertEqual(response.status_code, 204)
        path, payload, _ = identity.call_args.args
        self.assertEqual(path, "/internal/auth/step-up/consume")
        self.assertEqual(payload, {"access_token": "t" * 40, "step_up_token": PROOF, "purpose": "business.member_remove",
                                   "audience": "business", "resource_id": BUSINESS})
        envelope = json.loads(peer.call_args.kwargs["payload"])
        self.assertEqual(envelope["step_up"], {"purpose": "business.member_remove", "resource_id": BUSINESS})

    @patch("service.business.signed_internal_request")
    @patch("service.business._invoke")
    @patch("service.business.authenticated_actor", return_value=(ACTOR, "viewer"))
    def test_without_a_proof_nothing_is_attested_and_identity_is_not_asked(self, actor, identity, peer):
        peer.return_value = NoContent(b"")
        self.call({"DELETE": "member_remove"}, "DELETE", {"HTTP_IDEMPOTENCY_KEY": "k" * 20},
                  business_id=BUSINESS, member_id=MEMBER)
        identity.assert_not_called()
        self.assertIsNone(json.loads(peer.call_args.kwargs["payload"])["step_up"])

    @patch("service.business.signed_internal_request")
    @patch("service.business._invoke")
    @patch("service.business.authenticated_actor", return_value=(ACTOR, "viewer"))
    def test_a_refused_foreign_or_misplaced_proof_never_reaches_the_service(self, actor, identity, peer):
        identity.return_value = JsonResponse({"detail": "Step-up required"}, status=403)
        response = self.call({"DELETE": "member_remove"}, "DELETE", {"HTTP_X_STEP_UP_TOKEN": PROOF},
                             business_id=BUSINESS, member_id=MEMBER)
        self.assertEqual((response.status_code, json.loads(response.content)["detail"]), (403, "Step-up required"))
        identity.side_effect = lambda path, payload, statuses: JsonResponse(
            {"account_id": str(uuid4()), "purpose": payload["purpose"], "resource_id": payload["resource_id"]})
        self.assertEqual(self.call({"DELETE": "member_remove"}, "DELETE", {"HTTP_X_STEP_UP_TOKEN": PROOF},
                                   business_id=BUSINESS, member_id=MEMBER).status_code, 403)  # someone else's proof
        identity.side_effect = None
        self.assertEqual(self.call({"GET": "member_list"}, "GET", {"HTTP_X_STEP_UP_TOKEN": PROOF},
                                   business_id=BUSINESS).status_code, 400)  # an operation that takes no proof
        self.assertEqual(self.call({"DELETE": "member_remove"}, "DELETE", {"HTTP_X_STEP_UP_TOKEN": "short"},
                                   business_id=BUSINESS, member_id=MEMBER).status_code, 400)
        identity.return_value = JsonResponse({"detail": "x"}, status=500)
        self.assertEqual(self.call({"DELETE": "member_remove"}, "DELETE", {"HTTP_X_STEP_UP_TOKEN": PROOF},
                                   business_id=BUSINESS, member_id=MEMBER).status_code, 503)
        peer.assert_not_called()
