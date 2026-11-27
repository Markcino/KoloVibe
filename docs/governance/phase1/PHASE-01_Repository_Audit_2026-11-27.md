# Phase 1 repository audit (Task 1)

**Commit audited:** `main` at `1c706ce` (after #303), 27 November 2026. **Method:** static inspection of the repository, the Gateway URL resolver run with every capability flag enabled, the Figma file metadata, GitHub issues and pull requests, and CI on `1c706ce`. **No staging access:** the owner's computer, where `ssh swarm-manager` and `ssh swarm-worker` are configured, was offline when the read-only check was attempted, so every runtime statement below is from the dated 26 November staging record and is marked historical.

Classifications follow the [phase tracker vocabulary](../PHASE_EXECUTION_TRACKER.md). The per-feature result is in the [traceability matrix](PHASE-01_Feature_Traceability_Matrix.csv).

## 1. Application services

| Service | Source lines (non-test) | Test files | Migrations | Models (owned data) | State |
| --- | --- | --- | --- | --- | --- |
| Gateway | 5,120 | 40 | 0 (stateless) | none | Built; 155 public routes; default-deny capability flags |
| Identity | 4,869 | 23 | 18 | 22, incl. sessions, MFA, step-up, legal acceptance, privacy requests, erasure jobs, access exports | Built |
| Creators | 2,017 | 15 | 9 | 8, incl. profiles, applications, restrictions, appeals | Built |
| Content | 3,859 | 21 | 14 | 13, incl. videos, uploads, revisions, copyright screening | Built (+ media worker with FFmpeg) |
| Engagement | 1,528 | 14 | 6 | 6, incl. likes, follows, watch sessions, qualified watches, fraud holds | Built |
| Points | 1,157 | 10 | 6 | 5, append-only ledger | Built |
| Moderation | 2,444 | 14 | 9 | 12, incl. reports, actions, appeals, rights holders, strikes | Built |
| Audit | 792 | 9 | 6 | 2, append-only security events and read grants | Built |
| Business | 5,006 | 19 | 8 | 26 | Built, not on staging |
| Finance | — | — | — | — | **Missing** (design PROPOSED) |
| Events | — | — | — | — | **Missing** (design PROPOSED) |
| Advertising | — | — | — | — | **Missing** (design PROPOSED) |

`services/staging_runtime/` is a shared runtime package (launch, health, roles, capabilities), not a service. Every service has its own schema, role and signing keys (`test_service_identity`, `test_signing_keys` in each suite). No DRF is used anywhere (`rest_framework` is not imported); the agent instructions said "Django/DRF" and are corrected in this change.

## 2. API contract and Gateway

- **Route parity:** with every capability enabled, the Gateway resolves 155 public `/api/v1` routes. DOC-205 (`docs/architecture/DOC-205_OpenAPI_3_1_DRAFT.yaml`, 12,629 lines) lists 161 paths. Every Gateway route is in DOC-205; the 6 DOC-205-only paths are internal or health endpoints that are not public (`/internal/auth/moderator-invitations*`, `/internal/security-events`, `/health/live`, `/health/ready`). **Result: PASS for paths.** Methods and schemas were not compared (#305).
- **Canonical location conflict:** DOC-205 is still marked DRAFT and lives under `docs/architecture/`, while `packages/contracts/openapi/` holds only `health.yaml`. #305 makes one canonical contract.
- **Capability flags:** `business_*` (5), `creator_onboarding`, `media`, `analytics`, `moderation`, `engagement`, `points`, `watch`, `audit_read`. In staging only names in `STAGING_CAPABILITIES` are on; anything else fails closed.

## 3. RabbitMQ and background work

- Event types are defined per service in `events.py` (for example 39 `business.*`, 13 `moderation.*`, 6 `points.*`), plus `kolovibe.engagement.trending.v1`, `kolovibe.identity.access.v1` and the `kolovibe.content.media` routing key. There is **no event contract catalogue** (#305).
- **No dead-letter configuration** exists in the repository; staging had no dead-letter policy on 26 November (#311).
- `infra/swarm/staging-aws.yml` defines 18 worker and job services (dispatchers, consumers, audit delivery, purge, requeue, media worker), all at **zero replicas**, marked "Candidate; NOT approved, NOT deployed".

## 4. Infrastructure, deployment and CI

- `infra/`: Dockerfiles (services, web, FFmpeg), HAProxy and host Nginx configurations (both with `limit_req`), PostgreSQL isolation and ownership SQL, RabbitMQ configuration, Swarm stacks for Oracle (`staging.yml`) and AWS (`staging-aws.yml`, `web-aws.yml`). `infra/observability/` has a README only (#145).
- CI (`.github/workflows/ci_cd.yml`) on `1c706ce`: image build and scan for the three images and eight service images, OSV, Flutter static and widget tests, security scans and SBOM all **success**; the Django services job was still running when read. Bandit, secret scanning (GitGuardian) and dependency locks are present.
- **Last recorded staging (historical, 26 November):** v0.542.1 from source `38d0380`; 64 commits have merged since, so #283 to #303 are **not deployed**. Business has no staging schema. Production is NO-GO.

## 5. Flutter, console and Figma

- **Flutter:** 17 feature folders, 144 screen ids (M-001 to M-144; M-109 to M-144 are Business), 65 test files; 1,888 tests passed at the #299 head (27 November). No push-notification, Google Mobile Ads or payment dependency in `pubspec.yaml`. Android `applicationId` is `com.kolovibe.kolovibe` and release signing is deliberately unconfigured (#166).
- **Console:** 35 routes in `apps/web_django/web/urls.py` covering moderation, creators, measures, rights holders, privacy requests and holds, business, fraud, points, audit and the operator's own account; 20 test files including a route-security matrix. No Finance, Events or Advertising pages.
- **Figma** (`ANaV0jnwjZ0LEcByTc98HP`, read 27 November): two pages only, **Mobile Designed** (the 108 approved R1 frames) and **R1 adaptations (pending owner review)** (8 frames: M-019, M-033, M-034, M-089, M-096 and five M-078 states). **No frames exist** for Business (built implementation-led), Finance, Events, Advertising, Notifications or the console (#306).

## 6. GitHub

- **Pull requests:** none open. #294 to #303 are merged, including #300 (restore-safe recovery) and #303. #303 was marked superseded by #302 but was merged after it, so it overwrote #302's versions of `AGENTS.md`, the mandate file and the instruction pointers, and added a second tracker. This change reconciles the two trackers (section 7).
- **Issues:** 44 issues existed before this phase (42 open). They were organized by the R1 "Stage 1 to 6" milestones. They are now assigned to the Phase 2 to 11 milestones; 22 new issues (#304 to #325) cover every gap with no issue.

## 7. Documentation conflicts found and resolved

| Conflict | Resolution in this change |
| --- | --- |
| Two phase trackers: `PHASE_EXECUTION_TRACKER.md` (#303) and `Phase_Execution_Tracker.md` (#302). They differ only by case and collide on macOS and Windows checkouts | `PHASE_EXECUTION_TRACKER.md` stays canonical (it is the one `AGENTS.md` names); the carry-over and decision tables from the other are merged into it; the duplicate is removed |
| `docs/README.md` presented R1 sources as current and linked the removed tracker | Rewritten as the authoritative index with one canonical source per subject |
| DEC-001, PRD/SRS v0.2, go-live readiness and the seven-stage plan treat Business, ticketing and payouts as deferred and frame the goal as a pilot | Kept as history; [FP-000](../../requirements/FP-000_Full_Product_Requirements_Baseline.md) and the [archive register](../../archive/ARCHIVE_REGISTER.md) say what governs now; a banner is added to go-live readiness |
| `AGENTS.md` stack line says "Django/DRF" | Corrected to Django (no DRF in use) |
| Phase 12 defect register showed D13-006 open | Corrected: closed by #277 |
| `docs/mobile-live-integration-gaps.md` says cover choice and playback are not wired | Listed in the archive register as superseded by the feature matrix (FP-CT-02, FP-CT-03 are built) |
| Two status vocabularies (EXECUTION_PROGRESS and the standing directive) | One vocabulary in the tracker, with the mapping |

## 7a. Reverified earlier findings (repository side only)

| Finding | State at `1c706ce` |
| --- | --- |
| D12-001 edge rate limits and trusted client address | `limit_req` in both repository Nginx templates; staging unverified (#325) |
| D13-001 Points audit key mismatch | Still open; plan merged (#281), not applied |
| D13-002 Content and Creators audit delivery | Repository side done (#292), not deployed |
| D13-003 erasure pipeline | Repository side done (#294), not deployed |
| D13-004 CPU reservations | Open; measurement package merged (#283), not run |
| D13-006 Flutter lockfile | Closed (#277) |
| D13-007 video stuck in processing | Not reverifiable without staging; requeue command exists (`test_requeue_stalled_media`) |

## 8. What could not be verified in Phase 1

| Item | Why | Needed |
| --- | --- | --- |
| Live staging versions, replicas, schema versions, broker queues | Owner's computer offline; no SSH from the cloud environment | Owner runs the read-only `release-readback` (D13-005 record) or approves a Remote Control session |
| Device behavior | No device run in this phase | Phase 10 (#158) |
| Full local test suites at `1c706ce` | Not re-run in this documentation phase; last full results are at the #298 and #299 heads | CI on this PR runs every service suite |
