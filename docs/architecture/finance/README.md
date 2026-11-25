# Revenue accounting, sharing and sandbox payouts (R4) — Phase 9A design package

**Status: PROPOSED — not approved.** 25 November 2026. F1 requires the accounting design to be approved before implementation; this package is that design. **Documents only: no code, migration, flag, AWS or staging change; no provider contacted; no real money.** Revenue sharing and payouts are R4 and still deferred in the approved records (PRD-F14, DOC-022, DEC-001); [DR-FIN-01](FIN-Owner_Decisions_Required_PHASE9A.md) asks the owner to reconcile that. Production NO-GO. **No financial value is proposed anywhere**: every rate, share, reserve, threshold, period and window is an unset policy parameter that the engine refuses to calculate without.

## Deliverables

| # | Deliverable | File |
| --- | --- | --- |
| 1 | **Owner decisions and approvals required** | [FIN-Owner_Decisions_Required_PHASE9A.md](FIN-Owner_Decisions_Required_PHASE9A.md) |
| 2 | Requirements | [FIN-Requirements_PRD_SRS_PROPOSED.md](../../requirements/FIN-Requirements_PRD_SRS_PROPOSED.md) |
| 3 | Architecture decision (bounded context, single ledger, events) | [ADR-FIN-001](../../adr/ADR-FIN-001_Financial_Bounded_Context_and_Ledger_PROPOSED.md) |
| 4 | **Accounting design** (chart of accounts, currency and decimals, recognition, policy versions, allocation engine, posting templates, lifecycles, reconciliation, provider interfaces, audit controls) | [FIN-Accounting_Design_PROPOSED.md](FIN-Accounting_Design_PROPOSED.md) |
| 5 | ERD and state machines | [FIN-ERD_and_State_Machines_PROPOSED.md](FIN-ERD_and_State_Machines_PROPOSED.md) |
| 6 | API and event contracts | [FIN-API_Contract_PROPOSED.md](FIN-API_Contract_PROPOSED.md) |
| 7 | **Control model and authorization matrix** (separation of duties) | [FIN-Control_Model_and_Authorization_Matrix_PROPOSED.md](../../security/phase9/FIN-Control_Model_and_Authorization_Matrix_PROPOSED.md) |
| 8 | STRIDE threat model | [FIN-STRIDE_Threat_Model_PROPOSED.md](../../security/phase9/FIN-STRIDE_Threat_Model_PROPOSED.md) |
| 9 | **Accounting correctness specification**, acceptance criteria, slice plan, implementation matrix, amendments, blockers | [FIN-Acceptance_Correctness_and_Delivery_Plan_PROPOSED.md](../../engineering/phase9/FIN-Acceptance_Correctness_and_Delivery_Plan_PROPOSED.md) |

## Reading order for the approver

0. [Owner decisions required](FIN-Owner_Decisions_Required_PHASE9A.md), 1. [ADR-FIN-001](../../adr/ADR-FIN-001_Financial_Bounded_Context_and_Ledger_PROPOSED.md), 2. [Accounting design](FIN-Accounting_Design_PROPOSED.md) (for the independent accountant), 3. [Control model](../../security/phase9/FIN-Control_Model_and_Authorization_Matrix_PROPOSED.md), then the rest as reference.

## Key design points

A `finance` service owns the **one** double-entry, append-only, hash-chained ledger; Events, Ads and Points hold none, and producers integrate only by signed business events through an idempotent inbox (the existing outbox/inbox pattern). Money is exact: integer minor units after `Decimal` calculation with a policy-supplied rounding rule; no floats. Every rule value comes from an immutable, independently approved policy version; allocations are deterministic (re-run gives the same hash), conserve the pool exactly and record the policy hashes used. Points are not an input, not a basis and not convertible; a static test enforces it both ways. Separation of duties is mechanical: mutually exclusive grants, distinct accounts per transaction, two approvers for adjustments and payouts, a different releaser, approvals bound to content hashes, no break-glass. Payouts run only against a sandbox provider with failure injection; `live` books and real adapters are refused by guards.

## What the owner should know

1. **I could not and did not choose any financial parameter.** The design is complete without them, and the engine says `parameter_not_approved` until an approved policy supplies each one.
2. **An independent accountant must sign the design** (DR-FIN-04); the author cannot approve it.
3. **This resolves the ledger question** left open by Phase 7 (DR-EV-03) and Phase 8 (DR-AD-03); the amendment list is in the plan.
4. **No correctness report, test evidence or sandbox results exist yet** because nothing is implemented; the plan specifies exactly what they will show (22 invariants, 23 acceptance criteria).
5. **Allocation inputs need additive changes in three other services** (a period-final basis, eligibility snapshots, event emitters), each needing approval.
