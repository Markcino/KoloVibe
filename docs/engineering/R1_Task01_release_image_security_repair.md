# R1 Task 01: release image `sqlite-libs` repair

Status: **proposed fix on `fix/r1-task01-release-image-sqlite`; not merged, not deployed, no image published.**
Image build, scan and the eight-service container matrix run only in GitHub Actions (this workstation has no Docker daemon, so they were **not** run locally). The CI result for this branch must be recorded in the pull request before review sign-off.

## Root cause

- The pinned `python:3.12.16-alpine3.23` base installs `sqlite-libs 3.53.4-r0` because CPython's `_sqlite3` extension links it. Alpine has no fixed package; `alpine3.24` ships the same version, so a base bump does not help (see the [Stage 4A record](R1_Stage4A_security_ci_acceptance.md)).
- Grype reports four High CVEs against it (CVE-2026-119586, -119379, -119374, -119373). The `anchore/scan-action` step (`fail-build: true`, `severity-cutoff: high`) correctly fails `image-build`, so the eight-service matrix and `publish` are skipped.
- Nothing in a release profile uses SQLite. Django only loads `django.db.backends.sqlite3` when a service falls back to `local.sqlite3`, which settings do only for `KOLOVIBE_ENV=local` **without** PostgreSQL variables. Staging already refuses it (`staging_runtime.configure`). The only consumer of the SQLite profile inside the image was the CI smoke test, which started each service on the local profile (seven of eight touch the database at startup).

## Architecture

One Dockerfile, two targets (the base image digest is unchanged):

| Target | Contents | Used for |
| --- | --- | --- |
| `local` | The previous image, SQLite included. | Developers who want the SQLite profile in a container. Never scanned, verified, published or deployed. |
| `release` (**last stage, so the default**) | `local` plus removal of `sqlite-libs`, the `sqlite3` package and `_sqlite3` extension. | The image CI builds, scans, smoke-tests and publishes. |

The release stage first re-pins every other Python runtime library under a new apk virtual package, so deleting the base image's `.python-rundeps` virtual package cannot cascade into libraries Python still needs. It then fails the build (explicit `if`, not `!`, which `set -e` ignores) if SQLite is still installed or importable, or if the stdlib modules and the locked application libraries (Django, psycopg, cryptography, Celery, Gunicorn) no longer import, or `pip check` fails.

CI changes (all gates kept):

- `docker build --target release`.
- New gate: the image must have no importable `sqlite3` and no SQLite apk package; the image SBOM must list no SQLite component.
- The Grype step is **unchanged** (`fail-build`, `severity-cutoff: high`, no ignore file). Secret scanning, pip-audit, OSV, Bandit and `publish` conditions are unchanged.
- The eight-service matrix now runs [`scripts/smoke_release_image.py`](../../scripts/smoke_release_image.py): the selected service starts from the exact tested image (read-only root, tmpfs, no capabilities) against disposable TLS-only PostgreSQL (`verify-full`, per-service unprivileged login, service schema, migrations applied). It checks liveness, a verified-TLS database session, no pending migrations, no `sqlite3` module and **no silent SQLite fallback**. The existing refusal checks for unset, production and incomplete staging profiles are kept.

## Compatibility impact

- Staging, production-gated profiles and the Swarm stack: none (they already require TLS PostgreSQL).
- `KOLOVIBE_ENV=local` in the release image now requires the PostgreSQL variables; without them the first database access fails with a missing-`sqlite3` error instead of creating a file.
- Host-side local development and the `python` CI job (SQLite unit suites, `makemigrations --check`) are untouched. Use `--target local` for a SQLite container.

## Evidence gathered on this workstation

| Check | Result |
| --- | --- |
| `origin/main` | `d32cb60`, as previously verified. |
| Full disposable TLS PostgreSQL suite (`scripts/test_postgres_foundations.py`, all eight services migrated and tested) with `sqlite3`/`_sqlite3` made unimportable | passes |
| Container database probe and SQLite-fallback probe, run on the host with `sqlite3` blocked, all eight services (PostgreSQL 14 fixture) | PostgreSQL probe passes; fallback refused for every service |
| Negative control: same fallback probe with SQLite available | succeeds, so the probe does discriminate |
| `python -m unittest discover -s scripts` | 101 pass (97 before; four new Dockerfile and workflow contracts) |
| Mutation checks: weaker cutoff, dropped `--target release`, removal deleted, `!` negation, SQLite smoke profile | each fails a contract test |
| Bandit gate; secret scan of changed files | 0 medium or high; pass |
| Docker build, Grype scan, SBOM, eight-container matrix | **not run locally; see CI** |

## Residual risks and decisions for the owner

1. **Unverified build assumptions.** The `apk` virtual-package handling and import checks follow Alpine and Docker Python image conventions but were never executed here. The build is designed to fail loudly, not silently, if they are wrong; CI is the proof.
2. **Layer history.** `sqlite-libs` still exists inside the lower base-image layer of `image.tar` (hidden by the upper layer, absent from the final filesystem, apk database and SBOM). Scanners that scan the squashed filesystem will not report it; an all-layers scanner would. Eliminating it requires flattening the root filesystem into a `FROM scratch` image and re-declaring the base `ENV`. Not done: more moving parts and not verifiable without Docker. Owner decision.
3. **Remaining image findings.** Findings below High (pip, Python 3.12.16, busybox, per the Stage 4A record) are unchanged and below the gate; any new finding in CI is reported on the PR rather than ignored.
4. No image signature or provenance (Stage 4A finding 4) is unchanged.
