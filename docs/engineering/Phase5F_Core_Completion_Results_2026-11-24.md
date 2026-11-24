# Phase 5F — core application completion: results and R1 development-completion matrix

**Date:** 24 November 2026. **Base:** `main` at `5e7eda7` (merge of #219; no open pull requests at the start). **Scope:** repository changes only. No AWS, staging, migration, RabbitMQ, database-privilege, merge or deployment action was taken. Production remains **NO-GO**. The owner-verified staging release is still `v0.373.1` (`bb79e1a`); `main` is **70 commits ahead** of it, so nothing below is evidence of staging behaviour.

## 1. Outcome in one paragraph
Inspection of `main` found the eight services, the 108 mobile screens and the administrator/moderator console substantially complete. Almost every remaining item on the Phase 5F work-package list is **implemented and awaiting deployment and acceptance**, or **blocked by an unmade owner decision**. Only **one genuine, policy-independent functional gap** was found and closed (creator invitation listing and revocation, P5F-01). One piece of dead duplicated mobile code was removed and one missing mobile regression test added (P5F-02). **No policy was invented.** Eleven owner decisions are set out in §5 with a least-privilege recommendation and the effect on implementation for each.

## 2. Evidence base (what was actually run on 24 November)
| Check | Result | Notes |
| --- | --- | --- |
| Django service suites (disposable SQLite) | identity 157, gateway 215, creators 84, content 135, engagement 72, points 68, moderation 71, audit 49, business 162: **all pass** | `makemigrations --check` clean for all nine services. Skips are optional-dependency tests (AWS CRT signer, real FFmpeg, OpenSSL), so the **real-FFmpeg and reference-signer paths were not run here** |
| Administrator console suite | 138 pass | up from 131; `manage.py check` clean |
| Script suites (route contract, role matrix, drift guards, mobile asset/design checks) | 446 pass | includes the default-deny, role/MFA and DOC-205 parity tests |
| DOC-205 | validates with `openapi-spec-validator` 0.7.2 | 158 operations declared |
| Engagement→RabbitMQ-contract→Points pipeline on **real PostgreSQL 16** | 8 tests pass | `verify_event_pipeline.py`, run as the `postgres` OS user. The broker itself is simulated by the repository's test double: **no live RabbitMQ** |
| Database role/ownership preflight on PostgreSQL 16 | 16 tests pass | disposable cluster only; says nothing about staging |
| Creators migrations `0001`–`0006` and the full Creators suite on **PostgreSQL 16** | applied, 84 pass | `0006` is one `CREATE TABLE` plus one index; the status-choices change is a no-op in SQL |
| Flutter, **CI-pinned SDK 3.47.8**, lockfile enforced | `flutter analyze`: **no issues**; **1,556 tests pass** | Phase 4 had only SDK 3.50.1 and an unenforced lockfile; this is the first run at the pinned version recorded in this repository. Fake repositories and `MockClient`; **no physical device, no network** |

Not run, by design: staging, live R2, live FFmpeg, live RabbitMQ, physical iPhone or Android, accessibility with a screen reader, performance (Phase 11).

## 3. What is genuinely missing versus awaiting acceptance
**Genuinely missing, independent of policy (closed in this phase):**
- Creator invitation listing and revocation (console, gateway, Creators, contract). → [P5F-01](phase5f/P5F-01_creator_invitation_management.md).

**Genuinely missing, blocked by an owner decision (not built):** creator-level restriction/suspension *write* path, post-approval re-review, privacy export/deletion, points reversal, fraud-hold clearing, audit retention/legal hold, R2 lifecycle deletion, M-045 frame choice, profile photos, M-078 submit. See §5.

**Implemented, awaiting deployment and acceptance:** everything else (see §4). Source presence and local tests are not staging acceptance.

**Corrections to earlier records found while inspecting** (no behaviour changed):
1. The tracker said creator invite and review were "administrator-only in console and service". They are administrator-only **in the console only**. DOC-205 and the Creators service accept `moderator` or `administrator` for `invite`, `pending` and `review` (the matrix test pins this as a deliberate delegation). Decision D-9 below asks whether to narrow the API to match the console.
2. The tracker's identity row still says refresh revoke/replay negatives were "unproven". Phase 1 (#195) proved replay revocation, wrong-token safety and logout isolation, and #197 added the account-level MFA lock. Still not proven: concurrent refresh exactly-once on PostgreSQL, and any of it on staging.
3. The Phase 5 tracker row "Creator invitation management … Missing" is now **Implemented, awaiting integration** (P5F-01).

## 4. Work-package results

### WP1 Identity and accounts — no code gap found
Registration, verification and resend, sign-in, sign-out, session restore, refresh rotation and replay revocation, password reset and change, session list/revoke, MFA with account-level lock, notification preferences, privacy-request intake and status (`/me/privacy-requests` GET/POST) all exist in Identity, Gateway and Flutter (M-001–M-016, M-079–M-094), with 157 Identity and 215 Gateway tests plus the Phase 1 negative suites. No second session system exists. **Blocked:** privacy export and deletion (D-5). **Open for the owner:** SEC-05 iPhone session-restore retest; staging replay evidence.

### WP2 Creator functionality — one gap closed
Applications, approval, profiles, owner-only editing, library and library search, analytics, standing read and enforcement exist. **Closed:** outstanding-invitation listing and revocation (administrator-only at console, gateway and Creators; `invited → revoked`; `revoked → invited` by re-invitation by an administrator; used or decided applications refused 409; applicant sees 404; event trail; no email or name ever listed). **Blocked:** profile photos (D-3); the write path for creator restriction and suspension (D-8) — enforcement and display exist, but no operation sets `restricted` or `suspended`; creator-role narrowing (D-9).

### WP3 Video and media — no policy-independent gap found
Draft → size-bound create-only R2 grant → exact-object completion → FFmpeg → review → moderation → publish → five-minute signed playback → unpublish is covered by the Phase 3 journey test and stalled-job requeue by 6 tests; thumbnails and the poster, rights attestation, Content-owned moderation receipts and cross-creator 404 exist. Not changed. **Blocked:** post-approval edits remain publishable without re-review (D-1, risk R-03); M-045 frame choice (D-2); R2 lifecycle deletion (D-10). **Not run:** real FFmpeg and the reference R2 signer in this environment; live R2.

### WP4 Engagement and Points — verified, unchanged
Likes, follows, shares, watch sessions, server-measured qualified views, 24-hour dedup, creator daily cap, self-view rejection, fraud holds (read-only), append-only ledger, outbox/inbox idempotency and the named `kolovibe.points` exchange routing are covered, and the pipeline passed again on PostgreSQL 16. Routing and broker permissions were not touched. **Blocked:** reversals (D-6), hold clearing (D-7), dead-letter handling (owner broker configuration). No monetary conversion rule exists or was invented. Self-likes are accepted and earn nothing (product note, unchanged).

### WP5 Moderation and audit — no policy-independent gap found
Reports, notices, standing, appeals with independent reviewer rule, reviewer assignments and grant-scoped permission enforcement, Audit ingest with append-only guards and redacted projection exist. **Blocked:** appeal submission design conflict (D-4), retention/redaction/legal hold (D-11). **Follow-up recorded:** Creators has no Audit delivery credential, so P5F-01 stores a service-owned event table instead; delivery to Audit and a database append-only trigger need an Audit credential and an operations-approved migration.

### WP6 Administrator and moderator web — complete for approved scope
Existing pages: login with privileged MFA, dashboard, moderation queues and details for videos, reports and appeals with decisions, assignments, creators (now with outstanding invitations), moderator invitations (team), fraud review, points review, audit, own account, sessions, logout. 138 console tests including the route security matrix and the layout/accessibility static checks. No public page exists or was added. **Not done:** screen-reader, real-width browser and keyboard walk-through (manual accessibility pass, owner or Phase 11). Account and session management of *other* people's accounts has no approved rule and was not built.

### WP7 Flutter completion — nothing further buildable without decisions
All 108 screens and states are implemented and reachable; there are **no duplicate screen classes**. One search found two widgets (`SectionHeader`, `EmptySection`) with **zero references in code or tests**; both were deleted (P5F-02) and the full suite still passes. Loading, empty and error handling were checked on every `FutureBuilder`; the startup and compatibility paths degrade rather than fail. A regression test now pins that a withdrawn creator invitation (404) reads as "no application". M-045, profile photos, M-078 and M-091–M-094 completion remain decisions (D-2, D-3, D-4, D-5). **No physical-device acceptance is claimed.**

## 5. Owner decisions required
Each row states the exact missing decision, the least-privilege recommendation and what it unlocks. None was implemented.

| ID | Missing decision | Recommendation (least privilege) | Effect on implementation |
| --- | --- | --- | --- |
| D-1 | Must an edit to a **published** video go back through review? (risk R-03; tracker B-08) | Yes. A change to title, description, category, tags or cover on a published video unpublishes it into the existing review queue; it returns to public only after approval of the new revision. Rights/sensitive-field edits never apply silently | Content state transition plus a Moderation intake path; mobile M-054 wording ("changes need review"); migration only if a pending-revision field is added |
| D-2 | M-045: add a frame-thumbnail endpoint or accept the cover-moment slider | Accept the slider for R1; no new media surface | None if accepted; otherwise a Content endpoint and FFmpeg frame job |
| D-3 | Profile photos and their moderation policy | Not in R1: keep the initial-letter avatar. If wanted: upload only after verification, private until approved by a reviewer | None if deferred; otherwise upload endpoint, R2 prefix, moderation queue type, six screens |
| D-4 | M-078 appeal: submit or read-only | Submit, only for the existing appealable states, because the service already enforces one appeal per removal and an independent reviewer; update the design record | Documentation only (client already shows a form only when the notice says appealable) |
| D-5 | Privacy retention, export and deletion (ADR-020) | R1: intake and status only, fulfilled manually under a documented procedure; no self-service deletion | None for intake; export/deletion need a retention schedule, legal sign-off and a fulfilment job |
| D-6 | When may a points award be reversed, by whom | Administrator only, with a reason code and second-administrator confirmation, only for an award tied to a removed video or upheld fraud finding; written as a compensating append-only ledger entry; no conversion to money | A Points write operation plus audit; the constraints for it already exist |
| D-7 | May a reviewer clear a fraud hold | Assigned moderator or administrator, with a reason code, audited; holds are never created by hand | An Engagement operation and a console form on the fraud page |
| D-8 | Who may restrict or suspend a creator, for what, and how it is appealed | Administrator only, with a reason code, a creator notice and the existing appeal route; reinstatement by a different administrator | Creators operation, Moderation standing notice, Points withholding input, console page |
| D-9 | Should the invite, pending and review API be narrowed from moderator-or-administrator to administrator, matching the console | Yes, unless moderators are meant to approve creators in DEC-004 | One-line role change in Creators and Gateway, contract and test updates |
| D-10 | R2 lifecycle: retention for originals, abandoned uploads, superseded renditions, and a delete-capable credential (OD-07) | 7-day expiry of abandoned uploads; keep originals until the video is removed or the creator deletes it; delete credential scoped to the media prefix and never shared with the signer | Content cleanup command and an owner-created credential |
| D-11 | Audit retention, redaction and legal hold (OD-08, ADR-017) | Retain security and moderation evidence for a fixed period set by counsel; hold flag blocks purge; redaction by projection only | Audit purge command and hold table |

## 6. R1 development-completion matrix
**Status key.** *Ready for UAT after deploy* = code-complete with automated tests, but **not deployed** since `v0.373.1`; it needs the listed deployment step first, then Phase 11 acceptance. *Decision* = blocked by §5. *By design* = out of R1.

### 6.1 Services
| Feature | Service | Evidence | Status | Needs |
| --- | --- | --- | --- | --- |
| Account lifecycle, sessions, MFA, lock, preferences, privacy intake | identity, gateway | 157 + 215 tests; Phase 1 negatives | Ready for UAT after deploy | iPhone SEC-05 retest |
| Privacy export and deletion | identity | none | **Decision D-5** | policy |
| Creator invitation, application, review, role sync | creators, identity, gateway | 84 + 215; PostgreSQL 16 | Ready for UAT after deploy | onboarding flag on; **migration 0006** |
| Creator invitation listing and revocation | creators, gateway | 8 + 6 new tests; PostgreSQL 16 | Ready for UAT after deploy | **migration 0006** and runtime grants on `service_onboardingevent` |
| Creator profile, owner edit, search, standing read | creators, gateway | existing suites | Ready for UAT after deploy | staging flags |
| Creator restriction/suspension write path | creators, moderation | none | **Decision D-8** | policy |
| Video draft, upload grant, completion, FFmpeg, stalled recovery | content, worker | 135 tests; journey test | Ready for UAT after deploy | live R2/FFmpeg/RabbitMQ run; owner schedules requeue |
| Moderation before publish, secure playback, unpublish, takedown | content, moderation | journey test; 71 tests | Ready for UAT after deploy | live run |
| Published-video edit re-review | content, moderation | none | **Decision D-1** | policy |
| Media cleanup under retention | content | none | **Decision D-10** | policy, credential |
| Likes, follows, shares, watch sessions, qualified views, caps, self-view rejection | engagement, gateway | 72 tests | Ready for UAT after deploy | staging flags |
| Fraud holds (read) | engagement | 72 tests | Ready for UAT after deploy | thresholds untuned |
| Fraud hold clearing | engagement | none | **Decision D-7** | policy |
| Points award, balances, append-only ledger | points | 68 tests; PostgreSQL 16 pipeline | Ready for UAT after deploy | live RabbitMQ run |
| Points reversal; monetary conversion | points | none | **Decision D-6** / **By design** | policy |
| Reports, notices, standing, appeals, reviewer assignments | moderation | 71 tests | Ready for UAT after deploy (appeal wording **D-4**) | live run |
| Audit ingest, redacted read, append-only guards | audit | 49 tests | Ready for UAT after deploy | delivery job scheduled by owner |
| Audit retention, legal hold | audit | none | **Decision D-11** | policy |
| Business module (outside R1) | business | 162 tests | Local only, flags closed | owner scope decision |
| Live streaming, payments, ticketing, ads | none | n/a | **By design** (excluded or approval-blocked) | none |

### 6.2 Administrator and moderator web (no public pages)
| Page | Evidence | Status |
| --- | --- | --- |
| Login, privileged MFA, session validation, logout | route security matrix, 138 tests | Deployed earlier; positive UAT reported 6/6 on `v0.357.1`; negatives and `main` changes need Phase 11 |
| Dashboard, video/report/appeal queues, details, decisions, assignments | existing tests | Ready for UAT after deploy |
| Creators: invite, applications, **outstanding invitations and revoke** | new tests; mutation-checked | Ready for UAT after deploy (**migration 0006**) |
| Moderator invitations (team) | existing tests | Ready for UAT after deploy |
| Fraud review, points review, audit browse | existing tests | Ready for UAT after deploy |
| Own account, password, sessions | existing tests | Ready for UAT after deploy |
| Accessibility | 11 static checks | **Partial**: manual screen-reader and keyboard pass not done |

### 6.3 Flutter mobile (108 screens, 1,556 tests, SDK 3.47.8, analysis clean)
| Journey | Screens | Status | Open |
| --- | ---: | --- | --- |
| J1 Accounts, settings, privacy | 32 | Implemented; ready for device UAT | M-091–M-094 completion **D-5**; SEC-05 |
| J2 Discovery and playback | 19 | Implemented; ready for device UAT | device playback with real published content |
| J3 Creator Studio | 25 | Implemented; ready for device UAT | M-045 **D-2**; profile photo screens **D-3**; live upload |
| J4 Points | 9 | Implemented; ready for device UAT | reversal display only after **D-6** |
| J5 Trust and moderation | 9 | Implemented; ready for device UAT | M-078 **D-4** |
| J6 System states and dialogs | 14 | Implemented; ready for device UAT | none |
Screen-by-screen visual parity (8 matched, 99 functional with a recorded deviation, 1 not verified) is carried forward from the 20 November review and was **not re-captured**. **No device result exists.**

## 7. Security findings
1. **No new vulnerability found.** New controls: administrator-only at three layers, self-revocation refused, state guard, signed session-bound console intent per row (an intent minted for one operation does not authorize another), target taken from the path only, validated responses, no email or name exposed, the applicant cannot distinguish revocation from never-invited, event written in the same transaction. Each control was removed in turn and a test failed.
2. **Authorization finding (D-9):** the creator invite, pending and review API permits moderators although the console restricts them to administrators. This matches the approved contract, so it was not changed.
3. **Residual:** `OnboardingEvent` rows are not protected by a database trigger and are not delivered to Audit. The runtime database role needs INSERT and SELECT on the new table; with the existing ownership risk (R-01) this must be handled in the owner's operations plan.
4. **Environment:** the first PostgreSQL run needed a non-root OS user (`initdb` refuses root); this is a property of this container, not the product.

## 8. Pull request and tracker
One pull request carries this phase on the session branch `claude/funny-pascal-l1jzhf` (P5F-01, P5F-02, this document and the tracker update). **It is not merged and nothing was deployed.** The tracker section "Phase 5F" and two corrected rows were added to `R1_Application_Tracker.md`.

## 9. Prerequisites for the next phase
1. Owner decisions D-1 to D-11 (D-1, D-4, D-8 and D-9 unblock the most code).
2. Owner merges, then deploys `main` to staging under an approved plan, applies Creators migration `0006`, and grants the runtime role access to the new table.
3. Recording the v0.373.1 digests and the current deployed commit (B-01).
4. Owner-run live R2, FFmpeg and RabbitMQ journeys, then device runs on the iPhone and Android checklists. These belong to Phase 11.
