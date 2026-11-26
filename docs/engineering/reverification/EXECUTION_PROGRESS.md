# KoloVibe execution progress

**Read this file first when resuming.** Then check the repository state (`git log origin/main`, open PRs) before continuing. This tracker covers the owner's mandate "Complete application reverification, development completion, testing and final acceptance", in its 25 November 2026 form. The mandate was re-issued that day; this file continues the existing work and does not restart it.

Updated: 26 November 2026, `main` at `68d8df6`. A staging deployment and verification ran that evening ([record](../../operations/R1_AWS_Staging_Verification_2026-11-26.md)): **v0.542.1 is deployed on all 16 staging services** (migrations Identity 0016 and Content 0013 applied). Earlier that day a first simulator test of the app ran that day against a local stack ([results](simulator-run-2026-11-26/results.md)). The mandate was re-issued again that day as "Continue verified end-to-end development, final design and acceptance"; this file continues under it. **Production is NO-GO.** Nothing in this file is deployed to staging unless a row says so.

## Where the other records live

This file does not duplicate the authoritative records; it points to them.

| Mandate deliverable | Where it lives |
| --- | --- |
| Application baseline (Phase 00) | [Phase 1 reverification](Phase1_Reverification_2026-11-25.md) and the [Phase 0 baseline](../Phase0_Implementation_Baseline_2026-11-23.md) |
| Requirements traceability matrix (Phase 01) | The feature matrix in [Phase 1 reverification](Phase1_Reverification_2026-11-25.md), plus [DOC-007](../../requirements/DOC-007_Traceability_and_Signoff_DRAFT.md) |
| Implementation gap register (Phase 02) | [Phase 2 requirements, architecture and plan](Phase2_Requirements_Architecture_Plan_2026-11-25.md), sections 4 and 5 |
| Owner decisions | [Owner decisions A to J](../../planning/Owner_Decisions_A-J_2026-11-25.md) |
| Feature and release history | [R1 application tracker](../R1_Application_Tracker.md) |
| Last defect register and readiness assessment | [Phase 12 defect register](../phase12/Phase12_Defect_Register.md) and [readiness report](../phase12/Phase12_Release_Readiness_Report.md) |
| Staging deployment, test execution and new defects D13-001 to D13-007 (26 November) | [AWS staging verification](../../operations/R1_AWS_Staging_Verification_2026-11-26.md) and the [defect register](../phase12/Phase12_Defect_Register.md) staging section |
| Simulator application test (26 November, local stack, not staging) | [Simulator run results](simulator-run-2026-11-26/results.md), with screenshots and the gateway access log |
| Development completeness gate, master test plan, test execution, security, regression, infrastructure, staging and final acceptance reports | **Not created yet.** They are due at Phases 09 to 14, and each will be added here when its phase starts. |

## Status vocabulary

The requirement classifications are: VERIFIED COMPLETE, IMPLEMENTED BUT UNVERIFIED, PARTIALLY IMPLEMENTED, NOT IMPLEMENTED, DEFECTIVE, SECURITY BLOCKER, EXTERNAL DEPENDENCY BLOCKER, NOT APPLICABLE and APPROVED DEFERRED. Older records use their own terms, which map as follows:

| Older term | Classification used here |
| --- | --- |
| Verified complete (scoped) | VERIFIED COMPLETE, within the evidence scope stated |
| Implemented, awaiting integration; Deployed, awaiting acceptance | IMPLEMENTED BUT UNVERIFIED |
| Partial | PARTIALLY IMPLEMENTED |
| Missing | NOT IMPLEMENTED |
| Blocked by dependency | EXTERNAL DEPENDENCY BLOCKER |
| Blocked by approval | NOT IMPLEMENTED, waiting on a named owner decision |

The phase statuses are NOT STARTED, IN PROGRESS, COMPLETED, FAILED and BLOCKED.

## Phase status

