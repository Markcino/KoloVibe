"""Create the ignored local .env with independent random Django secrets."""

import os
import secrets
from pathlib import Path

from run_local_service import ROOT, SERVICES


def create_local_env(path: Path) -> None:
    lines = ["KOLOVIBE_ENV=local", "DJANGO_DEBUG=0"]
    lines.extend(
        f"KOLOVIBE_{service.upper()}_DJANGO_SECRET_KEY={secrets.token_urlsafe(48)}"
        for service in SERVICES
    )
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write("\n".join(lines) + "\n")
    except BaseException:
        path.unlink(missing_ok=True)
        raise


if __name__ == "__main__":
    create_local_env(ROOT / ".env")
    print("Created owner-only .env with unique secrets for all services")
