"""Local service tests. Never sets or uses deployment credentials."""
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NAMES = ("gateway", "identity", "creators", "content", "engagement", "points", "moderation", "audit")
for name in NAMES:
    env = dict(
        os.environ,
        KOLOVIBE_ENV="local",
        DJANGO_SECRET_KEY="kolovibe-local-tests-only-secret-key-123456",
        DJANGO_DEBUG="0",
    )
    subprocess.run(
        [sys.executable, "manage.py", "test", "tests", "--verbosity", "1"],
        cwd=ROOT / "services" / name,
        env=env,
        check=True,
    )
print("All local service checks passed")