| Phase | Status | Evidence or note |
| --- | --- | --- |
| 00 Discovery and baseline | COMPLETED | Phase 1 reverification (`d56e7ce`) |
| 01 Requirements and architecture | COMPLETED | Phase 1 matrix; Phase 2 plan; decisions A to J recorded (PR #239) |
| 02 Gap analysis | COMPLETED | Phase 2 plan, sections 4 and 5 |
| 03 Backend development | IN PROGRESS | See the work packages below |
| 04 PostgreSQL and data | IN PROGRESS | Done alongside each work package; additive migrations only |
| 05 Flutter | IN PROGRESS | Done alongside each work package |
| 06 Web and administration | IN PROGRESS | Done alongside each work package |
| 07 Security hardening | NOT STARTED | Run as a dedicated pass |
| 08 Infrastructure and DevSecOps | IN PROGRESS | 26 November: staging access used; v0.542.1 verified, migrated and deployed on all 16 services. Open: #271 to #275, D12-001 undeployed |
| 09 Completeness gate | NOT STARTED | Starts only when 03 to 06 are complete |
| 10 to 14 Testing, defects, regression, staging, acceptance | NOT STARTED | Starts only after the gate passes |

## Completed work packages (merged to `main`)

| Package | Requirement | PRs | Classification now | What still lacks evidence |
| --- | --- | --- | --- | --- |
| Phase 3 core completion: poster re-render, Creators and Content audit delivery, maintenance roles | D-P2-01, D11-007, D11-009 | #234, #235, #236 | IMPLEMENTED BUT UNVERIFIED | Staging deployment |
| Phase 4 Business | Business R1 scope | #238 | IMPLEMENTED BUT UNVERIFIED | Staging; the extensions blocked on DR-BZ decisions |
| G Identity step-up | DR-BZ-33 | #240, #241 (via #245) | IMPLEMENTED BUT UNVERIFIED | Staging |
| B Terms and privacy acceptance, separate marketing consent, policies page | RV2-02 | #243 (backend from #242), #244 | IMPLEMENTED BUT UNVERIFIED | Legal texts are drafts marked "pending legal review"; staging |
| A Re-review of published-video edits | RV2-01 | #246 backend, #247 app, #248 dashboard | IMPLEMENTED BUT UNVERIFIED | Staging; device UAT |
| F Creator warnings, restrictions, suspensions and appeals | D-8 (administrator only, the proposed answer) | #250 backend, #251 console, #252 app | IMPLEMENTED BUT UNVERIFIED | Staging; device UAT; visual approval of the app section. The no-measure Account status screen was seen working on the simulator on 26 November; applying a measure was not tried |
| E Copyright: verified rights holders and reviewer copyright signals | D11-008 | #254 backend and reviewer signals, #255 console page | IMPLEMENTED BUT UNVERIFIED | Staging; the copyright contact is still a placeholder; not exercised on the simulator |
| SIM-02 Sharing as app links only, store fallback, in-app error | Owner decision SIM-02 | #257 | IMPLEMENTED BUT UNVERIFIED | Native app-link association and device activation; staging |
| Simulator defects SIM-01, SIM-03 to SIM-10 | Simulator run, 26 November | This PR | IMPLEMENTED BUT UNVERIFIED | A repeat simulator or device run. SIM-03 changes copy only: trending stays empty until real engagement exists |

Local test evidence for package A, recorded on 25 November:
- Content 166 passed, Moderation 78, Gateway 233, Audit 52, console 184 and scripts 475.
- PostgreSQL: business 2 of 2, journeys 11 of 11, staging runtime PASS and event pipeline 8 of 8.
- Flutter: 1,860 passed.
- CI on `main` was green at `e01776a`.

Local test evidence for package F, recorded on 25 November:
- Creators 107 passed, Gateway 248, Audit 52, console 193 and scripts 480.
- PostgreSQL: business 2 of 2, journeys 11 of 11, staging runtime PASS and event pipeline 8 of 8.
- Flutter: 1,867 passed.
- CI was green on #250 (`f63ffec`) and #252 (`2ff5f23`).

What package F deliberately leaves out:
- Suspension does not unpublish existing videos; removal stays a moderation decision.
- Monetization is a capability flag only. Finance (J) will read it for future earnings.

## Remaining work, in order

1. ~~E Copyright workflow~~ merged in #254 and #255 (see above).
2. ~~Simulator-run defects~~: SIM-02 merged in #257; SIM-01 and SIM-03 to SIM-10 fixed in the app PR listed above.
2a. **Static policies and account-deletion request page** (owner ruling, 26 November; see below). Then point the app's policy, guidelines and help links at it.
3. **C Privacy processing and retention** (ADR-020). Retention periods are proposed only. Deletion must handle `LegalAcceptance` (`on_delete=PROTECT`).
4. **D Backups and observability**, repository side (ADR-016 in part, ADR-017).
5. **RV2-03 Dead letters.** The proposed values (retry ceiling 10, kept 14 days, administrator-only replay) are flagged as proposed.
6. **J Finance ledger**, sandbox only, followed by **H Events** and **I Advertising**. Check current Google documentation before building advertising. No invented payout thresholds, shares, exchange rates or tax rules.
7. Then Phase 07, Phase 08 (needs access and an approved plan), the Phase 09 gate and Phases 10 to 14.

**Still waiting on the owner:**
- DR-BZ-25: what happens to reviews and messages after a business closes.
- DR-BZ-08: how business ownership transfer works.
- RV2-04: media retention values.
- Legal review of the draft texts.
- Staging access and approval for any AWS, secret, database or RabbitMQ change.

## Owner rulings on 26 November 2026

- **SIM-02 sharing:** app deep links only, falling back to the store, with an in-app error otherwise. Implemented in #257.
- **Public web exception:** the owner chose a *static policies page plus an account-deletion request page*, and nothing else public. This narrows the 25 November "policies page only" exception. It is not a product website: there is no feed, playback, profile, registration or shop.
- **Why the deletion page is needed** (checked on the official pages, 26 November):
  - Google Play requires an in-app deletion path and a web resource outside the app where users can request account and data deletion. That resource is declared in the Data safety form.
  - Apple 5.1.1(v) requires deletion to start inside the app. 5.1.1(i) requires a privacy policy link in the app and in App Store Connect.
- **Distribution blocker:** until the page exists and its texts pass legal review, Android store distribution is blocked.

The remaining public-web dependency in the app is `PublicLinks` (`KOLOVIBE_PUBLIC_WEB_ORIGIN`, unset by default) in [`system_ui.dart`](../../../apps/mobile/lib/features/system/system_ui.dart). It must point only at that static page.

## Simulator application test (26 November 2026)

The app was built from `b907486` and driven on an iPhone 17 Pro simulator (iOS 26.3) against the repository's disposable local stack: TLS PostgreSQL, all nine services and the console, with no RabbitMQ, no Docker and no real R2. Counted by row: 33 PASS, 0 FAIL, 4 BLOCKED, 10 NOT RUN. Ten defects were found, nine Low and one Medium needing an owner decision. No crash occurred. Full table: [results](simulator-run-2026-11-26/results.md).

What it shows: the account lifecycle, discovery, likes, follows, reports, creator library and publish controls, settings and the Business invitation gate work end to end through the gateway. Playback, the upload transfer, processing, qualified views and points could not be observed, because they need R2, the media worker and RabbitMQ. This is local evidence only, not staging or device acceptance.

## Next executable task

**Staging first (26 November):** v0.542.1 is deployed; fix #275 so `main` can publish again, and decide #271 (Points key) and #274 (capacity) before #272 and #273.


Build the static policies and account-deletion request page (item 2a), then continue with decision C (privacy processing, ADR-020).
