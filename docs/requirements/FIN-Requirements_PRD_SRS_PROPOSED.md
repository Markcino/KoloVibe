# Revenue accounting, sharing and sandbox payouts — requirements (proposed)

**Status: PROPOSED — not approved.** 25 November 2026. Proposed content for PRD-F14 and DOC-022. Development-only, sandbox books, closed flags, production NO-GO ([DR-FIN-01](../architecture/finance/FIN-Owner_Decisions_Required_PHASE9A.md)). Priority: **M** must, **P** needs an approved policy value (unset in this design), **B** blocked.

## 1. Scope

**In:** the Finance ledger; verified revenue records and reconciliation; versioned financial policies; deterministic period allocations with holds, reversals and adjustments; eligibility review; statements; Flutter payee screens; sandbox payout workflow with providers behind interfaces; console administration with separation of duties; financial audit.

**Out:** real money, real providers, bank connections, tax filing; conversion of Points to money or any use of Points as an input; any invented rate, share, threshold, schedule or period; payee web portal; emailed statements; live acceptance (separately authorized); automated payout without human approvals.

## 2. Definitions

| Term | Meaning |
| --- | --- |
| Payee | A creator or business account eligible under an approved definition to receive allocations |
| Revenue record | A verified fact of money owed or received from a classified source, with a provider reference |
| Shareable revenue | Recognized, collected, reconciled, class-flagged and past the clawback window (accounting design §4) |
| Policy version | An immutable, approved, versioned parameter document |
| Allocation run | A deterministic computation for one period, policy and input snapshot |
| Allocation | A payee's share from a run, split into released and held portions |
| Payout | A request to move a payee's released payable to a destination through a provider |
| Sandbox book | A ledger whose money is simulated; never promotable to live |

## 3. Functional requirements

### F1 Financial architecture

| ID | Requirement | Pri |
| --- | --- | --- |
| FN-R-001 | One Finance service owns the only monetary ledger; Events, Ads, Points hold none | M |
| FN-R-002 | Double-entry journals; debits equal credits per currency; enforced in database and code | M |
| FN-R-003 | Append-only ledger and history tables; reversals by contra-journal; no update or delete path | M |
| FN-R-004 | Balances derived from postings; any projection proven equal by a verifier | M |
| FN-R-005 | ISO 4217 currency on every account, journal and posting; no implicit conversion; mixed-currency postings refused | M |
| FN-R-006 | Money is exact: integer minor units stored, decimal arithmetic with an explicit rounding rule from policy, no floating point in any financial path (static check) | M |
| FN-R-007 | Revenue source classes with owner-approved shareability flags; ticket face value is never shareable | M/P |
| FN-R-008 | Books are `sandbox` or `live`; a live book cannot be opened without an approval constant | M |
| FN-R-009 | Producers integrate only through signed business events (allowlist of source and kind) and provider interfaces; no cross-service table access | M |
| FN-R-010 | Every command and event is idempotent at its layer (accounting design §7) | M |
| FN-R-011 | Financial audit: hash-chained, attributed, externally anchored daily, id-only copy to Audit | M |
| FN-R-012 | Contracts, ERD, STRIDE and policy decisions approved before implementation | M |

### F2 Revenue records

| ID | Requirement | Pri |
| --- | --- | --- |
| FN-R-020 | A revenue record exists only from a verified source line or a signed business event, with a provider reference | M |
| FN-R-021 | Duplicate prevention: unique `(source, provider_reference)`; a repeat is a no-op or a duplicate exception, never a second posting | M |
| FN-R-022 | Recognition follows the policy's recognition rule per class; no recognition from estimates, impressions or unfinalized records | M/P |
| FN-R-023 | Collected and reconciled states require matching cash and source statements | M |
| FN-R-024 | Three-way reconciliation per source and period; differences become exceptions; never auto-corrected | M |
| FN-R-025 | Corrections only by approved adjustment, write-off or contra-journal; closed periods never edited | M |
| FN-R-026 | Manual revenue entry by a preparer needs an approver and a unique reference | M |
| FN-R-027 | Immutable accounting history viewable per record and per account | M |

### F3 Revenue sharing

| ID | Requirement | Pri |
| --- | --- | --- |
| FN-R-030 | Policy versions are immutable, versioned, approved by someone other than the author with independent evidence, effective prospectively | M |
| FN-R-031 | Every policy parameter is required and has no default; calculation refuses with `parameter_not_approved` | M |
| FN-R-032 | Eligible creator and business definitions are policy objects; eligibility is a signed snapshot recorded in each run | M/P |
| FN-R-033 | Allocation uses only shareable revenue up to a recorded ledger cut-off and a period-final basis dataset; never the Points ledger | M |
| FN-R-034 | Calculation is deterministic: same inputs give the same `run_hash`; conservation: allocations sum exactly to the distributable amount per currency | M |
| FN-R-035 | Period-based: periods are policy-defined, closed once, never reopened; late items flow to a later period with a reference | M/P |
| FN-R-036 | Held and withheld allocations carry reason codes (policy, fraud, eligibility, destination) and are released only by approval | M |
| FN-R-037 | Reversal and adjustment handling by correction run and adjustment path | M |
| FN-R-038 | Eligibility review workflow for payees under restriction, suspension or evidence gaps | M |
| FN-R-039 | Statements are generated from the ledger and reproduce its totals; versioned and immutable once issued | M |
| FN-R-040 | The calculation, not an operator, determines amounts; an operator can only approve or reject a run, never edit its figures | M |

