"""Every console route, classified, against every way a request can fail to be a valid privileged one.

The URL table is walked, not listed by hand: a route that is added without being classified here fails the first test,
so it cannot ship without a decision about who may reach it. For each privileged route the matrix proves, with the
gateway replaced by a recorder, that an anonymous caller, a non-privileged account, a password-only session, an idle
session, a missing CSRF token and (for administrator-only pages) a moderator are all refused before any business
request is made.
"""

import secrets
import uuid
from datetime import timedelta
from unittest.mock import patch

from django.test import Client, TestCase
from django.urls import get_resolver, reverse
from django.utils import timezone

from web.models import WebCredential

SAMPLE = str(uuid.uuid4())
# Reachable without a console session. Each answers for itself and is covered by its own tests.
PUBLIC = {"web-liveness", "web-static", "root", "moderator-home", "dashboard-alias", "login", "login-mfa",
          "moderator-invitation", "moderator-invitation-qr"}
# Administrator-only pages the console itself refuses a moderator on (403, before any gateway call), as defence in
# depth on top of the owning service's own check.
CONSOLE_CHECKED = {"creators", "moderation-videos-assign", "moderation-reports-assign", "moderation-appeals-assign"}
# Administrator-only page where the console forwards and the gateway and Identity decide (the console surfaces the
# refusal). Listed explicitly so a change in either direction is a visible decision.
DELEGATED = {"team"}
ADMIN_ONLY = CONSOLE_CHECKED | DELEGATED
# Privileged routes whose POST changes state.
POSTING = {"profile-edit", "password-change", "revoke-session", "logout", "team", "creators",
           "moderation-videos-detail", "moderation-reports-detail", "moderation-appeals-detail",
           "moderation-videos-assign", "moderation-reports-assign", "moderation-appeals-assign"}


def route_table():
    """(name, concrete path) for every route in the console's URL table."""
    found = {}

    def walk(patterns, prefix=""):
        for pattern in patterns:
            if hasattr(pattern, "url_patterns"):
                walk(pattern.url_patterns, prefix + str(pattern.pattern))
            else:
                text = prefix + str(pattern.pattern)
                for converter in ("uuid:preview_id", "uuid:target_id", "uuid:session_id"):
                    text = text.replace(f"<{converter}>", SAMPLE)
                text = text.replace("<path:asset>", "console.css")
                found[pattern.name] = "/" + text
    walk(get_resolver().url_patterns)
    return found


ROUTES = route_table()
PRIVILEGED = {name: path for name, path in ROUTES.items() if name not in PUBLIC}


