# R1 application delivery tracker

**Updated 24 November 2026 (Phase 5F section added).** Stage 3 (Technical Foundation) was **declared completed by the owner on 10 November**, while unresolved security, operations and recovery controls remain open. Stage 4 (R1 MVP implementation) and Stage 5 (verification) remain in progress on AWS staging. Production is **NO-GO**. See the [Stage 3 tracker](Stage3_Implementation_Tracker.csv) and the [current AWS release record](../operations/R1_AWS_Staging_Reconciliation_2026-11-23.md).

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
| Post-approval metadata edits | content | M-054 | none | `PATCH /videos/{id}` | Published videos can change with no re-review (R-03) | included above | **Blocked by approval** | Owner decision: re-review or risk acceptance | B-08 |
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
| Business listings and verification (R2) | none | none | none | none | none | none | **Missing**; **Blocked by approval** | Outside R1 (DEC-001); PRD/SRS detail unapproved (#133). Phase 6A design approved by the owner on 24 November (PR #218 merged; [approval record](../architecture/business/BIZ-Owner_Approval_Record_2026-11-24.md)); **Phase 6B backend implemented locally behind closed flags, not deployed, not staging-tested** ([completion report](phase6/Phase6B_Business_Backend_Completion_Report_2026-11-24.md)); still outside R1 | B-19 |
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

Local test run at HEAD and the full backlog, DRY analysis, risk register and Phase 1 acceptance criteria are in the [Phase 0 baseline](Phase0_Implementation_Baseline_2026-11-23.md#2-local-test-evidence-at-head).

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
