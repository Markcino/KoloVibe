"""The R1 secret generator: shapes the staging runtime accepts, no overwrite, no value ever printed."""

import contextlib
import io
import json
import os
from pathlib import Path
import secrets
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts/ops"))
sys.path.insert(0, str(ROOT / "services"))

import generate_r1_secrets as gen  # noqa: E402
import staging_runtime  # noqa: E402

GOOD_R2 = {"KOLOVIBE_R2_ACCESS_KEY_ID": "a1" * 16, "KOLOVIBE_R2_SECRET_ACCESS_KEY": "b2" * 32,
           "KOLOVIBE_R2_ACCOUNT_ID": "c3" * 16, "KOLOVIBE_R2_MEDIA_BUCKET": "kolovibe-media"}


def generated(env=None):
    directory = Path(tempfile.mkdtemp()) / "secrets"
    files, notes = gen.build(GOOD_R2 if env is None else env)
    gen.write_all(directory, files)
    return directory, files, notes


class GeneratorTests(unittest.TestCase):
    def test_a_full_set_validates_and_has_every_expected_file(self):
        directory, files, notes = generated()
        self.assertEqual(notes, [])
        names = gen.validate(directory)
        self.assertEqual(len(names), 22)
        for required in ("identity_mfa_encryption", "identity_audit_signing", "identity_audit_peers",
                         "kolovibe_gateway_trusted_peers_r1_v1", "kolovibe_gateway_outbound_r1_v1",
                         "kolovibe_account_approval_r1_v1", "audit_callers_2", "content_callers_2",
                         "kolovibe_content_r2_access_key_r1_v1", "kolovibe_content_r2_secret_key_r1_v1"):
            self.assertIn(required, names)
        self.assertEqual(directory.stat().st_mode & 0o777, 0o700)
        for name in names:
            self.assertEqual((directory / name).stat().st_mode & 0o777, 0o600, name)
            self.assertFalse((directory / name).read_text().endswith("\n"), name)

    def test_every_secret_name_is_one_the_tool_allows_or_an_own_service_name(self):
        sys.path.insert(0, str(ROOT / "scripts/ops"))
        import kolovibe_cluster as cluster

        directory, files, _ = generated()
        allowed = {n for names in cluster.AWS_STAGING.service_allowed_secrets.values() for n in names}
        for name in files:
            own = any(name.startswith(service + "_") for service in cluster.SERVICES)
            self.assertTrue(own or name in allowed, name)

    def test_generated_values_satisfy_the_staging_runtime_itself(self):
        from cryptography.fernet import Fernet

        directory, files, _ = generated()
        for name in ("identity_audit_signing", "kolovibe_points_outbound_key_r1_v1"):
            self.assertGreaterEqual(len((directory / name).read_text()), 32)
            self.assertNotIn("\n", (directory / name).read_text())
        Fernet((directory / "identity_mfa_encryption").read_text().encode())
        peers = json.loads((directory / "kolovibe_gateway_trusted_peers_r1_v1").read_text())
        self.assertEqual(set(peers), staging_runtime.capabilities.gateway_peers(gen.ALL_CAPS, True))
        for service in gen.BROKER_ACCOUNTS:
            path = directory / f"kolovibe_{service}_rabbitmq_url_r1_v1"
            with patch.dict(os.environ, {"KOLOVIBE_RABBITMQ_URL_FILE": str(path)}, clear=True):
                self.assertTrue(staging_runtime.broker_url().startswith("amqps://kolovibe_" + service + ":"))
        # configure()'s own caller check: audit's producers are distinct and from the allowed set.
        audit = json.loads((directory / "audit_callers_2").read_text())
        self.assertLessEqual(set(audit), {"identity", "moderation", "creators", "content", "points", "gateway"})
        self.assertEqual(len(set(audit.values())), len(audit))

    def test_keys_are_unique_across_every_audience_and_between_runs(self):
        directory, _, _ = generated()
        other, _, _ = generated()
        for name in ("identity_audit_signing", "kolovibe_points_outbound_key_r1_v1"):
            self.assertNotEqual((directory / name).read_text(), (other / name).read_text())
        values = json.loads((directory / "kolovibe_gateway_outbound_r1_v1").read_text())
        self.assertEqual(len(set(values.values())), 6)

    def test_r2_files_are_written_only_for_keys_of_the_shape_cloudflare_issues(self):
        for label, change in (("missing access key id", {"KOLOVIBE_R2_ACCESS_KEY_ID": ""}),
                              ("short id", {"KOLOVIBE_R2_ACCESS_KEY_ID": "abc"}),
                              ("secret too short", {"KOLOVIBE_R2_SECRET_ACCESS_KEY": "ab" * 8}),
                              ("secret not hex", {"KOLOVIBE_R2_SECRET_ACCESS_KEY": "Z" * 64})):
            with self.subTest(label):
                directory, files, notes = generated(dict(GOOD_R2, **change))
                self.assertNotIn("kolovibe_content_r2_access_key_r1_v1", files)
                self.assertNotIn("kolovibe_content_r2_secret_key_r1_v1", files)
                self.assertTrue(any("R2 key files NOT written" in n for n in notes))
                self.assertNotIn(GOOD_R2["KOLOVIBE_R2_SECRET_ACCESS_KEY"], " ".join(notes))
                self.assertEqual(len(gen.validate(directory)), 20)
        _, _, notes = generated(dict(GOOD_R2, KOLOVIBE_R2_ACCOUNT_ID="x" * 53, KOLOVIBE_R2_MEDIA_BUCKET="a.b/c"))
        self.assertEqual(sum("deployment input" in n for n in notes), 2)

    def test_it_never_overwrites_and_refuses_a_non_empty_or_in_repo_directory(self):
        directory, files, _ = generated()
        with self.assertRaises(FileExistsError):
            gen.write_all(directory, {"identity_audit_signing": "other"})
        with tempfile.TemporaryDirectory() as parent, patch.object(gen, "read_env", return_value=GOOD_R2):
            target = Path(parent) / "s"
            target.mkdir()
            (target / "keep").write_text("x")
            with self.assertRaises(SystemExit):
                gen.main(["--out", str(target)])
            with self.assertRaises(SystemExit):
                gen.main(["--out", str(ROOT / "tmp-secrets-test")])
            self.assertFalse((ROOT / "tmp-secrets-test").exists())

    def test_the_command_line_prints_names_only(self):
        with tempfile.TemporaryDirectory() as parent:
            env = Path(parent) / "env"
            env.write_text("\n".join(f"{k}={v}" for k, v in GOOD_R2.items()))
            env.chmod(0o600)
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.assertEqual(gen.main(["--out", str(Path(parent) / "s"), "--env", str(env)]), 0)
            text = out.getvalue()
            self.assertIn("PASS: 22 secret files", text)
            for value in (GOOD_R2["KOLOVIBE_R2_SECRET_ACCESS_KEY"], GOOD_R2["KOLOVIBE_R2_ACCESS_KEY_ID"]):
                self.assertNotIn(value, text)
            for path in (Path(parent) / "s").iterdir():
                self.assertNotIn(path.read_text(), text)
            scripts = Path(parent) / "s-scripts"
            for script in scripts.iterdir():
                body = script.read_text()
                self.assertEqual(script.stat().st_mode & 0o777, 0o700)
                for file in (Path(parent) / "s").iterdir():
                    self.assertNotIn(file.read_text(), body)  # scripts hold names and commands, never values
            self.assertIn("docker secret create", (scripts / "create-secrets.sh").read_text())
            self.assertIn("secret inspect", (scripts / "create-secrets.sh").read_text())  # never replaces
            self.assertIn("add_user", (scripts / "broker-setup.sh").read_text())


