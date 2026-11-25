"""Decision B at the edge: public legal texts, signed-in acceptance and marketing consent, strict shapes both ways."""
import hashlib
import json
import secrets
from unittest.mock import patch

from django.http import JsonResponse
from django.test import RequestFactory, SimpleTestCase

from service import legal

TEXT = "# Terms\n\nDRAFT. PENDING LEGAL REVIEW."
SHA = hashlib.sha256(TEXT.encode()).hexdigest()


def summary(kind, **extra):
    return {"kind": kind, "title": kind.title(), "version": "2026-11-25", "effective_at": "2026-11-25",
            "status": "pending_legal_review", "sha256": SHA, **extra}


STATE = {"documents": [summary("terms", accepted_version=None, accepted_at=None),
                       summary("privacy", accepted_version="2026-11-25", accepted_at="2026-11-25T10:00:00+00:00")],
         "acceptance_required": True,
         "marketing": {"granted": False, "version": "2026-11-25", "updated_at": None}}


class LegalGatewayTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def call(self, view, method, body=None, token="t" * 40, **kwargs):
        headers = {"HTTP_AUTHORIZATION": f"Bearer {token}"} if token else {}
        request = getattr(self.factory, method)("/api/v1/x", json.dumps(body) if body is not None else None,
                                                content_type="application/json", **headers)
        return view(request, **kwargs)

    def test_a_document_is_public_cacheable_and_checked(self):
        with patch.object(legal, "_invoke", return_value=JsonResponse({**summary("terms"), "text": TEXT})) as invoke:
            response = self.call(legal.document, "get", token=None, kind="terms")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(invoke.call_args.args[:2], ("/internal/auth/legal/document", {"kind": "terms"}))
        self.assertIn("public", response["Cache-Control"])
        self.assertEqual(self.call(legal.document, "get", token=None, kind="cookies").status_code, 404)

    def test_an_unexpected_document_answer_is_never_passed_on(self):
        for bad in ({**summary("privacy"), "text": TEXT}, {**summary("terms"), "text": ""},
                    {**summary("terms"), "text": TEXT, "extra": 1}, {**summary("terms", status="final"), "text": TEXT},
                    {**summary("terms", sha256="x"), "text": TEXT}):
            with self.subTest(bad), patch.object(legal, "_invoke", return_value=JsonResponse(bad)):
                self.assertEqual(self.call(legal.document, "get", token=None, kind="terms").status_code, 503)

    def test_state_and_acceptance_need_a_session_and_strict_bodies(self):
        with patch.object(legal, "_invoke", return_value=JsonResponse(STATE)) as invoke:
            self.assertEqual(self.call(legal.acceptance, "get").status_code, 200)
            self.assertEqual(invoke.call_args.args[1], {"access_token": "t" * 40, "operation": "get"})
            ok = self.call(legal.acceptance, "post", {"accepted": {"terms": "2026-11-25"}})
            self.assertEqual(ok.status_code, 200)
            self.assertEqual(invoke.call_args.args[1]["accepted"], {"terms": "2026-11-25"})
            invoke.reset_mock()
            for body in ({}, {"accepted": {}}, {"accepted": {"marketing": "2026-11-25"}}, {"accepted": {"terms": 1}},
                         {"accepted": {"terms": "2026-11-25"}, "account_id": "x"}, {"accepted": ["terms"]}):
                with self.subTest(body):
                    self.assertEqual(self.call(legal.acceptance, "post", body).status_code, 400)
            invoke.assert_not_called()
            self.assertEqual(self.call(legal.acceptance, "get", token=None).status_code, 401)

    def test_an_unexpected_state_is_never_passed_on(self):
        broken = [{**STATE, "extra": 1}, {**STATE, "documents": STATE["documents"][::-1]},
                  {**STATE, "acceptance_required": "yes"}, {**STATE, "marketing": {"granted": True}}]
        for bad in broken:
            with self.subTest(bad), patch.object(legal, "_invoke", return_value=JsonResponse(bad)):
                self.assertEqual(self.call(legal.acceptance, "get").status_code, 503)

    def test_marketing_consent_is_strict(self):
        with patch.object(legal, "_invoke", return_value=JsonResponse(STATE)) as invoke:
            self.assertEqual(self.call(legal.marketing_consent, "put", {"granted": True, "version": "2026-11-25"})
                             .status_code, 200)
            self.assertEqual(invoke.call_args.args[1], {"access_token": "t" * 40, "operation": "marketing",
                                                        "granted": True, "version": "2026-11-25"})
            invoke.reset_mock()
            for body in ({"granted": "true", "version": "2026-11-25"}, {"granted": True}, {"granted": True, "version": ""}):
                with self.subTest(body):
                    self.assertEqual(self.call(legal.marketing_consent, "put", body).status_code, 400)
            invoke.assert_not_called()


class RegistrationAcceptanceTests(SimpleTestCase):
    def post(self, body):
        from service import accounts
        request = RequestFactory().post("/api/v1/auth/register", json.dumps(body), content_type="application/json")
        return accounts.register(request)

    def test_registration_must_carry_an_acceptance_and_a_strict_marketing_flag(self):
        base = {"email": "a@example.test", "password": secrets.token_urlsafe(16), "display_name": "A"}
        with patch("service.accounts._invoke", return_value=JsonResponse({"id": "1"}, status=201)) as invoke:
            for body in (base, {**base, "accepted": "yes"}, {**base, "accepted": {"terms": "v"}, "marketing_consent": 1}):
                with self.subTest(body):
                    self.assertEqual(self.post(body).status_code, 400)
            invoke.assert_not_called()
            accepted = {"terms": "2026-11-25", "privacy": "2026-11-25"}
            self.assertEqual(self.post({**base, "accepted": accepted, "marketing_consent": True}).status_code, 201)
            self.assertEqual(invoke.call_args.args[1]["accepted"], accepted)

    def test_only_the_outdated_version_code_is_passed_through(self):
        from io import BytesIO
        from urllib.error import HTTPError
        from service import accounts
        for code, kept in (("legal_version_outdated", True), ("something_else", False)):
            error = HTTPError("http://identity", 409, "Conflict", {},
                              BytesIO(json.dumps({"detail": "x", "code": code}).encode()))
            with self.subTest(code), patch("service.accounts.signed_internal_request", side_effect=error):
                body = json.loads(accounts._invoke("/internal/auth/register", {}, {201}).content)
            self.assertEqual("code" in body, kept)
