# Advertising — acceptance criteria and delivery plan (proposed)

**Status: PROPOSED — not approved.** 25 November 2026. Delivers A1 to A7 one independently testable capability at a time; focused tests and CI per slice; no automatic merges or AWS deployments; comprehensive UAT deferred to Phase 11. **No slice starts before its decisions are recorded** ([gate table](../../architecture/advertising/AD-Owner_Decisions_Required_PHASE8A.md#what-each-capability-needs-before-it-can-start)).

## 1. Rules for every PR

1. One capability; reuse existing patterns; no deferred feature (network SDK, real charging, targeting beyond contextual, media before pipeline, advertiser portal).
2. Each operation lands with its contract entry, authorization row, registry-driven tests and console or Flutter counterpart **in the same PR**.
3. Flags closed by default; production NO-GO; owner approves every merge and deployment.
4. A results file per slice in `docs/engineering/phase8/`: actual changes, tests run, failures, unresolved work, blockers. Nothing claimed that was not run.
5. After repeated unsuccessful fixes, stop and report the blocker.

## 2. Wiring checklist (from Business Phase 6E and Events)

Gateway (`capabilities.py`, `settings.py`, `urls.py`, `routes/`, local peer table in `internal_client.py`); `staging_runtime` capability table and `scripts/ops/kolovibe_cluster.py` (empty capability set); Audit producer, migration and `service_auth.py` (approval needed); service-identity tests in every service and `scripts/test_service_identity_drift.py`; `scripts/check_structure.py`, `run_local_service.py`, `test_gateway_role_matrix.py`, `test_gateway_route_contract.py`, `probe_*`; a new `scripts/ads_journey.py` in `verify_local_journeys.py`; `.github/workflows/ci_cd.yml`; OpenAPI in `packages/contracts`. A test fails if any place is missed.

**Ads-specific static guards** (added in the first PR): no Ads import of or reference to Points, Engagement or Content tables; no payment adapter or charge route; no network SDK dependency without an approval constant; no float in money paths.

## 3. Slices and PR order

The instruction orders A1 to A7. Three dependencies are noted so the order stays honest: A2's "submit creative" needs A3; A4 needs an approved creative and a consent source; A5 needs A4's decisions. **Recommendation for approval:** build A3 (text creative and review) immediately after A2's campaign shell, as below, and interleave the A6 console pages with the slice each belongs to rather than leaving them to the end.

| PR | Capability | Backend | Flutter | Console | Needs |
| --- | --- | --- | --- | --- | --- |
| P8-A0 | Service skeleton, flags, wiring, guards, audit producer | shell, health, service auth, limits | — | — | DR-AD-01 to 04 |
| P8-A1a | Advertiser registration, membership, invitations | advertiser, grant, membership | onboarding, team | grants | DR-AD-10, 13, 60, 61 |
| P8-A1b | Verification, Business link, restriction and suspension | cases, decisions, Business check | verification status, profile | verification queue, restrict/suspend | DR-AD-11, 12, 14, 15 (05 for SU) |
| P8-A2a | Campaign shell: state machine, schedule, budget bounds, idempotency | campaign, budget, placements | create, edit, list, detail, pause/resume | campaign review queue | DR-AD-20 to 23 |
| P8-A3a | Text creatives, versions, review, rejection reasons, appeal | creative, versions, decisions | creative editor, review status | creative moderation | DR-AD-24 to 27 |
| P8-A3b | Image and video creatives | media intent, screening hooks | media picker | preview | **DR-AD-06 (blocked)** |
| P8-A4a | Placement config, eligibility, decision, label, fallback, consent gate | decision, reservation, frequency | sponsored card, why/report sheets | placements, report queue | DR-AD-07, 30 to 32, 35, 40, 43, 62 |
| P8-A5a | Impression and click validation, dedupe, IVT rules, finalizer | events, billable events, hold | — | fraud alerts | DR-AD-33, 34, 41 |
| P8-A5b | Reporting (advertiser and scoped) | aggregates, suppression | results screens | scoped analytics | DR-AD-42 |
| P8-A6 | Campaign suspension, advertising audit, grants completeness | — | — | suspension, audit history | DR-AD-61 |
| P8-A7a | Reservations hardening, invoice data | invoice, lines | invoice view | — | DR-AD-21, 50, 51 |
| P8-A7b | Corrections, reconciliation interface (sandbox) | corrections, recon | — | billing corrections, recon | DR-AD-50, 52 |
| P8-SEC | Cross-cutting security suite, four-way reconciliation, real-HTTP journey, mutation checks | tests | layout audit | route security | — |
| P8-R | Results, tracker, README, flag-opening approval request | docs | — | — | — |

Each slice's security tests ship in that slice; P8-SEC consolidates, as Phase 6E did, and is not a place to defer missing tests.

## 4. Acceptance criteria

IDs `AC-AD-nnn`.

### A1 Advertiser accounts

| ID | Criterion |
| --- | --- |
| AC-AD-001 | Registration refused without grant; owner server-assigned; same key returns the same advertiser |
| AC-AD-002 | Non-members get 404 on every advertiser operation (registry-driven) |
| AC-AD-003 | Moderators, administrators and reviewers cannot be members; members cannot hold grants |
| AC-AD-004 | Verification flow with reason codes, one resubmission, submitter ≠ decider; unverified advertiser cannot be approved |
| AC-AD-005 | Business link only through the signed Business check; a client-supplied claim is refused |
| AC-AD-006 | Invitation codes single use, hashed, expiring, throttled |
| AC-AD-007 | Restriction and suspension follow the state machine; restorer ≠ suspender; delivery stops at the next decision |
| AC-AD-008 | Step-up operations fail closed until Identity provides the proof |

### A2 Campaigns

| ID | Criterion |
| --- | --- |
| AC-AD-010 | Client cannot set `state`; invalid transitions refused with bounded codes |
| AC-AD-011 | Schedule and budget validation per DR-AD-22/23; unapproved placement refused |
| AC-AD-012 | Pause and resume rules; suspended campaigns cannot be resumed by the advertiser |
| AC-AD-013 | Every state change idempotent; key reuse with another body refused (409) |
| AC-AD-014 | Budget cannot be lowered below spent plus reserved; concurrent budget edits serialise |
| AC-AD-015 | **Cross-campaign IDOR** proved from the registry for every campaign-scoped operation |

### A3 Creatives

| ID | Criterion |
| --- | --- |
| AC-AD-020 | Versions immutable; delivery reads only the approved version; an edit never changes a serving version |
| AC-AD-021 | Review by `ad_review` only; submitter ≠ decider; reviewer not a member; bounded reason codes; appeal by a different reviewer |
| AC-AD-022 | **Unsafe destinations:** `javascript:`, `data:`, `file:`, `http:`, userinfo, IP literals, localhost and private ranges, shorteners, redirectors, punycode lookalikes, over-long and control-character inputs are all refused; the external route is closed while its flag is closed |
| AC-AD-023 | Text fields are length-bounded, plain, and cannot imitate the "Sponsored" label |
| AC-AD-024 | **Fraudulent creatives:** fixtures for impersonation, prohibited category and misleading claim are rejected; a user report can suspend a creative |
| AC-AD-025 | Media absent and recorded as blocker until DR-AD-06 |

### A4 Delivery

| ID | Criterion |
| --- | --- |
| AC-AD-030 | A sponsored item appears only in a separate response field with `sponsored: true`; the Flutter card shows the label and advertiser, differs from organic cards, offers no like, share or comment |
| AC-AD-031 | Eligibility predicate enforced at every decision; ineligible returns no item, not an error that reveals why |
| AC-AD-032 | Density and frequency caps hold under concurrency |
| AC-AD-033 | Without consent, or after withdrawal, decisions and events are refused; delivery flags refuse to start without the consent source |
| AC-AD-034 | Unavailable ad collapses the slot; a slow or failing ad service never delays organic content (client timeout) |
| AC-AD-035 | A member of the advertiser never receives its own ads as billable traffic |
| AC-AD-036 | Layout audit passes with large text and small screens |

### A5 Measurement

| ID | Criterion |
| --- | --- |
| AC-AD-040 | **Fake impression injection:** forged ids, bad MAC, unknown decisions, other accounts' decisions, expired decisions, impossible timing, impressions exceeding decisions: none changes spend or billable counts |
| AC-AD-041 | **Click replay:** concurrent and sequential repeats yield one click event and the same destination; click without valid impression refused |
| AC-AD-042 | Client-reported events alone never create a billable event; only the finalizer does, after the hold |
| AC-AD-043 | Every IVT rule has a test with synthetic traffic and an expected outcome; no rule penalises an account |
| AC-AD-044 | **No-Points test:** static scan both directions and a runtime run posting every ad event kind to the Points consumer path produces zero entries |
| AC-AD-045 | **Sensitive analytics leakage:** suppression below 20, differencing attempts over adjacent ranges, bounded range and granularity, no account fields; console reads audited |
| AC-AD-046 | Impression and click answers are constant-shape; rejected payloads are counted, not stored |

### A6 Console

| ID | Criterion |
| --- | --- |
| AC-AD-050 | Every route needs MFA and the right grant; unregistered pages fail the route-security test |
| AC-AD-051 | **Privileged review bypass:** a member, a grant-less moderator, a reviewer approving their own item, a restorer who suspended, and a replayed decision are all refused or recorded once |
| AC-AD-052 | Double-submit safe forms (claim, confirm, decision) |
| AC-AD-053 | Suspension takes effect at the next decision; audit is id-only |

### A7 Billing preparation

| ID | Criterion |
| --- | --- |
| AC-AD-060 | **Budget bypass:** N concurrent decisions against a small budget never exceed it; unreported decisions release their reservation exactly once |
| AC-AD-061 | **Duplicate billing records:** concurrent finalizer runs and replays produce one billable event per decision and kind; each billable event is invoiced once |
| AC-AD-062 | Invoice totals equal the recomputation from billable events; rounding once per line; float-breaking amounts tested |
| AC-AD-063 | Corrections are append-only; requester ≠ approver; threshold requires a second approver |
| AC-AD-064 | Reconciliation records differences and never changes billing facts |
| AC-AD-065 | **Billing guard:** no charge, payment or collection route, import or status exists |

### Cross-cutting

| ID | Criterion |
| --- | --- |
| AC-AD-070 | With every flag closed no Ads route is served |
| AC-AD-071 | Four-way reconciliation of contract, Gateway, service registry and clients shows no difference; real answers validate against schemas |
| AC-AD-072 | Real-HTTP journey: advertiser onboarding to approved campaign to sponsored item to validated impression and click to invoice, with a second advertiser attacking at each step |
| AC-AD-073 | Mutation checks: removing one membership join, one MAC check, one budget condition or one consent check makes a named test fail |
| AC-AD-074 | Log and audit content tests show no MAC, consent detail, URL or free text |
| AC-AD-075 | No network SDK, advertising-ID or tracking dependency exists in the app or services |

## 5. Test approach

Service tests on real PostgreSQL for concurrency (reservation, finalizer, frequency), Gateway tests, Dart unit and widget tests with the layout audit, console tests, then the shared scripts and CI. Synthetic-traffic generators drive the IVT rules. **Not run in Phase 8:** staging, devices, load and soak, any real network or payment provider, penetration testing (Phase 11).

## 6. Flutter work

Route numbers from M-200. About 24 screens plus two components (the sponsored card and the "Why this ad / Report" sheet). Reuse design tokens, shared widgets, repositories, secure storage and the drift-tested model approach. The sponsored card must be a distinct widget that cannot be built from the organic video card.

## 7. Blockers register

| # | Blocker | Affects | Needs |
| --- | --- | --- | --- |
| BL-AD-01 | Consent store and envelope field | all delivery and measurement | DR-AD-07, 40 |
| BL-AD-02 | Image/video pipeline | media creatives | DR-AD-06 |
| BL-AD-03 | Identity step-up | budget raise, team change, closure, corrections | DR-AD-05 |
| BL-AD-04 | Ledger ownership across Events and Ads | any real charging | DR-AD-03, DR-EV-03 |
| BL-AD-05 | Currency, tax, invoice entity, price list | real billing | DR-AD-21, 51 |
| BL-AD-06 | Legal review: data protection, minors, ad content | delivery to the public | DR-AD-40, 43, 24 |
| BL-AD-07 | Network (AdMob) eligibility and the website conflict | any network ads | DR-AD-36 |
| BL-AD-08 | Business read-only check endpoint | Business association | DR-AD-11 |
| BL-AD-09 | Database role model; capacity for another service | any deployment | DR-AD-05 |
| BL-AD-10 | Retention and privacy orchestration | purge, export, erase | DR-AD-41, ADR-020 |
| BL-AD-11 | DOC-023 change request | governance | DR-AD-01 |
| BL-AD-12 | Device attestation | stronger fraud resistance | not requested |
