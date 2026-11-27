# Revenue accounting, sharing and sandbox payouts (Phase 9) — exact owner decisions and approvals required

## Current reconciliation — 27 November 2026

This table records existing approvals, not new owner choices. [Phase 1 gate register](../../governance/phase1/PHASE-01_Governance_Gate_Register.md) and [Decisions A to J](../../planning/Owner_Decisions_A-J_2026-11-25.md) remain the approval evidence; current ADR headers and DOC-205 govern over conflicting proposals below.

| Decision | Current ruling | Remaining gate |
| --- | --- | --- |
| DR-FIN-01/02 | Scope and Finance single-ledger ownership approved by J/GD-01; providers Finance-owned by FP-PAY | Detailed contract review; no live activation |
| DR-FIN-03 | GD-01 approved double-entry/append-only/hash-chain/minor-unit sandbox structure | Independent posting/template/rounding review remains required |
| DR-FIN-05/06 | GD-04 approves grants and maker/checker/releaser structure; G approves centralized step-up | Exact grant/control matrix and deployment capacity/security evidence still need review |
| DR-FIN-07 | Sandbox-only development approved; no live activation | Live approval remains absent |
| DR-FIN-04 | Owner named Mark Allen Gbalazeh as accounting-review contact in the current task | Actual qualified independent review and signed findings NOT RUN; assignment alone does not satisfy independence |
| DR-FIN-08 and financial/legal/provider values | No new value approval inferred | Remain pending in their original rows |

## Historical proposal and still-open policy rows

