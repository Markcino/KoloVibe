# Stage 3 — Current execution status

> **Current delivery note (23 November 2026):** Stage 3 remains **owner-declared complete** as of 10 November; this historical task assessment is not a current infrastructure snapshot. AWS staging subsequently reached **v0.357.1**, with 16/16 services and 6/6 HTTPS probes passing and owner-reported 6/6 administrator/moderator web UAT. Stage 4/5 remain open for full R1 security, media and mobile tests; production is **NO-GO**. See the [current AWS release reconciliation](../operations/R1_AWS_Staging_Reconciliation_2026-11-23.md) and [go-live readiness](../planning/go_live_readiness.md). Do not transfer this document's dated Oracle checks or task percentages to the latest AWS release.

As of 10 November 2026. Owner and sole developer: **Mark Allen Gbalazeh (@Markcino)**, with AI assistance.

**Stage 3 completed by owner declaration on 10 November 2026.** Stage 4 MVP implementation and Stage 5 testing and security verification are in progress. Outstanding foundation evidence remains tracked below. See the [R1 application tracker](R1_Application_Tracker.md) and the [AWS staging deployment record](../operations/AWS_Staging_Deployment_Verification_2026-11-10.md).

The working tracker is [Stage3_Implementation_Tracker.csv](Stage3_Implementation_Tracker.csv). Engineering, DBA, API, DevSecOps, SRE and sponsor labels describe responsibilities assigned to the same owner; they do not imply additional developers. Security assurance requirements remain separate from everyday PR self-review.

## Oracle Cloud deployment evidence · 3 November 2026

[Current deployment record](../operations/Deployment_Verification_2026-11-03.md):
GitHub CI and GHCR publication are verified for commit `be03dbcced01f1a4f71c643dbc179da2810ffa61`.
Owner-supplied Gateway output passes HTTPS/certificate and PostgreSQL `verify-full`
checks on VM2. The working database/DNS/firewall setup is preserved. All 19
independent public API checks returned HTTP 503. Other services, RabbitMQ,
ingress and full acceptance remain pending. The new Cloud Shell runner has
passed offline tests but has not yet executed against the VMs.

