# Stage 3 — Current execution status

As of 1 November 2026. Owner and sole developer: **Mark Allen Gbalazeh (@Markcino)**, with AI assistance.

Overall: **IN PROGRESS — conditional authorization; exit acceptance pending.**

The working tracker is [Stage3_Implementation_Tracker.csv](Stage3_Implementation_Tracker.csv). Engineering, DBA, API, DevSecOps, SRE and sponsor labels describe responsibilities assigned to the same owner; they do not imply additional developers. Security assurance requirements remain separate from everyday PR self-review.

## Evidence-based task assessment

| Classification | Count | Meaning |
| --- | --- | --- |
| Complete | 3 | FND-01 is owner-declared; FND-02 and FND-03 are complete within previously verified CI scope. |
| Partial | 12 | Implementation/configuration or CI evidence exists; integration or acceptance evidence is missing. |
| Pending | 3 | Required implementation, environment/decision prerequisites or stage acceptance remains pending. |

These counts describe task evidence, not overall percentage completion or formal stage approval.

| ID | Deliverable | Assessment | Remaining work |
| --- | --- | --- | --- |
| FND-01 | Repo governance, branch protection, CODEOWNERS | Complete - owner-declared | Retain owner declaration and historical verification provenance; no new independent readback |
| FND-02 | Pin toolchains and dependency lockfiles | Complete - CI scope | Continue toolchain/dependency maintenance |
| FND-03 | Django microservice skeletons and health checks | Complete - CI scope | Production runtime/deployment tracked under FND-12 and FND-14 |
| FND-04 | Flutter and Django web shells | Partial - mobile and local web shells | Live R1 service contracts and staging security profile remain open |
| FND-05 | OpenAPI lint and consumer contract tests | Partial - local contract journeys verified | Remaining gated business contracts and deployed transport evidence |
| FND-06 | Security scanning and SBOM | Partial - publication verification pending | Pinned base digest and verified-artifact publication workflow implemented; new Actions/image/registry evidence pending |
| FND-07 | Per-service PostgreSQL roles and migrations | Partial - local integration verified | Disposable TLS PostgreSQL isolation/migration tests pass; deployed topology and login evidence pending |
| FND-08 | RabbitMQ/Celery private queues and retries | Partial - integration evidence pending | RabbitMQ DHI TLS deployment; approved queue/workload identity |
| FND-09 | Outbox/inbox and idempotency scaffold | Partial - database integration verified | PostgreSQL rollback/republication and deduplication pass with a publisher double; live broker evidence pending |
| FND-10 | Service identity enforcement | Partial - Django-native identity and gated TOTP/audit implemented | Isolated SMTP/MFA/audit and protected secret validation pass; full ADR-013/OD-01/ADR-012, privileged clients, recovery/rotation and deployed acceptance remain open |
| FND-11 | Append-only noncash ledger scaffold | Partial - PostgreSQL tests verified; CI acceptance pending | SQLite/PostgreSQL ledger tests pass locally; run new CI acceptance. Award formula/public APIs are separate later work |
| FND-12 | Hardened image and Swarm secret handling | Partial - isolated staging runtime verified | Actual image/Swarm deployment; digests; secret lifecycle |
| FND-13 | VM1 host Nginx configuration | Partial - candidate; activation blocked | Actual syntax/private route; OD-02 transport; certificate ownership |
| FND-14 | Swarm staging stack and network zones | Partial - candidate; infrastructure blocked | Docker validation; OD-03 sizing; private network/rollout acceptance |
| FND-15 | Central logs, metrics and alerts | Pending - monitoring implementation | OD-08 monitoring and audit retention |
| FND-16 | Backup/restore and rollback drill | Pending - recovery targets blocked | OD-04 approved RTO/RPO; deployed database/infrastructure |
| FND-17 | Stage 3 threat-control verification | Partial - CI baseline only | DOC-203/206; deployed environment; complete negative-test matrix |
| FND-18 | Stage 3 gate and handoff | Pending - stage acceptance | All remaining blockers dispositioned; security and sponsor acceptance |

