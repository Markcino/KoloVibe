# R1 application delivery tracker

**Updated 25 November 2026 (Phase 12 section and reverification Phases 1 and 2 added).** Stage 3 (Technical Foundation) was **declared completed by the owner on 10 November**, while unresolved security, operations and recovery controls remain open. Stage 4 (R1 MVP implementation) and Stage 5 (verification) remain in progress on AWS staging. Production is **NO-GO**. See the [Stage 3 tracker](Stage3_Implementation_Tracker.csv) and the [current AWS release record](../operations/R1_AWS_Staging_Reconciliation_2026-11-23.md).

## Current release checkpoint — v0.357.1 (23 November)

The operator supplied deployment and smoke-test output for immutable release `807b1edc6e80454bd6bfcb4a78761fa284cd6bee` (published by [successful CI run 45196093209](https://github.com/Markcino/KoloVibe/actions/runs/45196093209)): **16/16** services updated (eight APIs, six background jobs, media worker and web) and **six/six** public HTTPS checks passed. Identity migration `0011_moderator_invitations` was previously applied and retained. This records a verified **deployment**, not full API/mobile acceptance.

On the same release, the owner reported **six/six authenticated administrator/moderator UAT passes**: dashboard, video review, reports/appeals, points review, moderator assignment, and moderator access. This resolves the *reported positive-path* “Request unavailable” regression for those tested journeys; it does not certify negative authorization, browser-session/MFA replay protections or every R1 contract. The earlier read-only check found **one administrator, one moderator and zero reviewer assignments** when 403s were observed; scoped grants are required for a moderator.

The 23 November database catalog audit found **26 tables and eight sequences owned by runtime `_app` roles**. Role inheritance/effective grants and a safe migration-owner correction remain to be investigated before any DDL. Backup/restore, origin and workload identity, live R2/FFmpeg/RabbitMQ journeys, qualified engagement/points, mobile device UAT and pilot sign-off remain open. Follow the [security and acceptance detail](../operations/R1_AWS_Staging_Reconciliation_2026-11-23.md) and [go-live readiness](../planning/go_live_readiness.md).

**Evidence boundary:** the **26 passed / 0 failed / 19 pending** assessment belongs only to [v0.187.2, 17 November](../operations/R1_AWS_Staging_Reconciliation_2026-11-17.md); no full row-by-row retest of that matrix was supplied for v0.357.1. The repository `main` tip inspected on 23 November was four commits ahead of v0.357.1, with creator-admin and account-lookup work **not observed deployed**; do not infer staging acceptance from source presence.

The dated feature table and 10 November iPhone run below are retained as **historical implementation and test evidence**, not the current release's feature acceptance. Updates must keep those dates and their tested builds separate.

## Phase 0 verified implementation baseline — repository HEAD `bb79e1a` (23 November)

Source: [Phase 0 baseline](Phase0_Implementation_Baseline_2026-11-23.md), which holds the evidence, backlog (B-xx), DRY analysis, risk register (R-xx) and Phase 1 backlog (P1-xx). **HEAD is 30 commits ahead of v0.357.1.** The owner reports a v0.373.1 rollout; **no repository file records its commit or digests**, so "Deployed" below means deployed on v0.357.1 only. Source presence and passing local tests are not staging acceptance. Production is **NO-GO**.

**Status key:** *Verified complete* (scoped to the stated evidence) · *Implemented, awaiting integration* · *Partial* · *Missing* · *Blocked by dependency* · *Blocked by approval* · *Deployed, awaiting acceptance*. Mobile column cites design IDs (M-xxx); "wired" means a live repository against the gateway exists, proven only by widget tests with test doubles. Tests column gives Python suites that **passed locally at HEAD on 23 November** (counts) or, for Flutter, declared tests only (Flutter was not runnable here). No coverage is measured.

| Feature | Service | Mobile | Web | API | Security | Tests | Status | Blocker | Next task |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Eight-service layout, health, structure check | all eight | n/a | n/a | `/health/live` | read-only roots, non-root image (CI) | `check_structure.py` OK; 432 script tests pass | **Verified complete** (repository scope) | None | None |
| Service-to-service identity (per-audience HMAC keys, nonce table) | all eight | n/a | n/a | internal | ±60 s window, TLS, one key per peer; 8 copies drift-tested | `test_service_identity_drift.py` | **Verified complete** (code); deployed secret distinctness unverified | Owner read-back on staging | None (owner) |
| Account register, verify, sign-in, refresh, sign-out, `/me` | identity, gateway | M-002–M-016 wired | n/a | DOC-205 | ADR-013 implemented; refresh replay, wrong-token and logout negatives proven locally by #195, account MFA lock by #197 (staging evidence and PostgreSQL concurrency still open) | identity 139, gateway 183, Flutter FL-A | **Deployed, awaiting acceptance** | SEC-05 iPhone retest; SEC-08 | P1-03 |
| Password reset/change, sessions, notification preferences | identity, gateway | M-009–M-011, M-082–M-086 wired | own password/sessions | DOC-205 | single-use reauth proofs | included above | **Implemented, awaiting integration** | No staging/device evidence | P1-03 |
| Privacy requests, data export, account deletion | identity | M-091–M-094 intake wired | none | `/me/privacy-requests` | retention undefined | included above | **Blocked by approval** | ADR-020 retention/deletion/export policy | B-18 |
| Admin console: moderation queues, detail, decisions, assignments | moderation, gateway | n/a | wired | DOC-205 | MFA, 15/30-minute sessions, CSRF, owning-service scope | web 101, moderation 67 | **Deployed, awaiting acceptance** (positive UAT 6/6 owner-reported) | Negative/BOLA evidence | P1-01, P1-02 |
| Admin: moderator invitations and assignment summary | identity, gateway | n/a | wired | DOC-205 | TOTP replay protection, audited | identity 139, web 101 | **Deployed, awaiting acceptance** | Live QR enrolment receipt | P1-02 |
| Admin: creators find, invite, approve | creators, identity, gateway | n/a | wired (`742aaac`, main only) | DOC-205 | console: administrator-only with confirmation step; **API and Creators accept moderator or administrator** for invite, pending and review (DOC-205; see Phase 5F D-9) | creators 72, web 101 | **Implemented, awaiting integration** | Not evidenced on v0.357.1; staging onboarding flag default off | B-01 |
| Admin: audit read, points review (read-only) | audit, points | n/a | wired | DOC-205 | grant-scoped, redacted, denials audited | audit 44, points 64 | **Deployed, awaiting acceptance** | Retention/redaction policy (OD-08) | B-18 |
| Creator onboarding (DEC-004) | creators, gateway | M-036–M-039 wired | via admin page | DOC-205 | account-bound invitations, verified email | creators 72 | **Implemented, awaiting integration** | Staging activation and end-to-end journey | B-10 |
| Public video/creator discovery and search | content, creators, gateway | M-017–M-028 wired | none | `GET /videos`, `/creators/*` | public allow-list; `user_id` removed from public creator reads | content 123 | **Deployed, awaiting acceptance** (feed 200; empty) | No published content; no leak regression test | P1-05 |
| Video upload to R2, FFmpeg processing, review, publish | content, media worker, gateway | M-041–M-052 wired | review preview | DOC-205 | signed size/type, create-only PUT, no-shell FFmpeg, DEC-005 gate | content 123; image E2E in CI | **Implemented, awaiting integration** | Live R2/FFmpeg/RabbitMQ untested; worker sandbox; R2 lifecycle | B-10 |
| Authorized playback | content, gateway | M-024–M-035 (`video_player`) | admin preview | `/videos/{id}/playback` | 5-minute links, published+approved only | included above | **Partial** | No device playback evidence | B-12 |
| Post-approval metadata edits | content, moderation | M-054 shows the review state | Video edits review page | `PATCH /videos/{id}`, `/moderation/edits` | Decision A (25 November): edits to a published video's text are held for review (PRs #246 to #248) | content 166, moderation 78, console 184 | **Implemented, awaiting integration** | Staging and device evidence | None |
| Likes, follows, shares | engagement, gateway | M-028–M-030 wired | none | DOC-205 | server-derived identity | engagement 67 | **Implemented, awaiting integration** | Staging activation | B-10 |
| Qualified views and watch sessions (DEC-003) | engagement, gateway | engagement controller wired | none | `/watch-sessions`, `/engagement/watch-events` | server elapsed time, 24 h dedup, creator cap | engagement 67 | **Implemented, awaiting integration** | Live RabbitMQ; device playback | B-11 |
| Engagement → RabbitMQ → Points delivery | engagement, points | n/a | n/a | internal | outbox/inbox idempotency; WRITE-only publish to `kolovibe.points` | engagement 67, points 64 | **Partial** | Three fixes after v0.357.1; no live retry/dead-letter/recovery evidence. Do not change permissions | B-11 (owner-run) |
| Non-cash points ledger and balance | points, gateway | M-061–M-069 wired | read-only | DOC-205 | append-only triggers, idempotent awards | points 64 | **Implemented, awaiting integration** | Live delivery; TRUNCATE grant unverified | P1-06 |
| Fraud holds | engagement | none | dashboard card | `/engagement/fraud-holds` | scoped to assigned videos | engagement 67 | **Partial** | No mobile surface; thresholds untuned | B-11 |
| Reports, notices, standing | moderation, gateway | M-070–M-077 wired | queues | DOC-205 | idempotent decisions, receipts | moderation 67 | **Implemented, awaiting integration** | M-070 options sheet; staging activation | P1-02 |
| Appeals | moderation, gateway | M-078 read-only state | queues | `POST /videos/{id}/appeals` | independent reviewer rule | moderation 67 | **Blocked by approval** | M-078 design says "does not submit"; API accepts submit | B-17 |
| Copyright screening and notices | content, moderation | notice screens | queues | DOC-205 | pipeline and notice flow | content 123 | **Partial** | Needs live media journey | B-10 |
| Creator analytics | content, engagement, gateway | M-058–M-060 wired | none | `/creators/me/analytics` | owner-only | gateway 183 | **Implemented, awaiting integration** | Staging activation | B-10 |
| Audit event pipeline and retention | audit, identity | n/a | audit page | internal | append-only ingest, grants | audit 44 | **Partial** | Delivery scheduling, retention (OD-08, ADR-017) | B-18 |
| Shared API contracts | `packages/contracts` | hand-written parsers | hand-written validators | only `health.yaml`; business contract is DOC-205 **DRAFT** | none | CI validates syntax only | **Partial** | No route-to-contract or auth-metadata test | P1-01, B-13 |
| CI and supply-chain controls | CI | Flutter job | web image | n/a | SHA-pinned actions, secrets scan, audit, Bandit, OSV, Grype, SBOM | no coverage metric | **Partial** | No required checks on `main` (#142); OpenSSL exception ends 2026-11-28 (#143) | B-15 |
| Database role separation | PostgreSQL | n/a | n/a | n/a | 26 tables + 8 sequences owned by runtime roles | `r1_readonly_preflight.sql` in CI | **Partial** (open High risk R-01) | Needs read-only role/grant report, then owner-approved plan | P1-06 |
| Backup, restore, RTO/RPO, monitoring | infra | n/a | n/a | n/a | none evidenced | none | **Blocked by approval** | ADR-016, INF-05/INF-10 | B-16 |
| Business listings and verification (R2) | none | none | none | none | none | none | **Missing**; **Blocked by approval** | Outside R1 (DEC-001); PRD/SRS detail unapproved (#133). Phase 6A design approved by the owner on 24 November (PR #218 merged; [approval record](../architecture/business/BIZ-Owner_Approval_Record_2026-11-24.md)); **Phase 6B backend implemented locally behind closed flags, not deployed, not staging-tested** ([completion report](phase6/Phase6B_Business_Backend_Completion_Report_2026-11-24.md)); still outside R1. **Client decision (DR-BZ-21, 24 November 2026): Flutter mobile for visitors, customers, owners and staff; protected console for moderators and administrators only; no public website and no business web portal** ([client architecture](../architecture/business/BIZ-Client_Architecture_DR-BZ-21.md)); the Business console pages (Phase 6C) and the 36 Flutter Business screens (Phase 6D, implementation-led, not visually approved) now exist locally. **Phase 6E (25 November):** the backend, console and app are integrated and proven by one real-HTTP journey, a four-way contract reconciliation and a security hardening suite ([results](phase6/Phase6E_Business_Integration_Results_2026-11-25.md)); still local only, flags closed, policy-blocked items unchanged. **Phase 6A reconciliation:** [validation](../architecture/business/BIZ-Architecture_Validation_PHASE6A.md) found five deviations of the as-built backend from the approved design and the [exact owner decisions required](../architecture/business/BIZ-Owner_Decisions_Required_PHASE6A.md) (gates A, B, C); the DOC-020 register row and DOC-207 logs still say Deferred (change request not raised) | B-19 |
| Events and ticketing (R3) | none | none | none | none | none | none | **Missing**; **Blocked by approval** | Outside R1; payment and legal approvals | B-19 |
| Advertising and sponsorship | none | none | none | none | none | none | **Missing**; **Blocked by approval** | Advertising policy and approvals | B-19 |
| Payments, payouts, settlement | none | none | none | none | disabled | none | **Missing**; **Blocked by approval** | Provider, financial-control and legal approvals; sandbox only when authorised | B-19 |
| Public viewer/creator website | none | n/a | admin console only | none | n/a | n/a | **Missing** (by design) | Not in approved R1 scope | None |
| Live streaming | none | none | none | none | n/a | n/a | **Excluded** | Excluded by owner | None |

### Phase 2 backend completion (23 November) — open pull requests, none merged

Same columns and status key as above. These rows add to, or supersede the "Next task" of, the rows above once their pull requests merge. Evidence is local test runs plus the pull-request CI; **none is deployed or staged**.

| Feature | Service | Mobile | Web | API | Security | Tests | Status | Blocker | Next task |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Internal request nonce retention (replay table bounded) | all eight | n/a | n/a | internal | nonces older than 10 minutes cannot match the 60-second window; purge cannot fail a request | 4 shared tests × 8 services; real PostgreSQL check | **Implemented, awaiting integration** ([#202](https://github.com/Markcino/KoloVibe/pull/202)) | Runtime login must keep DELETE on the nonce table (B-09) | Owner review and deploy |
| Identity retention of expired throttle, code, challenge, replay-marker and finished-session rows | identity | n/a | n/a | internal + `purge_expired_security_rows` | closes anonymous growth of `LoginThrottle`; replay detection preserved; accounts, events, audit rows untouched | identity 8 new tests (suite 147) | **Implemented, awaiting integration** ([#203](https://github.com/Markcino/KoloVibe/pull/203)) | Unverified-account and event retention need ADR-020/OD-08 | Owner schedules the command if wanted |
| Search within a creator's own video library (`q`) | content, gateway | M-040 search field not built | n/a | `GET /creators/me/videos?q=` (additive, DOC-205 updated) | own non-deleted videos only; cursor stays in the filtered view; response checked | content 1 + gateway 1 new (suites 124 / 184) | **Implemented, awaiting integration** ([#204](https://github.com/Markcino/KoloVibe/pull/204)) | Mobile adoption | Flutter search field (client phase) |
| Points reversal and award adjustment execution | points | M-067 reads only | read-only review | none | no write path exists by design | n/a | **Blocked by approval** | No approved reversal rule (DEC-003 covers qualified awards and the daily cap only); README states no execution routes | Owner defines when and by whom a reversal is allowed |
| Audit retention, redaction policy and legal-hold | audit | n/a | audit page | `/internal/audit/read` | conservative projection and append-only guards exist | audit 48 | **Blocked by approval** | OD-08, ADR-017 | Owner decision |
| Post-approval edit re-review; appeal submit (M-078); account deletion and export | content, moderation, identity | M-054, M-078, M-091–M-094 | queues | existing | see risks R-03, R-13 | existing | **Blocked by approval** | B-08, B-17, B-18 | Owner decisions |

### Phase 3 media and event integration (23 November) — open pull requests, none merged

Same columns and status key. Evidence is local runs (disposable PostgreSQL for the event pipeline) plus pull-request CI. **Nothing here is recorded as staging-accepted**: no live R2, RabbitMQ or device run was made, and the AWS rollout was not touched.

| Feature | Service | Mobile | Web | API | Security | Tests | Status | Blocker | Next task |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Creator upload to authorized playback chain (draft, size-bound create-only R2 grant, exact-object completion, FFmpeg, review, moderation, publication, 300 s signed playback, unpublish, cross-creator 404) | content, gateway | M-041–M-052, M-024–M-035 wired | admin preview | `/videos/*` | private bucket, no playback grant before publication, creator cannot skip moderation | 1 journey test ([#209](https://github.com/Markcino/KoloVibe/pull/209)); real FFmpeg when on PATH | **Implemented, awaiting integration** | Live R2, worker and device playback not run | Owner staging run of the journey |
| Recovery of videos stalled in `processing` | content | n/a | n/a | `requeue_stalled_media` command | repeat-safe under the worker lease; counts only | 6 tests ([#206](https://github.com/Markcino/KoloVibe/pull/206)) | **Implemented, awaiting integration** | Owner schedules it (not added to any stack) | Owner |
| Qualified view → outbox → message → Points inbox → receipt → ledger | engagement, points | engagement controller wired | read-only points | internal | verified routing asserted: exchange and key `kolovibe.points`, queue and exchange no-declare, persistent; duplicate and concurrent redelivery have one effect; killed worker recovered; cap withholds without a ledger row | 8 cross-service tests on disposable PostgreSQL + new CI step ([#207](https://github.com/Markcino/KoloVibe/pull/207)) | **Implemented, awaiting integration** | Broker itself (permissions, confirms, durability) untested; no live RabbitMQ | Owner-run broker acceptance |
| Self-view rejection | engagement, gateway | n/a | n/a | watch routes | refused in both services, no session or event | 2 tests ([#208](https://github.com/Markcino/KoloVibe/pull/208)) | **Verified complete** (repository scope) | Self-likes allowed (earn nothing): product decision | None |
| Audit evidence delivery from Points | points, audit | n/a | audit page | internal | retained on failure, retried with backoff, no creator identifier | covered in #207 | **Implemented, awaiting integration** | Live Audit delivery job not scheduled by the repository | Owner |
| Points reversal write path | points | M-067 reads | read-only | none | constraints only (negative, single, targeted, append-only) | #207 | **Blocked by approval** | No approved reversal rule | Owner |
| R2 lifecycle: delete originals, abandoned uploads, superseded renditions | content | n/a | n/a | none | no deletion added | n/a | **Blocked by approval** | Retention rule (OD-07) and a credential allowed to delete | Owner |
| Poison-message handling (dead-letter) for the Points queue | points | n/a | n/a | n/a | malformed payload is raised and acknowledged, not retried | #207 documents | **Blocked by dependency** | Needs broker configuration (owner); permissions untouched | Owner |

### Phase 4 mobile (23 November) — merged: #211, #212

Same columns and status key. Evidence: whole Flutter suite 1,555 tests passing locally on SDK 3.50.1 (CI pins 3.47.8 and its Flutter job passed on #211). **No physical-device result exists.** Per-journey runs and the screen table by journey are in [mobile-phase4-journey-matrix](../mobile-phase4-journey-matrix.md).

| Feature | Service | Mobile | Web | API | Security | Tests | Status | Blocker | Next task |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 108 mobile screens and states (M-001–M-108) | gateway | all implemented; 8 visually matched, 99 functional with a recorded deviation, 1 not verified | n/a | DOC-205 | refresh credential in platform secure storage; ownership and points never computed on the client | 1,555 Flutter tests | **Implemented, awaiting integration** | Physical iPhone and Android runs; owner decisions for M-045, profile photos, M-078, brand mark | Run the iPhone and Android checklists |
| M-040 search within the creator's own library | content, gateway | wired (#211) | n/a | `GET /creators/me/videos?q=` | validated before any request | repository and widget tests | **Implemented, awaiting integration** | Device acceptance | Device run |
| M-045 cover choice | content | slider stands in | n/a | none for frames | n/a | n/a | **Blocked by approval** | Frame-thumbnail endpoint or accept the slider (D-2) | Owner |

### Phase 5 administration console (23 November) — open pull requests

Same columns and status key. Evidence is the web test suite plus pull-request CI; **no staging run was made** and the owner-reported 6/6 positive UAT on v0.357.1 remains the only privileged evidence from a deployed environment.

| Feature | Service | Mobile | Web | API | Security | Tests | Status | Blocker | Next task |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Secure login, privileged MFA, session validation, secure logout | identity, gateway | n/a | existing | `/auth/*`, `/me/*` | encrypted server session, 15-minute absolute and 30-minute idle limits, MFA flag checked in two layers | route security matrix, 11 tests ([#213](https://github.com/Markcino/KoloVibe/pull/213)) plus 101 existing | **Deployed, awaiting acceptance** (matrix itself: **Verified complete**, repository scope) | Negative authorization and MFA replay on staging | Owner run |
| Administrator dashboard, video review, report management, appeals, content restrictions (remove, restore, reject decisions), decision idempotency | moderation, content, gateway | n/a | existing | `/moderation/*` | intent bound to actor, session, target and expiry; stable idempotency keys; CSRF on every decision | existing 101 + #213 | **Deployed, awaiting acceptance** | Staging negative and cross-account evidence | Owner run |
| Moderator assignment management and moderator invitations | moderation, identity | n/a | existing | `/admin/moderation/assignments`, `/admin/moderator-invitations` | administrator-only; assignment scope enforced by Moderation | existing + #213 | **Deployed, awaiting acceptance** | Live QR enrolment receipt | Owner run |
| Creator verification: find, invite, review applications | creators, identity, gateway | n/a | existing (main only at v0.357.1) | `/creator-invitations`, `/creator-applications` | administrator-only in the console; the API accepts moderator or administrator (DOC-205), see Phase 5F D-9 | existing | **Implemented, awaiting integration** | Not evidenced on staging | Owner run |
| Creator invitation management: list outstanding invitations, revoke | creators, gateway | n/a (applicant sees 404) | wired (Phase 5F) | `GET /creator-invitations`, `POST /creator-invitations/{id}/revoke` | administrator-only at console, gateway and Creators; `invited→revoked` only | creators 84, gateway 215, web 138 | **Implemented, awaiting integration** (superseded: see Phase 5F) | Creators migration `0006` and runtime grants; Audit delivery and DB trigger for the event table | Owner deploys; Phase 11 |
| Fraud review page | engagement, gateway | n/a | new ([#214](https://github.com/Markcino/KoloVibe/pull/214)) | `GET /engagement/fraud-holds?cursor=` | scoped by the gateway, read-only, response validated | 8 tests | **Implemented, awaiting integration** | Clearing or creating holds has no approved rule or operation | Owner decision |
| Points review (read-only) and audit browsing | points, audit | n/a | existing | `/admin/points/*`, `/admin/audit` | grant-scoped, redacted, denials audited | existing | **Deployed, awaiting acceptance** | Award or reversal execution and audit retention blocked by approval | Owner decisions |
| Own account settings | identity | n/a | existing | `/me`, `/me/password`, `/me/sessions` | reauthentication proofs, session revoke ownership | existing | **Deployed, awaiting acceptance** | Staging evidence | Owner run |
| Layout and accessibility checks | n/a | n/a | tests ([#215](https://github.com/Markcino/KoloVibe/pull/215)) | n/a | n/a | 11 static checks | **Partial** | No screen-reader pass, browser check at real widths or keyboard walk-through performed | Manual accessibility pass |

### Phase 5F core completion (24 November) — one pull request, not merged

Same columns and status key. Base `main` at `5e7eda7`, which is **70 commits ahead of the owner-verified `v0.373.1`**; nothing here is deployed. Full evidence, the 11 owner decisions and the matrix of every service, console page and mobile journey: [Phase 5F results](Phase5F_Core_Completion_Results_2026-11-24.md). Local runs: nine Django suites, 446 script tests, console 138, PostgreSQL 16 pipeline (8) and preflight (16), and Flutter **3.47.8 (CI-pinned)** analysis clean with **1,556 tests**. No device, staging, live R2, FFmpeg or RabbitMQ run.

| Feature | Service | Mobile | Web | API | Security | Tests | Status | Blocker | Next task |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Creator invitation listing and revocation ([P5F-01](phase5f/P5F-01_creator_invitation_management.md)) | creators, gateway | none needed (404 pinned by test) | new panel and confirm page | DOC-205 updated | administrator-only at three layers, no self-revocation, state guard, signed per-row intent, no personal data listed, event trail | creators +8, gateway +6, web +7; each control mutation-checked | **Implemented, awaiting integration** | Migration `0006` on staging; runtime grants; Audit delivery and DB append-only trigger for `OnboardingEvent` | Owner |
| Dead duplicate widgets removed; withdrawn-invitation state pinned ([P5F-02](phase5f/P5F-02_mobile_dead_code_and_withdrawn_invitation.md)) | none | `SectionHeader`, `EmptySection` deleted (no references) | n/a | n/a | n/a | 1,556 Flutter tests | **Verified complete** (repository scope) | None | None |
| Creator restriction/suspension write path | creators, moderation | n/a | none | none | enforcement and read exist; nothing sets the status | n/a | **Blocked by approval** | D-8 | Owner |
| Remaining blocked items: post-approval re-review (D-1), M-045 (D-2), profile photos (D-3), M-078 (D-4), privacy export/deletion (D-5), points reversal (D-6), fraud-hold clearing (D-7), invite API roles (D-9), R2 lifecycle (D-10), audit retention and legal hold (D-11) | various | various | various | none | none added | n/a | **Blocked by approval** | [Decision register](Phase5F_Core_Completion_Results_2026-11-24.md#5-owner-decisions-required) | Owner |

### Phase 6B hardening (24 November) — Business backend, second pass

Same columns and status key. Base `main` at `09a5bc9`. **Nothing here is deployed** and every Business flag is closed; production is NO-GO. Evidence: [Phase 6B hardening results](phase6/Phase6B_Hardening_Results_2026-11-24.md). Business suite 178 (SQLite), 13 on disposable PostgreSQL 16; Audit 51 and 2; Gateway 218.

| Feature | Service | Mobile | Web | API | Security | Tests | Status | Blocker | Next task |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Negative authorization for every Business operation | business | n/a | n/a | none changed | registry-driven gate matrix, 39-operation object matrix against real data, nested-id swap, coverage guard; 12 mutations caught | +12 | **Implemented, awaiting integration** | none | none |
| Tested migration upgrade and rollback (Business 0001–0007, Audit 0006) | business, audit | n/a | n/a | none | schema round trip identical; rows survive; Audit rollback refused over a `business` grant | +4 SQLite, +4 PostgreSQL (in CI) | **Implemented, awaiting integration** | none | none |
| Business routes are JSON-only (DR-BZ-21): no HTML, cookies, CORS, templates | gateway, business | n/a | n/a | JSON 405 with `Allow` (defect fixed) | middleware list pinned | +5 | **Implemented, awaiting integration** | none | AC-CLI-005…008 need client work |
| B2 file evidence and suspension; B3 lists and copy; B6 policy values; B7 staff removal, closure, transfer; notification contracts | business | none | none | none | fail closed or absent | n/a | **Blocked by approval** | [Owner decisions required](../architecture/business/BIZ-Owner_Decisions_Required_PHASE6A.md) gate A | Owner |

### Phase 6C Business administrator and moderator console (24 November) — pull request

Same columns and status key. Base `main` at `01b73e2`. **Nothing here is deployed**; every Business flag is closed and production is NO-GO. Evidence: [Phase 6C results](phase6/Phase6C_Business_Console_Results_2026-11-24.md) (route inventory, feature matrix, test results). Console suite 174 (was 138); no migration; no contract change.

| Feature | Service | Mobile | Web | API | Security | Tests | Status | Blocker | Next task |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Business overview, verification, profile-review and report queues and decisions | business, gateway | none (Flutter is for owners and customers) | 9 routes under `/admin/business/` | the 13 approved operations | privileged role, MFA, grant scope enforced by the service, signed single-operation intent with idempotency key, confirmation step, strict response validation | +35 | **Implemented, awaiting integration** | Flags closed; owner-approved release record; reviewer grants; Audit read access | Owner |
| Categories and reviewer / registration access (administrator) | business | none | 2 routes | `PUT` category, reviewer grant, registration grant | administrator-only in console, gateway and service | in the 35 | **Implemented, awaiting integration** | same | Owner |
| Audit page accepts the `business` producer | gateway, audit | none | existing page | `GET /admin/audit` | exact allow-list in both validator copies | +3 gateway, +1 console | **Verified complete** (repository scope) | none | none |
| Suspension, restoration, appeals, listing and impersonation complaints, disputes, moderation metrics, business list, decision history | business | none | none | **no backend operation** | n/a | n/a | **Blocked by approval** | DR-BZ-25, DR-BZ-29 and new backend contracts | Owner |

### Phase 6D Flutter Business experience (24 November) — pull request

Same columns and status key. Base `main` at `01b73e2`. **Nothing here is deployed**; every Business flag is closed and production is NO-GO. Evidence: [Phase 6D results](phase6/Phase6D_Business_Mobile_Results_2026-11-24.md) (36-screen matrix, 43 of 44 operations, test evidence, device recipes). **Not visually approved:** the screens were built from the design system by the owner's decision A1; no Business design exists.

| Feature | Service | Mobile | Web | API | Security | Tests | Status | Blocker | Next task |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Business discovery, customer, owner and staff screens M-109 to M-144 and the Businesses tab | business (fixture test only) | 36 screens, repository, strict parsers, business context, sixth tab | none (no business website) | 43 of the 44 app-facing operations; staff removal deliberately not offered | role from the service only, owner rows and Block hidden from staff and re-enforced, one-time codes in memory only, fresh key per code request, lost access forgotten, no link leaves the app | Flutter suite grown from 1,556 (see results), Business suite 181; layout audit over all 36 screens; 22 mutations caught | **Implemented, awaiting integration** | visual review and wording from the owner (DR-BZ-27); step-up (P6B-04); Phase 11 device run | Owner |
| Contact change on a live profile; staff removal | business | one explanatory row each, no control | none | refused by the service | fail closed | tested absent | **Blocked by approval** | DR-BZ-33, P6B-04 | Owner |
| Appeals, notifications, images, file evidence, share links, report a listing or an owner reply | business | not built | none | no contract | n/a | n/a | **Blocked by approval** | DR-BZ-25, DR-BZ-28 and new contracts | Owner |

### Phase 6E Business development integration and hardening (25 November) — pull request

Columns for this phase: Feature · Backend · Mobile · Admin dashboard · Contract · Security · Automated tests · Status. Base `main` at `fa6fd3f`. **Nothing here is deployed or staged**; every Business flag is closed and production is NO-GO. This is development integration, not staging UAT. Evidence: [Phase 6E results](phase6/Phase6E_Business_Integration_Results_2026-11-25.md). Status **Code-complete** means implemented, declared in DOC-205, routed, exercised by the real-HTTP journey or its service tests, and green locally; it is not a deployment or UAT claim. Operations: 57 declared, 57 routed, 57 implemented; 44 are app-facing (43 integrated, staff removal deliberately not offered) and 13 are console-only.

| Feature | Backend | Mobile | Admin dashboard | Contract | Security | Automated tests | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Registration, ownership, staff join and leave (10 operations) | business, gateway | M-126–128, 139–144 | registration grants (administrator) | declared and reconciled | invitation-only, server-assigned ownership, no authority field accepted, one-time codes, revoked staff denied at once | journey steps 2, 13, 14; ownership, matrix and hardening suites | **Code-complete** (staff removal: see policy-blocked) |
| Verification, text evidence (8) | business, gateway | M-133 | claim, decide, grants (console, MFA) | declared, answers validated against schemas | claim required, no self-verification, replay-safe, grant scope exact, conflict of interest | journey steps 3–5 (decision through the real console); bypass, scope and replay suites | **Code-complete** |
| Profiles, hours, categories, profile review (9) | business, gateway | M-129–132 | profile queue and decision; categories | declared and reconciled (`profile_review` scope added to the contract) | material change re-reviewed; contacts hidden from anonymous callers | journey steps 3, 5, 7; profile suites | **Code-complete** |
| Listings and discovery (5) | business, gateway | M-109–117, 134 | none (no business website) | declared and reconciled | only verified, owner-listed businesses are discoverable; contact reveal needs a verified email | journey steps 6–8; eligibility table of 8 states | **Code-complete** |
| Inquiries (12) | business, gateway | M-118–120, 135–136 | none | declared and reconciled | participants only, blocked customer never disclosed, budgets | journey steps 9–11, 13 | **Code-complete** |
| Reviews, responses, review invitations, reports and report decisions (13) | business, gateway | M-116, 121–125, 137–138 | report queue and decision | declared and reconciled | basis stored, fraud holds, no hide or edit by the business, moderator scope | journey steps 11–12; review and hardening suites | **Code-complete** |
| Audit evidence | business, audit | n/a | audit page accepts the `business` producer | event vocabulary equal in both services | ids and codes only; delivery row lock pinned | journey end check; delivery and lock-scope tests | **Code-complete** (delivery over HTTP not run in the journey) |
| Contract, Gateway, service, app and console agree | all | 48 captured answers | request alignment test | reconciliation test, 11 + 5 tests | default-deny against the contract | `scripts/test_business_contract_reconciliation.py`, console alignment | **Code-complete** |
| Staff removal and contact change on a live profile (Decision G, 25 November) | business, gateway, identity | M-139 remove with password, M-130 live contacts with password | none | declared (`/me/step-up`, `X-Step-Up-Token`) | one-time proof bound to session, account, purpose, service and business; consumed by the Gateway at Identity | service, Gateway, journey and Flutter tests (PRs #240 and the app PR) | **Implemented, awaiting integration** (not deployed) |
| Closure and ownership transfer | business | none | none | absent | purposes registered in Identity, no operation yet | n/a | **Missing** (next Decision G step) |
| File evidence, suspension and appeals, notifications, images, share links, review policy values, visual approval of the 36 screens, DB owner/runtime separation | business | not built or flagged | none | no contract | n/a | n/a | **Policy-blocked** ([owner decisions](../architecture/business/BIZ-Owner_Decisions_Required_PHASE6A.md) gates A and B; DR-BZ-27, 28) |
| Duplicate-business scan scales with the whole table (K4); category list unbounded (K5); audit call under a row lock (K6); listing reconcile query pattern (K7); an unrelated copyright journey failed once and was not diagnosed (K8) | business, scripts | none | none | none | none exploitable found | none | **Known defects** (results §6) |
| Staging, devices, screen reader, browser console pass, real authenticator MFA, Audit delivery over HTTP, PR CI, independent review | n/a | n/a | n/a | n/a | n/a | n/a | **Unexecuted live UAT** (results §7) |

Local test run at HEAD and the full backlog, DRY analysis, risk register and Phase 1 acceptance criteria are in the [Phase 0 baseline](Phase0_Implementation_Baseline_2026-11-23.md#2-local-test-evidence-at-head).

### Phase 10 platform development integration (25 November 2026) — branch `claude/blissful-albattani-81b81r`, no pull request

Full record: [Phase 10 report](phase10/Phase10_Platform_Integration_Report_2026-11-25.md), [UAT preparation](phase10/Phase10_UAT_Preparation_Checklist.md), generated [inventories](phase10/inventory/). **Development integration on disposable infrastructure, not CI, not UAT, nothing deployed, production NO-GO.** Nine of fifteen listed modules exist as code; **Events, Ticketing, Advertising and Revenue/financial workflows are design packages only (7A, 8A, 9A) and are Not implemented, blocked by product approval.**

| Item | Backend | Mobile | Admin web | Database | Contract | Security | Tests | Status | Blocker | Owner |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Whole implemented platform (11 matrix rows) | nine services | 144 screens | 30 route declarations | 60 migrations, drift-free | DOC-205, 158 operations | Bandit 0 medium or high; secrets and `pip-audit` clean | services 1,089; console 179; scripts 459; Flutter 3.47.8 **1,823**, analyze clean; 11 of 11 local journeys; staging runtime and preflight pass | **Development complete** for rows 1, 2, 3, 5, 6, 7, 9, 13, 14, 15, 17 | Phase 11 environment (see checklist A) | Owner |
| Engagement to Points on a real RabbitMQ (new `verify_event_pipeline_broker.py`) | outbox, dispatcher, worker | n/a | n/a | outbox, inbox | internal | least-privilege accounts proved | 6 pass | **Verified complete** (repository scope) | Deployed broker permissions unverified | Owner |
| **Defect fixed:** Engagement non-qualified events used the default exchange | `events.py` | n/a | n/a | n/a | n/a | refused by a least-privilege account; would have forced a widening | 2 new unit tests, mutation-checked | **Verified complete** | None | None |
| **Defect fixed:** broker setup script granted `.*` to every account | generator | n/a | n/a | n/a | n/a | wildcard removed | 1 new test | **Verified complete** (generator only) | Live grants not inspected | Owner |
| Creators and Content audit delivery (FR-015) | registered kinds never emitted | n/a | audit page lacks them | n/a | declared | accountability gap | none | **Missing implementation** | Credentials and a reviewed slice | Owner |
| Copyright claimant intake in the app | backend complete | no client | via moderation | n/a | declared | n/a | local journey | **Partial** | Copyright policy is a draft | Owner |
| Scheduled maintenance commands | three unscheduled; one undocumented | n/a | n/a | n/a | n/a | row growth | none | **Partial** | Add roles or document | Owner |

### Phase 11 comprehensive testing (25 November 2026) — branch `claude/blissful-albattani-81b81r`, no pull request

Full record: [Phase 11 report](phase11/Phase11_Test_Report.md), [matrix](phase11/Phase11_Test_Matrix.md), [defect register](phase11/Phase11_Defect_Register.md), [release blockers](phase11/Phase11_Release_Blockers.md). **Local disposable stack only; no AWS, device, R2 or image was available. Not UAT acceptance; production NO-GO.** 242 rows: 149 PASS, 11 FAIL (8 product defects, 1 static finding, 2 runner errors of the test script itself), 39 BLOCKED, 43 NOT RUN. Events, Advertising, Finance (no code) and all physical-device tests are not run.

| Item | Backend | Mobile | Admin web | Database | Contract | Security | Tests | Status | Blocker | Owner |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Service database ownership and append-only guards (D11-002, R-01) | n/a | n/a | n/a | login inherits table owner: 117 of 117 tables | n/a | a service credential can disable the ledger and audit guards | T10_03, T10_04 FAIL | **Defect (High, release blocker)** | Separate owner role; staging read-back | Owner |
| Points consumer poison pill (D11-001) | worker dies and crash-loops on a malformed task envelope | n/a | n/a | n/a | n/a | needs broker write access | T3_35 FAIL | **Defect (Medium, release blocker for shared environments)** | Fix, dead-letter policy | Owner |
| Registration enumeration and no registration limit (D11-003, D11-004) | Identity | n/a | n/a | n/a | DOC-205 declares the 409 | ADR-013 | T1_03, T1_94 FAIL | **Defects (Medium)** | Fix, policy value | Owner |
| Validation before authorization; console overflow at 320 px (D11-005, D11-006) | Gateway, Business | n/a | console CSS | n/a | n/a | Low | T1_31, T4_23, T9_32 FAIL | **Defects (Low)** | None | None |
| Accounts, sessions, MFA, object-level authorization, media validation, engagement and points on a real broker, Business isolation, console sessions and CSRF | all | n/a | yes | yes | yes | tested black-box | 122 PASS of 130 new tests | **Verified (local, repository scope)** | Device and staging gates | Owner |

### Execution progress (25 November 2026)

Resume from [EXECUTION_PROGRESS.md](reverification/EXECUTION_PROGRESS.md), which records the phase status, the completed work packages and the next task under the re-issued mandate. Decision A (re-review of published-video edits) merged in PRs #246 to #248.

### Owner decisions A to J (25 November 2026)

[Decision record](../planning/Owner_Decisions_A-J_2026-11-25.md). Approved for development and staging testing: published-edit re-review (A, RV2-01), terms and privacy acceptance (B, RV2-02), privacy processing (C, ADR-020 mechanism), backup and observability (D, ADR-016 in part, ADR-017), copyright (E, D11-008), creator restrictions (F, D-8), Identity step-up (G, DR-BZ-33), Events (H), Advertising (I) and Finance owning the only ledger (J, X-01). Values, legal text and five conflicts with the standing directive stay open (sections 2 and 3). Production NO-GO.

### Reverification Phase 4: Business (25 November 2026)

[Phase 4 Business completion](reverification/Phase4_Business_Completion_2026-11-25.md). All approved Business functionality is development complete: all 57 operations are routed, 44 have a Flutter client and 13 have a console client, and only staff removal is refused by design. The eleven listed extensions are **Blocked by approval** (DR-BZ-14, 18, 19, 20, 25, 26, 29, 33). Not activated anywhere. Production NO-GO.

### Reverification Phase 3 (25 November 2026)

Repository-side development, not deployed: [Phase 3 report](reverification/Phase3_Core_Completion_Report_2026-11-25.md). D-P2-01 fixed (PR #234), Creators and Content audit delivery D11-007 (PR #235), maintenance roles at zero replicas D11-009 (PR #236). **Correction:** M-050 to M-052 were already live in-flow states; the Phase 1 and 2 gap was a false positive. Dead letters stay **Blocked by approval** (RV2-03). Production NO-GO.

### Reverification Phase 2 (25 November 2026) — `main` at `8a6e7a0`

Planning only: [Phase 2 requirements, architecture and plan](reverification/Phase2_Requirements_Architecture_Plan_2026-11-25.md) and the [R1 completion design (PROPOSED)](../architecture/R1_Completion_Design_PROPOSED.md). Nothing approved. Track A (no policy needed): poster re-render defect **D-P2-01**, Creators and Content audit delivery, M-050 to M-052, maintenance roles, dead-letter wiring. New decisions raised: RV2-01 (re-review of published-video edits), RV2-02 (consent record), RV2-03 (dead-letter values), RV2-04 (media retention values), X-01 (one monetary ledger).

### Reverification Phase 1 (25 November 2026) — `main` at `d56e7ce`

Full record and the single authoritative feature matrix: [Phase 1 reverification](reverification/Phase1_Reverification_2026-11-25.md). Read-only; every status re-checked against source and re-run tests (services 1,103, console 179, scripts 475, PostgreSQL, journeys and pipeline suites, Flutter 1,824; 0 failed). **Production NO-GO.** Release 1 core is development complete; **Partial**: privacy processing (FR-017, blocked by ADR-020), Creators and Content audit delivery (FR-015), observability (FR-019), copyright claimant intake, maintenance scheduling. **Missing in code:** dead-letter handling, upload result screens M-050 to M-052. Events, Advertising and Finance have no code (blocked by approval). Corrections: the Studio analytics chart and a cover-moment control are already live.

### Phase 12 defect remediation, regression and release readiness (25 November 2026) — branch `claude/blissful-albattani-81b81r`

Full record: [readiness report](phase12/Phase12_Release_Readiness_Report.md), [defect register](phase12/Phase12_Defect_Register.md), [matrix](phase12/Phase12_Test_Matrix.md). **Local disposable stack only; no deployment, no AWS or staging action.** **Conclusion: NOT READY — BLOCKERS REMAIN.**

| Item | Status | Evidence | Blocker | Owner |
| --- | --- | --- | --- | --- |
| Points consumer poison pill (D11-001) | **Fixed, verified** | unit, real broker, T3_35 PASS | Dead-letter policy (broker) | Infrastructure owner |
| Database ownership and append-only guards (D11-002, R-01) | **Fixed in the repository; NOT converted on staging** | T10_03, T10_04, T10_31 PASS; conversion script tested on a recreated legacy schema | Migration logins, conversion, read-back, backup first | Infrastructure owner, DBA |
| Registration limit (D11-004); trusted client address and edge rate limits (D12-001) | **Fixed in the repository (follow-up); not yet deployed** | T1_94, T10_81, T10_87 PASS; real-Nginx edge tests | Deploy with the real connector address and test through the real edge | Infrastructure owner |
| Registration enumeration (D11-003) | **Fixed, verified** (owner chose the fix; ADR-013 A-2) | T1_03 PASS; Identity and mobile tests | None | None |
| Validation before authorization (D11-005); console reflow (D11-006) | **Fixed, verified** | T1_31, T4_23, T9_32 PASS | None | None |
| Creators and Content audit (D11-007), copyright intake client (D11-008), maintenance scheduling (D11-009) | **Open** (runbook written) | — | Owner decisions and approvals | Product owner, Infrastructure owner |
| Regression on the fixed build | After the follow-up, 244 rows: 162 PASS, 0 FAIL, 39 BLOCKED, 43 NOT RUN; console 179, scripts 475, Flutter 1,824 | matrix | Devices, real R2, backup restore, edge | Owner |

## Earlier implementation and acceptance record

| Area | Status recorded before this reconciliation | Evidence | Remaining gate at that time |
| --- | --- | --- | --- |
| Mobile UI | Partial | 108 recipes retained. On the iPhone staging release, account journey UAT passed 9/9 by tester report. Startup session restore merged in [PR #30](https://github.com/Markcino/KoloVibe/pull/30). The Flutter job passed on the reviewed PR and on `main`. | Retest SEC-05 on a physical iPhone using a release build from `main` that includes PR #30. Expiry-driven refresh, offline recovery, secure-storage evidence, and physical Android UAT remain open. |
| Django web | Partial | Paginated feed, video/creator details, CSRF account forms and HttpOnly cookies; 14 tests plus real local account journeys pass; rotation survives dependency outages and logout reports unconfirmed revocation. | Full creator/reviewer journeys, production cookie/transport profile and full accessibility review. |
| Identity and gateway | Partial - AWS staging exercised | The public API suite passed 15/15. Two verified tester accounts independently signed in, received their own profile, signed out, and received HTTP 401 on `/me` with the former access token. Existing privileged identity and audit controls are implemented in code. | Refresh-token revocation after logout, refresh rotation and replay evidence, throttling, privileged authorization and broader ADR-013 acceptance remain open. |
| Discovery | Partial | Both clients paginate public feeds. AWS staging returned HTTP 200 for video discovery, 400 for an invalid cursor, and 404 for an unknown creator. Existing gateway contract tests cover pagination across 21 records. | Search, recommendation policy, streaming playback, and device acceptance with published content. |
| Creator onboarding | Backend implemented. Activation pending. | DEC-004 approved. Account-bound invitations, verified-email applications, reviewer decisions and upload eligibility are implemented. | PostgreSQL and privileged staging acceptance, deployment activation, and Flutter integration deferred. |
| Content publishing | Local R2 and FFmpeg candidate. | Private draft, conditional R2 upload, Celery encoding, DEC-005 review and authorized playback. | Live R2/RabbitMQ acceptance, sandboxed worker image, resource and lifecycle controls, staging activation. Flutter upload journey wired locally ([FL-C](FL-C_creator_upload_acceptance.md)); device and live-R2 acceptance open. |
| Engagement | Likes on main. Qualified views implemented locally. | Signed-in tracked playback checks server elapsed time, current publication revision and account/video deduplication under DEC-003. | PostgreSQL CI, edge throttling and abuse verification, staging activation, and Flutter wiring. |
| Non-cash points | DEC-003 approved. Local backend implemented. | Durable qualified-view awards, per-creator UTC cap, and creator-owned balance and history. Award and cap-withholding decisions now write transactional, append-only audit evidence ([BE-AU](BE-AU_points_audit_evidence.md)); delivery scheduling and Points audit credentials are not yet provisioned. | Live RabbitMQ delivery and recovery, deployment activation, and Flutter wiring. |
| Moderation and audit | Local backend implemented. Activation pending. | DEC-005 reports, reviewer decisions, takedowns and independent appeals. Content applies each decision once against the recorded video revision. | AWS staging, PostgreSQL, reviewer MFA acceptance, operational audit scheduling and retention. |
| Profile/privacy/settings | Gated | Own account read via `/me`. | Approved retention and deletion policy, session management, profile/preferences APIs. |
| Deployment | AWS staging deployed. Acceptance partial. | Eight Django services, PostgreSQL and RabbitMQ reached 1/1 each. The public mobile API and protected backend were exercised. See the [AWS rollout record](../operations/AWS_Staging_Deployment_Verification_2026-11-10.md). | Production acceptance, Cloudflare rate-limit evidence, audit operations, backup and restore, resilience, and remaining MVP integrations. Oracle Cloud deployment evidence is tracked separately. |

See the [API test deployment roadmap](API_Test_Deployment_Roadmap.md) for deployment sequencing and earlier environment evidence. No demo data or fixed credential is part of the application.

## Video search integration

Flutter Explore sends a title or description search to `GET /api/v1/videos?q=…`. Gateway validates the query and Content applies it to approved public records before pagination. This implements the video search path toward M-021, M-022 and M-098. Creator search, the full search filter interface, and staging device acceptance remain open.

Local verification: 12 Content video tests, 9 Gateway video tests, and Flutter discovery analysis passed. Tests cover private draft exclusion, query normalization, and invalid inputs.

## Reviewed creator search

Flutter Explore links to creator handle search through `GET /api/v1/creators/search`. Gateway forwards signed requests to Creators. Results include only reviewed active profiles and support cursor pagination and profile navigation. This advances M-021, M-022, M-026 and M-098. The combined search filters and deployed device acceptance remain open.

Local checks passed for four Creators profile tests, three Gateway creator tests, and Flutter analysis of the affected code. Tests cover private service authentication, pending and restricted profile exclusion, pagination, and rejected upstream results.

## Verification resend

Flutter verification links to the resend email form. The local gateway forwards `POST /api/v1/auth/verification/resend` to Identity. The response does not disclose account or delivery status. Identity applies a two-minute cooldown, replaces the prior code after successful delivery, and records the resend in the audit outbox. AWS staging remains closed for this route pending edge throttling and SMTP acceptance.

Local checks passed for resend and registration verification in Identity, the Gateway account suite, and Flutter analysis of the affected account and shell code.

## Active sessions

M-083 opens from Flutter My account. The local gateway lists the 40 most recent active sessions for the bearer account and supports revoking another session owned by that account. Responses omit credentials. Identity rejects both access and refresh credentials for a revoked session and records the action in the audit outbox. The current session still uses sign out. Staging activation and device acceptance remain open.

## AWS staging acceptance on 10 November 2026

| Check | Status | Evidence and next action |
| --- | --- | --- |
| iPhone account journey | Passed, tester-reported 9/9 | App opened, account registration and email verification completed, sign-in and own-profile display worked, and sign-out ended the app session. |
| Public API acceptance | Passed 15/15 | Zero mismatches and zero transport failures on the AWS staging mobile API (`https://mobile-api.cabetechs.shop/api/v1`) and protected backend. Covered health, discovery, input validation, unauthenticated profile access, and restricted routes. |
| SEC-09 own-account profile | Passed for `/me` | Both verified testers received their own account details. This evidence covers `/me`. |
| SEC-08 logout revocation | Partial | Both accounts returned login 200, profile 200, logout 204, then profile 401 with the former access token. Refresh-token rejection after logout remains unverified. |
| SEC-05 iPhone session restore | Failed on tested build; fix awaiting device retest | Closing without signing out returned the tester to Welcome and prompted sign-in. [PR #30](https://github.com/Markcino/KoloVibe/pull/30) merged on 10 November at `ea9fe0aa` and checks the saved session before routing. Retest with a release build from `main` containing the fix. A valid session should open Home, and Profile should show the same account without entering credentials again. |
| CI on PR #30 and reviewed `main` (`b6441bd1`) | Flutter and Django jobs passed. Overall CI failed. | Dependency advisory, security/SBOM and shared-image build/scan jobs failed. Image publication was skipped on `main`. [PR run](https://github.com/Markcino/KoloVibe/actions/runs/42829189953) · [Main run](https://github.com/Markcino/KoloVibe/actions/runs/42830288613) |
| Remaining acceptance | Open | Complete expiry-driven refresh, rotation and replay handling, offline recovery, secure-storage verification, physical Android UAT, Cloudflare rate-limit evidence, and the remaining publishing, playback, engagement, points, and moderation gates. |

**Next device check.** Install a release build from `main` containing `ea9fe0aa` on the physical iPhone. Sign in, force-close without signing out, then relaunch from the app icon. Confirm Home opens and Profile shows the same account without another sign-in. Record the tested commit, device result and any error before closing SEC-05. Use the [physical iPhone instructions](../../apps/mobile/README.md#run-on-a-physical-iphone) to build it.

## DEC-004 staging activation checklist

Creator onboarding defaults off in staging. Only the Gateway and Creators service accept `KOLOVIBE_STAGING_CREATOR_ONBOARDING=1`. Gateway also requires the existing privileged and account capability approvals. Keep Identity's privileged MFA and audit checks enabled when testing reviewer actions. Apply the Identity and Creators migrations, verify the exact gateway ingress paths and rate limits, and capture PostgreSQL and reviewer MFA acceptance before activation. The current production profile remains closed.

## OD-07 local R2 and FFmpeg VOD candidate

Set `KOLOVIBE_LOCAL_MEDIA_ENABLED=1` only for the local candidate. The launcher passes the flag to Gateway and Content. Content receives `KOLOVIBE_R2_ACCOUNT_ID`, `KOLOVIBE_R2_MEDIA_BUCKET`, `KOLOVIBE_R2_ACCESS_KEY_FILE`, `KOLOVIBE_R2_SECRET_KEY_FILE` and the Content AMQPS broker URI `KOLOVIBE_CONTENT_RABBITMQ_URL` from the owner-only environment. Use a dedicated private bucket and scoped object permissions. Install the optional hash-locked dependencies with `python -m pip install --require-hashes -r requirements-media.txt` in the local Gateway/Content development environment. The native signer is outside the shared Alpine image. Install FFmpeg and ffprobe on the local worker and run `python scripts/run_local_service.py content run_media_worker`.

The candidate accepts MP4 uploads up to 50 MiB, with a five-minute duration and 1080p input limit. R2 upload links expire in ten minutes and require the signed size, content type and create-only condition. Upload completion checks the object and records its ETag before queueing. The single worker produces a private MP4 up to 720p, then moves the video to review. Moderation controls publication. Authorized playback links expire in five minutes.

If RabbitMQ is unavailable after completion is recorded, retry the same completion request to enqueue processing. The worker uses a database lease to prevent duplicate processing and recover stale leases. The separate production worker still needs a sandbox and bounded resources, monitored reconciliation of stuck jobs, and an approved R2 lifecycle for expired originals and abandoned renditions. Staging activation and paid provisioning are outside this change.

## DEC-005 local candidate

Set `KOLOVIBE_LOCAL_MODERATION_ENABLED=1` in the existing owner-only local environment. Configure the internal Moderation origin as `KOLOVIBE_MODERATION_URL` and a `KOLOVIBE_MODERATION_OUTBOUND_KEY` distinct from the Gateway signing key. Apply the Content and Moderation migrations before starting the local services. Reviewer routes rely on Identity's existing privileged MFA session validation. Staging and production routes remain closed.

A Content timeout leaves the moderation decision pending. Retry the same operation and idempotency key. Content records a transactional receipt so a response lost after applying a decision cannot reapply it. Use a new key for a different decision. Restoration requires a different reviewer and the same removal revision. Live R2 and media worker provisioning, reviewer MFA on staging and the PostgreSQL concurrency checks remain separate acceptance work.
