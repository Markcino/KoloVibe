"""Smoke-test one service of the PostgreSQL-only release image on its intended database profile.

The release image has no SQLite. This starts the selected service from the image against a
disposable, TLS-only PostgreSQL (verify-full, least-privilege per-service login, service
schema) and proves that the image serves HTTP, reaches its database over verified TLS, sees
fully applied migrations, and cannot fall back to SQLite. Disposable credentials only.
"""

import argparse
from http.client import HTTPConnection
import json
import os
from pathlib import Path, PurePosixPath
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import time

from test_postgres_foundations import SERVICES, postgres_fixture

SHARE = "/run/kolovibe-smoke"
# The container's tmpfs mount point (as in the Swarm stack), not a host temporary file.
CONTAINER_TMPFS = str(PurePosixPath("/") / "tmp")

# Runs inside the container, in the selected service directory, with the container's own
# environment. It must use only what the release image ships.
DATABASE_PROBE = """
import json, os
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "service.settings")
django.setup()
from django.conf import settings
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
database = settings.DATABASES["default"]
assert database["ENGINE"] == "django.db.backends.postgresql", database["ENGINE"]
assert database["OPTIONS"]["sslmode"] == "verify-full"
with connection.cursor() as cursor:
    cursor.execute("SELECT current_user, current_schema(), (SELECT ssl FROM pg_stat_ssl "
                   "WHERE pid = pg_backend_pid())")
    user, schema, tls = cursor.fetchone()
    cursor.execute("SELECT rolsuper OR rolcreatedb OR rolcreaterole FROM pg_roles "
                   "WHERE rolname = current_user")
    privileged = cursor.fetchone()[0]
assert tls is True, "database connection is not using TLS"
assert privileged is False, "database login must be unprivileged"
executor = MigrationExecutor(connection)
assert not executor.migration_plan(executor.loader.graph.leaf_nodes()), "pending migrations"
print(json.dumps({"service": settings.KOLOVIBE_SERVICE_NAME, "schema": schema, "tls": tls}))
"""

# Without PostgreSQL settings the local profile would use SQLite. The release image must
# refuse instead of silently creating a database file.
SQLITE_FALLBACK_PROBE = """
import os
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "service.settings")
django.setup()
from django.db import connection
connection.ensure_connection()
"""


def docker(*arguments, **options):
    return subprocess.run(["docker", *arguments], text=True, capture_output=True, **options)


def free_port():
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        return reservation.getsockname()[1]


def hardening():
    """Mirror the staging stack: read-only root, tmpfs /tmp, no capabilities."""
    return ["--read-only", "--tmpfs", CONTAINER_TMPFS, "--cap-drop", "ALL",
            "--security-opt", "no-new-privileges"]


def service_options(service):
    return ["-e", "KOLOVIBE_SERVICE_NAME=" + service, "-e", "KOLOVIBE_ENV=local",
            "-e", "DJANGO_SECRET_KEY"]  # value comes from the process environment, not argv


def run_command(image, service, name, port, share, environment):
    """Container command: host networking reaches the fixture's 127.0.0.1 TLS listener."""
    database = [
        "-e", "KOLOVIBE_DB_NAME=" + environment["KOLOVIBE_DB_NAME"],
        "-e", "KOLOVIBE_DB_USER=" + environment["KOLOVIBE_DB_USER"],
        "-e", "KOLOVIBE_DB_HOST=" + environment["KOLOVIBE_DB_HOST"],
        "-e", "KOLOVIBE_DB_PORT=" + environment["KOLOVIBE_DB_PORT"],
        "-e", f"KOLOVIBE_DB_PASSWORD_FILE={SHARE}/password",
        "-e", f"KOLOVIBE_DB_SSLROOTCERT={SHARE}/ca.crt",
    ]
    return ["docker", "run", "-d", "--name", name, "--network", "host", *hardening(),
            "-v", f"{share}:{SHARE}:ro", *service_options(service), *database,
            "-e", f"GUNICORN_CMD_ARGS=--bind 127.0.0.1:{port} --workers 1", image]