class ValidatorRejectionTests(unittest.TestCase):
    def mutate(self, name, change):
        directory, _, _ = generated()
        path = directory / name
        path.write_text(change(path.read_text()))
        with self.assertRaises((ValueError, json.JSONDecodeError)):
            gen.validate(directory)

    def test_tampered_sets_fail_validation(self):
        outbound = json.loads
        cases = {
            "gateway key shared by two audiences": ("kolovibe_gateway_outbound_r1_v1", lambda t: json.dumps(
                {**outbound(t), "points": outbound(t)["identity"]})),
            "short key": ("kolovibe_gateway_outbound_r1_v1", lambda t: json.dumps({**outbound(t), "points": "short"})),
            "peers missing an audience": ("kolovibe_gateway_trusted_peers_r1_v1", lambda t: json.dumps(
                {k: v for k, v in outbound(t).items() if k != "points"})),
            "peers over http": ("kolovibe_gateway_trusted_peers_r1_v1", lambda t: t.replace("https://", "http://", 1)),
            "callers with the wrong key": ("points_callers_2", lambda t: json.dumps({"gateway": "x" * 40})),
            "audit callers missing points": ("audit_callers_2", lambda t: json.dumps(
                {k: v for k, v in outbound(t).items() if k != "points"})),
            "mfa key not Fernet": ("identity_mfa_encryption", lambda t: "not-a-fernet-key"),
            "trailing newline": ("identity_audit_signing", lambda t: t + "\n"),
            "empty approvals reference": ("kolovibe_account_approval_r1_v1", lambda t: json.dumps(
                {**outbound(t), "mfa": " "})),
            "broker uri on the wrong vhost": ("kolovibe_points_rabbitmq_url_r1_v1", lambda t: t.replace("%2Fkolovibe", "kolovibe")),
            "broker uri without tls": ("kolovibe_points_rabbitmq_url_r1_v1", lambda t: t.replace("amqps://", "amqp://")),
        }
        for label, (name, change) in cases.items():
            with self.subTest(label):
                self.mutate(name, change)

    def test_a_missing_file_or_loose_permissions_fail(self):
        directory, _, _ = generated()
        (directory / "points_callers_2").unlink()
        with self.assertRaises(ValueError):
            gen.validate(directory)
        directory, _, _ = generated()
        (directory / "identity_audit_signing").chmod(0o644)
        with self.assertRaises(ValueError):
            gen.validate(directory)
        directory, _, _ = generated()
        directory.chmod(0o755)
        with self.assertRaises(ValueError):
            gen.validate(directory)


if __name__ == "__main__":
    unittest.main()