## Confirmed implementation and evidence

Restricted staging preparation and current test results are centralized in the
[API roadmap](API_Test_Deployment_Roadmap.md#restricted-staging-preparation-and-evidence).
Nginx/Swarm candidates now exist, so FND-13/FND-14 are partial, not accepted.
Production remains NO-GO; FND-01 stays owner-declared complete.

- FND-02: CI pins the Flutter SDK and Python runtime; application and CI dependency lockfiles include hash checks. CI resolves locked packages and checks Flutter lockfile drift.
- FND-03: eight independent Django services now share one build image; each selected
  service retains its non-root runtime smoke/health check and separate database
  permissions. Production settings remain gated. See [shared-image delivery](container-verification.md).
- Flutter application entry is `lib/main.dart`. The alternate entry point, fixture and inactive simulation controls were removed through [PR #12](https://github.com/Markcino/KoloVibe/pull/12) and [PR #13](https://github.com/Markcino/KoloVibe/pull/13). The 108 design recipes remain; their presence is not proof of live business functionality.
- The previously recorded merged Flutter CI suite reported 133 passing tests and clean static analysis. [API quality evidence](https://github.com/Markcino/KoloVibe/actions/runs/41050289508). Current local continuation evidence is separate and linked below; it does not establish new remote CI results.
- Dependency and source security scans, container checks and SBOM generation are implemented. [Container evidence](https://github.com/Markcino/KoloVibe/actions/runs/41050331889) and [dependency review evidence](https://github.com/Markcino/KoloVibe/actions/runs/41050332526).
- PostgreSQL schema/role SQL, service HMAC middleware, RabbitMQ/Celery configuration and transactional event primitives are present. Current tests include rejection of unsigned/spoofed calls and event operations outside transactions. Live database/broker integration acceptance remains pending.
- FND-11: SQLite and PostgreSQL guards, reversal, source-decision uniqueness and ORM/SQL mutation-rejection tests pass locally. A PostgreSQL-only transaction-boundary issue in the test was corrected. The Stage 3 scaffold does not require an award formula or public points API; those remain separate gated product work.
- The gateway contains account forwarding routes, and `apps/mobile` contains opt-in account and public-video metadata adapters. The owner selected Django-native client identity in ADR-013 on 2026-11-01, but those features and the selection do not settle its token/session/MFA requirements, provide a deployed gateway, or implement media playback and the remaining R1 business APIs.
- The creator service now stores review-gated profiles and returns only active reviewed records through a signed gateway route. Mobile and web read those profiles from the gateway. No creator application or approval API is enabled.

## Local verification · 1 November 2026

Initial review evidence (before the delivery changes):

- `cd apps/mobile && flutter analyze && flutter test`: passed after creator-read wiring; 137 tests.
- All eight Django service test suites and `makemigrations --check --dry-run`: passed; 94 tests total after creator profile tests.
- RabbitMQ/Celery, Stage 3 foundation, local launcher and secret-finding regression tests: passed; 18 tests total.
- `python3 scripts/check_mobile_design.py`, Python/Flutter dependency-lock checks and CI-toolchain lock check: passed.
- `python3 scripts/check_structure.py`: passed after removing the ignored legacy `apps/mobile_flutter` generated build and IDE directory. No source files were present in that obsolete directory.

The subsequent mobile/web continuation verifies account rotation/revocation, paginated discovery and real signed gateway contracts against disposable PostgreSQL, with test-only mail capture. Current commands and results are centralized in the [API test roadmap](API_Test_Deployment_Roadmap.md#current-continuation-evidence), including the passing unsigned iOS build and the blocked simulator hot-reload/broker checks. The [R1 tracker](R1_Application_Tracker.md) distinguishes local journeys from gated product features. All points APIs/UI remain gated. The example SMTP credential was cleared; provider revocation/rotation remains required.

Web tests, local HTTP contract journeys and web Python scanning are wired into the single `ci_cd` workflow. Its publication job depends on all quality jobs in the same run; required check names remain unchanged. The workflow consolidation has local regression/lint evidence but no new remote Actions evidence. See [container verification](container-verification.md) for operation selection and the publication boundary. Full Stage 3 and R1 acceptance remain pending.

Evidence links refer to executed CI on merged changes; the solo-governance/status follow-up requires its own CI results.

## FND-01 owner declaration

The proposed main policy requires pull requests, all 12 CI checks, up-to-date branches, resolved conversations and administrator enforcement. Force pushes/deletion remain disabled. Mandatory approvals are zero; code-owner and latest-push approval requirements are disabled.

Mark records self-review in the PR checklist. CODEOWNERS identifies Mark's responsibility and does not require another person to approve his PR. This is an explicit solo-development workflow, not independent review evidence.

Mark directed that FND-01 remain complete on 1 November 2026. The tracker records **owner-declared completion**, not new independent verification. The earlier `protected: false` and plan-restriction observations are historical; no current settings readback, billing change or protection modification was performed in this change.

See [activation and acceptance](FND-01_repository_governance.md).

## Test-gated GHCR delivery

The [container verification record](container-verification.md) describes the new publication pipeline. The shared build/scan plus all required API, Flutter, dependency/security and eight selected-service container checks must succeed for the same main push commit. PRs cannot publish. The pipeline preserves one image/SBOM artifact and publishes it once using `GITHUB_TOKEN`; no persistent credential enters source or images.

The base digest is pinned. Registry publication is implemented but **not yet executed or verified**: these changes must first reach main through the normal PR process. Docker is unavailable in this local environment, so new image build/scan evidence must come from Actions. Published local/CI images still reject staging/production activation.

## Open decisions and hold points

The [nine-decision register](Stage3_Open_Decisions.csv) retains unresolved items. The owner selected Django-native client identity (partial ADR-013 decision); the remaining session/MFA approval, other ADRs and security acceptance are not implied by that selection.

- OD-01: **Django-native client identity selected** under [ADR-013](../architecture/ADR-013_Django_Native_Identity_Selection_2026-11-01.md); final client token/session/MFA contract and separate ADR-012 workload identity/rotation still require approval.
- OD-02: private Nginx-to-Swarm encryption and certificate ownership.
- OD-03: hosting, cluster size and capacity.
- OD-04: database topology, login provisioning and recovery targets.
- OD-05: creator verification and privacy retention.
- OD-06: qualified-view thresholds and points formula.
- OD-07: video provider and verified webhooks.
- OD-08: monitoring and audit retention.
- OD-09: GitHub Actions is implemented; deployment trust, credentials and environment acceptance remain open.

The active broker implementation is RabbitMQ/Celery as requested. Historical approved plans retain their original Redis wording; this status update does not silently amend those documents.

## Next execution order and exit gate

Run the new Actions pipeline and verify GHCR image digests. Retain PostgreSQL/ledger/service-auth/inbox-outbox integration evidence, then verify live RabbitMQ delivery and deployed database/identity controls when their prerequisites are approved. Complete image/runtime, Nginx, monitoring and recovery work when their decisions and infrastructure are available. Points APIs and award calculations are later product integrations, not prerequisites for the Stage 3 ledger scaffold.

Stage 3 closes only after the exit checklist, security evidence, recovery/rollback evidence and recorded acceptance are complete. CI success does not authorize production or formally close Stage 3. Stage 4 formal handoff remains pending. A local Django web shell now exists under the user's expanded R1 scope; production web acceptance remains open.

The approved architecture and Stage 3 plan are retained as baselines. This file and the CSV are execution records and do not assert a new sign-off.
