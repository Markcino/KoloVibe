# Container verification and GHCR publication

One shared Django image contains all eight services and the infrastructure-only
`staging_runtime` package. It uses the existing Dockerfile, pinned Python base,
hash-locked dependencies and UID/GID 10001. Each container selects exactly one
service with `KOLOVIBE_SERVICE_NAME`; missing/unknown names and path traversal
fail startup. The launcher changes to that service's directory and replaces PID 1
with Gunicorn. Only the selected service's `service` package is on its application
import path. Local developer launchers remain unchanged.

This is shared packaging, not a merged application: gateway, identity, creators,
content, engagement, points, moderation and audit still run separately, with
distinct runtime secrets, logins, schema permissions and capability gates.
All source code is visible inside the shared image; separate images no longer
provide code-distribution isolation. Updating the image requires coordinated
digest promotion/rollback across the service containers. Production stays blocked.

## Required quality gate

The single [ci_cd workflow](../../.github/workflows/ci_cd.yml) runs backend/web, Flutter, source security, dependency advisories and all eight image checks on PRs and main pushes. Existing required job/check names are preserved, so the repository's branch-protection check list does not change. Backend tests include a disposable TLS-only PostgreSQL fixture: migrations for all eight services, cross-service SQL access denial, nonce replay/expiry/audience checks, ledger guards and transactional inbox/outbox tests. The publisher in the outbox test is a controlled double, not a live RabbitMQ broker.

The `image-build` job builds and scans the shared image **once**, generates one
SBOM and uploads one commit-bound artifact on PR, main and manual CI runs.
The artifact contains the archive/checksum, image identity, complete eight-service
inventory, commit and SBOM. The eight `build-and-verify` matrix jobs download/load
that exact artifact without rebuilding, smoke-test their selected service and
verify production/incomplete-staging refusal. Existing matrix check names stay
unchanged. PR/manual artifacts are needed for same-run testing; neither event
can publish or receive registry write permissions.

The `publish` job uses native `needs` dependencies on every quality job, including the entire image matrix and reusable advisory scan. GitHub's default success condition prevents publication when a required job fails, is cancelled or is skipped; pending jobs must finish first. The publication condition additionally requires a main-branch push. There is no `workflow_run` trigger, API polling gate or cross-run artifact selection.

## Single entry point

Use **Actions → ci_cd → Run workflow** for manual operations:

| Event / operation | Jobs |
| --- | --- |
| Main push | All quality jobs, then GHCR publication if all succeed |
| Pull request | All quality jobs; no publication |
| Manual `ci` (default) | All quality jobs on the selected ref; no publication |
| Weekly schedule | Dependency advisory scan |
| Non-main branch push | No workflow; use a PR or manual `ci` |
| Manual `dependency-locks` on `security/ci-hardening` | Generate, validate, commit and upload lockfiles; only this job has repository write access |
| Manual `staging-security` on reviewed `main` | Environment-protected read-only staging verification |

Invalid maintenance/staging branch selections fail explicitly. The existing lock job's GITHUB_TOKEN push does not trigger another Actions run: manually run `ci` on the generated commit before relying on its checks. Staging secrets remain confined to the `staging-security-review` environment; see the [verification runbook](../security/staging-verification.md).

## Publication

After the shared build/scan, all eight service checks and every other quality job
pass, one publication job downloads the artifact from **its own workflow run**.
It verifies `github.sha`, complete inventory, image identity, SBOM and archive
bytes, loads the same tested image without rebuilding, and publishes once to:

```text
ghcr.io/markcino/kolovibe/services:<full-commit>-<image-config-sha256>
```

Including the image configuration identity prevents a rebuild of the same commit from replacing a different artifact's tag. No moving `latest` tag is published. The job pulls the published image back, verifies its image identity, and records one remote digest/tag artifact and the job summary. Repeated publication of the same verified artifact is idempotent. Historical per-service packages are not deleted; future builds publish only the shared `services` package.

## Running separate services

Build once (no `SERVICE` build argument):

```bash
docker build -f infra/docker/Dockerfile.service -t kolovibe/services:ci .
```