**Status: request for owner decisions, 25 November 2026. Every item is OPEN. Nothing here is approved.** Accountable owner: Mark Allen Gbalazeh (@Markcino). Record answers with the Business template ([decision record template](../business/BIZ-Owner_Decision_Register_PROPOSED.md#decision-record-template-use-when-the-owner-decides)).

**Read this first.**

1. **F1 requires approval of the accounting design before implementation.** This package is that design. Nothing was built: no code, migration, flag, AWS or staging change, and no provider contacted.
2. **No financial value is proposed anywhere in this package.** Pool share, reserve, revenue-sharing percentage, commission, pay-per-view rate, minimum payout, schedule, settlement period, close lag, hold period, clawback window, fee and tax are all **unset policy parameters**. The design makes the engine *refuse to calculate* until an approved, versioned policy supplies each one ([accounting design §5](FIN-Accounting_Design_PROPOSED.md#5-policy-versions-and-the-allocation-engine)). Where a decision row says "you supply", that is literal.
3. **Points are not money.** The Points ledger is non-cash (ADR-009, DEC-003, "no cash equivalence"). Finance has no read path to Points data, never converts it, and a static test fails the build if it tries. The approved documents already say so: BR-011 (monetary ledger separate from engagement and points, double-entry, reconciliation), BR-010 (pool from actual reconciled collected revenue, not estimated impressions), BR-012 (no cash disbursement until provider, legal, fraud, approval and security gates pass), DOC-004 (two distinct approvers for payout release, no self-approval).
4. **Live money is out of scope.** Books are `sandbox` or `live`; a `live` book cannot be opened without an approval constant naming the owner decision. Live financial acceptance and activation are separately authorized.
5. **This package resolves a conflict between earlier packages.** Phase 7 proposed the money ledger inside Events (DR-EV-03) and Phase 8 left Ads billing facts open (DR-AD-03). Both are *unapproved*; both can be answered by DR-FIN-02 below, and the amendments are listed in the [delivery plan](../../engineering/phase9/FIN-Acceptance_Correctness_and_Delivery_Plan_PROPOSED.md#6-amendments-to-the-phase-7-and-8-packages-if-dr-fin-02-is-approved).

**Not asked again (inherited):** ADR-009, ADR-010 (financial separation), DR-BZ-21 (Flutter for payees; console for administrators and moderators only; no payee web portal), FR-016 (ad interaction earns nothing), PRD "no guarantee of fixed dollars per view".

## How to answer

Each row gives a recommendation where the *design* can recommend (structure, controls). Rows marked **Supply** need a **number, list or legal fact only you, finance and legal can provide**; the recommendation is that the value stays unset until then.

## Gate G — architecture, controls and governance

| # | Decision | Recommendation | Why it matters |
| --- | --- | --- | --- |
| DR-FIN-01 | **Scope reconciliation.** Approve developing R4 revenue accounting, sharing and *sandbox* payouts now: closed flags, sandbox books only. Raise the DOC-023 change request moving PRD-F14, DOC-022, BR-010 to 012 and DEC-001 wording from "Deferred" to "approved for development, not release"; note the R1 SRS statement that the console excludes payouts and points execution is superseded for the finance pages only | Approve. Production NO-GO | Registers must not contradict the work |
| DR-FIN-02 | **Financial bounded context and ledger ownership.** A new `finance` service owns the **one** double-entry ledger. Events and Ads keep operational state (orders, invoices) and emit **signed business events**; they hold no ledger and no balances. Finance never reads their tables | Approve. This is the answer to DR-EV-03 and DR-AD-03 | "One approved accounting source of truth"; no ledger logic in Events, Ads or Points |
| DR-FIN-03 | **Accounting method.** Double-entry, append-only, hash-chained journals; money as integer minor units after explicit decimal calculation; no stored mutable balances; reversals by contra-journal; closed periods immutable (corrections post in a later period with a reference) | Approve | Core correctness |
| DR-FIN-04 | **Independent accounting approver.** Name the qualified independent person or firm who signs off the chart of accounts, recognition rules, posting templates and each policy version | **Supply.** Design cannot be approved by the author. Until named, no policy version can reach `approved` in a live book | The instruction requires an "independently approved financial policy" |
| DR-FIN-05 | **Control model (separation of duties).** Maker-checker-releaser with mutually exclusive grants; the matrix in the [control model](../../security/phase9/FIN-Control_Model_and_Authorization_Matrix_PROPOSED.md) | Approve the matrix as written; it is the "explicitly approved control model" the instruction requires. Without approval no one may both create and approve, or approve and release, the same transaction | Core control |
| DR-FIN-06 | **Authority and shared prerequisites.** Finance authority is Finance-owned **grants**, not new Identity roles, held only by named administrator accounts under MFA; payee identity is the platform account. Shared prerequisites answered once: Identity step-up (DR-EV-05), database ownership model (DR-EV-06), capacity (DR-EV-07), broker vhost and queue for Finance | Approve. Until step-up exists, grant changes, destination changes, policy approval, payout release and freeze-lift fail closed | Several controls depend on step-up |
| DR-FIN-07 | **Environment guard.** Ledger books are `sandbox` or `live`; data never moves between them; `live` cannot be created without a named approval constant; sandbox fixtures can never be approved as live policy | Approve | Prevents accidental real money |
| DR-FIN-08 | **Audit integrity anchoring and retention.** Daily signed digest of each ledger and audit chain stored outside the Finance database (for example an immutable external store); retention periods | Approve the mechanism; **Supply** the retention period (legal, ADR-020, DR-EV-30) | Hash chains alone do not defeat a database owner |

## Gate A — financial policy (all parameters are Supply; none has a recommended value)

| # | Decision | What the owner and finance must supply | Notes |
| --- | --- | --- | --- |
| DR-FIN-10 | **Currencies and conversion** | Currencies accepted; whether any conversion exists; rate source and date rule | Recommended default: **no conversion**; allocate and pay within the currency of the revenue; legal input on collectable currencies (DR-EV-20, DR-AD-21) |
| DR-FIN-11 | **Revenue source classes and which are shareable** | For each class (network ad revenue, direct-sold ad revenue, sponsorship, ticket platform fees, other): shareable yes or no | **Ticket face value is a liability to the organizer and is never shareable**; the design enforces that. Everything else is your decision |
| DR-FIN-12 | **Recognition and shareability rules** | When revenue is *recognized* (accounting) and when it becomes *shareable* | Approved principle already: shareable only when **collected and reconciled** (BR-010); you supply any lag, clawback window and dispute holdback |
| DR-FIN-13 | **Allocation periods** | Period type, close lag, who may close | Structure: periods are policy-defined, closed once, never reopened |
| DR-FIN-14 | **Pool formation** | How shareable revenue becomes a distributable pool: share, reserve, cost deductions | **Supply**; "revenue-sharing percentage only after collected revenue, costs, reserves and legal review" (DOC-006) |
| DR-FIN-15 | **Allocation basis** | What measurable, finalized quantity divides the pool among payees | Options for you: (a) finalized qualified-view counts per creator (an Engagement-owned, period-final dataset, **never Points**), (b) finalized watch time, (c) equal share among eligible payees, (d) a campaign or sponsorship attribution rule. Each is a *basis provider* with a version. The design does not choose |
| DR-FIN-16 | **Eligible creator and business definitions** | Status conditions (for example active, not restricted), identity and rights evidence, age, jurisdiction | Eligibility is a signed snapshot from Creators or Business, recorded in each run; Finance does not read their tables |
| DR-FIN-17 | **Holds** | Hold period for new allocations; reasons for withholding; appeal window | Structure supports policy hold, fraud hold, eligibility hold, destination hold |
| DR-FIN-18 | **Payout rules** | Minimum threshold, schedule, who bears provider fees, retry and return handling | **Supply**; none invented |
| DR-FIN-19 | **Payee onboarding** | Payout destination verification, identity (KYC), AML and sanctions screening, tax and withholding | **Legal blocker**; nothing here assumes Liberian rules |
| DR-FIN-20 | **Adjustments and clawbacks** | Allowed reasons, evidence, what happens after payout (negative balance, offset against future allocations, write-off) | Structure: always two approvers, reason code, evidence reference; **Supply** the clawback policy |
| DR-FIN-21 | **Creator disputes** | Window, adjudicator, outcomes, time limit | Recommended structure: finance reviewer ≠ the person who prepared the contested item |
| DR-FIN-22 | **Statements** | Content, issuing schedule, legal wording, retention | In-app only; no emailed or downloadable-link statement unless you decide (DR-BZ-28 position) |

## Gate B — providers (interfaces only; nothing live)

| # | Decision | Recommendation |
| --- | --- | --- |
| DR-FIN-30 | **Revenue-source providers** (ad network statements, direct-ad invoices, ticket captures, bank statements) | Build the `RevenueStatementSource` interface and sandbox sources; no real connection. Real sources need their own approval (for AdMob see [provider constraints](../advertising/AD-Third_Party_Provider_Constraints_PROPOSED.md)) |
| DR-FIN-31 | **Payout provider** | **Blocker, not decided here.** Build the `PayoutProvider` interface and a sandbox adapter with failure injection. A real provider needs due diligence, Liberia coverage, legal review, security review and a separate approval. Provider approval is not promised |

## Gate C — clients and operations

| # | Decision | Recommendation |
| --- | --- | --- |
| DR-FIN-40 | **Flutter designs and route space.** Reserve **M-300 and up** (Phase 7 uses M-145+, Phase 8 M-200+). About 20 screens in a separate Finance section; strong visual and wording separation from Points; Money type with no floating point | Approve per slice |
| DR-FIN-41 | **Console pages and grants.** Grants: `fin_preparer`, `fin_approver`, `fin_releaser`, `fin_reconciler`, `fin_policy_author`, `fin_policy_approver`, `fin_auditor`, `fin_fraud` | Approve; grant changes need two administrators |
| DR-FIN-42 | **Notifications** | None; in-app status only (no delivery provider exists) |

## Required approvals and sign-offs (completion deliverable)

| Approval | By | Needed before |
| --- | --- | --- |
| Accounting design (this package, DR-FIN-02, 03, 05, 07) | Owner **and** independent accountant (DR-FIN-04) | any implementation |
| Each financial policy version | Policy author ≠ policy approver, plus independent accountant evidence | any calculation in a live book; sandbox calculations use clearly labelled fixtures only |
| Control model and grant holders | Owner | any financial write |
| Legal: tax, withholding, KYC/AML, data protection, retention | Legal adviser | live payouts and statements |
| Provider due diligence and security review | Owner, security lead | any real provider |
| Independent security test | Independent tester | live activation |
| Live financial acceptance | Owner | live activation (separate authorization) |

## What each slice needs before it can start

| Slice | Needs decided | Can be built without |
| --- | --- | --- |
| F0 Skeleton and wiring | DR-FIN-01, 02, 06, 07 | any policy |
| F2 Revenue records | F0, DR-FIN-03, 04, 10 to 12, 30 | allocation, payouts |
| F3 Revenue sharing | F2, DR-FIN-13 to 17, 20, 22 | payouts, providers |
| F4 Creator experience | F3 data, DR-FIN-40, 42 (21 and 22 for disputes and statements) | payout execution |
| F5 Sandbox payouts | F3, DR-FIN-05, 18, 19 (structure), 31 (interface) | **any real provider** |
| F6 Console | one slice at a time, DR-FIN-41 | — |

## Minimum to start

Approve DR-FIN-01, 02, 03, 05, 06, 07 and name the independent accountant (04). That unlocks F0 and the ledger core. Policy rows (10 to 22) can wait until F2 and F3 start, but **no allocation run is possible without them**, and the engine will say so.

## Not requested

No real money, provider, payout, tax filing or bank connection; no conversion of Points; no change to Points, Engagement, Creators, Business, Events or Ads except the additive items listed in the plan (business-event emitters, a finalized-basis read, an eligibility snapshot read, an Audit producer).