class RouteSecurityMatrixTests(TestCase):
    def setUp(self):
        self.account = {"id": str(uuid.uuid4()), "email": "admin@example.test",
                        "display_name": "Console administrator", "roles": ["administrator"]}
        self.access = secrets.token_urlsafe(36)
        self.refresh = str(uuid.uuid4()) + "." + secrets.token_urlsafe(48)

    def sign_in(self, role="administrator", client=None):
        client = client or self.client
        self.account["roles"] = [role]
        with patch("web.views._api", return_value=(202, {"mfa_required": True,
                                                         "challenge_token": secrets.token_urlsafe(48), "expires_in": 300})):
            client.post(reverse("login"), {"email": self.account["email"], "password": secrets.token_urlsafe(30)})
        with patch("web.views._api", return_value=(200, {"user": self.account, "access_token": self.access,
                                                         "refresh_token": self.refresh})):
            self.assertEqual(client.post(reverse("login-mfa"), {"code": "012345"}).status_code, 302)

    def identity_only(self, role=None):
        """The gateway as the console sees it: only `/me` answers; any other call is recorded as a business request."""
        calls = []

        def fake(path, **kwargs):
            if path == "/me":
                return 200, dict(self.account, roles=[role or self.account["roles"][0]])
            calls.append((path, kwargs.get("method", "GET")))
            return 503, {}
        return fake, calls

    # --- the table itself --------------------------------------------------------------------

    def test_every_route_is_classified_and_every_privileged_route_lives_under_admin(self):
        self.assertEqual(set(PUBLIC) - set(ROUTES), set(), "a public name no longer exists; update the matrix")
        for name in (ADMIN_ONLY | POSTING):
            self.assertIn(name, PRIVILEGED, f"{name} is classified but is not a privileged route")
        for name, path in PRIVILEGED.items():
            self.assertTrue(path.startswith("/admin/"), f"{name} is privileged but lives outside /admin/: {path}")
        self.assertGreaterEqual(len(PRIVILEGED), 20)

    # --- no session ----------------------------------------------------------------------------

    def test_anonymous_requests_to_every_privileged_route_are_sent_to_login_without_any_gateway_call(self):
        for name, path in PRIVILEGED.items():
            for method in ("get", "post", "put", "patch", "delete"):
                with self.subTest(route=name, method=method), patch("web.views._api") as api:
                    response = getattr(self.client, method)(path)
                    self.assertIn(response.status_code, (302, 405), f"{method.upper()} {path} answered {response.status_code}")
                    if response.status_code == 302:
                        self.assertEqual(response["Location"].split("?")[0], "/login/")
                    api.assert_not_called()

    # --- a session that is not a valid privileged session ---------------------------------------

    def test_a_non_privileged_account_is_refused_on_every_privileged_route_before_any_business_call(self):
        self.sign_in()
        for name, path in PRIVILEGED.items():
            for method in ("get", "post"):
                fake, calls = self.identity_only(role="viewer")
                with self.subTest(route=name, method=method), patch("web.views._api", side_effect=fake):
                    response = getattr(self.client, method)(path)
                    self.assertIn(response.status_code, (403, 405, 302), f"{method.upper()} {path}")
                    self.assertEqual(calls, [], "a business request was made for a non-privileged account")

    def test_a_sign_in_stopped_after_the_password_stage_reaches_no_privileged_route(self):
        """The real password-only state: the challenge is pending and the code was never verified."""
        with patch("web.views._api", return_value=(202, {"mfa_required": True,
                                                         "challenge_token": secrets.token_urlsafe(48), "expires_in": 300})):
            self.client.post(reverse("login"), {"email": self.account["email"], "password": secrets.token_urlsafe(30)})
        for name, path in PRIVILEGED.items():
            for method in ("get", "post"):
                with self.subTest(route=name, method=method), patch("web.views._api") as api:
                    response = getattr(self.client, method)(path)
                    self.assertIn(response.status_code, (302, 405))
                    if response.status_code == 302:
                        self.assertEqual(response["Location"].split("?")[0], "/login/")
                    api.assert_not_called()

    def test_a_session_whose_mfa_flag_is_not_true_is_never_privileged(self):
        """Two independent layers check the flag (the view guard and the server-session validator); the flag alone is
        not enough to forge a privileged session because the encrypted server record is the authority."""
        self.sign_in()
        session = self.client.session
        session["mfa_verified"] = False
        session.save()
        for name, path in PRIVILEGED.items():
            fake, calls = self.identity_only()
            with self.subTest(route=name), patch("web.views._api", side_effect=fake):
                response = self.client.get(path)
                self.assertIn(response.status_code, (302, 405, 403))
                if response.status_code == 302:
                    self.assertEqual(response["Location"].split("?")[0], "/login/")
                self.assertEqual(calls, [])

    def test_an_idle_or_over_age_session_is_rejected_on_every_privileged_route(self):
        for field, age in (("last_activity_at", timedelta(minutes=31)), ("created_at", timedelta(minutes=16))):
            self.client = Client()
            self.sign_in()
            WebCredential.objects.update(**{field: timezone.now() - age})
            for name, path in PRIVILEGED.items():
                fake, calls = self.identity_only()
                with self.subTest(expired=field, route=name), patch("web.views._api", side_effect=fake):
                    response = self.client.get(path)
                    self.assertIn(response.status_code, (302, 405))
                    if response.status_code == 302:
                        self.assertEqual(response["Location"].split("?")[0], "/login/")
                    self.assertEqual(calls, [])
                    if response.status_code == 302:
                        break  # the first rejection deletes the server record; later routes see no session

    # --- CSRF -------------------------------------------------------------------------------------

    def test_every_state_changing_route_rejects_a_post_without_a_csrf_token_before_any_gateway_call(self):
        self.sign_in()
        strict = Client(enforce_csrf_checks=True)
        strict.cookies = self.client.cookies
        for name in sorted(POSTING):
            with self.subTest(route=name), patch("web.views._api") as api:
                response = strict.post(PRIVILEGED[name], {})
                self.assertEqual(response.status_code, 403)
                api.assert_not_called()

    def test_a_token_from_another_session_does_not_authorize_a_post(self):
        self.sign_in()
        other = Client(enforce_csrf_checks=True)
        other.get(reverse("login"))
        foreign = other.cookies["csrftoken"].value
        strict = Client(enforce_csrf_checks=True)
        strict.cookies = self.client.cookies
        for name in sorted(POSTING):
            with self.subTest(route=name), patch("web.views._api") as api:
                response = strict.post(PRIVILEGED[name], {"csrfmiddlewaretoken": foreign})
                self.assertEqual(response.status_code, 403)
                api.assert_not_called()

    def test_safe_methods_never_reach_a_state_changing_gateway_call(self):
        self.sign_in()
        for name, path in PRIVILEGED.items():
            fake, calls = self.identity_only()
            with self.subTest(route=name), patch("web.views._api", side_effect=fake):
                self.client.get(path)
                self.assertEqual([call for call in calls if call[1] != "GET"], [], f"GET {path} made a mutating request")

    # --- role matrix --------------------------------------------------------------------------------

    def test_the_console_itself_refuses_a_moderator_on_its_administrator_only_pages(self):
        self.sign_in("moderator")
        for name in sorted(CONSOLE_CHECKED):
            for method in ("get", "post"):
                fake, calls = self.identity_only("moderator")
                with self.subTest(route=name, method=method), patch("web.views._api", side_effect=fake):
                    response = getattr(self.client, method)(PRIVILEGED[name], {})
                    self.assertIn(response.status_code, (403, 405), f"{method.upper()} {PRIVILEGED[name]}")
                    self.assertEqual(calls, [], "a moderator caused a gateway request on an administrator-only page")

    def test_a_delegated_page_surfaces_the_owning_services_refusal_never_content(self):
        """For `team` the gateway and Identity decide; the console must show their refusal faithfully: no 2xx, no data,
        no echo of the service's detail, and no more than the one refused request."""
        self.sign_in("moderator")
        for name in sorted(DELEGATED):
            for method, body in (("get", None), ("post", {"email": "x@example.test"})):
                calls = []

                def refusing(path, **kwargs):
                    if path == "/me":
                        return 200, dict(self.account, roles=["moderator"])
                    calls.append((path, kwargs.get("method", "GET")))
                    return 403, {"detail": "Request unavailable"}

                with self.subTest(route=name, method=method), patch("web.views._api", side_effect=refusing):
                    response = getattr(self.client, method)(PRIVILEGED[name], body or {})
                    self.assertNotEqual(response.status_code // 100, 2, f"{method.upper()} {PRIVILEGED[name]} succeeded")
                    self.assertLessEqual(len(calls), 1, "more than the one refused request was made")
                    self.assertNotIn("Request unavailable", response.content.decode(), "internal detail leaked")
