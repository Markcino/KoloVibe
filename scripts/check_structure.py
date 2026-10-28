from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVICES = ("gateway", "identity", "creators", "content", "engagement", "points", "moderation", "audit")
REQUIRED = ("manage.py", "service/__init__.py", "service/settings.py", "service/urls.py", "service/health.py", "tests/__init__.py", "tests/test_health.py")
for name in SERVICES:
    for path in REQUIRED:
        if not (ROOT / "services" / name / path).is_file():
            raise RuntimeError(f"Missing {name}/{path}")
print(f"Structure OK: {len(SERVICES)} services")
