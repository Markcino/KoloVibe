# Dependency management and security verification

Python services target Python 3.12 and Django 5.2 LTS. Direct dependencies are declared in `requirements-dev.in`; `requirements-dev.txt` is compiled with all transitive dependencies and package hashes. Install with `pip install --require-hashes -r requirements-dev.txt`. Do not manually edit the generated lockfile.

Flutter uses Flutter SDK 3.47.8 and commits `apps/mobile_flutter/pubspec.lock`. CI runs `flutter pub get --enforce-lockfile`; dependency changes require reviewing the lockfile diff.

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

## Locked baseline

The reviewed lock-generation job produces Python 3.12 SHA-256 package hashes and a Flutter 3.47.8 pubspec.lock. Each proposed dependency change is checked against these committed locks; CI must pass on the updated commit before review.

## CI toolchain lock

`requirements-ci.in` declares security and API-validation tools; `requirements-ci.txt` includes all resolved dependency hashes. The dedicated lock-generation branch refreshes both Python lockfiles together. Runtime and CI tools are installed with `--require-hashes`.

## GitHub Action verification

Third-party actions reference reviewed immutable commits. Moving version tags are not sufficient. Keep a record of the full SHA and update each pinned action only in reviewed pull requests.

## Local service checks

CI uses fixed commands with enumerated service names and a newly generated local-only secret. There is no subprocess-based Python test runner.
