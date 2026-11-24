"""Gateway behaviour for Business routes: authenticate, bind actor, bound, forward; no business rules here."""
import json
from unittest.mock import patch
from urllib.error import HTTPError
from uuid import uuid4

from django.http import JsonResponse
from django.test import RequestFactory, SimpleTestCase, override_settings

from service.business import OPERATIONS, business_endpoint
from service.routes import business as business_routes
from .test_videos import Response

ACTOR = str(uuid4())
KEY = "idem-key-0123456789"


class _Error(HTTPError):
    def __init__(self, code, body):
        super().__init__("https://business.internal/x", code, "e", {}, None)
        self._body = body

    def read(self, limit=-1):
        return self._body[:limit]

    def close(self):
        pass


class BusinessGatewayTests(SimpleTestCase):
    def call(self, operations, *, method="POST", body=None, query="", headers=None, **ids):
        factory = RequestFactory()
        data = json.dumps(body) if body is not None else ""
        request = factory.generic(method, "/api/v1/x" + query, data, content_type="application/json", **(headers or {}))
        return business_endpoint(request, operations, **ids)

    @patch("service.business.signed_internal_request")
    def test_anonymous_request_never_reaches_business(self, peer):
        self.assertEqual(self.call({"GET": "list_mine"}, method="GET").status_code, 401)
        peer.assert_not_called()

    @patch("service.business.signed_internal_request")
    @patch("service.business.authenticated_actor")
    def test_actor_comes_from_the_session_and_envelope_is_exact(self, actor, peer):
        actor.return_value = (ACTOR, "creator")
        peer.return_value = Response(json.dumps({"id": "x"}).encode())
        response = self.call({"POST": "register"}, body={"display_name": "Shop", "legal_name": "Shop Ltd"},
                             headers={"HTTP_IDEMPOTENCY_KEY": KEY})
        self.assertEqual(response.status_code, 200)
        actor.assert_called_once()
        self.assertIs(actor.call_args.kwargs["require_verified_email"], True)
        envelope = json.loads(peer.call_args.kwargs["payload"])
        self.assertEqual(envelope, {"actor_id": ACTOR, "role": "creator", "mfa_verified": False, "email_verified": True,
                                    "idempotency_key": KEY, "data": {"display_name": "Shop", "legal_name": "Shop Ltd"}})
        self.assertEqual(peer.call_args.args[:2], ("business", "/internal/business/register"))

    @patch("service.business.signed_internal_request")
    @patch("service.business.authenticated_actor", return_value=(ACTOR, "viewer"))
    def test_reads_do_not_demand_a_verified_email(self, actor, peer):
        peer.return_value = Response(b'{"items":[],"next_cursor":null}')
        self.assertEqual(self.call({"GET": "list_mine"}, method="GET", query="?limit=5").status_code, 200)
        self.assertIs(actor.call_args.kwargs["require_verified_email"], False)
        self.assertEqual(json.loads(peer.call_args.kwargs["payload"])["data"], {"limit": "5"})

    @patch("service.business.signed_internal_request")
    @patch("service.business.authenticated_actor", return_value=(ACTOR, "viewer"))
    def test_malformed_requests_are_refused_before_forwarding(self, actor, peer):
        bid = uuid4()
        cases = [
            dict(operations={"GET": "list_mine"}, method="GET", query="?role=admin"),
            dict(operations={"GET": "list_mine"}, method="GET", query="?limit=1&limit=2"),
            dict(operations={"GET": "get_mine"}, method="GET", body={"x": 1}, business_id=bid),
            dict(operations={"POST": "staff_invite"}, body={"business_id": str(uuid4()), "label": "x"}, business_id=bid),
            dict(operations={"POST": "register"}, body=["not", "an", "object"]),
            dict(operations={"POST": "register"}, body={"display_name": "x" * 5000}),
            dict(operations={"POST": "register"}, body={"a": 1}, headers={"HTTP_IDEMPOTENCY_KEY": "short"}),
            dict(operations={"POST": "register"}, query="?x=1", body={}),
        ]
        for case in cases:
            self.assertEqual(self.call(**case).status_code, 400, case)
        peer.assert_not_called()

    @patch("service.business.signed_internal_request")
    @patch("service.business.authenticated_actor", return_value=(ACTOR, "viewer"))
    def test_wrong_method_is_405_and_path_ids_are_bound_into_data(self, actor, peer):
        self.assertEqual(self.call({"GET": "get_mine"}, method="POST", business_id=uuid4()).status_code, 405)
        peer.return_value = Response(b'{"status":"ok"}')
        bid = uuid4()
        self.call({"POST": "member_leave"}, body={}, headers={"HTTP_IDEMPOTENCY_KEY": KEY}, business_id=bid)
        self.assertEqual(json.loads(peer.call_args.kwargs["payload"])["data"], {"business_id": str(bid)})

    @patch("service.business.signed_internal_request")
    @patch("service.business.authenticated_actor", return_value=(ACTOR, "viewer"))
    def test_upstream_refusals_pass_through_only_as_bounded_detail(self, actor, peer):
        for code in (400, 403, 404, 409, 429):
            peer.side_effect = _Error(code, b'{"detail":"Not found"}')
            response = self.call({"GET": "get_mine"}, method="GET", business_id=uuid4())
            self.assertEqual((response.status_code, json.loads(response.content)), (code, {"detail": "Not found"}))
        peer.side_effect = _Error(409, b'{"detail":"Limit","code":"business_limit"}')
        self.assertEqual(json.loads(self.call({"GET": "get_mine"}, method="GET", business_id=uuid4()).content)["code"],
                         "business_limit")
        for bad in (b'{"detail":"x","stack":"trace"}', b'{"detail":5}', b"not json", b'{"detail":"' + b"x" * 600 + b'"}'):
            peer.side_effect = _Error(404, bad)
            self.assertEqual(self.call({"GET": "get_mine"}, method="GET", business_id=uuid4()).status_code, 503)
        for failure in (_Error(500, b"{}"), OSError("down"), RuntimeError("no key")):
            peer.side_effect = failure
            self.assertEqual(self.call({"GET": "get_mine"}, method="GET", business_id=uuid4()).status_code, 503)

    @patch("service.business.signed_internal_request")
    @patch("service.business.authenticated_actor", return_value=(ACTOR, "viewer"))
    def test_non_object_or_oversized_success_bodies_are_not_passed_on(self, actor, peer):
        for payload in (b"[1]", b'"x"', b"x" * 70000, b"not json"):
            peer.side_effect = None
            peer.return_value = Response(payload)
            self.assertEqual(self.call({"GET": "get_mine"}, method="GET", business_id=uuid4()).status_code, 503)

    @patch("service.business.signed_internal_request")
    @patch("service.business.principal")
    def test_grant_route_requires_the_existing_privileged_mfa_gate(self, principal, peer):
        principal.return_value = JsonResponse({"detail": "Forbidden"}, status=403)
        response = self.call({"PUT": "registration_grant"}, method="PUT", body={"active": True}, account_id=uuid4(),
                             headers={"HTTP_IDEMPOTENCY_KEY": KEY})
        self.assertEqual(response.status_code, 403)
        peer.assert_not_called()
        principal.return_value = (ACTOR, "administrator")
        peer.return_value = Response(b'{"account_id":"a","active":true}')
        self.call({"PUT": "registration_grant"}, method="PUT", body={"active": True}, account_id=uuid4(),
                  headers={"HTTP_IDEMPOTENCY_KEY": KEY})
        self.assertIs(json.loads(peer.call_args.kwargs["payload"])["mfa_verified"], True)

    def test_every_operation_is_routed_and_routes_are_closed_without_the_flag(self):
        with override_settings(ENVIRONMENT="local", LOCAL_BUSINESS_ENABLED=True):
            routed = {op for pattern in business_routes.patterns() for op in pattern.default_args["operations"].values()}
        self.assertEqual(routed, set(OPERATIONS))
        with override_settings(ENVIRONMENT="local", LOCAL_BUSINESS_ENABLED=False):
            self.assertEqual(business_routes.patterns(), [])
        with override_settings(ENVIRONMENT="staging", STAGING_CAPABILITIES=frozenset()):
            self.assertEqual(business_routes.patterns(), [])
