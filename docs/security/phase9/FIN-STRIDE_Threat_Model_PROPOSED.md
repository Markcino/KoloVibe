# Finance — STRIDE threat model (proposed)

**Status: PROPOSED — not approved.** 25 November 2026. Extends DOC-203 (TM-028 ledger tampering, TM-031 unreconciled revenue, TM-030 ad events and points). Each threat has a control and a named test required before its slice is accepted; the last column maps to the Phase 9 security list.

## 1. Assets and boundaries

| Asset | Why it matters |
| --- | --- |
| Ledger and journals | The book of record; tampering is fraud or concealment |
| Policy versions | Define who is paid what; a swapped policy redirects money |
| Allocations and payable balances | Direct financial entitlement |
| Payout destinations and payout state | Theft channel |
| Provider notifications | A forged one could settle or fail a payout |
| Grants and approvals | The control model itself |
| Statements and payee data | Privacy; sensitive financial data |
| Audit chains | Evidence |

Boundaries: B1 app ⇄ Gateway; B2 Gateway ⇄ Finance; B3 producers ⇄ Finance (broker); B4 Finance ⇄ providers; B5 console ⇄ Gateway; B6 Finance ⇄ Audit and external digest store; B7 Finance ⇄ database operators.

## 2. Threats and controls

| ID | STRIDE | Threat | Control | Test |
| --- | --- | --- | --- | --- |
| T-FN-01 | T | **Balance manipulation:** a payable or balance is changed directly, by a stored value, an UPDATE, or a crafted journal | No mutable balance; append-only triggers; INSERT-only role; deferred balance trigger; projection verifier | **Balance manipulation** (direct SQL UPDATE/DELETE refused; unbalanced journal refused; projection mismatch detected) |
| T-FN-02 | T | A journal is posted to a closed period or to the wrong currency account | Period state check; currency equals account | Closed-period and currency tests |
| T-FN-03 | E | **Unauthorized adjustment:** a preparer, a single approver, a payee or an administrator without a grant posts an adjustment | Grants, two distinct approvers, content-hash binding, payee exclusion | **Unauthorized adjustments** (each actor combination) |
| T-FN-04 | E | A person creates, approves and releases the same transaction by holding several grants or using two accounts they control | Exclusive grants, per-transaction distinctness, grant changes need two administrators, SoD report | **Privilege escalation** (grant stacking, self-grant, grant then act, stale approvals) |
| T-FN-05 | E | An administrator without finance grants reaches finance pages or APIs | Grant check per page; 404; no default grants | Console route-security test |
| T-FN-06 | E | A payee gains staff capability, or staff become payees | Mutual exclusion of payee and grants | Conflict-of-interest test |
| T-FN-07 | T | **Duplicate settlement:** a payout is settled twice by retried jobs, duplicated notifications or concurrent workers | Unique posting per `(payout_id, template)`; unique provider event id; state machine; row locks | **Duplicate settlement** (sequential and concurrent) |
| T-FN-08 | T | **Payment replay:** a captured payment or provider notification is replayed to post revenue or settle again | Unique inbox key and journal key committed together; unique provider event id | **Payment replay** |
| T-FN-09 | S | **Forged provider event:** a fabricated "settled" or "failed" message | Signature over raw body with tolerance; unique event id; mandatory server-side `retrieve` agreeing on id, amount and currency | **Forged provider events** (bad signature, stale, wrong amount, wrong currency, unknown id, out-of-order) |
| T-FN-10 | S | A forged business event posts revenue (T3) or an invoice | Source allowlist by (service, kind); service-identity signature; schema validation | Forged-event and non-allowlisted-kind test |
| T-FN-11 | T | **Incorrect currency handling:** mixed-currency journals, an allocation across currencies, an implicit conversion, a wrong exponent | Single-currency groups; no conversion without approved policy; exponent table; decimal strings only | **Incorrect currency handling** (mixed, unknown, zero-decimal, exponent errors, float input) |
| T-FN-12 | T | Rounding drift or float error moves money or breaks conservation | Decimal context; rounding from policy; largest-remainder rule; conservation checks; static float ban | Property tests (conservation, determinism, order independence), float-lint test |
| T-FN-13 | T | **Concurrency:** parallel payout requests exceed the payable; parallel allocation posting or period close; concurrent adjustments | Payee row lock; unique constraints; idempotent posting per run; period state machine | **Concurrency** (N parallel payouts against one payable; double close; double post) on real PostgreSQL |
| T-FN-14 | T | A policy is changed after approval, or a calculation uses an unapproved or draft policy | Immutability; content hash in every run; `parameter_not_approved`; sandbox fixtures barred from live | Policy-immutability and refusal tests |
| T-FN-15 | T | An operator edits allocation figures | No edit path; runs immutable; approve or reject only | No-edit test |
| T-FN-16 | T | Non-deterministic allocation (time, ordering, locale) produces different results | Fixed inputs, cut-off, canonical ordering, `run_hash` | Determinism test across shuffles and repeated runs |
| T-FN-17 | T | Basis or eligibility data is swapped between snapshot and posting | Hashes recorded in the run; verifier recomputes | Input-tamper test |
| T-FN-18 | E | **Points are converted or used as an input** | No import, table, event or key shared with Points; allowlist excludes Points; static scan both ways | No-Points test (static and runtime) |
| T-FN-19 | I | **Cross-account financial access:** a payee reads or acts on another payee's data by id or path | `/me/…` routes; no payee id parameter; object queries filtered by session payee; 404 | **Cross-account financial access** (every payee operation; guessed ids in sub-resources such as `allocations/{id}`) |
| T-FN-20 | I | **Sensitive financial data leakage** in responses, logs, audit, errors, statements, console lists or exports | Masked destinations; no raw account data stored; id-only audit; redaction; staff reads audited; minimal console fields | **Sensitive financial data leakage** (response-field allowlists, log and audit content scan, console field test) |
| T-FN-21 | I | Existence disclosure of payees, payouts or grants by error or timing | Uniform 404 and shape | Existence-disclosure test |
| T-FN-22 | T | **Audit integrity:** an audit or journal row is altered or deleted, or a database owner rewrites the whole chain | Hash chains; triggers; external daily signed digest; verifier | **Audit integrity** (tamper, truncate, reorder, replace chain: verifier fails; digest mismatch detected) |
| T-FN-23 | R | A user denies approving or releasing | Attributed, hash-bound approvals; actor, grant and MFA state recorded | Attribution test |
| T-FN-24 | T | An approval is reused after the object changed | Content-hash binding | Stale-approval test |
| T-FN-25 | T | Payout destination swapped between approval and release | Destination id and token bound in the approved content hash; change voids approvals | Destination-swap test |
| T-FN-26 | S | A payee adds a destination belonging to someone else, or a session thief changes it | Step-up; provider verification; cooling period before first use (a policy parameter, unset); notification in-app | Destination-change test |
| T-FN-27 | D | Reconciliation, close or verifier jobs lock the ledger or starve posting | Bounded batches; read replicas not assumed; job locks scoped | Job-bound test |
| T-FN-28 | D | A flood of business events or notifications | Per-source bounds; cheap rejection; counters instead of rows | Ingestion-bound test |
| T-FN-29 | D | A provider outage leaves payouts hanging | Aged in-flight detection, exception cases, no automatic retry that could double-pay | Provider-outage test |
| T-FN-30 | E | A live book or live adapter is enabled by configuration | Approval constant guard; startup refusal; sandbox fixture barred from live | **Live-guard test** |
| T-FN-31 | T | A revenue record is counted twice or recognized from an estimate | Unique reference; recognition only from verified sources; no impression-based path | Duplicate and estimate-refusal tests |
| T-FN-32 | T | Late or disputed revenue changes a closed period | Period immutability; correction in a later period with reference | Closed-period correction test |
| T-FN-33 | E | Freeze lifted by one person, or bypassed by direct release | Dual lift; release checks freeze in-transaction | Freeze tests |
| T-FN-34 | I | Statements expose other payees' data or staff view them without audit | Own-only; staff reads audited; grant required | Statement access test |
| T-FN-35 | T | A statement differs from the ledger | Generated from the ledger; verifier compares totals | Statement-reproduction test |
| T-FN-36 | E | A grant is assigned without a second administrator or while step-up is missing | Dual approval; fail closed | Grant-control test |

## 3. Residual risks

| Risk | Treatment |
| --- | --- |
| Colluding finance staff (several real people) | Distinct-account rules cannot detect collusion; audit, SoD report, rotation and external review (non-code) |
| A database owner with all keys | Hash chains plus external digest detect, not prevent; DR-EV-06 role model |
| Unqualified accounting rules | Independent accountant sign-off (DR-FIN-04) is a gate; code cannot substitute |
| Sandbox is not a real provider | Real behaviour (partial settlement, delays, reversals, fees, chargebacks) is unknown; a provider-specific test pack and a second review precede any live use |
| Producers do not yet exist | Integration is proven against contracts and simulators only |
| Legal and tax unknowns | Blockers; no payout can go live |
| Payee identity fraud (fake creators) | Eligibility policy, destination verification, holds; policy parameters unset |
