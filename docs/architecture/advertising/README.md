# Advertising and sponsorship — Phase 8A design package

**Status: PROPOSED — not approved.** 25 November 2026. Design and decision stage that must precede Phase 8 implementation, mirroring Business 6A and Events 7A. **Documents only: no code, migration, flag, SDK, AWS or staging change.** Advertising is still "later" in the approved PRD, test-ads-only in FR-020, and "Missing; Blocked by approval" in tracker row B-19; [DR-AD-01](AD-Owner_Decisions_Required_PHASE8A.md) asks the owner to reconcile that. Production is NO-GO. No real money is charged and no provider approval is promised.

## Deliverables

| # | Deliverable | File |
| --- | --- | --- |
| 1 | **Exact owner decisions required** | [AD-Owner_Decisions_Required_PHASE8A.md](AD-Owner_Decisions_Required_PHASE8A.md) |
| 2 | Advertising requirements | [AD-Requirements_PRD_SRS_PROPOSED.md](../../requirements/AD-Requirements_PRD_SRS_PROPOSED.md) |
| 3 | Architecture decision | [ADR-AD-001](../../adr/ADR-AD-001_Advertising_Bounded_Context_PROPOSED.md) |
| 4 | Campaign authorization model and matrix | [AD-Authorization_Model_and_Matrix_PROPOSED.md](../../security/phase8/AD-Authorization_Model_and_Matrix_PROPOSED.md) |
| 5 | Database models and state machines | [AD-ERD_and_State_Machines_PROPOSED.md](AD-ERD_and_State_Machines_PROPOSED.md) |
| 6 | API contracts | [AD-API_Contract_PROPOSED.md](AD-API_Contract_PROPOSED.md) |
| 7 | Creative review, placement, impression and click verification, anti-fraud, consent and privacy, billing and reporting policies | [AD-Policies_PROPOSED.md](AD-Policies_PROPOSED.md) |
| 8 | Third-party provider constraints (AdMob/AdSense and similar) | [AD-Third_Party_Provider_Constraints_PROPOSED.md](AD-Third_Party_Provider_Constraints_PROPOSED.md) |
| 9 | STRIDE threat model | [AD-STRIDE_Threat_Model_PROPOSED.md](../../security/phase8/AD-STRIDE_Threat_Model_PROPOSED.md) |
| 10 | Acceptance criteria, slice and PR plan, blockers | [AD-Acceptance_and_Delivery_Plan_PROPOSED.md](../../engineering/phase8/AD-Acceptance_and_Delivery_Plan_PROPOSED.md) |

## Reading order for the approver

0. [Owner decisions required](AD-Owner_Decisions_Required_PHASE8A.md), 1. [ADR-AD-001](../../adr/ADR-AD-001_Advertising_Bounded_Context_PROPOSED.md), 2. [Policies](AD-Policies_PROPOSED.md), 3. [Provider constraints](AD-Third_Party_Provider_Constraints_PROPOSED.md), then the rest as reference.

## Key design points

A new `ads` service with advertiser membership authorization (no Identity role). Ads are served by the platform from reviewed, immutable, text-only creatives first; media waits for the shared image pipeline. A client report is a claim: billing needs a server-issued decision, a plausible report, invalid-traffic filtering and a hold window, and only a finalizer writes append-only billable events. Spend cannot exceed budget (reserve-then-settle). Ad events cannot reach Points or Engagement by construction. Consent is enforced at the edge and fails closed until Identity owns a consent record. Billing is sandbox-only facts with no ledger and no charge path; a future real charge posts to the single platform ledger. No network SDK, no advertiser portal, no website.

## What I found that the owner should know

1. **No consent record exists anywhere** (PRD-F09 requires them), so ad delivery and measurement cannot be enabled until Identity gains one.
2. **Phase 7's single-ledger decision (DR-EV-03) conflicts with Ads** unless the ledger is extractable; DR-AD-03 asks to settle it once for both.
3. **AdMob eligibility and payouts for Liberia are unverified**, `app-ads.txt` implies a developer website that DR-BZ-21 forbids, and AdSense is web-only.
4. **Three new services** (Business, Events, Ads) on an unmeasured two-VM stack is a capacity question for the owner (DR-AD-05).
