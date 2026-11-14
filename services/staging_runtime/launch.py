"""Select exactly one service from the shared image and replace PID 1 with WSGI."""

import argparse
import importlib
import os
from pathlib import Path
import sys

from staging_runtime import SERVICES


def service_directory(root, name):
    if name not in SERVICES:
        raise RuntimeError("KOLOVIBE_SERVICE_NAME must select one supported service")
    directory = Path(root) / name
    if not (directory / "service/settings.py").is_file():
        raise RuntimeError("Selected service is missing from the shared image")
    return directory


def run_role(root, directory, service, role, interval, limit):
    from staging_runtime import roles

    capability, kind, target, queue = roles.resolve(service, role)
    sys.path[:0] = [str(root), str(directory)]
    os.environ["DJANGO_SETTINGS_MODULE"] = "service.settings"
    import django
    from django.conf import settings

    django.setup()
    roles.require_capability(settings, capability)
    if kind == "celery":
        roles.run_celery(target, queue)
    else:
        roles.run_job(target, interval, limit)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-settings", action="store_true")
    parser.add_argument("--role", help="worker or scheduled-job role for this service instead of the API")
    parser.add_argument("--interval", type=int, default=30, help="seconds between job runs (jobs only)")
    parser.add_argument("--limit", type=int, default=100, help="batch size per job run (jobs only)")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    service = os.environ.get("KOLOVIBE_SERVICE_NAME")
    directory = service_directory(root, service)
    os.chdir(directory)
    sys.path.insert(0, str(directory))
    if args.check_settings:
        importlib.import_module("service.settings")
        if args.role:
            from staging_runtime import roles

            roles.resolve(service, args.role)
        return
    if args.role:
        run_role(root, directory, service, args.role, args.interval, args.limit)
        return
    os.execv(sys.executable, [
        sys.executable, "-m", "gunicorn",
        "--chdir", str(directory),
        "--pythonpath", ",".join((str(root), str(directory))),
        "--config", str(root / "staging_runtime/gunicorn.conf.py"),
        "staging_runtime.wsgi:application",
    ])


if __name__ == "__main__":
    main()