def check_without_sqlite(image, service, environment):
    """The release image has no SQLite module and no silent SQLite fallback."""
    result = docker("run", "--rm", *hardening(), "--entrypoint", "python", image,
                    "-c", "import sqlite3")
    if result.returncode == 0:
        raise SystemExit("Release image still provides the sqlite3 module")
    result = docker("run", "--rm", *hardening(), *service_options(service),
                    "-e", "DJANGO_SETTINGS_MODULE=service.settings",
                    "-w", f"/app/services/{service}", "--entrypoint", "python", image,
                    "-c", SQLITE_FALLBACK_PROBE, env=environment)
    if result.returncode == 0:
        raise SystemExit(f"{service}: release image fell back to a SQLite database")
    if "sqlite" not in result.stderr.lower():
        raise SystemExit(f"{service}: fallback refusal was not the missing SQLite module:\n"
                         + result.stderr[-2000:])
    print(f"{service}: no sqlite3 module and no SQLite fallback", flush=True)


def wait_for_live(name, port):
    deadline = time.monotonic() + 40
    while time.monotonic() < deadline:
        if not docker("ps", "--filter", f"name=^{name}$", "--filter", "status=running",
                      "--quiet").stdout.strip():
            raise SystemExit("Container exited unexpectedly")
        connection = HTTPConnection("127.0.0.1", port, timeout=2)
        try:
            connection.request("GET", "/health/live")
            response = connection.getresponse()
            body = json.loads(response.read())
            if response.status != 200 or body != {"status": "ok"}:
                raise SystemExit(f"Unexpected liveness response: {response.status} {body}")
            connection.request("POST", "/health/live")
            post = connection.getresponse()
            post.read()
            if post.status != 405:
                raise SystemExit(f"Liveness accepted POST: {post.status}")
            return
        except (ConnectionError, OSError):
            time.sleep(0.5)
        finally:
            connection.close()
    raise SystemExit("Service liveness timed out")


def smoke(image, service):
    if service not in SERVICES:
        raise SystemExit("Unknown service")
    process_environment = dict(os.environ, DJANGO_SECRET_KEY=secrets.token_urlsafe(48))
    check_without_sqlite(image, service, process_environment)
    with postgres_fixture() as (_, environments), \
            tempfile.TemporaryDirectory(prefix="kolovibe-smoke-share-") as share_directory:
        environment = environments[service]
        share = Path(share_directory)
        # The container user (10001) must read these; they are disposable and public/test-only.
        share.chmod(0o755)
        shutil.copyfile(environment["KOLOVIBE_DB_PASSWORD_FILE"], share / "password")
        shutil.copyfile(environment["KOLOVIBE_DB_SSLROOTCERT"], share / "ca.crt")
        for name in ("password", "ca.crt"):
            (share / name).chmod(0o444)
        name, port = f"kolovibe-smoke-{service}", free_port()
        started = subprocess.run(run_command(image, service, name, port, share, environment),
                                 text=True, capture_output=True, env=process_environment)
        if started.returncode:
            raise SystemExit("Could not start container: " + started.stderr)
        try:
            wait_for_live(name, port)
            probe = docker("exec", "-w", f"/app/services/{service}", name,
                           "python", "-c", DATABASE_PROBE)
            if probe.returncode:
                raise SystemExit(f"{service}: database profile check failed\n" + probe.stderr[-3000:])
            report = json.loads(probe.stdout.strip().splitlines()[-1])
            if report != {"service": service, "schema": service, "tls": True}:
                raise SystemExit(f"{service}: unexpected database profile {report}")
            print(f"{service}: liveness, verified-TLS PostgreSQL, migrations and schema OK", flush=True)
        except BaseException:
            print(docker("logs", name).stdout, file=sys.stderr)
            print(docker("logs", name).stderr, file=sys.stderr)
            raise
        finally:
            docker("rm", "-f", name)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", required=True)
    parser.add_argument("--service", required=True, choices=sorted(SERVICES))
    arguments = parser.parse_args()
    smoke(arguments.image, arguments.service)
