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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-settings", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    directory = service_directory(root, os.environ.get("KOLOVIBE_SERVICE_NAME"))
    os.chdir(directory)
    sys.path.insert(0, str(directory))
    if args.check_settings:
        importlib.import_module("service.settings")
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
