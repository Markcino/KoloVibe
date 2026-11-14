"""Validate the restricted staging candidate without contacting Docker or a VM."""

import os
from pathlib import Path
import re

import yaml

ROOT = Path(__file__).resolve().parents[1]
INPUT = re.compile(r"\$\{([A-Z0-9_]+):\?[^}]+\}")
SERVICES = {"gateway", "identity", "content", "creators", "engagement", "points",
            "moderation", "audit"}


def memory_bytes(value):
    match = re.fullmatch(r"([1-9][0-9]*)([kKmMgG]?)(?:[iI]?[bB])?", str(value))
    if not match:
        raise ValueError("Memory budgets must be positive whole bytes/K/M/G quantities")
    factor = {"": 1, "k": 1024, "m": 1024 ** 2, "g": 1024 ** 3}[match[2].lower()]
    return int(match[1]) * factor


def load_stack(path, environment):
    def replace(match):
        name = match[1]
        value = environment.get(name, "")
        if not value or not re.fullmatch(r"[a-zA-Z0-9_.:/@,-]+", value):
            raise ValueError(f"Missing/invalid non-secret staging input: {name}")
        return value

    return yaml.safe_load(INPUT.sub(replace, Path(path).read_text()))


ORACLE_PROFILE = "oracle-staging"
AWS_PROFILE = "aws-staging"
PROFILES = (ORACLE_PROFILE, AWS_PROFILE)


