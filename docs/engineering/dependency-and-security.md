# Dependency management and security verification

Python services target Python 3.12 and Django 5.2 LTS. Direct dependencies are declared in `requirements-dev.in`; `requirements-dev.txt` is compiled with all transitive dependencies and package hashes. Install with `pip install --require-hashes -r requirements-dev.txt`. Do not manually edit the generated lockfile.

Flutter uses Flutter SDK 3.35.0 and commits `apps/mobile_flutter/pubspec.lock`. CI runs `flutter pub get --enforce-lockfile`; dependency changes require reviewing the lockfile diff.

## Continuous verification

- Django liveness and repository structure checks.
- OpenAPI schema validation.
- `pip-audit` for published Python dependency vulnerabilities.
- `bandit` static Python security analysis.
- `detect-secrets` findings checked as a failing gate.
- CycloneDX SBOM as a downloadable workflow artifact.
- Flutter static analysis, widget tests and dependency lock enforcement.

Scanners are not substitutes for an architecture security review, container scanning, service authorization tests, or staging-specific penetration tests. Those remain separate release criteria.

GitHub Actions security tools and marketplace actions should ultimately be pinned to immutable commit SHAs; deployment credentials must never be granted to PR checks. Report names and workflows are engineering artifacts, not product-facing branding.

## Updating dependencies

In a reviewed PR, update the direct Python dependencies, regenerate hashed locks, run CI and examine advisories. For Flutter, use the pinned Flutter SDK, run `flutter pub upgrade`, review `pubspec.lock`, analyze and execute widget/device tests. Security changes must go through normal review before merge.
