# Phase 0 — verified implementation baseline

**Date:** 23 November 2026. **Repository HEAD inspected:** `main` at `bb79e1a` (merge of PR #191). **Scope:** read-only inspection plus local test execution. No AWS access, no staging migration, no RabbitMQ permission change, no deployment, no feature code. Production remains **NO-GO**.

This record complements, and does not replace, the [R1 application tracker](R1_Application_Tracker.md) (feature matrix), the [23 November AWS reconciliation](../operations/R1_AWS_Staging_Reconciliation_2026-11-23.md) (deployment evidence) and [go-live readiness](../planning/go_live_readiness.md). It adds: the HEAD-versus-staging boundary, test evidence at HEAD, a dependency-ordered backlog, a DRY analysis, a security risk register and the exact Phase 1 backlog.

## 1. Repository HEAD versus the staging checkpoint

| Item | Evidence | Limit |
| --- | --- | --- |
| Repository HEAD | `bb79e1a`, 23 Nov 2026 20:35 UTC | Source presence is not deployment. |
| Last release recorded in the repository | **v0.357.1**, commit `807b1edc6e80454bd6bfcb4a78761fa284cd6bee`; 16/16 services updated, 6/6 public HTTPS probes; owner-reported 6/6 administrator/moderator UAT | Owner-supplied terminal output; no repository artefact of the rollout itself. |
| Owner-stated current rollout | **v0.373.1**, "controlled rollout" | **No file in the repository names v0.373.1** (searched docs, infra, scripts, workflows). Its commit, image digests, migrations and smoke results are **not verifiable from this checkout**. |
| Commits between v0.357.1 and HEAD | **30** (22 non-merge) | Listed below. |

Changes after v0.357.1 that a later release would plausibly carry (inferred from git history only; **not** confirmed as part of v0.373.1):

- `742aaac` administrator Creators page (find, invite, review) — web and gateway account lookup.
- `0cbc8b6` CI: check and retry the web-image artefact download before publishing.
- `d11a53f`, `dfa861b` (+ tests `cdedc56`, `0c59ccb`, `a490513`, `aaf32cf`): Engagement now publishes qualified views to the pre-provisioned `kolovibe.points` exchange **without declaring or binding broker resources**, so the Engagement RabbitMQ user needs only WRITE on that exchange. This is the code side of the Engagement-to-Points integration and was **not modified** by this phase.
- `c8ce1c9`, `d6542fb`, `76d78bb`: sanitized dispatcher diagnostics (exception *types* only) and secret-scanner-safe fixtures.
- Documentation reconciliation commits (tracker, readiness, ADR index, as-built).

**Owner action requested:** record the v0.373.1 source commit SHA and image digests (or a link to its CI run) so the tracker can state which of the rows below are deployed. Until then, every "Deployed" claim in this baseline is limited to v0.357.1.

## 2. Local test evidence at HEAD

Run from the repository root with the existing ignored `.env` and the repository `.venv` (Python 3.12.5). No network service, staging resource or secret was touched.

| Suite | Command | Result |
| --- | --- | --- |
| Gateway | `scripts/run_local_service.py gateway test tests` | **183 ran, OK, 14 skipped** |
| Identity | same, `identity` | **139 ran, OK, 1 skipped** (177 s) |
| Creators | same | **72 ran, OK, 1 skipped** |
| Content | same | **123 ran, OK, 2 skipped** |
| Engagement | same | **67 ran, OK, 1 skipped** |
| Points | same | **64 ran, OK, 1 skipped** |
| Moderation | same | **67 ran, OK, 1 skipped** |
| Audit | same | **44 ran, OK, 1 skipped** |
| Administration web | `scripts/run_local_web.py test tests` | **101 ran, OK** (after installing the lockfile-pinned `segno==1.6.6`; see below) |
| Repository/infra scripts | `python -m unittest discover -s scripts -p 'test_*.py'` | **432 ran, OK** (87 s) |
| Structure | `scripts/check_structure.py` | OK, 8 services |

**Failures: none.** Skips are the shared caller-policy tests that apply only to services that do (or do not) accept internal callers (`skipTest` in the shared test block), not disabled coverage. Environment note: the first web run failed with `ModuleNotFoundError: segno` because the local ignored `.venv` was behind `requirements-dev.txt`; the hash-pinned version from the repository lockfile was installed into that venv and the run repeated. No repository file was changed by this.

**Not executed:** Flutter analysis and widget tests (`flutter` is not installed on this machine), Docker image builds and scans, PostgreSQL TLS integration jobs and the disposable-PostgreSQL preflight (these run in CI only), `scripts/verify_local_journeys.py`. The Flutter test inventory below is a static count of `test(`/`testWidgets(` declarations, **not a pass result**. Mobile claims therefore rest on the most recent CI evidence cited in existing documents (PR #30 CI, FL-A–FL-D acceptance records) and are labelled accordingly.

Test inventory (declared tests; Python counts match executed counts): gateway 183, identity 139, content 123, creators 72, engagement 67, moderation 67, points 64, audit 44, web console 101, script/infra tests 432 (executed count), Flutter 559 (47 files, 18,931 lines of Dart in 92 files).

There is **no coverage measurement** anywhere in CI (`coverage`/`--cov` absent from the workflow and requirement files). Coverage statements in this baseline are therefore inventory counts, not percentages.

## 3. Verification by area

### 3.1 Eight backend services and contracts

| Service | Responsibility | Source/test lines (non-test / test Python) | Migrations | URL patterns (incl. health/probe) |
| --- | --- | ---: | ---: | --- |
| gateway | Only public API; signs every internal call; capability gates | 3,695 / 2,932 | none of its own | 76 public `/api/v1` routes |
| identity | Accounts, sessions, MFA, privacy requests, moderator invitations | 2,170 / 2,206 | 11 | 24 internal |
| creators | Profiles, DEC-004 onboarding | 693 / 926 | 5 | 9 |
| content | Videos, R2 upload, FFmpeg jobs, playback, rights status | 2,395 / 1,896 | 11 (two `0005_*` merged by `0006`) | 12 |
| engagement | Likes, follows, shares, watch sessions, fraud holds, outbox | 1,168 / 987 | 6 | 12 |
| points | Append-only non-cash ledger, review reads | 882 / 882 | 6 | 5 |
| moderation | Reports, decisions, appeals, assignments, copyright notices | 1,284 / 1,070 | 6 | 3 (one workflow router) |
| audit | Append-only ingest, grant-scoped reads | 495 / 584 | 5 | 4 |

- `scripts/check_structure.py`: **OK, 8 services and approved layout**.
- **Contract coverage.** `docs/architecture/DOC-205_OpenAPI_3_1_DRAFT.yaml` declares 84 paths. Normalised comparison against the gateway's 76 routes: every gateway route except the dynamic `moderation/{kind}/{id}` template is declared in DOC-205; the nine DOC-205-only paths are health and internal-only paths. CI validates DOC-205 *syntactically* (`openapi_spec_validator`) but **no test asserts route-to-contract parity or per-route authorization metadata**. The DOC-205 file is labelled **DRAFT** with a deliberately invalid server URL.
- **`packages/contracts/openapi` contains only `health.yaml`.** The shared-contracts package is not the source of truth for any business contract; the draft lives under `docs/architecture/`. Mobile and web consume contracts by hand-written parsers.
- Service-to-service identity: per-audience signing keys (fix for the 13 Nov review finding #1) are present at HEAD (`internal_client.py` rejects duplicate or single-credential-for-many-peers keys). Eight copies of the signer/verifier are drift-tested by `scripts/test_service_identity_drift.py`.

### 3.2 Mobile navigation, screens and integrations

- Flutter entry `lib/main.dart`; gateway from `--dart-define=KOLOVIBE_API_URL` (HTTPS `/api/v1`, debug loopback). Without it, every adapter reports "unavailable"; no bundled accounts, content or points.
- Navigation: five-tab shell (Home, Explore, Create, Videos, Profile) plus route groups `account`, `creator`, `discovery`, `settings`, `trust`. Five feature folders (`home`, `explore`, `create`, `videos`, `profile`) are 11-line `MobileScreen` shells that delegate to shared recipes.
- Design parity (20 Nov, widget-render evidence, not device): **8 visually matched, 99 functional with a specified deviation, 1 not verified** (M-045 cover selection) of 108 screens/states. Ten open design/product decisions D-1…D-10 (see §7).
- Live repositories exist for account, public video, creators, content/upload, engagement (like/follow/share/watch), points, reports, standing, notices, appeal (read state), analytics, settings/privacy. Playback uses `video_player`; physical-device playback, session restoration (SEC-05), Android and expiry-driven refresh remain unaccepted.
- The exact mobile artefact paired with v0.357.1/v0.373.1 is **unidentified**.

### 3.3 Administration web

Server-rendered Django console (14 templates), **moderators and administrators only**, MFA-gated, 15-minute absolute / 30-minute idle sessions, CSRF POSTs, no scripts in CSP. Routes: login/MFA, dashboard totals and fraud holds, video/report/appeal queues with detail, decisions, assignments and previews, creators (find/invite/approve), team (moderator invitations), read-only points, audit, own account/sessions. **There is no public, viewer or creator web.** 101 console tests; real-service journey fixture exists but needs PostgreSQL (CI).

### 3.4 Video upload, processing and playback

Implemented: DEC-005-gated private R2 presigned PUT (50 MiB, 5 min, create-only, size/type signed), completion check with ETag, Celery/RabbitMQ job with database lease, FFmpeg in a separate image (no shell, protocol whitelist, one 720p MP4), review → moderation → publish, 5-minute playback links, cover-time edit, soft delete, copyright pipeline/screening migrations. CI builds and scans the media image and runs an end-to-end pipeline test inside it. **Not evidenced:** live R2 upload, live worker conversion, authorized playback on a device, R2 lifecycle, worker sandbox/resource limits, stuck-job reconciliation. Post-approval metadata edits keep a video public with no re-review (13 Nov finding #2, still present: `media_api.py` allows `PUBLISHED` in the edit state set).

### 3.5 Engagement, RabbitMQ and Points

Implemented: DEC-003 watch sessions with server elapsed-time checks, 24 h de-duplication, per-creator UTC cap, fraud holds, transactional **outbox** in Engagement and **idempotent inbox** (`accept_once`) in Points, append-only ledger with DB triggers, audit evidence rows. Three production-path fixes landed on 23 Nov (#188, #189, #191). RabbitMQ in-repo configuration is a **candidate**; `infra/rabbitmq/README.md` still says "NOT ACTIVE (oracle-staging placement)" and records no AWS sizing. **Not evidenced:** live retry, dead-letter, recovery, publisher-confirm behaviour, queue/exchange permission matrix on the live broker, mobile balance journey. No change was made to broker permissions or the integration.

### 3.6 Creator onboarding and verification

DEC-004 backend: account-bound invitations, verified-email applications, reviewer decisions, upload eligibility; administrator Creators page on `main` (post-v0.357.1). Staging default is **off** (`KOLOVIBE_STAGING_CREATOR_ONBOARDING`). Flutter M-036–M-039 wired. Creator-role synchronisation (identity ↔ creators) exists. **Open:** end-to-end staging acceptance, retention/deletion policy (ADR-020), broader identity verification beyond email (not approved).

### 3.7 Moderation and appeals

Implemented: reports, reviewer queues, decisions (idempotent keys, receipts), takedown/restoration with distinct reviewer, independent appeals, moderator assignment grants, notices, copyright notices/counter-notices, standing read. Web UAT positive path passed (owner-reported). **Open:** unassigned/cross-moderator/role negative tests on staging, appeal separation-of-duties evidence, SLA/routing model (owner question), M-078 appeal submit (design says "does not submit an appeal" while the API accepts `POST /videos/{id}/appeals` — owner decision).

### 3.8 Business and event readiness

**Missing.** No business listing, verification, review, event, ticket, QR, organiser or refund code exists in services, web or mobile (searched `services`, `apps/web_django/web`, `apps/mobile/lib`). Scope: PRD v0.2 places business verification in **R2** and events/tickets/payments in **R3**; DEC-001 puts them **out of R1**. PRD/SRS bodies are working drafts (document control #133 approved methods only), so none of those requirements is an approved baseline.

### 3.9 Existing public web

None by design: README and web README state the Django web client has no landing page and no public, viewer or creator pages. Public reads are the mobile API (`GET /videos`, `/creators/*`).

### 3.10 Advertising and financial integrations

**None implemented** (no ad network, sponsorship, payment provider, wallet, payout, settlement or ticket-payment code). Points are non-cash; no cash value, rate or redeem path is reachable in the API or UI. This matches the instruction that real-money payouts and ticket payments stay disabled pending separate approvals; sandbox work is permitted but not started.

### 3.11 API and database dependencies

- Per-service PostgreSQL schemas with per-service `_app` roles; `infra/postgres/schema_isolation.sql` and a read-only preflight exist. Migration ownership is **not** separated from runtime ownership on staging: 26 tables + 8 sequences owned by `_app` roles (23 Nov catalog audit, **open**).
- Call graph: Gateway → {identity, content, creators, engagement, points, moderation, audit} over TLS with HMAC, nonce table and per-audience keys; Identity → Audit delivery; Engagement → RabbitMQ → Points; Content → R2/RabbitMQ → media worker; Moderation → Content (decision application).
- Dependencies without live evidence: R2, RabbitMQ, SMTP, FFmpeg runtime limits, Cloudflare rate limits, backup/restore.

### 3.12 CI, coverage and security controls

CI jobs: Python (lockfile reproducibility, PostgreSQL TLS migrations/isolation/ledger/event integration, gateway/mail/web journeys, staging WSGI, read-only DB preflight, service checks, OpenAPI syntax), Security (secrets, pip-audit, Bandit, SBOM), Flutter (analyze/test, lock drift), OSV, shared/media/web image build + Grype + SBOM, per-service PostgreSQL smoke, publish, environment security review. Actions are SHA-pinned. **Gaps:** no coverage metric; no ASVS/MASVS evidence matrix; `main` has no required checks or reviews (#142); OpenSSL scanner exception expires **2026-11-28** (#143); no mobile dependency/SAST beyond OSV; no DAST; no contract-parity test.

### 3.13 Reuse and duplication

See [§5 DRY analysis](#5-dry-analysis).

### 3.14 Outstanding architectural and product decisions

See [§7](#7-open-decisions-that-gate-work).

## 4. Dependency-ordered implementation backlog

Order rule: authorization and sensitive-data controls first, then correctness of already-implemented journeys, then integration and acceptance evidence, then new modules. Items needing owner approval or live-environment access are marked and are **not** executable by repository work alone.

| # | Item | Depends on | Type | Notes |
| --- | --- | --- | --- | --- |
| B-01 | Record v0.373.1 commit/digests; reconcile tracker | owner | evidence | Unblocks all "deployed" claims. |
| B-02 | Gateway route inventory + DOC-205 parity + default-deny authorization table test | — | repo | Phase 1 task P1-01. Makes every later route reviewable. |
| B-03 | Negative authorization suite: roles × privileged routes; moderator-assignment BOLA; admin-only operations | B-02 | repo | P1-02. |
| B-04 | Refresh-token revocation after logout, rotation and replay (SEC-08) tests at gateway level | — | repo | P1-03. |
| B-05 | Account-level MFA failure lockout and login-throttle keying | B-04 | repo | P1-04. From the 13 Nov review's residual risks. |
| B-06 | Public-response data minimisation test (no `user_id`, no internal ids, no storage keys) | B-02 | repo | P1-05. |
| B-07 | Read-only DB role/ownership/grant report script + disposable-PostgreSQL test (owner runs on staging) | — | repo + owner | P1-06. No DDL. |
| B-08 | Decision: post-approval metadata edit → re-review or documented risk acceptance | owner | decision | Finding #2. |
| B-09 | DB ownership remediation plan (migration-owner role, `ALTER OWNER`) | B-07, owner window | ops | Not executable by Phase 1. |
| B-10 | Live R2 + FFmpeg + RabbitMQ staging journey and evidence | B-01, owner | acceptance | Needs staging access: owner-run. |
| B-11 | Engagement→Points broker acceptance (retry, dead letter, recovery, permission matrix) | B-10 | acceptance | Do not alter broker permissions from code. |
| B-12 | Mobile build identification; SEC-05 iPhone retest; Android UAT; Flutter in CI evidence | B-01 | acceptance | Needs devices. |
| B-13 | Promote DOC-205 to `packages/contracts` with generated/validated consumers; contract tests in web and mobile | B-02 | repo | Depends on DEC for DOC-205 approval status. |
| B-14 | Coverage measurement in CI (report only, then thresholds) | — | repo | Needs owner-chosen thresholds. |
| B-15 | Required status checks on `main` (#142), expire/replace OpenSSL exception by 2026-11-28 | owner | governance | Owner action. |
| B-16 | Backups, restore drill, RTO/RPO (ADR-016, INF-05/10) | owner | ops | Production gate. |
| B-17 | M-078 appeal submit decision; D-1…D-10 design/product decisions | owner | decision | Gate mobile work only. |
| B-18 | Privacy retention/deletion/export policy (ADR-020) | owner/legal | approval | Gates M-091–M-094 completion. |
| B-19 | Business/event/advertising/payment modules | approved PRD/SRS detail baseline (#133), ADR-020, financial-control and legal approvals | approval | **Blocked by approval.** First permitted step after approval: sandbox-only design, no real-money paths. |

## 5. DRY analysis

| ID | Duplication | Evidence | Recommendation | Risk |
| --- | --- | --- | --- | --- |
| D-A | Service-identity signer/verifier copied into all eight services | `# BEGIN shared service-identity` blocks; byte-identical `service_auth.py` in five, `internal_client.py` in six | **Keep.** Independent deployables; drift is already tested by `scripts/test_service_identity_drift.py`. Do not couple services through a shared import. | None; intentional. |
| D-B | `health.py` identical in all eight services (48 lines each, one md5) plus `staging_runtime/health.py` (different) | `md5` of `*/service/health.py` | Candidate to move to `staging_runtime` if images already ship it; confirm Dockerfile layout first. | Low; touches liveness. |
| D-C | `_error(detail, status)` defined nine times; cursor/pagination helpers five times | `grep` over services | **Do not share across services.** Within gateway (five modules) a single `forwarding` helper for `_error` + `_valid_result` is safe. | Low. |
| D-D | `invitation_contracts.py` and `reviewer_contracts.py` are **byte-identical** in gateway and web (56 and 54 lines); `admin_contracts.py` diverges (web adds candidate/summary validators) | `diff` | Candidate for one source under `packages/contracts` with a drift test (the D-A pattern) once B-13 lands. Do not import across deployables. | Medium: web consumes gateway responses and must reject malformed data independently. |
| D-E | `.github/CLAUDE.md` is identical to `AGENTS.md`; `.github/copilot-instructions.md` restates scope | `diff -q` | Keep `AGENTS.md` canonical; replace the copies with a one-line pointer (docs-only, owner approval since these are governance files). | Negligible. |
| D-F | Five mobile feature folders are 11-line shells; 1,228-line `live_video_screen.dart`, 923-line `kolo_components.dart` | `wc -l` | Split only with existing widget tests as the safety net; no behavioural change. | Medium. |
| D-G | Gateway forwarding modules (`media`, `moderation`, `analytics`, `creator_onboarding`, `pilot_points`) repeat request → sign → validate-shape → map error | module structure | Extract the validation/mapping pattern behind per-route schema table (see D-C) after P1-01 gives each route an authorization row. | Medium. |
| D-H | DOC-205 (draft), gateway validators and Dart parsers each encode response shapes | three sources | Single contract source (B-13); tests derive from it. | Medium. |

Principle applied: duplication that exists to keep independently owned services decoupled (D-A, D-C across services) is retained and guarded; duplication inside one deployable (D-C within gateway, D-G) or between gateway and web with identical content (D-D) is the reuse target, each behind existing tests.

## 6. Security risk register

Ranked: authorization and sensitive-data first, then session and abuse, then operational, then cosmetic. Severity is assessed from source and existing evidence; nothing here is a penetration-test result.

| Rank | ID | Risk | Severity | Evidence | Mitigation / next task | Status |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | R-01 | Runtime roles own 26 tables + 8 sequences on staging; a compromised service could alter schema/guards (e.g. append-only triggers on points/audit) | **High** | 23 Nov catalog audit | P1-06 read-only report; B-09 plan; no DDL until reviewed | Open |
| 2 | R-02 | No negative/object-level authorization evidence for privileged routes; positive UAT only | **High** | Reconciliation 23 Nov | P1-01, P1-02 | Open |
| 3 | R-03 | Published video metadata can change with no re-review | Medium | `media_api.py` edit state set includes `PUBLISHED`; review finding #2 | B-08 decision, then implementation | Open |
| 4 | R-04 | MFA failure lockout is per challenge; ~25 TOTP guesses per 15 min per moderator password; login throttle keys on email+address | Medium | 13 Nov review residuals | P1-04 | Open |
| 5 | R-05 | Refresh revocation after logout and rotation/replay unverified on deployed stack | Medium | SEC-08 partial | P1-03 | Open |
| 6 | R-06 | Public responses could expose internal ids (`user_id` removed from public creators; `_profile_data` still returns it internally) | Medium→Low | `profiles.py` `with_account` flag | P1-05 regression test | Open |
| 7 | R-07 | Registration 409 and reset/resend timing reveal account existence | Low | 13 Nov review | Backlog after P1; owner policy on enumeration | Open |
| 8 | R-08 | Engagement/points: broker permissions unproven live; at-least-once delivery relies on inbox idempotency | Medium | `infra/rabbitmq/README.md` NOT ACTIVE; PRs #188–#191 | B-11 owner-run; **do not change permissions** | Open |
| 9 | R-09 | Media worker sandbox, resource limits, stuck-job reconciliation and R2 lifecycle absent | Medium | OD-07 notes | B-10 | Open |
| 10 | R-10 | `main` has no required checks/reviews; OpenSSL exception expires 2026-11-28 | Medium | #142, #143 | B-15 owner | Open (dated) |
| 11 | R-11 | No backups or restore drill for PostgreSQL/RabbitMQ in any environment | High (production gate) | Remediation plans §6 | B-16 | Open |
| 12 | R-12 | Single shared key risk (review #1) | — | Per-audience map at HEAD; verify on staging that deployed secrets are distinct | `verify_staging_runtime.py` owner run | Fixed in code; deployment unverified |
| 13 | R-13 | Privacy retention/deletion/export undefined (ADR-020) while M-091–M-094 collect requests | Medium | Open decision | B-18 | Blocked by approval |
| 14 | R-14 | No coverage metric, DAST or mobile SAST | Low–Medium | CI inspection | B-14 | Open |
| 15 | R-15 | Design deviations D-1…D-10 (copy, icons, layout) | Cosmetic | parity record | After all above | Open |

## 7. Open decisions that gate work

- **Document control (#133):** PRD/SRS detail bodies are drafts; only R1 scope (DEC-001) and DEC-003/004/005, OD-07 carry restricted-pilot authority. DEC-002 (name/legal entity), DEC-006/007 open. **No business, event, advertising or payment requirement is approved for implementation.**
- **Architecture:** ADR-011/012/017/018/022 proposed; ADR-014/015/016/020/021 open; ADR-019 general-release parameters open; INF-01…INF-14 open (AWS as-built addendum supersedes Oracle-era assumptions but ADRs not formally re-approved, #138).
- **Product/design:** D-1 six-digit code (the repository now has `0010_six_digit_codes` and `six_digit_code_test.dart`, so D-1 may be resolved — owner to confirm), D-2 cover frames, D-3 data saver, D-4 curation, D-5 recent searches privacy, D-6 per-creator popularity, D-7 export form, D-8 brand mark, D-9 public view count, D-10 profile photos, M-078 appeal submit, moderation SLA/routing model, audit redaction/retention.
- **Security policy:** post-approval edit re-review (R-03), enumeration policy (R-07).

## 8. Phase 1 backlog and acceptance criteria

**Phase 1 theme:** authorization, session-security and sensitive-data verification, repository-only. Every task is an independent branch and pull request, uses existing test harnesses, requires no staging access, adds no feature, and weakens no control. Phase 1 must not start until the owner authorises it.

### P1-01 — Gateway route inventory, contract parity and default-deny table

- **Branch:** `test/gateway-route-authorization-inventory`
- **Files:** a new `services/gateway/tests/test_route_inventory.py`; read-only use of `services/gateway/service/urls.py`, `routes/*`, DOC-205.
- **Work:** enumerate every public gateway route; require each to appear in an explicit table with `{method, auth: anonymous|account|creator|moderator|administrator, mfa, capability}`; assert parity with DOC-205 paths; fail when a new route lacks a row.
- **Acceptance:** (1) test fails if a route is added without a table row; (2) table agrees with DOC-205 for all 75 non-dynamic routes plus the dynamic moderation route; (3) anonymous requests to every non-anonymous row return 401 and never reach an internal service (stubbed client asserts zero calls); (4) no production code changes; (5) `run_local_service.py gateway test tests` passes.

### P1-02 — Role-by-route negative authorization suite

- **Branch:** `test/privileged-negative-authorization`
- **Depends on:** P1-01 table.
- **Acceptance:** for each privileged row, test account, creator, unassigned moderator, assigned moderator of another item, moderator on admin-only operations, administrator without MFA, expired MFA, and revoked session: expected 401/403, no body leakage, audit denial event recorded where the owning service defines one; moderator assignment BOLA across videos, reports and appeals; appeal reviewer ≠ original decider; cross-creator video/analytics/points reads return 404; all pass with existing Moderation, Content, Points and Identity suites untouched.

### P1-03 — Refresh/logout revocation, rotation and replay

- **Branch:** `test/refresh-revocation-replay`
- **Acceptance:** after `POST /auth/logout`, refresh with the old refresh token returns the documented rejection; replay of a rotated refresh token revokes the token family and the live session; concurrent refresh yields exactly one success; access token for a revoked session rejected at `/me`; tests run at gateway level against the real Identity service fixture (existing pattern) and assert no token in logs.

### P1-04 — Account-level MFA failure lockout

- **Branch:** `fix/account-level-mfa-lockout`
- **Acceptance:** failed MFA attempts across challenges for one account lock further MFA attempts for a bounded period; the lock cannot be bypassed by creating a new challenge; successful MFA clears the counter; lock and unlock are audited without secrets; a legitimate user is not locked by a single failure; existing MFA replay and enrolment tests unchanged; migration, if needed, is additive, reversible and **not applied to staging**; owner approval before merge because it changes authentication behaviour under ADR-013.

### P1-05 — Public-response data-minimisation regression tests

- **Branch:** `test/public-response-minimisation`
- **Acceptance:** anonymous `GET /videos`, `/videos/{id}`, `/creators/{id}`, `/creators/search` responses contain only allow-listed keys (schema-exact); no `user_id`, account id, storage key, bucket, moderation reason code, report counts or email; error bodies carry no stack or internal host.

### P1-06 — Read-only database ownership, membership and grant report

- **Branch:** `ops/db-role-ownership-report`
- **Files:** extend `infra/postgres/r1_readonly_preflight.sql` or add a sibling read-only SQL; test in the existing disposable-PostgreSQL CI step.
- **Acceptance:** report lists object owners, `pg_auth_members` inheritance, effective DDL/TRUNCATE rights on append-only tables (`points_entries`, audit events) and default privileges, by schema; script contains no `ALTER`, `GRANT`, `REVOKE`, `CREATE` or `DROP` (asserted by test); passes on disposable PostgreSQL; output is redacted of passwords/URIs; runbook line states the **owner** runs it on staging read-only and nothing is remediated by Phase 1.

### Phase 1 exit criteria

All six PRs open with passing focused tests; the tracker's Security and Tests columns updated per row with evidence; no staging, AWS, RabbitMQ-permission, migration-application or merge/deploy action taken; remaining blockers (B-01, B-08, B-09–B-12, B-15, B-16) restated for the owner.
