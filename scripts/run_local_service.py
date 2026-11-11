"""Run one Django service with only its own credentials from the root .env.

This launcher is for local development. Staging and production settings remain gated.
"""

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVICES = (
    "gateway", "identity", "creators", "content", "engagement",
    "points", "moderation", "audit",
)


def read_local_env(path: Path) -> dict[str, str]:
    if path.is_symlink() or not path.is_file():
        raise ValueError("Create a regular root .env file before starting a service")
    if path.stat().st_mode & 0o077:
        raise ValueError("Restrict .env permissions to the owner (chmod 600 .env)")
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if not text or text.startswith("#"):
            continue
        if "=" not in text:
            raise ValueError("Invalid .env line: expected KEY=VALUE")
        key, value = text.split("=", 1)
        key, value = key.strip(), value.strip()
        if not key.isidentifier() or key in values:
            raise ValueError("Invalid or repeated .env key")
        values[key] = value
    if values.get("KOLOVIBE_ENV") != "local":
        raise ValueError("This launcher requires KOLOVIBE_ENV=local")
    return values


def environment_for(service: str, values: dict[str, str]) -> dict[str, str]:
    if service not in SERVICES:
        raise ValueError("Unknown service")
    key = f"KOLOVIBE_{service.upper()}_DJANGO_SECRET_KEY"
    secret = values.get(key, "")
    if len(secret) < 32:
        raise ValueError(f"Set a unique {key} of at least 32 characters in .env")
    env = {name: value for name, value in os.environ.items()
           if not name.startswith("KOLOVIBE_")}
    env["KOLOVIBE_ENV"] = "local"
    env["DJANGO_SECRET_KEY"] = secret
    env["DJANGO_DEBUG"] = values.get("DJANGO_DEBUG", "0")
    env["KOLOVIBE_SERVICE_NAME"] = service
    prefix = f"KOLOVIBE_{service.upper()}_"
    required_db = ("DB_NAME", "DB_USER", "DB_HOST", "DB_PASSWORD_FILE", "DB_SSLROOTCERT")
    database = {name: values.get(prefix + name) for name in (*required_db, "DB_PORT")}
    if any(database.values()):
        if not all(database[name] for name in required_db):
            raise ValueError(f"Incomplete PostgreSQL configuration for {service}")
        for name, value in database.items():
            if value:
                env["KOLOVIBE_" + name] = value
    if service in ("engagement", "points") and values.get(prefix + "RABBITMQ_URL"):
        env["KOLOVIBE_RABBITMQ_URL"] = values[prefix + "RABBITMQ_URL"]
    gateway_key = values.get("KOLOVIBE_GATEWAY_OUTBOUND_KEY", "")
    if service == "gateway":
        if "KOLOVIBE_PUBLIC_WEB_ORIGIN" in values:
            env["KOLOVIBE_PUBLIC_WEB_ORIGIN"] = values["KOLOVIBE_PUBLIC_WEB_ORIGIN"]
        for platform in ("IOS", "ANDROID"):
            for field in ("MIN_VERSION", "LATEST_VERSION", "STORE_URL"):
                name = f"KOLOVIBE_APP_{field}_{platform}"
                if name in values:
                    env[name] = values[name]
        if len(gateway_key) >= 32:
            env["KOLOVIBE_GATEWAY_OUTBOUND_KEY"] = gateway_key
        for name in ("identity", "content", "creators", "engagement"):
            url = values.get(f"KOLOVIBE_{name.upper()}_URL")
            if url:
                env[f"KOLOVIBE_{name.upper()}_URL"] = url
    elif service in ("identity", "content", "creators", "engagement") and len(gateway_key) >= 32:
        env["KOLOVIBE_CALLER_GATEWAY_KEY"] = gateway_key
    if service in ("gateway", "content", "moderation") and values.get("KOLOVIBE_LOCAL_MODERATION_ENABLED") == "1":
        moderation_key = values.get("KOLOVIBE_MODERATION_OUTBOUND_KEY", "")
        if len(moderation_key) < 32 or moderation_key == gateway_key:
            raise ValueError("Local moderation requires a distinct outbound key")
        env["KOLOVIBE_LOCAL_MODERATION_ENABLED"] = "1"
        if service == "gateway":
            env["KOLOVIBE_MODERATION_URL"] = values.get("KOLOVIBE_MODERATION_URL", "")
        elif service == "content":
            env["KOLOVIBE_CALLER_MODERATION_KEY"] = moderation_key
        else:
            env["KOLOVIBE_MODERATION_OUTBOUND_KEY"] = moderation_key
            env["KOLOVIBE_CONTENT_URL"] = values.get("KOLOVIBE_CONTENT_URL", "")
            if len(gateway_key) >= 32:
                env["KOLOVIBE_CALLER_GATEWAY_KEY"] = gateway_key
    if service in ("gateway", "content") and values.get("KOLOVIBE_LOCAL_MEDIA_ENABLED") == "1":
        env["KOLOVIBE_LOCAL_MEDIA_ENABLED"] = "1"
        if service == "content":
            for name in ("KOLOVIBE_R2_ACCOUNT_ID", "KOLOVIBE_R2_MEDIA_BUCKET",
                         "KOLOVIBE_R2_ACCESS_KEY_FILE", "KOLOVIBE_R2_SECRET_KEY_FILE"):
                if name in values:
                    env[name] = values[name]
            broker = values.get("KOLOVIBE_CONTENT_RABBITMQ_URL")
            if broker:
                env["KOLOVIBE_RABBITMQ_URL"] = broker
    if service in ("gateway", "engagement", "points") and values.get("KOLOVIBE_LOCAL_POINTS_ENABLED") == "1":
        if len(gateway_key) < 32:
            raise ValueError("Local points require a Gateway signing key")
        env["KOLOVIBE_LOCAL_POINTS_ENABLED"] = "1"
        if service == "gateway":
            if values.get("KOLOVIBE_POINTS_URL"):
                env["KOLOVIBE_POINTS_URL"] = values["KOLOVIBE_POINTS_URL"]
        else:
            if not all(database[name] for name in required_db):
                raise ValueError(f"Local points require PostgreSQL for {service}")
            if service == "points":
                env["KOLOVIBE_CALLER_GATEWAY_KEY"] = gateway_key
    if service == "audit" and values.get("KOLOVIBE_AUDIT_CALLER_KEYS_FILE"):
        env["KOLOVIBE_CALLER_KEYS_FILE"] = values["KOLOVIBE_AUDIT_CALLER_KEYS_FILE"]
    if service == "moderation" and values.get("KOLOVIBE_LOCAL_MODERATION_ENABLED") == "1":
        if values.get("KOLOVIBE_AUDIT_URL"):
            env["KOLOVIBE_AUDIT_URL"] = values["KOLOVIBE_AUDIT_URL"]
        if values.get("KOLOVIBE_INTERNAL_CA_FILE"):
            env["KOLOVIBE_INTERNAL_CA_FILE"] = values["KOLOVIBE_INTERNAL_CA_FILE"]
    if service == "identity":
        for name in ("KOLOVIBE_SMTP_HOST", "KOLOVIBE_SMTP_PORT",
                     "KOLOVIBE_SMTP_USER", "KOLOVIBE_SMTP_PASSWORD", "KOLOVIBE_FROM_EMAIL"):
            if name in values:
                env[name] = values[name]
    return env


def main(argv: list[str]) -> int:
    if len(argv) < 3 or argv[1] not in SERVICES:
        print("Usage: python scripts/run_local_service.py SERVICE manage.py-arguments...", file=sys.stderr)
        return 2
    try:
        values = read_local_env(ROOT / ".env")
        env = environment_for(argv[1], values)
    except ValueError as error:
        print(error, file=sys.stderr)
        return 2
    command = [sys.executable, "manage.py", *argv[2:]]
    return subprocess.call(command, cwd=ROOT / "services" / argv[1], env=env)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