### F4 Creator financial experience (Flutter)

| ID | Requirement | Pri |
| --- | --- | --- |
| FN-R-050 | Screens: earnings overview, revenue history, allocation details, pending and settled states, statements, payout eligibility, payout request, failure and dispute states | M |
| FN-R-051 | The Finance section is separate from Points: separate navigation entry, tokens and wording; no Points figure, term or link on any Finance screen and no Finance figure on a Points screen; an explicit "Points are not money" notice | M |
| FN-R-052 | The client shows server state and decimal-string amounts through an integer-backed `Money` type; no `double` for money | M |
| FN-R-053 | Payee endpoints take no payee id; a payee sees only their own data | M |
| FN-R-054 | The app never states a rate, share, guarantee or schedule that is not in the approved policy version it displays, and never promises payment | M |
| FN-R-055 | Payout request offered only when the server says the payee is eligible; destination entry and change need step-up and (sandbox) verification | M/B |
| FN-R-056 | Dispute opening and status for an allocation or statement | M/P |

### F5 Sandbox payouts

| ID | Requirement | Pri |
| --- | --- | --- |
| FN-R-060 | Payout request → eligibility check → two distinct approvals → release by a third account → provider call → settlement or failure | M |
| FN-R-061 | Payout cannot exceed the payee's released payable; concurrent requests cannot together exceed it | M |
| FN-R-062 | The provider call is idempotent on the payout id; duplicate settlement is impossible | M |
| FN-R-063 | Provider notifications are signature-verified, replay-guarded and confirmed by a server-side `retrieve` agreeing on id, amount and currency | M |
| FN-R-064 | Failure, delay, return and out-of-order notifications are handled by the state machine; failed funds return to payable by contra-journal | M |
| FN-R-065 | Reconciliation of payouts against the provider statement; unknown or aged items become exceptions | M |
| FN-R-066 | Only the sandbox adapter is registered; a guard fails the build otherwise; no live transfer is possible | M |
| FN-R-067 | Full audit history of every payout step | M |

### F6 Financial administration (console)

| ID | Requirement | Pri |
| --- | --- | --- |
| FN-R-070 | Pages: revenue reconciliation, allocation review, fraud holds, payout approval and release, exception handling, audit reports, access-controlled statements, policy authoring and approval, grants | M |
| FN-R-071 | MFA and a specific grant per page; wrong-grant answers 404 | M |
| FN-R-072 | Separation of duties per the control model; conflicts refused and reported | M |
| FN-R-073 | Approvals bind to an object content hash; a changed object voids approvals | M |
| FN-R-074 | Grant changes need two administrators and step-up; freeze is single, lift is dual | M |
| FN-R-075 | Statement and payee reads by staff are audited | M |

### Cross-cutting

| ID | Requirement | Pri |
| --- | --- | --- |
| FN-R-080 | Every operation: closed Gateway flag, service identity, grant check, per-object authorization, allowlist validation, throttle | M |
| FN-R-081 | No financial value appears in code, configuration defaults, fixtures presented as policy, documentation or UI copy | M |
| FN-R-082 | Logs and audit never contain destination details, tokens, provider payloads or free text | M |
| FN-R-083 | The service owns its schema and role; no foreign keys or reads across services | M |
| FN-R-084 | Retention per DR-FIN-08 and ADR-020; nothing purged until decided | P |

## 4. Non-functional

| ID | Requirement |
| --- | --- |
| FN-N-01 | Correctness over speed: posting, allocation and payout steps are serializable-safe and lock the rows they depend on |
| FN-N-02 | Reproducibility: any past statement or allocation can be regenerated from stored inputs and policy hashes |
| FN-N-03 | A verification command checks journal balance, chain integrity, projection equality and statement totals on demand and nightly |
| FN-N-04 | Reporting queries bounded by period and page size |
| FN-N-05 | Flutter finance screens follow existing tokens, accessibility and large-text audit |
| FN-N-06 | With all flags closed no Finance route is served |

## 5. Traceability

Requirement → [API](../architecture/finance/FIN-API_Contract_PROPOSED.md) → [control matrix](../security/phase9/FIN-Control_Model_and_Authorization_Matrix_PROPOSED.md) → [threat](../security/phase9/FIN-STRIDE_Threat_Model_PROPOSED.md) → [acceptance and correctness test](../engineering/phase9/FIN-Acceptance_Correctness_and_Delivery_Plan_PROPOSED.md).
