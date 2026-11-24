"""DR-BZ-21 (decided): the Business service speaks JSON to the Gateway only; no template, cookie or CORS machinery."""
from django.conf import settings

from .support import BusinessTestCase


class BusinessClientSurfaceTests(BusinessTestCase):
    def test_no_template_cors_cookie_or_session_machinery_is_configured(self):
        self.assertEqual(settings.TEMPLATES, [])
        self.assertEqual([app for app in settings.INSTALLED_APPS
                          if any(word in app.lower() for word in ("cors", "session", "staticfiles", "admin"))], [])
        self.assertEqual(settings.MIDDLEWARE, ["django.middleware.security.SecurityMiddleware",
                                               "service.service_auth.ServiceAuthMiddleware"])

    def test_every_kind_of_refusal_is_json_without_cookies_or_cors(self):
        from service.api import dispatch
        import json
        from uuid import uuid4
        cases = [("register", {"method": "get"}), ("unknown_operation", {}), ("register", {"caller": "moderation"}),
                 ("category_put", {"role": "viewer"}), ("get_mine", {"data": {"business_id": str(uuid4())}}),
                 ("register", {"envelope": {"bad": 1}})]
        for operation, kwargs in cases:
            body = kwargs.get("envelope") or {"actor_id": str(uuid4()), "role": kwargs.get("role", "viewer"), "mfa_verified": False,
                                              "email_verified": True, "idempotency_key": None, "origin": None,
                                              "data": kwargs.get("data", {})}
            request = self.factory.generic(kwargs.get("method", "post").upper(), "/internal/business/" + operation,
                                           json.dumps(body), content_type="application/json")
            request.service_caller = kwargs.get("caller", "gateway")
            response = dispatch(request, operation)
            where = f"{operation} {kwargs} -> {response.status_code}"
            self.assertGreaterEqual(response.status_code, 400, where)
            self.assertEqual(response["Content-Type"].split(";")[0], "application/json", where)
            self.assertEqual(len(response.cookies), 0, where)
            self.assertFalse([h for h in response.headers if h.lower().startswith("access-control-")], where)