Run that image once per required service with `KOLOVIBE_SERVICE_NAME=gateway`,
`identity`, etc. Staging also needs the existing secret files and approved
configuration; never set local mode on a VM. See the
[Swarm candidate](../../infra/swarm/README.md), which uses one `KOLOVIBE_IMAGE`
digest across all eight APIs while preserving distinct secret mounts.
The same deployment YAML defines RabbitMQ with its own pinned DHI image.
All replicas remain zero until activation prerequisites are accepted.
The optional `--check-settings` entrypoint argument validates the selected
service without starting a server; arbitrary service paths/commands are rejected.

Authentication uses `${{ secrets.GITHUB_TOKEN }}` with `packages: write` **only** in the gated publication job. No PAT is required. If an existing GHCR package has restricted Actions access, the owner must grant this repository access; authentication/push failures are not suppressed.

## Credentials and activation

Persistent DB, broker, provider, private-registry and environment credentials must be GitHub Actions secrets, preferably scoped to the approved named environment. Document names, never values. Pass runtime credentials through restricted temporary files or external runtime secrets; do not use Docker build arguments or image layers.

Disposable test-only credentials are generated inside isolated runners, never used against deployed systems, and removed with their fixture. The container smoke credential is masked. The current public Python base requires no private-registry login. Any future DHI/private base requires separately configured Actions secret names and approved access.

No local push, merge or VM deployment is part of this change. The workflow must reach main through the normal PR process before publication can execute. A package upload does not authorize staging or production activation. Images reject unknown/production environments and staging without its required secret files, TLS and capability configuration. The image matrix checks these refusals, plus local HTTP behavior under Gunicorn. Real staging Gunicorn/TLS journeys use isolated runner PostgreSQL and certificates in the backend job; successful staging-profile execution inside an actual image remains an additional acceptance requirement.

Dependency lock generation resolves the CI lock first, then constrains the runtime
lock to it so shared packages do not conflict with audit/SBOM tools. Gunicorn is
pinned at 26.2.0; packaging 25.0 satisfies the existing CycloneDX tool constraint.

## Validation and remaining evidence

Current shared-image/single-deployment validation:

- `.venv/bin/python -m unittest discover -s scripts -p 'test_*.py'`: **60 passed**,
  including real HTTP startup for all eight selections through the shared launcher,
  exactly one build/publish wiring, inventory/checksum rejection and deployment
  digest, secret, capacity, zero-replica and private-network boundaries.
- `PYTHONPATH=scripts .venv/bin/python -m verify_staging_runtime`: **passed**,
  including shared-launcher checks for all staging profiles and isolated TLS,
  accounts, rotation, readiness, migration and dependency-outage journeys.
- `actionlint -shellcheck='' .github/workflows/ci_cd.yml`: **passed** using
  checksum-verified 1.7.7; official Compose schema validation of the single
  deployment YAML: **passed**. Docker stack parsing/runtime remains unverified.
- Full repository Bandit enforcement: **zero medium/high**; changed source and
  deployment secret scan: **passed**; structure and `git diff --check`: **passed**.

Historical consolidation evidence below predates the shared-image change:

Application/build evidence remains in the [API test roadmap](API_Test_Deployment_Roadmap.md#current-continuation-evidence). For this workflow consolidation, `actionlint -shellcheck='' .github/workflows/ci_cd.yml` passed. `.venv/bin/python -m unittest -v scripts/test_ci_cd.py scripts/test_image_artifact.py scripts/test_staging_verification.py` passed 20 tests covering event filters, same-run artifact wiring, required dependencies, permissions, maintenance branch errors and existing artifact/probe rejection behavior. These are local/static checks, not remote Actions execution.

The full script suite (`.venv/bin/python -m unittest discover -s scripts -p 'test_*.py'`) passed 39 tests. Bandit enforcement on the new workflow regression tests passed with zero medium/high findings; the existing quality, image-build and lock-generation steps were checked against their previous definitions and preserved.

Docker is not installed in the current local environment. New image builds/scans, GHCR uploads and remote digest evidence are **pending actual Actions execution**, not claimed successful.

Live RabbitMQ retries/dead-letter/crash recovery, workload-credential rotation, deployed PostgreSQL isolation, Nginx/Swarm private networking, observability, backups/restore/rollback and security/sponsor acceptance remain separate Stage 3 gates.