def validate(stack, profile=ORACLE_PROFILE):
    """Validate the stack file against one named placement profile.

    The stack file's placement is label-based and belongs to oracle-staging. The AWS nodes have no
    Swarm labels, so aws-staging is refused explicitly instead of passing a file that cannot schedule.
    """
    if profile == AWS_PROFILE:
        raise ValueError("staging.yml is the oracle-staging candidate (label placement); the AWS nodes "
                         "carry no labels, so use the aws-staging profile of scripts/ops/kolovibe_cluster.py")
    if profile != ORACLE_PROFILE:
        raise ValueError("Unknown placement profile; choose one of: " + ", ".join(PROFILES))
    if set(stack["services"]) != SERVICES | {"rabbitmq"}:
        raise ValueError("Single deployment must define eight API services and RabbitMQ")
    if len({stack["services"][name]["image"] for name in SERVICES}) != 1:
        raise ValueError("All staging services must use the same shared image digest")
    for name in SERVICES:
        service = stack["services"][name]
        if not re.fullmatch(r"ghcr\.io/markcino/kolovibe/services@sha256:[0-9a-f]{64}",
                            service["image"]):
            raise ValueError("Staging requires an immutable verified service image digest")
        if service.get("ports") or service.get("volumes") or service.get("privileged"):
            raise ValueError("Staging services must not publish ports or mount host paths")
        if service["user"] != "10001:10001" or not service.get("read_only"):
            raise ValueError("Staging requires a non-root read-only runtime")
        environment = service["environment"]
        if (environment["KOLOVIBE_ENV"] != "staging" or environment["DJANGO_DEBUG"] != "0"
                or environment["KOLOVIBE_STAGING_ACCOUNTS"] != "0"
                or environment["KOLOVIBE_STAGING_PRIVILEGED"] != "0"
                or environment["KOLOVIBE_SERVICE_NAME"] != name):
            raise ValueError("Staging capability/environment gate was changed")
        if any(re.search(r"(PASSWORD|SECRET_KEY|TOKEN|OUTBOUND_KEY|CALLER_KEYS)$", key)
               for key in environment):
            raise ValueError("Persistent credentials must be secret files, not environment values")
        if service["networks"] != ["private", "data_private"]:
            raise ValueError("API services must use only private service/data networks")
        if service["healthcheck"]["test"] != ["CMD", "python", "-m", "staging_runtime.probe"]:
            raise ValueError("Staging requires the verified-TLS readiness probe")
        if service["deploy"]["update_config"]["failure_action"] != "rollback":
            raise ValueError("Staging rollout must fail with rollback")
        if service["deploy"]["replicas"] != 0:
            raise ValueError("Candidate activation requires separate capacity/release approval")
        if service["deploy"].get("placement", {}).get("constraints") != [
                "node.labels.kolovibe.workloads == true"]:
            raise ValueError("All Django services must be constrained to the approved VM2 worker")
        resources = service["deploy"]["resources"]
        limit = memory_bytes(resources["limits"]["memory"])
        reservation = memory_bytes(resources["reservations"]["memory"])
        if reservation > limit:
            raise ValueError("API memory reservation exceeds its limit")
        targets = {secret["target"]: secret["source"] for secret in service["secrets"]}
        for target, suffix in (("django_key", "django"), ("db_password", "db"),
                               ("tls_cert", "tls_cert"), ("tls_key", "tls_key"),
                               ("caller_keys", "callers"), ("probe_token", "probe")):
            if targets.get(target) != name + "_" + suffix:
                raise ValueError("API secrets must belong only to their selected service")
        for secret in service["secrets"]:
            if (secret["uid"] != "10001" or secret["gid"] != "10001"
                    or secret["mode"] != 0o400
                    or stack["secrets"][secret["source"]] != {"external": True}):
                raise ValueError("Staging secrets must be external, service-readable and owner-only")
    if not stack["networks"]["private"].get("external"):
        raise ValueError("Staging network must already be approved and provisioned")
    for name, actual in (("data_private", "kolovibe_data"), ("broker_private", "kolovibe_messaging")):
        if stack["networks"][name] != {"external": True, "name": actual}:
            raise ValueError("Deployment must retain the approved private data/broker zones")
    broker = stack["services"]["rabbitmq"]
    if not re.fullmatch(r"dhi\.io/rabbitmq@sha256:[0-9a-f]{64}", broker["image"]):
        raise ValueError("RabbitMQ requires a reviewed immutable DHI digest")
    memory_bytes(broker["deploy"]["resources"]["limits"]["memory"])
    if (broker.get("ports") or broker.get("privileged") or broker.get("network_mode")
            or broker["networks"] != ["broker_private"] or broker["deploy"]["replicas"] != 0):
        raise ValueError("RabbitMQ must remain private and unactivated")
    if broker["deploy"]["placement"]["constraints"] != [
            "node.labels.kolovibe.workloads == true",
            "node.labels.kolovibe.rabbitmq == true"]:
        raise ValueError("RabbitMQ requires reviewed durable-node placement")
    if broker["volumes"] != ["rabbitmq_data:/var/lib/rabbitmq"]:
        raise ValueError("RabbitMQ requires its owning persistent volume")
    if stack["configs"]["rabbitmq_conf"]["file"] != "../rabbitmq/rabbitmq.conf":
        raise ValueError("Deployment must use the existing reviewed RabbitMQ configuration")
    if not (ROOT / "infra/swarm" / stack["configs"]["rabbitmq_conf"]["file"]).is_file():
        raise ValueError("RabbitMQ configuration source is missing")
    if set(broker["secrets"]) != {
            "kolovibe_rmq_ca", "kolovibe_rmq_cert", "kolovibe_rmq_key", "kolovibe_rmq_definitions"}:
        raise ValueError("RabbitMQ TLS/definitions secrets are incomplete")
    for name in broker["secrets"]:
        if stack["secrets"][name] != {"external": True}:
            raise ValueError("RabbitMQ secrets must remain external")


AWS_STACK = ROOT / "infra/swarm/staging-aws.yml"
AWS_ROLES = {
    "media-worker": ("content", "media-worker"), "engagement-consumer": ("engagement", "consumer"),
    "engagement-dispatch": ("engagement", "dispatch-events"), "points-consumer": ("points", "consumer"),
    "points-audit": ("points", "deliver-audit"), "moderation-audit": ("moderation", "deliver-audit"),
    "identity-audit": ("identity", "deliver-security-audit"),
}
AWS_NETWORKS = {"private": "kolovibe_services", "data_private": "kolovibe_data", "broker_private": "kolovibe_messaging"}
MAX_PROCESS_MEMORY = 1024 ** 3
MEDIA_IMAGE = r"ghcr\.io/markcino/kolovibe/media-worker@sha256:[0-9a-f]{64}"


