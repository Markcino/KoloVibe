"""Create the ignored local .env with independent random Django secrets."""

import os
import secrets
from pathlib import Path

from run_local_service import ROOT, SERVICES, read_local_env


def create_local_env(path: Path) -> None:
    lines = ["KOLOVIBE_ENV=local", "DJANGO_DEBUG=0"]
    lines.extend(
        f"KOLOVIBE_{service.upper()}_DJANGO_SECRET_KEY={secrets.token_urlsafe(48)}"
        for service in SERVICES
    )
    lines.extend((
        f"KOLOVIBE_WEB_DJANGO_SECRET_KEY={secrets.token_urlsafe(48)}",
        f"KOLOVIBE_GATEWAY_OUTBOUND_KEY={secrets.token_urlsafe(48)}",
        "KOLOVIBE_GATEWAY_URL=http://127.0.0.1:8000",
        "KOLOVIBE_IDENTITY_URL=http://127.0.0.1:8001",
        "KOLOVIBE_CONTENT_URL=http://127.0.0.1:8002",
    ))
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write("\n".join(lines) + "\n")
    except BaseException:
        path.unlink(missing_ok=True)
        raise


def add_local_peer_configuration(path: Path) -> None:
    """Upgrade an existing private local env without replacing any secret."""
    values = read_local_env(path)
    additions = {
        "KOLOVIBE_WEB_DJANGO_SECRET_KEY": secrets.token_urlsafe(48),
        "KOLOVIBE_GATEWAY_OUTBOUND_KEY": secrets.token_urlsafe(48),
        "KOLOVIBE_GATEWAY_URL": "http://127.0.0.1:8000",
        "KOLOVIBE_IDENTITY_URL": "http://127.0.0.1:8001",
        "KOLOVIBE_CONTENT_URL": "http://127.0.0.1:8002",
    }
    with path.open("a", encoding="utf-8") as stream:
        for key, value in additions.items():
            if key not in values:
                stream.write(f"{key}={value}\n")


if __name__ == "__main__":
    path = ROOT / ".env"
    if path.exists():
        add_local_peer_configuration(path)
        print("Updated missing local peer configuration without replacing existing values")
    else:
        create_local_env(path)
        print("Created owner-only .env with unique secrets for all services")
