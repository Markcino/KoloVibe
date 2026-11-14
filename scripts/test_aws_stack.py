"""The AWS R1 worker/job stack: hostname-pinned, fail-closed, equal to the tool's reviewed tables."""

import copy
import os
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from validate_staging_stack import (AWS_ROLES, AWS_STACK, check_release_evidence, load_stack,  # noqa: E402
                                     memory_bytes, validate, validate_aws)

INPUTS = {
    "STAGING_DB_NAME": "kolovibe_staging", "STAGING_DB_HOST": "172.31.16.20",
    "KOLOVIBE_IMAGE": "ghcr.io/markcino/kolovibe/services@sha256:" + "a" * 64,
    "KOLOVIBE_MEDIA_IMAGE": "ghcr.io/markcino/kolovibe/media-worker@sha256:" + "e" * 64,
    "R2_ACCOUNT_ID": "1" * 32, "R2_MEDIA_BUCKET": "kolovibe-media", "SMTP_HOST": "smtp.example.test",
    "SMTP_PORT": "587", "FROM_EMAIL": "noreply@example.test",
    **{service.upper() + "_DB_USER": "runtime_" + service
       for service in ("content", "engagement", "points", "moderation", "identity")},
}


def stack():
    return load_stack(AWS_STACK, INPUTS)


class AwsStackTests(unittest.TestCase):
    def test_the_committed_stack_passes_and_reports_its_memory_budget(self):
        budget = validate_aws(stack())
        self.assertEqual(set(budget), set(AWS_ROLES))
        self.assertEqual(sum(budget.values()), memory_bytes("1536M"))

    def test_the_oracle_stack_validator_still_refuses_aws(self):
        with self.assertRaisesRegex(ValueError, "oracle-staging candidate"):
            validate({}, "aws-staging")

    def test_inputs_are_required_non_secret_identifiers(self):
        for name in ("R2_ACCOUNT_ID", "R2_MEDIA_BUCKET", "KOLOVIBE_IMAGE", "KOLOVIBE_MEDIA_IMAGE", "STAGING_DB_HOST"):
            environment = dict(INPUTS)
            del environment[name]
            with self.subTest(name), self.assertRaises(ValueError):
                load_stack(AWS_STACK, environment)

    def test_the_file_is_not_the_oracle_stack(self):
        text = AWS_STACK.read_text()
        self.assertNotIn("node.labels", text)
        self.assertNotIn("kvtest-", text)
        self.assertNotIn("vm-swarm", text)
        code = [line for line in text.splitlines() if not line.lstrip().startswith("#")]
        self.assertEqual(sum("node.hostname==ip-172-31-16-154" in line for line in code), 1)  # one anchor, inherited by all

    def test_every_process_starts_at_zero_replicas_and_never_hardcodes_a_secret_value(self):
        for definition in stack()["services"].values():
            self.assertEqual(definition["deploy"]["replicas"], 0)
        for line in AWS_STACK.read_text().splitlines():
            if "PASSWORD" in line.upper() or "TOKEN" in line.upper():
                self.assertTrue("_FILE" in line or "source:" in line or "external" in line or line.lstrip().startswith("#"), line)


def mutate(change):
    definition = stack()
    change(definition)
    return definition


