"""The R1 staging capability policy: parsing, per-service limits, route coverage and fail-closed behaviour."""

import datetime
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services"))

from staging_runtime import capabilities as policy, configure  # noqa: E402
from staging_runtime.middleware import route_allowed  # noqa: E402

ALL = frozenset(policy.CAPABILITIES)
SAMPLE_UUID = "123e4567-e89b-42d3-a456-426614174000"
METHODS = ("GET", "POST", "PUT", "PATCH", "DELETE")
NOT_CAPABILITY = ("/health/live", "/internal/probe")
# Routes a service registers for its own (local) use that staging deliberately never exposes: Content's direct
# public reads are served through the Gateway only.
# Capabilities that switch a worker or job on rather than a route: Engagement's `points` gates the outbox
# dispatcher and, through `watch`, the watch API that feeds it.
NO_ROUTES = {("engagement", "points")}
UNEXPOSED = {("content", "/videos"), ("content", f"/videos/{SAMPLE_UUID}")}


def routes(service):  # noqa: D103
    out = subprocess.run([sys.executable, str(ROOT / "scripts/list_service_routes.py"), service],
                         capture_output=True, text=True, timeout=60, check=True).stdout
    return [path for path in json.loads(out) if path not in NOT_CAPABILITY and (service, path) not in UNEXPOSED]


def reachable(service, path, **flags):
    return any(route_allowed(service, method, path, **flags) for method in METHODS)


class PolicyDefinitionTests(unittest.TestCase):
    def test_parse_is_strict_and_closed_by_default(self):
        self.assertEqual(policy.parse(None), frozenset())
        self.assertEqual(policy.parse(""), frozenset())
        self.assertEqual(policy.parse("media,points"), {"media", "points"})
        for bad in ("media,unknown", "points,media", "media,media", " media", "Media", "media,", ",media"):
            with self.subTest(bad), self.assertRaises(RuntimeError):
                policy.parse(bad)

    def test_a_service_carries_only_capabilities_that_apply_to_it(self):
        for service in policy.SERVICES:
            for cap in policy.CAPABILITIES:
                if cap in policy.APPLICABLE[service] and service != "gateway":
                    policy.check(service, frozenset({cap}), accounts=True, privileged=True)
                elif cap not in policy.APPLICABLE[service]:
                    with self.subTest(service=service, cap=cap), self.assertRaises(RuntimeError):
                        policy.check(service, frozenset({cap}), accounts=True, privileged=True)

    def test_business_is_a_known_service_that_carries_no_capability(self):
        # Business is registered so its staging settings load, but nothing is switched on through it: every
        # capability is refused for it, and its routes stay closed until an owner-approved release record.
        policy.check("business", frozenset(), accounts=False, privileged=False)
        for capability in ALL:
            with self.assertRaises(RuntimeError, msg=capability):
                policy.check("business", frozenset({capability}), accounts=False, privileged=False)

    def test_gateway_dependencies_are_enforced(self):
        policy.check("gateway", ALL, accounts=True, privileged=True)
        for cap, needs in policy.REQUIRES.items():
            for missing in needs:
                with self.subTest(cap=cap, missing=missing), self.assertRaises(RuntimeError):
                    policy.check("gateway", frozenset({cap} | (needs - {missing})), accounts=True, privileged=True)

    def test_moderation_and_accounts_need_mfa_and_the_account_capability(self):
        with self.assertRaises(RuntimeError):
            policy.check("gateway", frozenset({"moderation"}), accounts=True, privileged=False)
        with self.assertRaises(RuntimeError):
            policy.check("identity", frozenset({"account_management"}), accounts=False, privileged=False)
        with self.assertRaises(RuntimeError):
            policy.check("identity", frozenset({"moderation"}), accounts=True, privileged=False)
        policy.check("identity", frozenset({"account_management", "moderation"}), accounts=True, privileged=True)

    def test_gateway_peers_follow_the_capabilities(self):
        self.assertEqual(policy.gateway_peers(frozenset(), False), {"content", "creators"})
        self.assertEqual(policy.gateway_peers(frozenset(), True), {"content", "creators", "identity"})
        self.assertEqual(policy.gateway_peers(ALL, True), {"content", "creators", "identity", "engagement", "points",
                                                          "moderation", "audit"})
        self.assertEqual(policy.receiver_peers("moderation", frozenset({"moderation"})), {"audit", "content"})
        self.assertEqual(policy.receiver_peers("points", frozenset({"points"})), {"audit"})
        self.assertEqual(policy.receiver_peers("content", ALL), set())

    def test_every_rule_names_a_known_service_capability_and_method(self):
        for rule in policy.RULES:
            self.assertIn(rule.service, policy.SERVICES)
            self.assertIn(rule.capability, policy.APPLICABLE[rule.service])
            self.assertTrue(rule.methods <= set(METHODS))
            self.assertTrue(rule.pattern.pattern.startswith("/"))
        # Reviewer/admin routes and invite-only MFA enrollment require the privileged switch.
        self.assertEqual({rule.pattern.pattern for rule in policy.RULES if rule.privileged},
                         {r"/api/v1/moderation/(?:videos|reports|appeals|edits)",
                          rf"/api/v1/moderation/(?:videos|reports|appeals|edits)/{policy.UUID}/decisions",
                          rf"/api/v1/moderation/(?:videos|reports|appeals|edits)/{policy.UUID}",
                          rf"/api/v1/moderation/previews/{policy.UUID}", r"/api/v1/moderation/totals", r"/api/v1/engagement/fraud-holds", r"/api/v1/admin/moderation/assignments(?:/summary)?", r"/api/v1/admin/audit", r"/api/v1/admin/points/balances", rf"/api/v1/admin/points/accounts/{policy.UUID}",
                          r"/api/v1/admin/moderator-invitations",
                          r"/api/v1/admin/accounts/lookup", r"/internal/auth/account-lookup",
                          rf"/api/v1/admin/moderator-invitations/{policy.UUID}/revoke",
                          r"/api/v1/auth/moderator-invitations/(?:setup|complete)",
                          r"/internal/auth/moderator-invitations",
                          r"/internal/auth/moderator-invitations/(?:setup|complete)"})

    def test_moderator_invitation_routes_need_both_accounts_and_privileged_gates(self):
        for service, path in (("gateway", "/api/v1/admin/moderator-invitations"),
                              ("gateway", "/api/v1/auth/moderator-invitations/setup"),
                              ("identity", "/internal/auth/moderator-invitations/complete")):
            self.assertFalse(route_allowed(service, "POST", path, accounts=True, privileged=True))
            self.assertFalse(route_allowed(service, "POST", path, accounts=True,
                                          capability_set=frozenset({"account_management"})))
            self.assertTrue(route_allowed(service, "POST", path, accounts=True, privileged=True,
                                         capability_set=frozenset({"account_management"})))


