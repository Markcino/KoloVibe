from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVICES = ("gateway", "identity", "creators", "content", "engagement", "points", "moderation", "audit")
REQUIRED = ("manage.py", "service/__init__.py", "service/settings.py", "service/urls.py", "service/health.py", "tests/__init__.py", "tests/test_health.py")
for name in SERVICES:
    for path in REQUIRED:
        if not (ROOT / "services" / name / path).is_file():
            raise RuntimeError(f"Missing {name}/{path}")
REPOSITORY_PATHS = (
    "apps/mobile/lib/main.dart",
    "apps/mobile/pubspec.yaml",
    "apps/mobile/pubspec.lock",
    "apps/mobile/android/gradlew",
    "apps/mobile/android/gradlew.bat",
    "apps/mobile/android/gradle/wrapper/gradle-wrapper.jar",
    "apps/web_django/static/images/logo.svg",
    "apps/web_django/static/images/landscape_logo_with_name.svg",
    "apps/web_django/static/images/portrait_logo_with_name.svg",
    "packages/contracts/openapi/health.yaml",
    "infra/docker/Dockerfile.service",
    "infra/postgres/schema_isolation.sql",
    "infra/nginx/README.md",
    "infra/swarm/README.md",
    "infra/observability/README.md",
    "docs/adr/README.md",
    "tests/security/README.md",
)
for path in REPOSITORY_PATHS:
    if not (ROOT / path).is_file():
        raise RuntimeError(f"Missing documented repository path: {path}")
for legacy in ("apps/mobile_flutter", "contracts", "apps/web"):
    if (ROOT / legacy).exists():
        raise RuntimeError(f"Unexpected legacy directory: {legacy}")
print(f"Structure OK: {len(SERVICES)} services and approved monorepo layout")