class AwsStackRejectionTests(unittest.TestCase):
    def rejected(self, label, change):
        with self.subTest(label), self.assertRaises((ValueError, KeyError, TypeError)):
            validate_aws(mutate(change))

    def test_structure_and_runtime_hardening(self):
        s = lambda d, n="media-worker": d["services"][n]  # noqa: E731
        self.rejected("extra service", lambda d: d["services"].update(extra=copy.deepcopy(s(d))))
        self.rejected("missing service", lambda d: d["services"].pop("points-audit"))
        self.rejected("two shared images", lambda d: s(d, "points-audit").update(image="ghcr.io/markcino/kolovibe/services@sha256:" + "b" * 64))
        self.rejected("media worker on the shared image", lambda d: s(d).update(image="ghcr.io/markcino/kolovibe/services@sha256:" + "a" * 64))
        self.rejected("a consumer on the media image", lambda d: s(d, "points-consumer").update(image=s(d)["image"]))
        self.rejected("media tag not digest", lambda d: s(d).update(image="ghcr.io/markcino/kolovibe/media-worker:latest"))
        self.rejected("media image from another repository", lambda d: s(d).update(image="ghcr.io/other/media-worker@sha256:" + "e" * 64))
        self.rejected("tag not digest", lambda d: [x.update(image="ghcr.io/markcino/kolovibe/services:latest") for x in d["services"].values()])
        self.rejected("port", lambda d: s(d).update(ports=["8000:8000"]))
        self.rejected("host mount", lambda d: s(d).update(volumes=["/var/lib:/data"]))
        self.rejected("privileged", lambda d: s(d).update(privileged=True))
        self.rejected("root", lambda d: s(d).update(user="0:0"))
        self.rejected("writable", lambda d: s(d).update(read_only=False))
        self.rejected("capabilities kept", lambda d: s(d).pop("cap_drop"))
        self.rejected("healthcheck", lambda d: s(d).update(healthcheck={"test": ["CMD", "true"]}))
        self.rejected("host network", lambda d: s(d).update(network_mode="host"))

    def test_roles_commands_and_flags(self):
        s = lambda d, n="media-worker": d["services"][n]  # noqa: E731
        self.rejected("wrong role", lambda d: s(d).update(command=["--role", "consumer"]))
        self.rejected("unknown role", lambda d: s(d).update(command=["--role", "shell"]))
        self.rejected("shell word", lambda d: s(d).update(command=["--role", "media-worker", "sh", "-c", "id"]))
        self.rejected("worker with interval", lambda d: s(d).update(command=["--role", "media-worker", "--interval", "30"]))
        self.rejected("job interval too short", lambda d: s(d, "points-audit").update(
            command=["--role", "deliver-audit", "--interval", "1", "--limit", "100"]))
        self.rejected("job batch too large", lambda d: s(d, "points-audit").update(
            command=["--role", "deliver-audit", "--interval", "30", "--limit", "5000"]))
        self.rejected("job without bounds", lambda d: s(d, "points-audit").update(command=["--role", "deliver-audit"]))
        self.rejected("extra capability", lambda d: s(d)["environment"].update(
            KOLOVIBE_STAGING_CAPABILITIES="analytics,engagement,media,moderation,points"))
        self.rejected("capability dropped", lambda d: s(d)["environment"].update(KOLOVIBE_STAGING_CAPABILITIES="media"))
        self.rejected("accounts on a worker", lambda d: s(d)["environment"].update(KOLOVIBE_STAGING_ACCOUNTS="1"))
        self.rejected("privileged off on identity", lambda d: s(d, "identity-audit")["environment"].update(
            KOLOVIBE_STAGING_PRIVILEGED="0"))
        self.rejected("debug", lambda d: s(d)["environment"].update(DJANGO_DEBUG="1"))
        self.rejected("wrong service", lambda d: s(d)["environment"].update(KOLOVIBE_SERVICE_NAME="gateway"))
        self.rejected("inline broker uri", lambda d: s(d)["environment"].update(KOLOVIBE_RABBITMQ_URL="amqps://u:p@h"))
        self.rejected("inline r2 key", lambda d: s(d)["environment"].update(KOLOVIBE_R2_SECRET_KEY="x"))
        self.rejected("inline token", lambda d: s(d)["environment"].update(SOME_TOKEN="x"))

    def test_placement_resources_and_networks(self):
        s = lambda d, n="media-worker": d["services"][n]  # noqa: E731
        self.rejected("oracle label placement", lambda d: s(d)["deploy"].update(
            placement={"constraints": ["node.labels.kolovibe.workloads == true"]}))
        self.rejected("unpinned", lambda d: s(d)["deploy"].update(placement={}))
        self.rejected("other host", lambda d: s(d)["deploy"].update(placement={"constraints": ["node.hostname==other"]}))
        self.rejected("active", lambda d: s(d)["deploy"].update(replicas=1))
        self.rejected("no rollback", lambda d: s(d)["deploy"]["update_config"].update(failure_action="pause"))
        self.rejected("unbounded memory", lambda d: s(d)["deploy"]["resources"]["limits"].update(memory="2G"))
        self.rejected("reservation over limit", lambda d: s(d)["deploy"]["resources"]["reservations"].update(memory="1G"))
        self.rejected("no memory limit", lambda d: s(d)["deploy"]["resources"]["limits"].pop("memory"))
        self.rejected("no broker network", lambda d: s(d).update(networks=["private", "data_private"]))
        self.rejected("broker network for an audit job", lambda d: s(d, "moderation-audit").update(
            networks=["private", "data_private", "broker_private"]))
        self.rejected("internal network renamed", lambda d: d["networks"].update(
            private={"external": True, "name": "ingress"}))
        self.rejected("network created by the stack", lambda d: d["networks"].update(private={"driver": "overlay"}))

    def test_secrets_belong_to_the_service_and_are_external_owner_only(self):
        s = lambda d, n="media-worker": d["services"][n]  # noqa: E731

        def swap(definition, process, target, source):
            for secret in definition["services"][process]["secrets"]:
                if secret["target"] == target:
                    secret["source"] = source
            definition["secrets"].setdefault(source, {"external": True})

        self.rejected("another service's key", lambda d: swap(d, "points-audit", "django_key", "content_django"))
        self.rejected("another service's r1 secret", lambda d: swap(d, "points-consumer", "rabbitmq_url",
                                                                 "kolovibe_content_rabbitmq_url_r1_v1"))
        self.rejected("renamed r2 secret", lambda d: swap(d, "media-worker", "r2_access_key", "r2_key"))
        self.rejected("secret dropped", lambda d: s(d)["secrets"].pop())
        self.rejected("extra secret", lambda d: s(d)["secrets"].append(
            {"source": "gateway_django", "target": "extra", "uid": "10001", "gid": "10001", "mode": 0o400}))
        self.rejected("world-readable", lambda d: s(d)["secrets"][0].update(mode=0o644))
        self.rejected("root-owned", lambda d: s(d)["secrets"][0].update(uid="0"))
        self.rejected("secret defined in the stack", lambda d: d["secrets"].update(content_django={"file": "./x"}))
        self.rejected("unused secret declared", lambda d: d["secrets"].update(orphan={"external": True}))

    def test_release_evidence_must_carry_exactly_the_stacks_two_digests(self):
        import tempfile

        loaded = stack()
        shared, media = INPUTS["KOLOVIBE_IMAGE"], INPUTS["KOLOVIBE_MEDIA_IMAGE"]

        def check(**changes):
            files = {"revision.txt": "d" * 40, "published-digest.txt": shared, "published-media-digest.txt": media, **changes}
            with tempfile.TemporaryDirectory() as directory:
                for name, text in files.items():
                    (Path(directory) / name).write_text(text)
                return check_release_evidence(directory, loaded)

        self.assertEqual(check(), "d" * 40)
        for label, changes in {
            "other media digest": {"published-media-digest.txt": "ghcr.io/markcino/kolovibe/media-worker@sha256:" + "9" * 64},
            "other shared digest": {"published-digest.txt": "ghcr.io/markcino/kolovibe/services@sha256:" + "9" * 64},
            "bad revision": {"revision.txt": "nope"},
            "media equals shared": {"published-media-digest.txt": shared},
        }.items():
            with self.subTest(label), self.assertRaises(ValueError):
                check(**changes)

    def test_the_workers_secrets_equal_the_tools_rollout_for_the_same_service(self):
        sys.path.insert(0, str(ROOT / "scripts/ops"))
        import kolovibe_cluster as cluster

        for name, (service, _) in AWS_ROLES.items():
            mounted = {x["target"]: x["source"] for x in stack()["services"][name]["secrets"]}
            for target, secret in cluster.AWS_STAGING.r1_rollout[service]["mounts"].items():
                self.assertEqual(mounted[target], secret, f"{name}:{target}")
            self.assertTrue(set(cluster.AWS_STAGING.r1_rollout[service]["mounts"].values())
                            <= cluster.AWS_STAGING.service_allowed_secrets[service])


if __name__ == "__main__":
    unittest.main()
