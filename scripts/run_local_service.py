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
    env = os.environ.copy()
    for name in list(env):
        if name.startswith("KOLOVIBE_") and name.endswith("_DJANGO_SECRET_KEY"):
            del env[name]
    env["KOLOVIBE_ENV"] = "local"
    env["DJANGO_SECRET_KEY"] = secret
    env["DJANGO_DEBUG"] = values.get("DJANGO_DEBUG", "0")
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
