# Container verification and GHCR publication

Eight Django service images use the shared Dockerfile, a pinned Python base-image digest, hash-locked dependencies and UID/GID 10001. Each contains only its owning service. Images are currently **local/CI-only**, not production runtime images.

## Required quality gate

The single [ci_cd workflow](../../.github/workflows/ci_cd.yml) runs backend/web, Flutter, source security, dependency advisories and all eight image checks on PRs and main pushes. Existing required job/check names are preserved, so the repository's branch-protection check list does not change. Backend tests include a disposable TLS-only PostgreSQL fixture: migrations for all eight services, cross-service SQL access denial, nonce replay/expiry/audience checks, ledger guards and transactional inbox/outbox tests. The publisher in the outbox test is a controlled double, not a live RabbitMQ broker.

Every main image is built, smoke-tested and scanned before preservation as a commit-bound artifact. The artifact includes the image archive, checksum, image identity, service, commit and CycloneDX SBOM. PRs do not upload publication artifacts or receive registry write permissions.

The `publish` job uses native `needs` dependencies on every quality job, including the entire image matrix and reusable advisory scan. GitHub's default success condition prevents publication when a required job fails, is cancelled or is skipped; pending jobs must finish first. The publication condition additionally requires a main-branch push. There is no `workflow_run` trigger, API polling gate or cross-run artifact selection.

## Single entry point

Use **Actions → ci_cd → Run workflow** for manual operations:

| Event / operation | Jobs |
| --- | --- |
| Main push | All quality jobs, then GHCR publication if all succeed |
| Pull request | All quality jobs; no publication |
| Manual `ci` (default) | All quality jobs on the selected ref; no publication |
| Feature/chore/fix/security branch push; weekly schedule | Dependency advisory scan |
| Push to `security/ci-hardening`, or manual `dependency-locks` on that branch | Generate, validate, commit and upload lockfiles; only this job has repository write access |
| Manual `staging-security` on reviewed `main` | Environment-protected read-only staging verification |

Invalid maintenance/staging branch selections fail explicitly. The existing lock job's GITHUB_TOKEN push does not trigger another Actions run: manually run `ci` on the generated commit before relying on its checks. Staging secrets remain confined to the `staging-security-review` environment; see the [verification runbook](../security/staging-verification.md).

## Publication

After all dependencies pass, the publication-only job downloads artifacts from **its own workflow run**. It validates `github.sha`, service, image identity, SBOM and archive bytes, loads the same tested image without rebuilding, and publishes it to:

```text
ghcr.io/markcino/kolovibe/<service>:<full-commit>-<image-config-sha256>
```

Including the image configuration identity prevents a rebuild of the same commit from replacing a different artifact's tag. No moving `latest` tag is published. The job pulls the published image back, verifies its image identity, and records the remote digest and tag in per-service workflow artifacts and the job summary. Repeated publication of the same verified artifact is idempotent.

Authentication uses `${{ secrets.GITHUB_TOKEN }}` with `packages: write` **only** in the gated publication job. No PAT is required. If an existing GHCR package has restricted Actions access, the owner must grant this repository access; authentication/push failures are not suppressed.

## Credentials and activation

Persistent DB, broker, provider, private-registry and environment credentials must be GitHub Actions secrets, preferably scoped to the approved named environment. Document names, never values. Pass runtime credentials through restricted temporary files or external runtime secrets; do not use Docker build arguments or image layers.

Disposable test-only credentials are generated inside isolated runners, never used against deployed systems, and removed with their fixture. The container smoke credential is masked. The current public Python base requires no private-registry login. Any future DHI/private base requires separately configured Actions secret names and approved access.

No local push, merge or VM deployment is part of this change. The workflow must reach main through the normal PR process before publication can execute. A package upload does not authorize staging or production activation: the images still use Django's development server and reject staging/production settings.

## Validation and remaining evidence

Application/build evidence remains in the [API test roadmap](API_Test_Deployment_Roadmap.md#current-continuation-evidence). For this workflow consolidation, `actionlint -shellcheck='' .github/workflows/ci_cd.yml` passed. `.venv/bin/python -m unittest -v scripts/test_ci_cd.py scripts/test_image_artifact.py scripts/test_staging_verification.py` passed 20 tests covering event filters, same-run artifact wiring, required dependencies, permissions, maintenance branch errors and existing artifact/probe rejection behavior. These are local/static checks, not remote Actions execution.

The full script suite (`.venv/bin/python -m unittest discover -s scripts -p 'test_*.py'`) passed 39 tests. Bandit enforcement on the new workflow regression tests passed with zero medium/high findings; the existing quality, image-build and lock-generation steps were checked against their previous definitions and preserved.

Docker is not installed in the current local environment. New image builds/scans, GHCR uploads and remote digest evidence are **pending actual Actions execution**, not claimed successful.

Live RabbitMQ retries/dead-letter/crash recovery, workload-credential rotation, deployed PostgreSQL isolation, Nginx/Swarm private networking, observability, backups/restore/rollback and security/sponsor acceptance remain separate Stage 3 gates.