class RouteCoverageTests(unittest.TestCase):
    """Every registered route is either baseline or reachable only through its own named capability."""

    FLAGS = dict(accounts=True, onboarding=True)

    @classmethod
    def setUpClass(cls):
        cls.routes = {service: routes(service) for service in policy.SERVICES}

    def test_every_registered_route_is_reachable_with_everything_on(self):
        for service, paths in self.routes.items():
            for path in paths:
                with self.subTest(service=service, path=path):
                    self.assertTrue(reachable(service, path, privileged=True, capability_set=ALL, **self.FLAGS),
                                    "no staging rule names this route; add one or it stays closed")

    def test_nothing_is_reachable_through_a_capability_that_is_off(self):
        """With every capability off, the reachable set is only what was open before the policy existed."""
        for service, paths in self.routes.items():
            closed = [p for p in paths if not reachable(service, p, privileged=True, capability_set=frozenset(),
                                                        **self.FLAGS)]
            by_cap = {cap: {p for p in closed if reachable(service, p, privileged=True, capability_set=frozenset({cap}),
                                                           **self.FLAGS)}
                      for cap in policy.APPLICABLE[service]}
            covered = set().union(*by_cap.values()) if by_cap else set()
            self.assertEqual(covered, set(closed), service + ": a closed route no single capability opens")

    def test_each_capability_opens_something_and_never_a_route_of_another_service(self):
        for service, caps in policy.APPLICABLE.items():
            for cap in caps:
                if (service, cap) in NO_ROUTES:
                    continue
                opened = [p for p in self.routes[service]
                          if reachable(service, p, privileged=True, capability_set=frozenset({cap}), **self.FLAGS)
                          and not reachable(service, p, privileged=True, capability_set=frozenset(), **self.FLAGS)]
                self.assertTrue(opened, f"{service}/{cap} opens no registered route")

    def test_reviewer_routes_need_the_privileged_capability_as_well(self):
        reviewer = ["/api/v1/moderation/videos", "/api/v1/moderation/reports", "/api/v1/moderation/appeals",
                    "/api/v1/moderation/edits", f"/api/v1/moderation/edits/{SAMPLE_UUID}/decisions",
                    f"/api/v1/moderation/videos/{SAMPLE_UUID}/decisions",
                    f"/api/v1/moderation/appeals/{SAMPLE_UUID}/decisions"]
        for path in reviewer:
            for method in ("GET", "POST"):
                if route_allowed("gateway", method, path, accounts=True, privileged=True, capability_set=ALL):
                    self.assertFalse(route_allowed("gateway", method, path, accounts=True, privileged=False,
                                                   capability_set=ALL), path)
                    self.assertFalse(route_allowed("gateway", method, path, accounts=True, privileged=True,
                                                   capability_set=ALL - {"moderation"}), path)

    def test_methods_are_exact(self):
        probes = {"/api/v1/reports": ("POST", ("GET", "PUT", "DELETE", "PATCH")),
                  f"/api/v1/videos/{SAMPLE_UUID}/publish": ("POST", ("GET", "PUT", "DELETE", "PATCH")),
                  f"/api/v1/videos/{SAMPLE_UUID}/like": ("PUT", ("POST", "PATCH")),
                  "/api/v1/creators/me/points": ("GET", ("POST", "PUT", "DELETE"))}
        for path, (good, bad) in probes.items():
            self.assertTrue(route_allowed("gateway", good, path, accounts=True, privileged=True, capability_set=ALL), path)
            for method in bad:
                self.assertFalse(route_allowed("gateway", method, path, accounts=True, privileged=True,
                                               capability_set=ALL), f"{method} {path}")

    def test_media_opens_only_the_exact_creator_eligibility_and_ownership_routes(self):
        base = "/internal/creators/onboarding/"
        media = frozenset({"media"})
        for op in ("eligibility", "ownership"):
            self.assertTrue(route_allowed("creators", "POST", base + op, capability_set=media), op)
            for method in ("GET", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"):
                self.assertFalse(route_allowed("creators", method, base + op, capability_set=media), method)
            for suffix in ("/", "2", "/x", "/../x"):
                self.assertFalse(route_allowed("creators", "POST", base + op + suffix, capability_set=media), suffix)
            for caps in (frozenset(), ALL - {"media"}):
                self.assertFalse(route_allowed("creators", "POST", base + op, privileged=True, capability_set=caps))
            for service in ("gateway", "content", "identity", "audit"):
                self.assertFalse(route_allowed(service, "POST", base + op, capability_set=ALL))
        for path in ("invite", "review", "pending", "submit", "status", "standing", "application", "Ownership",
                     "OWNERSHIP", "", "../ownership", "ownership%2f", "ownership?x=1", "eligibility/",
                     "eligibility2", "eligibility/x", "Eligibility"):
            for privileged in (False, True):
                self.assertFalse(route_allowed("creators", "POST", base + path, privileged=privileged,
                                               capability_set=media), path)
        # Without media (and without the onboarding flag) it stays closed; other services never open it.
        for caps in (frozenset(), ALL - {"media"}):
            self.assertFalse(route_allowed("creators", "POST", base + "eligibility", privileged=True,
                                           capability_set=caps))
        for service in ("gateway", "content", "identity", "audit"):
            self.assertFalse(route_allowed(service, "POST", base + "eligibility", capability_set=ALL))
        # The privileged flag alone does not open it; the onboarding flag keeps its separate, wider route.
        self.assertFalse(route_allowed("creators", "POST", base + "eligibility", privileged=True,
                                       capability_set=frozenset()))
        self.assertTrue(route_allowed("creators", "POST", base + "invite", onboarding=True,
                                      capability_set=frozenset()))

    def test_internal_capability_routes_accept_only_post(self):
        for service in ("content", "engagement", "points", "moderation", "identity"):
            for path in self.routes[service]:
                if path.startswith("/internal/"):
                    for method in ("GET", "PUT", "DELETE", "PATCH"):
                        self.assertFalse(policy.allowed(service, ALL, method, path, privileged=True),
                                         f"{method} {service} {path}")

    def test_unregistered_paths_stay_closed(self):
        for path in ("/admin/", "/api/v1/unknown", "/internal/likes/../secrets", "/api/v1/videos/not-a-uuid/publish",
                     "/api/v1/moderation/other", f"/api/v1/videos/{SAMPLE_UUID}/publish/extra"):
            self.assertFalse(reachable("gateway", path, privileged=True, capability_set=ALL, **self.FLAGS), path)
        self.assertFalse(reachable("audit", "/internal/likes", privileged=True, capability_set=ALL, **self.FLAGS))
        self.assertFalse(reachable("creators", "/internal/points/balance", privileged=True, capability_set=ALL,
                                   **self.FLAGS))

    def test_public_catalogue_and_account_baseline_are_unchanged_with_capabilities_off(self):
        for path in ("/api/v1/videos", f"/api/v1/videos/{SAMPLE_UUID}", f"/api/v1/creators/{SAMPLE_UUID}",
                     "/api/v1/creators/search"):
            self.assertTrue(route_allowed("gateway", "GET", path, accounts=False), path)
        self.assertFalse(route_allowed("gateway", "POST", "/api/v1/videos", accounts=True))
        self.assertFalse(route_allowed("gateway", "POST", "/api/v1/auth/login", accounts=False))
        self.assertTrue(route_allowed("gateway", "POST", "/api/v1/auth/login", accounts=True))


def certificate(directory):
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.x509.oid import NameOID

    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "fixture")])
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
            .serial_number(x509.random_serial_number()).not_valid_before(now - datetime.timedelta(days=1))
            .not_valid_after(now + datetime.timedelta(days=1))
            .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
            .sign(key, hashes.SHA256()))
    (directory / "cert.pem").write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    (directory / "key.pem").write_bytes(key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    return directory / "cert.pem", directory / "key.pem"


class ConfigureTests(unittest.TestCase):
    """`configure` accepts exactly the approved per-service slices and demands their secrets."""

    def setUp(self):
        self.directory = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(self.directory, ignore_errors=True))
        self.cert, self.key = certificate(self.directory)

    def private(self, name, text):
        path = self.directory / name
        path.write_text(text)
        path.chmod(0o600)
        return str(path)

    def environment(self, service, caps, *, accounts=None, privileged="0"):
        token = "k" * 40
        peers = {"origins": {}}
        env = {
            "KOLOVIBE_SERVICE_NAME": service, "KOLOVIBE_ALLOWED_HOSTS": service,
            "KOLOVIBE_DB_PASSWORD_FILE": self.private("db", "p" * 24), "KOLOVIBE_DB_SSLROOTCERT": str(self.cert),
            "KOLOVIBE_INTERNAL_CA_FILE": str(self.cert), "KOLOVIBE_TLS_CERT_FILE": str(self.cert),
            "KOLOVIBE_TLS_KEY_FILE": self.private("key", self.key.read_text()),
            "KOLOVIBE_CALLER_KEYS_FILE": self.private("callers", json.dumps({"gateway": token})),
            "KOLOVIBE_PROBE_TOKEN_FILE": self.private("probe", "q" * 40),
            "KOLOVIBE_STAGING_CAPABILITIES": ",".join(sorted(caps)),
            "KOLOVIBE_STAGING_ACCOUNTS": "1" if (accounts if accounts is not None else service in ("gateway", "identity")) else "0",
            "KOLOVIBE_STAGING_PRIVILEGED": privileged,
        }
        if service in ("gateway", "identity"):
            env["KOLOVIBE_ACCOUNT_APPROVAL_FILE"] = self.private("approvals", json.dumps(
                {name: "ref" for name in ("identity", "smtp", "credentials", "transport", "mfa", "audit")}))
        return env, peers

    def settings(self, service):
        return {"KOLOVIBE_SERVICE_NAME": service, "MIDDLEWARE": [],
                "DATABASES": {"default": {"ENGINE": "django.db.backends.postgresql", "OPTIONS": {"options": ""}}}}

    def test_capabilities_on_a_service_that_does_not_carry_them_stop_it(self):
        for service, caps in (("audit", {"media"}), ("creators", {"points"}), ("points", {"media"}),
                              ("identity", {"engagement"}), ("content", {"points"})):
            env, _ = self.environment(service, caps)
            with self.subTest(service), patch.dict(os.environ, env, clear=True), self.assertRaises(RuntimeError):
                configure(self.settings(service))

    def test_a_service_with_no_capabilities_gets_every_feature_switch_off(self):
        for service in ("content", "engagement", "points", "moderation"):
            env, _ = self.environment(service, set())
            settings = self.settings(service)
            with self.subTest(service), patch.dict(os.environ, env, clear=True):
                configure(settings)
            self.assertEqual(settings["STAGING_CAPABILITIES"], frozenset())
            for switch in ("LOCAL_MEDIA_ENABLED", "LOCAL_MODERATION_ENABLED", "LOCAL_POINTS_ENABLED"):
                self.assertFalse(settings.get(switch, False), switch)

    def test_receivers_with_a_capability_require_the_gateway_credential(self):
        env, _ = self.environment("points", {"points"})
        Path(env["KOLOVIBE_CALLER_KEYS_FILE"]).write_text(json.dumps({"audit": "z" * 40}))
        with patch.dict(os.environ, env, clear=True), self.assertRaises(RuntimeError):
            configure(self.settings("points"))

    def test_broker_uri_accepts_the_live_slash_named_vhost_and_nothing_stranger(self):
        from staging_runtime import broker_url

        good = ("amqps://u:p@kolovibe-rabbitmq:5671/%2Fkolovibe", "amqps://u:p@kolovibe-rabbitmq:5671/%2fkolovibe",
                "amqps://u:p@kolovibe-rabbitmq:5671/kolovibe", "amqps://u:p@kolovibe-rabbitmq:5671")
        bad = ("amqps://u:p@h:5671//kolovibe", "amqps://u:p@h:5671/%00", "amqps://u:p@h:5671/%2e%2e", "amqps://u:p@h:5671/a/b",
               "amqps://u:p@h:5671/k?x=1", "amqps://u:p@h:5671/" + "a" * 65, "amqp://u:p@h:5671/v", "amqps://h:5671/v")
        for value, accepted in [(g, True) for g in good] + [(b, False) for b in bad]:
            path = self.private("uri", value)
            with self.subTest(value=value.rsplit("@", 1)[-1]), patch.dict(os.environ, {"KOLOVIBE_RABBITMQ_URL_FILE": path}, clear=True):
                if accepted:
                    self.assertEqual(broker_url(), value)
                else:
                    with self.assertRaises(RuntimeError):
                        broker_url()

    def test_a_content_service_with_media_demands_r2_and_the_broker_as_secret_files(self):
        env, _ = self.environment("content", {"media"})
        with patch.dict(os.environ, env, clear=True), self.assertRaises(RuntimeError):
            configure(self.settings("content"))
        env.update(KOLOVIBE_R2_ACCOUNT_ID="a" * 32, KOLOVIBE_R2_MEDIA_BUCKET="kolovibe-media",
                   KOLOVIBE_R2_HTTPS_PROXY="http://kolovibe-r2-proxy:3128",
                   KOLOVIBE_R2_ACCESS_KEY_FILE=self.private("r2a", "A" * 24),
                   KOLOVIBE_R2_SECRET_KEY_FILE=self.private("r2s", "S" * 40),
                   KOLOVIBE_RABBITMQ_URL_FILE=self.private("amqp", "amqps://app:secret@rabbitmq:5671/kolovibe"),
                   KOLOVIBE_RABBITMQ_CA_FILE=str(self.cert))
        for bad in ("", "https://kolovibe-r2-proxy:3128", "http://u:p@kolovibe-r2-proxy:3128", "http://kolovibe-r2-proxy",
                    "http://kolovibe-r2-proxy:3128/x"):
            with patch.dict(os.environ, dict(env, KOLOVIBE_R2_HTTPS_PROXY=bad), clear=True), self.assertRaises(RuntimeError):
                configure(self.settings("content"))
        settings = self.settings("content")
        with patch.dict(os.environ, env, clear=True):
            configure(settings)
        self.assertTrue(settings["LOCAL_MEDIA_ENABLED"])
        self.assertFalse(settings["LOCAL_MODERATION_ENABLED"])
        for change in ({"KOLOVIBE_RABBITMQ_URL": "amqps://a:b@rabbitmq:5671"},
                       {"KOLOVIBE_RABBITMQ_URL_FILE": self.private("plain", "amqp://a:b@rabbitmq:5672")},
                       {"KOLOVIBE_RABBITMQ_URL_FILE": self.private("noauth", "amqps://rabbitmq:5671")},
                       {"KOLOVIBE_R2_ACCOUNT_ID": "short"}, {"KOLOVIBE_R2_MEDIA_BUCKET": "Bad_Bucket"},
                       {"KOLOVIBE_R2_SECRET_KEY_FILE": str(self.directory / "missing")}):
            with self.subTest(list(change)), patch.dict(os.environ, env | change, clear=True), \
                    self.assertRaises(RuntimeError):
                configure(self.settings("content"))
        (self.directory / "r2s").chmod(0o644)
        with patch.dict(os.environ, env, clear=True), self.assertRaisesRegex(RuntimeError, "owner-only"):
            configure(self.settings("content"))


if __name__ == "__main__":
    unittest.main()
