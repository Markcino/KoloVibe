"""Validate the restricted staging candidate without contacting Docker or a VM."""

import os
from pathlib import Path
import re

import yaml

ROOT = Path(__file__).resolve().parents[1]
INPUT = re.compile(r"\$\{([A-Z_]+):\?[^}]+\}")
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


def validate(stack):
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
    if broker["deploy"]["placement"]["constraints"] != ["node.labels.kolovibe.rabbitmq == true"]:
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


if __name__ == "__main__":
    validate(load_stack(ROOT / "infra/swarm/staging.yml", os.environ))
    print("Staging candidate inputs and static boundaries passed; live acceptance still required")