def check_release_evidence(directory, stack):
    """The stack's two digests must be exactly the ones the `published-image-<sha>` artifact recorded."""
    base = Path(directory)
    read = lambda name: (base / name).read_text().strip()  # noqa: E731
    revision = read("revision.txt")
    if not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise ValueError("Release evidence has no valid revision")
    shared, media = read("published-digest.txt"), read("published-media-digest.txt")
    if stack["services"]["media-worker"]["image"] != media:
        raise ValueError("The media worker image is not the published media-worker digest")
    if any(d["image"] != shared for n, d in stack["services"].items() if n != "media-worker"):
        raise ValueError("A process image is not the published shared digest")
    if not re.fullmatch(MEDIA_IMAGE, media) or media == shared:
        raise ValueError("The media-worker digest is invalid")
    return revision


def _aws_references():
    import sys

    sys.path[:0] = [str(ROOT / "scripts/ops"), str(ROOT / "services")]
    import kolovibe_cluster as cluster
    from staging_runtime import roles

    return cluster, roles


def validate_aws(stack):
    """Validate the AWS R1 worker/job stack against the aws-staging profile and the runtime's own policy.

    Returns {service name: memory limit in bytes}. Offline; contacts no Docker daemon, VM or registry.
    """
    cluster, roles = _aws_references()
    profile = cluster.AWS_STAGING
    if set(stack["services"]) != set(AWS_ROLES):
        raise ValueError("The AWS stack must define exactly the seven R1 worker and job services")
    for name, expected in AWS_NETWORKS.items():
        if stack["networks"].get(name) != {"external": True, "name": expected}:
            raise ValueError("AWS networks must be the existing approved external overlays")
    media = stack["services"]["media-worker"]["image"]
    if not re.fullmatch(MEDIA_IMAGE, media):
        raise ValueError("The media worker must use the immutable media-worker image digest")
    shared = {definition["image"] for name, definition in stack["services"].items() if name != "media-worker"}
    if len(shared) != 1 or not re.fullmatch(r"ghcr\.io/markcino/kolovibe/services@sha256:[0-9a-f]{64}", next(iter(shared))):
        raise ValueError("Every other AWS process must use the one immutable shared image digest")
    budget = {}
    for name, (service, role) in AWS_ROLES.items():
        definition = stack["services"][name]
        if (service, role) not in roles.ROLES:
            raise ValueError("The role is not an approved worker role")
        if definition.get("ports") or definition.get("volumes") or definition.get("privileged") \
                or definition.get("network_mode"):
            raise ValueError("AWS processes must not publish ports, mount host paths or run privileged")
        if definition["user"] != "10001:10001" or not definition.get("read_only") or definition.get("cap_drop") != ["ALL"]:
            raise ValueError("AWS processes require a non-root read-only runtime with no capabilities")
        if definition.get("healthcheck") != {"disable": True}:
            raise ValueError("Workers serve no HTTP port; the API readiness probe must be disabled")
        command = definition["command"]
        if command[:2] != ["--role", role]:
            raise ValueError("The command must select exactly the service's approved role")
        options = dict(zip(command[2::2], command[3::2]))
        if len(command) % 2 or set(options) - {"--interval", "--limit"}:
            raise ValueError("Only --interval and --limit may follow the role")
        kind = roles.ROLES[(service, role)][1]
        if kind == "job":
            if not roles.MIN_INTERVAL <= int(options.get("--interval", 0)) <= roles.MAX_INTERVAL \
                    or not 1 <= int(options.get("--limit", 0)) <= 1000:
                raise ValueError("A job needs a bounded interval and batch limit")
        elif options:
            raise ValueError("A queue worker takes no interval or batch limit")
        environment = definition["environment"]
        row = profile.r1_flags[service]
        if (environment.get("KOLOVIBE_ENV") != "staging" or environment.get("DJANGO_DEBUG") != "0"
                or environment.get("KOLOVIBE_SERVICE_NAME") != service
                or environment.get("KOLOVIBE_STAGING_ACCOUNTS") != row[cluster.FLAG_ACCOUNTS]
                or environment.get("KOLOVIBE_STAGING_PRIVILEGED") != row[cluster.FLAG_PRIVILEGED]
                or environment.get("KOLOVIBE_STAGING_CAPABILITIES") != row[cluster.FLAG_CAPABILITIES]
                or environment.get("KOLOVIBE_STAGING_CREATOR_ONBOARDING", "0") != row[cluster.FLAG_ONBOARDING]):
            raise ValueError("A worker must carry exactly its service's reviewed R1 flag row")
        if any(re.search(r"(PASSWORD|SECRET_KEY|TOKEN|OUTBOUND_KEY|CALLER_KEYS|ACCESS_KEY|RABBITMQ_URL)$", key)
               for key in environment):
            raise ValueError("Persistent credentials must be secret files, not environment values")
        if "KOLOVIBE_RABBITMQ_URL" in environment:
            raise ValueError("The broker URI must be a secret file")
        broker = service in ("content", "engagement", "points")
        if ("broker_private" in definition["networks"]) != broker or "private" not in definition["networks"] \
                or "data_private" not in definition["networks"] or len(definition["networks"]) != 2 + broker:
            raise ValueError("A worker joins the service and data networks, and the messaging network only if it uses the broker")
        placement = definition["deploy"].get("placement", {}).get("constraints")
        if placement != [profile.worker_constraint]:
            raise ValueError("AWS processes must carry the exact hostname pin and no label constraint")
        if definition["deploy"]["replicas"] != 0:
            raise ValueError("Candidate processes start at zero replicas")
        if definition["deploy"]["update_config"]["failure_action"] != "rollback":
            raise ValueError("Staging rollout must fail with rollback")
        limits = definition["deploy"]["resources"]
        limit, reservation = memory_bytes(limits["limits"]["memory"]), memory_bytes(limits["reservations"]["memory"])
        if reservation > limit or limit > MAX_PROCESS_MEMORY:
            raise ValueError("A process memory budget must be bounded and its reservation within its limit")
        mounted = {secret["target"]: secret["source"] for secret in definition["secrets"]}
        expected = {target: (name if not name.startswith("kolovibe_") else name)
                    for target, name in cluster.convention_secrets(service).items()}
        if service == "identity":
            expected.update(smtp_user="kolovibe_identity_smtp_user_20261110_v1",
                            smtp_password="kolovibe_identity_smtp_password_20261110_v1",  # pragma: allowlist secret
                            account_approvals="kolovibe_account_approval" + cluster.R1_SECRET_SUFFIX)
        expected.update(profile.r1_rollout[service]["mounts"])
        if mounted != expected:
            raise ValueError("A worker mounts exactly the secrets of its API service plus the reviewed R1 mounts")
        for secret in definition["secrets"]:
            if (secret["uid"] != "10001" or secret["gid"] != "10001" or secret["mode"] != 0o400
                    or stack["secrets"].get(secret["source"]) != {"external": True}):
                raise ValueError("Staging secrets must be external, service-readable and owner-only")
        budget[name] = limit
    unused = set(stack["secrets"]) - {s["source"] for d in stack["services"].values() for s in d["secrets"]}
    if unused:
        raise ValueError("The stack declares secrets that no process mounts")
    return budget


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=PROFILES, default=ORACLE_PROFILE)
    parser.add_argument("--release-dir", help="with --aws-stack: the downloaded published-image-<sha> artifact")
    parser.add_argument("--aws-stack", action="store_true",
                        help="validate infra/swarm/staging-aws.yml (the AWS R1 worker and job services) instead")
    args = parser.parse_args()
    if args.aws_stack:
        loaded = load_stack(AWS_STACK, os.environ)
        budget = validate_aws(loaded)
        if args.release_dir:
            print("release evidence matches both digests; revision", check_release_evidence(args.release_dir, loaded))
        print("AWS R1 worker stack passed offline; planned memory limits (MiB):",
              {name: limit // 1024 ** 2 for name, limit in budget.items()},
              "total", sum(budget.values()) // 1024 ** 2, "MiB; live capacity and secrets still unverified")
        raise SystemExit(0)
    if args.profile != ORACLE_PROFILE:
        validate({}, args.profile)  # raises the explicit refusal before any input is read
    validate(load_stack(ROOT / "infra/swarm/staging.yml", os.environ), args.profile)
    print("Staging candidate inputs and static boundaries passed; live acceptance still required")
