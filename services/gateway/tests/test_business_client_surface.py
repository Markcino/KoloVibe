"""DR-BZ-21 (decided): Business routes serve the Flutter app and nothing else, so they return JSON only.

No HTML, no cookies and no cross-origin permission on any Business route, for any outcome the Gateway can produce
without a credential or with the service down; and no template, CORS or session machinery is configured at all
(BZ-R-051; AC-CLI-001…004). These checks fail if a web surface is added by drift.
"""
from unittest.mock import patch

from django.conf import settings
from django.test import RequestFactory, SimpleTestCase
from django.urls import URLPattern

from service.routes import business as business_routes


def business_patterns():
    with patch.object(business_routes, "enabled", return_value=True):
        return [p for p in business_routes.patterns() if isinstance(p, URLPattern)]


def sample_kwargs(pattern):
    from uuid import uuid4
    kwargs = dict(pattern.default_args)
    for name in pattern.pattern.regex.groupindex:
        kwargs[name] = str(uuid4())
    return kwargs


class BusinessClientSurfaceTests(SimpleTestCase):
    def test_no_template_cors_cookie_or_session_machinery_is_configured(self):
        self.assertEqual(settings.TEMPLATES, [])
        self.assertEqual(settings.INSTALLED_APPS, [])
        # Exactly the transport-security and service-identity middleware: no CORS, session, CSRF, message or
        # common middleware. Adding one is a visible, reviewable change to this list.
        self.assertEqual(settings.MIDDLEWARE, ["django.middleware.security.SecurityMiddleware",
                                               "service.service_auth.ServiceAuthMiddleware"])

    def test_every_business_route_answers_in_json_without_cookies_or_cors(self):
        routes = business_patterns()
        self.assertGreaterEqual(len(routes), 40)
        factory = RequestFactory()
        for pattern in routes:
            operations = pattern.default_args["operations"]
            kwargs = sample_kwargs(pattern)
            requests = [(method, "") for method in operations] + [("OPTIONS", ""), ("TRACE", ""), ("PATCH" if "PATCH" not in operations else "HEAD", "")]
            for method, _ in requests:
                with patch("service.business.signed_internal_request", side_effect=OSError("peer down")):
                    request = factory.generic(method, "/api/v1/x", "", content_type="application/json",
                                              HTTP_ORIGIN="https://attacker.example", HTTP_COOKIE="sessionid=abc")
                    response = pattern.callback(request, **kwargs)
                where = f"{method} {pattern.pattern} -> {response.status_code}"
                self.assertEqual(len(response.cookies), 0, f"sets a cookie: {where}")
                for header in response.headers:
                    self.assertFalse(header.lower().startswith("access-control-"), f"CORS header on {where}")
                if response.status_code == 204 or not response.content:
                    self.assertNotIn("text/html", response.get("Content-Type", ""), f"empty body labelled HTML: {where}")
                else:
                    self.assertEqual(response["Content-Type"].split(";")[0], "application/json", f"non-JSON body: {where}")

    def test_a_wrong_method_is_a_json_405_that_names_the_allowed_methods(self):
        pattern = next(p for p in business_patterns() if set(p.default_args["operations"]) == {"GET", "POST"})
        response = pattern.callback(RequestFactory().generic("DELETE", "/api/v1/x"), **sample_kwargs(pattern))
        self.assertEqual((response.status_code, response["Content-Type"].split(";")[0], response["Allow"]),
                         (405, "application/json", "GET, POST"))
