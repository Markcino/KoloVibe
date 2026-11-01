"""Validate the restricted staging candidate without contacting Docker or a VM."""

import os
from pathlib import Path
import re

import yaml

ROOT = Path(__file__).resolve().parents[1]
INPUT = re.compile(r"\$\{([A-Z_]+):\?[^}]+\}")


def load_stack(path, environment):
    def replace(match):
        name = match[1]
        value = environment.get(name, "")
        if not value or not re.fullmatch(r"[a-zA-Z0-9_.:/@,-]+", value):
            raise ValueError(f"Missing/invalid non-secret staging input: {name}")
        return value

    return yaml.safe_load(INPUT.sub(replace, Path(path).read_text()))


def validate(stack):
    if set(stack["services"]) != {"gateway", "content", "creators"}:
        raise ValueError("Restricted staging must contain only the metadata slice")
    for name, service in stack["services"].items():
        if not re.fullmatch(rf"ghcr\.io/markcino/kolovibe/{name}@sha256:[0-9a-f]{{64}}",
                            service["image"]):
            raise ValueError("Staging requires an immutable verified service image digest")
        if service.get("ports") or service.get("volumes") or service.get("privileged"):
            raise ValueError("Staging services must not publish ports or mount host paths")
        if service["user"] != "10001:10001" or not service.get("read_only"):
            raise ValueError("Staging requires a non-root read-only runtime")
        environment = service["environment"]
        if (environment["KOLOVIBE_ENV"] != "staging" or environment["DJANGO_DEBUG"] != "0"
                or environment["KOLOVIBE_STAGING_ACCOUNTS"] != "0"
                or environment["KOLOVIBE_SERVICE_NAME"] != name):
            raise ValueError("Staging capability/environment gate was changed")
        if any(re.search(r"(PASSWORD|SECRET_KEY|TOKEN|OUTBOUND_KEY|CALLER_KEYS)$", key)
               for key in environment):
            raise ValueError("Persistent credentials must be secret files, not environment values")
        if service["networks"] != ["private"]:
            raise ValueError("Staging services must use only the approved private network")
        if service["healthcheck"]["test"] != ["CMD", "python", "-m", "staging_runtime.probe"]:
            raise ValueError("Staging requires the verified-TLS readiness probe")
        if service["deploy"]["update_config"]["failure_action"] != "rollback":
            raise ValueError("Staging rollout must fail with rollback")
        for secret in service["secrets"]:
            if (secret["uid"] != "10001" or secret["gid"] != "10001"
                    or secret["mode"] != 0o400
                    or stack["secrets"][secret["source"]] != {"external": True}):
                raise ValueError("Staging secrets must be external, service-readable and owner-only")
    if not stack["networks"]["private"].get("external"):
        raise ValueError("Staging network must already be approved and provisioned")


if __name__ == "__main__":
    validate(load_stack(ROOT / "infra/swarm/staging.yml", os.environ))
    print("Staging candidate inputs and static boundaries passed; live acceptance still required")
