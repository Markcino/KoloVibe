# Phase 1 full-product scope baseline (Task 2)

**Established 27 November 2026 at `1c706ce`.** This records the reconciled scope. Requirements per area are indexed in [FP-000](../../requirements/FP-000_Full_Product_Requirements_Baseline.md); approvals in the [governance gate register](PHASE-01_Governance_Gate_Register.md).

## 1. Sources reconciled

DEC-001 (Release 1 scope); PRD and SRS v0.2; Decisions A to J and the rulings of 25 and 26 November; the Business approval record; the Events, Advertising and Finance decision documents; DOC-207 ADRs and DOC-209 open decisions; the standing principal engineering directive; the full application mandate of 27 November.

## 2. MVP-only restrictions removed from active planning

| Restriction | Where it was | Now |
| --- | --- | --- |
| Release 1 is the delivery boundary; Business (R2), ticketing (R3), revenue pool and payouts (R4) deferred | DEC-001; PRD v0.2 PRD-F12 to PRD-F14; go-live readiness; seven-stage plan | Removed. All are in the development baseline (FP-BZ, FP-EV, FP-FN) |
| "Do not implement deferred features" | Agent instructions | Removed (#302, #303) |
| Goal is a controlled pilot; Stage 6 pilot issues define go-live | Go-live readiness; issues #163, #167, #168 | The goal is a production-ready full product. A staged rollout may still be used and #163 and #167 are kept as Phase 11 rollout work, not as the end goal |
| Advertising limited to AdMob/AdSense test placements, "Should" priority | PRD-F11 | Advertising, direct sponsorship and Google mobile ads are in the baseline (FP-AD, FP-GA) |
| Eight Django services | Earlier copilot instructions, SRS | Twelve expected services; nine built (section 4) |
| R1 status vocabulary and Stage 1 to 6 milestones | EXECUTION_PROGRESS, GitHub milestones | One vocabulary in the tracker; Phase 2 to 11 milestones |

The restrictions that **remain** are not MVP restrictions and are unchanged: live streaming excluded, no public website beyond the approved static resources, points never money, one Finance ledger, no live money or ads without separate approval, no merge, deploy or infrastructure change without approval, production NO-GO.

## 3. Full-product development baseline

The 18 capability areas of the mandate are in scope. Their requirement sets and status are in FP-000 section 2, and each feature is a row in the [traceability matrix](PHASE-01_Feature_Traceability_Matrix.csv). The matrix has 71 rows: 24 Ready for comprehensive testing, 6 Development complete, 13 Partial, 14 Missing, 11 Blocked by approval, 1 Defective, 2 Explicitly excluded. These are counts of matrix rows, not a completion percentage; rows differ greatly in size.

## 4. Service boundaries

| Mandate service | State | Boundary check |
| --- | --- | --- |
| Gateway, Identity, Creators, Content, Engagement, Points, Moderation, Audit | Built | Own schema, role and signing keys each; Gateway stateless; matches the approved architecture |
| Business | Built, not on staging | Own schema; membership authority; matches the approved Business ADR |
| Finance, Events, Advertising | Missing | PROPOSED ADRs exist; structural approval needed (GD-01, GD-02) |
| Notifications (capability, not in the twelve) | Missing | Recommended inside Identity as a separate process (GD-03); no 13th service unless the owner chooses it |
| Console (`apps/web_django`), media worker, static policies (`apps/policies`) | Built | Not services in the twelve: the console is the privileged client, the media worker is Content's process, the policy pages are static files |

## 5. Features that genuinely need a product decision

| Feature | Why a decision is needed | Recommendation |
| --- | --- | --- |
| Comments (GD-07, #135) | Not in any requirement set; adds moderation load | Decide explicitly before Phase 3 |
| Notifications channels and placement (GD-03) | Named in the mandate with no requirements | Identity-owned module; FP-NT requirements |
| Payment provider and payout provider (GD-20) | Provider choice, coverage in Liberia, KYC | Provider-neutral interface first |
| Google mobile ads products (DR-AD-36) | Must follow current Google policy | Test mode only until approved |
| Live streaming | Excluded by the directive | Stays excluded |
| Direct messaging between viewers and creators | Not requested anywhere; only Business inquiries exist | Not added. Listed so it is not built silently |
| Event images and ad creatives (GD-05) | No image pipeline | Extend Content's media path |

Nothing outside this list is added to the baseline.