On 10 November GitHub reported `protected: false` for `main`. As of 22 November, `main` reports `protected: true` under the active "KoloVibe Rules" ruleset, which blocks only deletion and non-fast-forward updates; it requires no status checks or pull request review. FND-01 remains owner-declared complete, with enforcement of required checks tracked in [#142](https://github.com/Markcino/KoloVibe/issues/142).

## Evidence-based task assessment

| Classification | Count | Meaning |
| --- | --- | --- |
| Complete | 3 | FND-02 and FND-03 are complete within verified CI scope. FND-18 records owner completion and handoff. |
| Partial | 13 | Implementation or verification evidence exists, with follow-up still open. |
| Pending | 2 | Monitoring and recovery verification remain pending. |

These counts describe task evidence, not overall percentage completion or formal stage approval.

| ID | Deliverable | Assessment | Remaining work |
| --- | --- | --- | --- |
| FND-01 | Repo governance, branch protection, CODEOWNERS | Partial enforcement. Owner-declared complete. | Apply and verify the solo-developer policy when GitHub plan eligibility allows |
| FND-02 | Pin toolchains and dependency lockfiles | Complete - CI scope | Continue toolchain/dependency maintenance |
| FND-03 | Django microservice skeletons and health checks | Complete - CI scope | Production runtime/deployment tracked under FND-12 and FND-14 |
| FND-04 | Flutter and Django web shells | Partial - mobile and local web shells | Live R1 service contracts and staging security profile remain open |
| FND-05 | OpenAPI lint and consumer contract tests | Partial. Local contract journeys and AWS public checks passed. | Remaining gated business contracts and deployed transport evidence |
| FND-06 | Security scanning and SBOM | Partial. Historical image published. Latest reviewed CI failed. | Restore passing dependency, source-security and image checks, then verify candidate provenance |
| FND-07 | Per-service PostgreSQL roles and migrations | Partial - Gateway DB verified on VM2 | Gateway verify-full/schema checks pass; deployed checks for the other seven runtime roles remain pending |
| FND-08 | RabbitMQ/Celery private queues and retries | Partial - integration evidence pending | RabbitMQ DHI TLS deployment; approved queue/workload identity |
| FND-09 | Outbox/inbox and idempotency scaffold | Partial - database integration verified | PostgreSQL rollback/republication and deduplication pass with a publisher double; live broker evidence pending |
| FND-10 | Service identity enforcement | Partial. Django-native identity and gated TOTP/audit implemented. | Verify approved ADR-013 design and close separate ADR-012 workload identity, privileged client, recovery/rotation and deployment gates |
| FND-11 | Append-only noncash ledger scaffold | Partial - CI ledger verified | Exact-commit CI PostgreSQL/ledger checks pass; deployed ledger acceptance remains pending; formula/public APIs are separate later work |
| FND-12 | Hardened image and Swarm secret handling | Partial - image and Gateway verified | Other seven deployed services, secret rotation and runtime acceptance |
| FND-13 | VM1 host Nginx configuration | Partial - public routing blocked | All 19 public checks returned 503; inspect actual private Gateway route and active configuration |
| FND-14 | Swarm staging stack and network zones | Partial - Gateway network verified | Capacity; remaining seven APIs and RabbitMQ; network/rollout acceptance |
| FND-15 | Central logs, metrics and alerts | Pending - monitoring implementation | OD-08 monitoring and audit retention |
| FND-16 | Backup/restore and rollback drill | Pending - recovery targets blocked | OD-04 approved RTO/RPO; deployed database/infrastructure |
| FND-17 | Stage 3 threat-control verification | Partial - CI baseline only | DOC-203/206; deployed environment; complete negative-test matrix |
| FND-18 | Stage 3 gate and handoff | Complete by owner declaration | Track open security, operational and deployment evidence alongside Stages 4 and 5 |

## Confirmed implementation and evidence

Restricted staging preparation and current test results are centralized in the
[API roadmap](API_Test_Deployment_Roadmap.md#restricted-staging-preparation-and-evidence).
FND-13 and FND-14 track the Oracle rollout. AWS staging has separate verification. Production remains NO-GO.

- FND-02: CI pins the Flutter SDK and Python runtime; application and CI dependency lockfiles include hash checks. CI resolves locked packages and checks Flutter lockfile drift.
- FND-03: eight independent Django services now share one build image; each selected
  service retains its non-root runtime smoke/health check and separate database
  permissions. Production settings remain gated. See [shared-image delivery](container-verification.md).
- Flutter application entry is `lib/main.dart`. The alternate entry point, fixture and inactive simulation controls were removed through [PR #12](https://github.com/Markcino/KoloVibe/pull/12) and [PR #13](https://github.com/Markcino/KoloVibe/pull/13). The 108 design recipes remain; their presence is not proof of live business functionality.
- The previously recorded merged Flutter CI suite reported 133 passing tests and clean static analysis. [API quality evidence](https://github.com/Markcino/KoloVibe/actions/runs/41050289508). Current local continuation evidence is separate and linked below; it does not establish new remote CI results.
- Dependency and source security scans, container checks and SBOM generation are implemented. [Container evidence](https://github.com/Markcino/KoloVibe/actions/runs/41050331889) and [dependency review evidence](https://github.com/Markcino/KoloVibe/actions/runs/41050332526).
- PostgreSQL schema/role SQL, service HMAC middleware, RabbitMQ/Celery configuration and transactional event primitives are present. Current tests include rejection of unsigned/spoofed calls and event operations outside transactions. Live database/broker integration acceptance remains pending.
- FND-11: SQLite and PostgreSQL guards, reversal, source-decision uniqueness and ORM/SQL mutation-rejection tests pass locally. A PostgreSQL-only transaction-boundary issue in the test was corrected. The Stage 3 scaffold does not require an award formula or public points API; those remain separate gated product work.
- The gateway contains account forwarding routes, and `apps/mobile` contains opt-in account and public-video metadata adapters. The owner approved the Django-native session and MFA design in ADR-013 v1.0. AWS staging exercised account and discovery paths. Full design implementation and verification, playback and remaining R1 business APIs are open.
- The creator service now stores review-gated profiles and returns only active reviewed records through a signed gateway route. Mobile and web read those profiles from the gateway. No creator application or approval API is enabled.

## Local verification · 1 November 2026

Initial review evidence (before the delivery changes):

- `cd apps/mobile && flutter analyze && flutter test`: passed after creator-read wiring; 137 tests.
- All eight Django service test suites and `makemigrations --check --dry-run`: passed; 94 tests total after creator profile tests.
- RabbitMQ/Celery, Stage 3 foundation, local launcher and secret-finding regression tests: passed; 18 tests total.
- `python3 scripts/check_mobile_design.py`, Python/Flutter dependency-lock checks and CI-toolchain lock check: passed.
- `python3 scripts/check_structure.py`: passed after removing the ignored legacy `apps/mobile_flutter` generated build and IDE directory. No source files were present in that obsolete directory.

The subsequent mobile/web continuation verifies account rotation/revocation, paginated discovery and real signed gateway contracts against disposable PostgreSQL, with test-only mail capture. Current commands and results are centralized in the [API test roadmap](API_Test_Deployment_Roadmap.md#current-continuation-evidence), including the passing unsigned iOS build and the blocked simulator hot-reload/broker checks. The [R1 tracker](R1_Application_Tracker.md) distinguishes local journeys from gated product features. All points APIs/UI remain gated. The example SMTP credential was cleared; provider revocation/rotation remains required.

Web tests, local HTTP contract journeys and web Python scanning are wired into the single `ci_cd` workflow. Publication depends on the quality jobs in the same run. See [container verification](container-verification.md) for the earlier successful publication, current failures and promotion rules.

## FND-01 owner declaration

The proposed main policy requires pull requests, all 12 CI checks, up-to-date branches, resolved conversations and administrator enforcement. Force pushes/deletion remain disabled. Mandatory approvals are zero; code-owner and latest-push approval requirements are disabled.

Mark records self-review in the PR checklist. CODEOWNERS identifies Mark's responsibility and does not require another person to approve his PR. This is an explicit solo-development workflow, not independent review evidence.

Mark directed that FND-01 remain complete on 1 November 2026. The 10 November readback showed an unprotected main branch; the 22 November readback shows a ruleset without required checks (see above).

See [activation and acceptance](FND-01_repository_governance.md).

## Test-gated GHCR delivery

The [container verification record](container-verification.md) describes the new publication pipeline. The shared build/scan plus all required API, Flutter, dependency/security and eight selected-service container checks must succeed for the same main push commit. PRs cannot publish. The pipeline preserves one image/SBOM artifact and publishes it once using `GITHUB_TOKEN`; no persistent credential enters source or images.

The pinned shared image was published for `be03dbcc` and used for the recorded AWS staging rollout. The 10 November main workflow skipped publication after failing required jobs. See [container verification](container-verification.md#validation-and-remaining-evidence).

## Open decisions and hold points

The [nine-decision register](Stage3_Open_Decisions.csv) tracks remaining implementation, deployment and verification decisions.

- OD-01: **Client session and MFA design approved** under [ADR-013](../architecture/ADR-013_Client_Authentication_and_Session_Security_v1.0_APPROVED.md). Executable contract and verification work remain open, along with separate ADR-012 workload identity and rotation.
- OD-02: private Nginx-to-Swarm encryption and certificate ownership.
- OD-03: hosting, cluster size and capacity.
- OD-04: database topology, login provisioning and recovery targets.
- OD-05: creator verification and privacy retention.
- OD-06: qualified-view thresholds and points formula.
- OD-07: video provider and verified webhooks.
- OD-08: monitoring and audit retention.
- OD-09: GitHub Actions is implemented; deployment trust, credentials and environment acceptance remain open.

The active broker implementation is RabbitMQ/Celery as requested. Historical approved plans retain their original Redis wording; this status update does not silently amend those documents.

## Foundation follow-up

Run the new Actions pipeline and verify GHCR image digests. Retain PostgreSQL/ledger/service-auth/inbox-outbox integration evidence, then verify live RabbitMQ delivery and deployed database/identity controls when their prerequisites are approved. Complete image/runtime, Nginx, monitoring and recovery work when their decisions and infrastructure are available. Points APIs and award calculations are later product integrations, not prerequisites for the Stage 3 ledger scaffold.

The Stage 3 handoff is recorded in FND-18. The exit checklist remains the reference for outstanding security and recovery evidence. The [R1 tracker](R1_Application_Tracker.md) tracks MVP delivery, device acceptance and production readiness.

