# KoloVibe execution progress

> **Historical as of 27 November 2026 (after #299).** The owner's [full application mandate](../../governance/Full_Application_Mandate_2026-11-27.md) replaces the mandates this file tracked. Current status lives in the [phase execution tracker](../../governance/PHASE_EXECUTION_TRACKER.md), whose section 4.3 carries every unfinished item below into a new phase. This file is kept unchanged below as evidence.

**Read this file first when resuming.** Then check the repository state (`git log origin/main`, open PRs) before continuing. This tracker covers the owner's mandate "Complete application reverification, development completion, testing and final acceptance", in its 25 November 2026 form. The mandate was re-issued that day; this file continues the existing work and does not restart it.

Updated: 27 November 2026, `main` after #290. The owner re-issued the mandate on 27 November as "Remediation and Completion" (baseline `e82f43e`, after #277). This file continues under it. Staging runs **v0.542.1** on all 16 application services (owner update on #169, 26 November 17:55 UTC; [record](../../operations/R1_AWS_Staging_Verification_2026-11-26.md), with its 27 November update). **Production is NO-GO.** Nothing in this file is deployed to staging unless a row says so.

*History (superseded):* on 26 November, `main` was at `68d8df6`. The live staging was v0.531.1 with the v0.542.1 schema, the rollout was waiting for the registry token, and a first simulator test ran against a local stack ([results](simulator-run-2026-11-26/results.md)).

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
| 08 Infrastructure and DevSecOps | IN PROGRESS | v0.542.1 deployed on 26 November (#169). #275 closed by #277. Open: #271 (plan ready, #281), #272, #273, #274 (capacity report and budget proposal, #283), D13-005, #142 (ruleset plan, #279), #143 (OpenSSL exception renewed to 5 Dec, #284; FFmpeg rules retired, #286; main run 45951479515 at `dc55ab5` green on all image scans), D13-005 (read-back tool and reconciliation, #287/#288), D12-001 undeployed |
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
| Simulator defects SIM-01, SIM-03 to SIM-10 | Simulator run, 26 November | #258 | IMPLEMENTED BUT UNVERIFIED | A repeat simulator or device run (retest required; the original findings are historical). SIM-03 changes copy only: trending stays empty until real engagement exists |
| Static policies and account-deletion request page | Owner ruling, 26 November | #259 | IMPLEMENTED BUT UNVERIFIED | Hosting, and legal review of the texts |
| C Privacy: administrator review, holds, deactivation and erasure across all five services, completion and re-apply, console "waiting on" view | Decision C, ADR-020 | #260 to #268 (#262 merged into #263; #264 signs re-rendered posters) | IMPLEMENTED BUT UNVERIFIED | Staging needs the broker accounts, queues and `account_management` capability (approved plan). Not built: the access export (B3; 3.3a since built for Identity and Engagement, see Phase 3 below), Audit read-back after an Identity restore, and the completion notice. Retention periods (ADR-020), RV2-04, DR-BZ-08 and DR-BZ-25 keep categories retained, so requests stay `processing` |

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
2a. ~~Static policies and account-deletion request page~~ merged (see above). Pointing the app's links at the hosted page waits on hosting.
3. **C Privacy:** review, holds and erasure merged in #260 to #268. Still open: the access export (B3), the Audit read-back after a restore, the completion notice, and the staging broker plan. Retention periods are proposed only (ADR-020).
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

**27 November (Remediation mandate, Phase 1), as of `main` after #290:**

| Item | State | Evidence |
| --- | --- | --- |
| 1.1 #143 scan exceptions | OpenSSL renewed to 5 Dec on the owner's decision; FFmpeg rules retired | #280 and #282 (decision record), #284 (rules restored), #286 (FFmpeg retired); main run 45951479515 green on the shared, media and web image scans. Before 5 Dec: remove the rules once Alpine ships a fixed OpenSSL, or put a new decision to the owner |
| 1.2 #274 CPU budget | Package ready; NOT RUN on staging | #283 (capacity mode and budget proposal). Needs the owner's go for the 24-hour read-only measurement |
| 1.3 #271 Points to Audit key | Plan ready; NOT APPLIED | #281. Needs the owner's approval and the step-0 code PR |
| 1.4 #142 ruleset | Plan ready; NOT APPLIED | #279. Needs the owner's approval to apply it |
| 1.5 D13-005 release reconciliation | Tool and record merged; read-back NOT RUN on VM1 | #287 and #288 |
| 1.6 records | Largely done | #285, #289, #290; issues #136, #152 and #153 updated; DOC-207 ADR-016, ADR-017 and ADR-020 status aligned with Decisions C and D, and #133, #134, #138, #141 and #169 updated, in this change |

**Phase 2 (Audit delivery and alerting), 27 November:**

| Item | State | Evidence |
| --- | --- | --- |
| 2.1 #271 Points to Audit | Waits on the owner's approval of #281 | The plan above |
| 2.2 #272 Content and Creators audit delivery | Roles, zero-replica jobs and distinct key names in the repository; NOT DEPLOYED | `docs/operations/R1_Content_Creators_Audit_Delivery_Plan_2026-11-27.md`. Needs the CPU budget (#274) first, then the owner's approval. Recommends one Audit map roll together with #271 |
| 2.3 #145 Audit alerting | Signals IMPLEMENTED BUT UNVERIFIED; notification NOT IMPLEMENTED (platform and channel are owner decisions, OD-08) | `docs/operations/R1_Audit_Alert_Signals_2026-11-27.md`. Thresholds have no defaults and are owner decisions |

**Phase 3 (Privacy), 27 November:**

| Item | State | Evidence |
| --- | --- | --- |
| 3.1 #273 Erasure runtime wiring | Roles, zero-replica processes, erasure-only capability row and validator in the repository; NOT DEPLOYED. The real-broker pipeline script passed locally on disposable infrastructure | `docs/operations/R1_Erasure_Runtime_Plan_2026-11-27.md`. Needs the broker plan approved, the CPU budget and memory room. Business is not on staging, so requests there will wait on it |
| 3.2 Untracked media | Content erasure now signs DELETE and lists the account's own prefixes on R2, removing objects no row points at; `untracked_media` is reported only if a key cannot be deleted. Merged (#295) | Content suite; real-broker script 2 of 2. Whether the staging R2 token allows DELETE and List is NOT VERIFIED |
| 3.2 Retention policy | Which retained evidence is compatible with a completed request is read from an owner-approved policy file; with none, every retained category keeps the request `processing`. `business_ownership` and `untracked_media` can never be waived. Merged (#296) | Identity suite. No category is approved: values are the ADR-020 / RV2-04 / #136 owner decision |
| 3.3a Access export | Approve-access, Identity and Engagement assembly, retrieval by the account only (re-authenticated), expiry (410) and purge, console state, audit. Merged (#297) | Identity 233, Engagement 85, Gateway 272, Audit 52, Content 183, console 208 and scripts 506 passed; real-broker script 3 of 3 (export part over the broker), 27 November, at the PR head. The retrieval window is an owner decision with no default. Creators, Moderation, Content and Business parts are NOT IMPLEMENTED (3.3b), so real exports wait on them. The app download screen is NOT IMPLEMENTED (3.3c) |

| 3.3b Export parts | Creators, Moderation, Content and Business assemble their parts; Moderation and Content are asked after Creators, with the profile id. Categories whose visibility is undecided are withheld by name. Merged (#298) | Identity 234, Engagement 85, Creators 119, Moderation 96, Content 186, Business 244, Gateway 273, Audit 52, console 208 and scripts 506 passed; real-broker script 3 of 3 (all six parts, completion and retrieval over the broker), 27 November, at the PR head. Business is not on staging, so exports there wait on it. The app download screen is NOT IMPLEMENTED (3.3c) |

| 3.3c App export view | "View my data" on a completed access request: fresh identity check, in-memory view by service and category, explicit copy only; expired and unready answers explained. PR open | Flutter 1,888 tests passed and `flutter analyze` clean, 27 November, at the PR head. Device UAT NOT RUN. Saving as a file is NOT IMPLEMENTED |

| 3.4 Restore-safe recovery | Audit answers Identity alone (signed, least-privilege path) with the two facts it holds: which accounts an approved deletion deactivated and which an erasure completed for. `recover_erasures_from_audit` re-applies them after a restore: signs the account out, deactivates it, de-identifies a completed erasure again, and puts a restored waiting deletion request back in `processing` with every service asked again; it never marks a request completed and prints counts only. `--dry-run`. Runbook "Restoring Identity's own database" added. PR open | Identity 240, Audit 55, Gateway 273 and scripts 506 passed; restore drill `scripts/test_erasure_restore_drill.py` passed on disposable TLS PostgreSQL, 27 November: pg_dump of the identity schema, real approval and completion, Audit ingest, pg_restore (the erased person came back), recovery (erased again), second run unchanged. The Identity to Audit HTTP hop is replaced by files in the drill (labelled). The recovery contract is PROPOSED and needs owner approval before first use. Staging restore NOT RUN |

Next: 3.5 (lifecycle execution, configurable; the completion notice is an owner decision), then the owner-gated steps above.

*History (superseded, 27 November before 3.4):* "Next: 3.4 restore-safe recovery and 3.5, then the owner-gated steps above."

*History (superseded, 27 November before 3.3c):* "Next: 3.3c, then 3.4 restore-safe recovery and 3.5, then the owner-gated steps above."

*History (superseded, 27 November before 3.3b):* "Next: 3.3b and 3.3c, then 3.4 restore-safe recovery and 3.5, then the owner-gated steps above."

*History (superseded, 27 November before #295/#296):* "Next: 3.2 retained categories, then the owner-gated steps above."

*History (superseded, 27 November before #284):* "1.1 #143: merge #284 …; 1.2 #274: the read-only measurement, then the budget; 1.3 #271: the key correction, once approved; 1.4 #142: apply the ruleset, once approved; 1.5 D13-005: reconcile the release; 1.6: the remaining record corrections."

*History (superseded):* the 26 November instruction read: "the operator runs the prepared v0.542.1 rollout …, then fix #275 …; build the static policies and account-deletion request page (item 2a), then continue with decision C." The rollout, #275, the page (#259) and the privacy slices #260 to #268 are done.
