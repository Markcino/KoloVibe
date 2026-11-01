# Container verification and GHCR publication

Eight Django service images use the shared Dockerfile, a pinned Python base-image digest, hash-locked dependencies and UID/GID 10001. Each contains only its owning service. Images are currently **local/CI-only**, not production runtime images.

## Required quality gate

The existing API quality, container quality and dependency vulnerability workflows run on PRs and main pushes. Backend tests include a disposable TLS-only PostgreSQL fixture: migrations for all eight services, cross-service SQL access denial, nonce replay/expiry/audience checks, ledger guards and transactional inbox/outbox tests. The publisher in the outbox test is a controlled double, not a live RabbitMQ broker.

Every main image is built, smoke-tested and scanned before preservation as a commit-bound artifact. The artifact includes the image archive, checksum, image identity, service, commit and CycloneDX SBOM. PRs do not upload publication artifacts or receive registry write permissions.

The publication workflow is triggered by completion of any required quality workflow. Its read-only gate queries the latest main-push run for the **same commit** in all three workflows and verifies every required job. Missing, pending, failed, cancelled or skipped checks withhold publication with a visible reason. Stale workflow attempts and other repositories/branches/PR events do not qualify.

## Publication

After the gate passes, a publication-only job downloads the artifacts from the exact successful container run. It validates the commit, service, image identity, SBOM and archive bytes, loads the same tested image without rebuilding, and publishes it to:

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

Local validation on 1 November 2026:

- All eight Django service suites: 89 tests passed; migration drift checks passed.
- Disposable verified-TLS PostgreSQL integration: 24 tests passed, including the existing six ledger tests; plaintext and wrong-host certificate connections must be rejected.
- `.venv/bin/python -m unittest discover -s scripts -p 'test_*.py' -v`: 34 script tests passed, including gate, artifact and environment-probe failure paths.
- Changed Actions workflows passed actionlint; `bandit -r services scripts` followed by the existing `scripts/enforce_bandit.py` gate passed with zero medium/high findings. Changed-file secret checks and lockfile validation passed.

Docker is not installed in the current local environment. New image builds/scans, GHCR uploads and remote digest evidence are **pending actual Actions execution**, not claimed successful.

Live RabbitMQ retries/dead-letter/crash recovery, workload-credential rotation, deployed PostgreSQL isolation, Nginx/Swarm private networking, observability, backups/restore/rollback and security/sponsor acceptance remain separate Stage 3 gates.
