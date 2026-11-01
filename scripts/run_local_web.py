"""Launch the local web client with only its own secret and loopback gateway URL."""

import os
import subprocess
import sys

from run_local_service import ROOT, read_local_env


def main(args):
    values = read_local_env(ROOT / ".env")
    secret = values.get("KOLOVIBE_WEB_DJANGO_SECRET_KEY", "")
    if len(secret) < 32:
        raise ValueError("Initialize a private local web secret")
    env = os.environ.copy()
    for name in list(env):
        if name.startswith("KOLOVIBE_") and ("SECRET" in name or "KEY" in name or "PASSWORD" in name):
            env.pop(name)
    env["KOLOVIBE_ENV"] = "local"
    env["DJANGO_SECRET_KEY"] = secret
    env["KOLOVIBE_GATEWAY_URL"] = values.get("KOLOVIBE_GATEWAY_URL", "")
    return subprocess.call([sys.executable, "manage.py", *args],
                           cwd=ROOT / "apps" / "web_django", env=env)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
