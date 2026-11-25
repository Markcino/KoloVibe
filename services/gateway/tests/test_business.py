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
                                    "idempotency_key": KEY, "origin": None, "step_up": None,
                                    "data": {"display_name": "Shop", "legal_name": "Shop Ltd"}})
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
    def test_a_client_cannot_put_authority_into_the_signed_envelope(self, actor, peer):
        """The envelope's actor, role, MFA and email flags come from the session; a body can only add to `data`."""
        peer.return_value = Response(b'{"id":"x"}')
        forged = {"actor_id": str(uuid4()), "role": "administrator", "mfa_verified": True, "email_verified": True,
                  "idempotency_key": "forged-key-0123456789", "origin": "10.0.0.1", "data": {"x": 1}}
        self.call({"POST": "register"}, body={"display_name": "Shop", **forged}, headers={"HTTP_IDEMPOTENCY_KEY": KEY})
        envelope = json.loads(peer.call_args.kwargs["payload"])
        self.assertEqual((envelope["actor_id"], envelope["role"], envelope["mfa_verified"], envelope["idempotency_key"], envelope["origin"]),
                         (ACTOR, "viewer", False, KEY, None))
        self.assertEqual(set(envelope), {"actor_id", "role", "mfa_verified", "email_verified", "idempotency_key", "origin", "data", "step_up"})
        self.assertEqual(envelope["data"]["role"], "administrator")  # carried as data, where the service refuses the field (400)

    @patch("service.business.signed_internal_request")
    @patch("service.business.authenticated_actor", return_value=(ACTOR, "viewer"))
    def test_bodies_that_are_not_one_small_json_object_never_reach_the_service(self, actor, peer):
        factory = RequestFactory()
        for content_type, body in (("multipart/form-data; boundary=x", b"--x\r\nContent-Disposition: form-data; name=f; filename=a.png\r\n\r\nPNG\r\n--x--"),
                                   ("image/png", b"\x89PNG\r\n\x1a\n"), ("application/json", b"\xff\xfe not utf-8"),
                                   ("application/json", b'{"a":' + b"1" * 5000 + b"}"), ("application/json", b"[]"),
                                   ("application/json", b"null"), ("text/plain", b"display_name=x")):
            request = factory.generic("POST", "/api/v1/x", body, content_type=content_type, HTTP_IDEMPOTENCY_KEY=KEY)
            self.assertEqual(business_endpoint(request, {"POST": "register"}).status_code, 400, content_type)
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

    @patch("service.business.signed_internal_request")
    @patch("service.business._invoke")
    def test_public_routes_are_anonymous_without_a_credential_and_never_call_identity(self, identity, peer):
        peer.return_value = Response(b'{"items":[],"next_cursor":null}')
        response = self.call({"GET": "public_search"}, method="GET", query="?q=bakery&open_now=true")
        self.assertEqual(response.status_code, 200)
        identity.assert_not_called()
        envelope = json.loads(peer.call_args.kwargs["payload"])
        self.assertEqual((envelope["actor_id"], envelope["role"], envelope["mfa_verified"], envelope["email_verified"]),
                         ("00000000-0000-0000-0000-000000000000", "anonymous", False, False))
        self.assertEqual(envelope["data"], {"q": "bakery", "open_now": "true"})

    @patch("service.business.signed_internal_request")
    @patch("service.business._invoke")
    def test_a_present_but_invalid_credential_is_never_downgraded_to_anonymous(self, identity, peer):
        identity.return_value = JsonResponse({"detail": "Unauthorized"}, status=401)
        for headers in ({"HTTP_AUTHORIZATION": "Bearer " + uuid4().hex}, {"HTTP_AUTHORIZATION": "Basic abc"},
                        {"HTTP_AUTHORIZATION": "Bearer "}):
            response = self.call({"GET": "public_detail"}, method="GET", headers=headers, business_id=uuid4())
            self.assertEqual(response.status_code, 401, headers)
        peer.assert_not_called()

    @patch("service.business.signed_internal_request")
    @patch("service.business._invoke")
    def test_a_valid_credential_carries_the_verified_email_flag_from_one_identity_call(self, identity, peer):
        account = str(uuid4())
        user = {"id": account, "email": "a@example.test", "display_name": "A", "created_at": "2026-11-10T00:00:00Z",
                "roles": ["viewer"]}
        peer.return_value = Response(b'{"id":"x"}')
        for verified in (True, False):
            identity.return_value = JsonResponse({"user": user, "email_verified": verified})
            self.call({"GET": "public_detail"}, method="GET", headers={"HTTP_AUTHORIZATION": "Bearer " + uuid4().hex},
                      business_id=uuid4())
            envelope = json.loads(peer.call_args.kwargs["payload"])
            self.assertEqual((envelope["actor_id"], envelope["role"], envelope["email_verified"]), (account, "viewer", verified))
        self.assertEqual(identity.call_args.args[1]["include_email_verification"], True)
        identity.return_value = JsonResponse({"user": {**user, "roles": ["viewer", "creator"]}, "email_verified": True})
        self.assertEqual(self.call({"GET": "public_detail"}, method="GET", headers={"HTTP_AUTHORIZATION": "Bearer " + uuid4().hex},
                                   business_id=uuid4()).status_code, 503)

    @patch("service.business.signed_internal_request")
    def test_client_address_is_forwarded_only_when_the_edge_vouches_for_it(self, peer):
        peer.return_value = Response(b'{"items":[],"next_cursor":null}')
        headers = {"HTTP_CF_CONNECTING_IP": "203.0.113.9"}
        self.call({"GET": "public_search"}, method="GET", headers=headers)
        self.assertIsNone(json.loads(peer.call_args.kwargs["payload"])["origin"])
        with override_settings(KOLOVIBE_TRUSTED_CLIENT_IP_HEADER="CF-Connecting-IP"):
            self.call({"GET": "public_search"}, method="GET", headers=headers)
            self.assertEqual(json.loads(peer.call_args.kwargs["payload"])["origin"], "203.0.113.9")
            self.call({"GET": "public_search"}, method="GET", headers={"HTTP_CF_CONNECTING_IP": "not-an-ip"})
            self.assertIsNone(json.loads(peer.call_args.kwargs["payload"])["origin"])

    @patch("service.business.signed_internal_request")
    def test_public_routes_still_bound_their_input(self, peer):
        for case in (dict(query="?lat=6.3"), dict(query="?q=a&q=b"), dict(body={"x": 1})):
            self.assertEqual(self.call({"GET": "public_search"}, method="GET", **case).status_code, 400, case)
        peer.assert_not_called()

    def test_every_operation_is_routed_and_routes_are_closed_without_the_flag(self):
        with override_settings(ENVIRONMENT="local", LOCAL_BUSINESS_ENABLED=True):
            routed = {op for pattern in business_routes.patterns() for op in pattern.default_args["operations"].values()}
        self.assertEqual(routed, set(OPERATIONS))
        with override_settings(ENVIRONMENT="local", LOCAL_BUSINESS_ENABLED=False):
            self.assertEqual(business_routes.patterns(), [])
        with override_settings(ENVIRONMENT="staging", STAGING_CAPABILITIES=frozenset()):
            self.assertEqual(business_routes.patterns(), [])
