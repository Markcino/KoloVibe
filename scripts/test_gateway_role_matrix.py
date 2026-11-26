"""Privileged gateway routes refuse every caller without the required role and fresh MFA, before forwarding.

Callers are simulated by role and MFA state (see scripts/probe_gateway_roles.py). For routes the gateway gates itself,
an insufficient caller must be refused with no call to any business service. Routes that deliberately delegate the
role decision to the owning service are listed explicitly, so a new privileged route that forwards a viewer cannot
appear unnoticed.
"""

import json
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
PRIVILEGED_PREFIXES = ("/api/v1/admin/", "/api/v1/moderation/", "/api/v1/creator-invitations",
                       "/api/v1/creator-applications", "/api/v1/engagement/fraud-holds")
REFUSED = {401, 403, 404, 405}
# The gateway authenticates the caller; the owning service authorises the role (Identity for moderator invitations,
# account lookup and privacy review, Creators for creator onboarding) and each has its own role tests.
DELEGATED = {
    "/api/v1/admin/accounts/lookup",
    "/api/v1/admin/moderator-invitations",
    "/api/v1/admin/moderator-invitations/{id}/revoke",
    "/api/v1/admin/privacy-requests",
    "/api/v1/admin/privacy-requests/{id}/review",
    "/api/v1/admin/privacy-requests/{id}/decline",
    "/api/v1/admin/privacy-requests/{id}/approve-deletion",
    "/api/v1/admin/accounts/{id}/holds",
    "/api/v1/admin/account-holds/{id}/release",
    "/api/v1/creator-invitations",
    "/api/v1/creator-invitations/{id}/revoke",
    "/api/v1/creator-applications",
    "/api/v1/creator-applications/{id}/decision",
}
# Administrator-only at the gateway itself.
ADMIN_ONLY = {"/api/v1/admin/moderation/assignments", "/api/v1/admin/moderation/assignments/summary",
              "/api/v1/admin/creators/{id}/restrictions", "/api/v1/admin/creator-restrictions/{id}/lift",
              "/api/v1/admin/creator-restriction-appeals", "/api/v1/admin/creator-restriction-appeals/{id}/decision",
              "/api/v1/admin/rights-holders", "/api/v1/admin/rights-holders/{id}/revoke"}
INSUFFICIENT = ("viewer:nomfa", "creator:nomfa", "moderator:nomfa", "administrator:nomfa")


def probe():
    out = subprocess.run([sys.executable, str(ROOT / "scripts" / "probe_gateway_roles.py")],
                         capture_output=True, text=True, timeout=300, check=True).stdout
    return json.loads(out.strip().splitlines()[-1])


class GatewayRoleMatrixTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.routes = probe()
        cls.privileged = {route: by for route, by in cls.routes.items() if route.startswith(PRIVILEGED_PREFIXES)}
        cls.gated = {route: by for route, by in cls.privileged.items() if route not in DELEGATED}

    def refused_without_forwarding(self, route, caller):
        for method, outcome in self.routes[route][caller].items():
            with self.subTest(route=route, caller=caller, method=method):
                self.assertIn(outcome["status"], REFUSED)
                self.assertEqual(outcome["business_calls"], 0)

    def test_the_privileged_route_set_is_what_this_matrix_covers(self):
        for route in DELEGATED | ADMIN_ONLY:
            self.assertIn(route, self.routes, f"{route} no longer exists; update the matrix")
        self.assertGreaterEqual(len(self.gated), 14)

    def test_gateway_gated_routes_refuse_callers_without_role_and_mfa(self):
        for route in self.gated:
            for caller in INSUFFICIENT:
                self.refused_without_forwarding(route, caller)
            for caller in ("viewer:nomfa", "creator:nomfa"):
                self.refused_without_forwarding(route, caller)

    def test_a_privileged_role_with_fresh_mfa_is_not_refused_by_the_gateway(self):
        """Positive control: the refusals above come from the role/MFA rule, not from a dead route."""
        for route in self.gated:
            caller = "administrator:mfa" if route in ADMIN_ONLY else "moderator:mfa"
            with self.subTest(route=route, caller=caller):
                self.assertTrue(any(outcome["status"] not in REFUSED for outcome in self.routes[route][caller].values()),
                                f"{caller} never got past the gateway on {route}")

    def test_administrator_only_routes_refuse_moderators_even_with_mfa(self):
        for route in ADMIN_ONLY:
            self.refused_without_forwarding(route, "moderator:mfa")

    def test_only_listed_delegated_routes_forward_a_viewer(self):
        """Any other privileged route that forwards a viewer to a business service has lost its gateway gate."""
        for route, by in self.privileged.items():
            if route in DELEGATED:
                continue
            for caller in ("viewer:nomfa", "creator:nomfa"):
                for method, outcome in by[caller].items():
                    with self.subTest(route=route, caller=caller, method=method):
                        self.assertEqual(outcome["business_calls"], 0)


if __name__ == "__main__":
    unittest.main()
