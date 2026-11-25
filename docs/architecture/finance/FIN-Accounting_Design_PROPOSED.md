# Finance — accounting design (proposed)

**Status: PROPOSED — not approved, and not accounting advice.** 25 November 2026. This is the F1 design. **It must be reviewed and signed by a qualified independent accountant (DR-FIN-04) before implementation.** The charts, templates and rules below are *structure*. **No financial value is stated or implied** (no rate, share, reserve, threshold, period length, fee or tax); every value is an unset policy parameter that an approved policy version must supply.

## 1. Principles

1. **One book of record.** The Finance service owns the only monetary ledger. No other service holds balances or journals (DR-FIN-02).
2. **Double-entry, append-only.** Every transaction is a journal of postings whose debits equal credits per currency. Journals and postings are never updated or deleted; mistakes are reversed by contra-journals that reference the original.
3. **Derived balances.** Balance = sum of postings. Any stored balance is a projection that a verification job proves equal to the sum; the projection is never authoritative.
4. **Exact arithmetic.** No binary floating point anywhere. Calculation uses decimal arithmetic with an explicit precision and rounding rule; posted amounts are integer minor units.
5. **Policy-driven.** Every rule that has a value comes from an immutable, approved, versioned policy. Every calculation records the policy version ids and content hashes it used.
6. **Deterministic and reproducible.** The same inputs and policy produce byte-identical outputs; each run carries a hash that a re-run must reproduce.
7. **Events, not shared tables.** Producers emit signed business events; Finance consumes them through an idempotent inbox. Finance does not read other services' tables and they do not read Finance's.
8. **Points are not money.** No input, rate, join or event from Points exists.
9. **Sandbox and live are different books.** Nothing moves between them.

## 2. Currency and numeric representation

| Item | Rule |
| --- | --- |
| Currency | ISO 4217 code on every account, journal and posting; a currency table records the minor-unit exponent. Only currencies approved by DR-FIN-10 exist |
| Stored amounts | `amount_minor` as signed 64-bit integer in the currency's minor unit; postings are always positive with an explicit debit or credit side |
| Inputs with fractions | Producers send amounts as **decimal strings** or integer minor units; never JSON floats (a JSON number with a fractional part or exponent is rejected). Per-impression micro-costs (Ads) are carried as an integer count of micro-minor units and rounded **once** per invoice line by the producer; Finance receives only whole minor units |
| Calculation | Python `Decimal` with a fixed context (precision 38; invalid-operation, overflow and division-by-zero traps enabled) and PostgreSQL `NUMERIC`; the rounding mode is a **policy parameter** (`rounding_rule`), never a default |
| API and client | Amounts are decimal strings plus a currency code. The Flutter app parses them into an integer-backed `Money` type; `double` is forbidden for money by a lint and a test |
| Mixed currency | A journal has exactly one currency per posting group and must balance within each; a posting whose currency differs from its account's is refused |
| Conversion | None unless DR-FIN-10 approves an FX policy; then the rate source, timestamp and rounding are recorded on a dedicated conversion journal |
| Zero and negative | A posting is strictly positive; a negative effect is the opposite side |

## 3. Chart of accounts (illustrative; needs independent sign-off)

| Code | Account | Type | Sub-ledger key |
| --- | --- | --- | --- |
| 1100 | Bank / cash held (sandbox bank in a sandbox book) | asset | bank account |
| 1200 | Source receivable | asset | revenue source |
| 1300 | Payment-processor receivable (ticket captures) | asset | processor |
| 2100 | Creator and business payable (released) | liability | payee |
| 2150 | Payable held (withheld) | liability | payee, hold reason |
| 2200 | Ticket proceeds payable to organizers | liability | organizer |
| 2300 | Revenue-share reserve | liability | policy version |
| 2400 | Refunds payable | liability | order |
| 2900 | Payout clearing | liability/clearing | payout |
| 4100 | Revenue: network advertising | revenue | source |
| 4200 | Revenue: direct-sold advertising | revenue | advertiser invoice |
| 4300 | Revenue: sponsorship | revenue | — |
| 4400 | Revenue: ticket platform fees | revenue | event |
| 5100 | Revenue-share expense | expense | policy version |
| 5900 | Adjustments and write-offs | expense | reason code |

Account creation and changes need the independent approver. A payee, advertiser, organizer or source is a sub-ledger key, not a separate service.

## 4. Revenue source classification, recognition and shareability

**Source classes (each a stored classification with owner-approved flags):** `network_advertising`, `direct_advertising`, `sponsorship`, `ticket_platform_fee`, `ticket_face_value`, `refund_or_chargeback`, `other`.

| Concept | Definition |
| --- | --- |
| **Recorded** | A revenue record exists from a verified source (a provider statement line or a signed business event) with a provider reference |
| **Recognized** | The recognition rule for its class (a policy parameter, from the independent accountant) is satisfied, and the receivable and revenue postings are made |
| **Collected** | Cash is matched to it (a bank or provider settlement line) |
| **Reconciled** | Source statement, ledger and cash agree within the policy tolerance (an approved parameter; the default tolerance is zero) |
| **Shareable** | Recognized **and** collected **and** reconciled **and** its class flagged shareable **and** past any clawback window the policy sets. Only shareable revenue can enter a pool. This restates the approved principle (BR-010): no pool from estimates or impressions |

`ticket_face_value` is a liability to organizers and is **structurally unshareable**: the posting template credits 2200, not a revenue account. Whether any other class is shareable is DR-FIN-11.

## 5. Policy versions and the allocation engine

### 5.1 Policy objects

A `policy_version` has `kind` (`recognition`, `sharing`, `eligibility`, `holds`, `payout`, `adjustment_authority`, `rounding`, `statements`), a canonical JSON `parameters` document, a `content_hash`, an `environment` (`sandbox_fixture` or `live`), a status and links to author, approver and independent-approver evidence. Statuses: `draft → submitted → approved → superseded`. Rules:

- Immutable after `submitted`; a change is a new version.
- `approved` requires **author ≠ approver**, the independent accountant's evidence reference, and an `effective_from` strictly after approval (no retroactive effect).
- Every parameter is **required with no default**. In `draft` any may be `null`; `approved` requires every parameter non-null or explicitly `not_applicable` with a justification code. The engine **refuses to run** with a null parameter (`parameter_not_approved`).
- `sandbox_fixture` versions can be used only in sandbox books and can never be approved for a live book. Test fixtures contain obviously artificial values, are labelled non-policy, and are not recommendations.

### 5.2 Parameters the sharing policy must supply (all unset in this design)

`shareable_classes`, `recognition_lag`, `clawback_window`, `period_type`, `close_lag`, `pool_formation` (how shareable revenue becomes a distributable pool: share, cost deductions), `reserve_rule`, `allocation_basis` (basis provider id and version), `eligibility_definition` (id and version), `hold_rules`, `rounding_rule`, `minimum_allocation` (or `not_applicable`), `currency_rule`.

### 5.3 Allocation run (deterministic specification)

Inputs, all fixed and hashed before calculation: the sharing policy version; the period; a **ledger cut-off** (the highest ledger sequence number included, so the revenue figure is a snapshot, not "now"); the basis dataset (period-final, immutable, with its hash, from the basis provider); the eligibility snapshot (signed, as-of time and hash). Steps, per currency:

1. `R` = sum of shareable revenue postings up to the cut-off (integer minor units to `Decimal`).
2. Pool and reserve by the policy's `pool_formation` and `reserve_rule` using exact `Decimal` arithmetic; results rounded **once** by `rounding_rule` to minor units.
3. Weights `w_i` = integer basis units of each eligible payee (ineligible payees are listed with a reason code and excluded).
4. Raw share `x_i = D × w_i / Σw` in `Decimal` (precision 38). Floor each to minor units; distribute the remaining minor units one each by **largest fractional remainder, ties broken by ascending payee id**, so that `Σ allocations = D` exactly. (The tie and remainder rule is itself part of `rounding_rule`, so it is approved, not assumed.)
5. Apply `minimum_allocation` and `hold_rules` from the policy, producing **released** and **held** portions with reason codes.
6. Output rows are ordered by payee id; `run_hash` = SHA-256 over canonical serialization of: policy hash, period, cut-off, basis hash, eligibility hash, and every output row.

Required properties (tests): determinism (a re-run reproduces `run_hash`), input-order independence (shuffled basis rows give the same result), conservation (`Σ outputs = distributable`, per currency), no float anywhere, monotonic (more weight never gives less, absent minimum rules), and a refusal if any parameter, basis, eligibility snapshot or policy approval is missing. A run is `computed → reviewed → approved → posted`; posting creates journals (template T5), is idempotent per run, and the run is immutable afterwards.

### 5.4 Reversals and adjustments of allocations

A mistake found after posting is corrected by a *correction run* in the current open period that references the original run and posts contra and replacement journals; closed periods are never edited. A payee dispute, a fraud finding or a source clawback follows the adjustment path (§8).

## 6. Posting templates (illustrative)

D = debit, C = credit; each balances per currency. Needs independent sign-off.

| Template | Trigger | Postings |
| --- | --- | --- |
| T1 Revenue recognized | verified source line meets recognition rule | D 1200 source receivable; C 4xxx revenue (by class) |
| T2 Cash collected | bank or settlement line matched | D 1100 bank; C 1200 receivable |
| T3 Ticket capture (event from Events) | `payment_captured` | D 1300 processor receivable (gross); C 2200 proceeds payable (face value); C 4400 fee revenue (fee) |
| T4 Refund settled | `refund_settled` | reverses T3 proportionally; D 2400 or 1300 as the template fixes |
| T5 Allocation posted | approved run | D 5100 revenue-share expense; C 2100 payable (released portions); C 2150 payable held (held portions); C 2300 reserve (reserve amount) |
| T6 Hold released | approved release | D 2150; C 2100 |
| T7 Payout submitted | provider accepted | D 2100 payable; C 2900 clearing |
| T8 Payout settled | verified provider settlement | D 2900; C 1100 bank |
| T9 Payout failed or returned | verified failure | D 2900; C 2100 (payable restored) |
| T10 Adjustment | two approvers | D/C per reason template; always includes 5900 or the corrected account |
| T11 Reversal | any journal | exact contra; links `reverses_journal_id`; unique per original |

## 7. Transaction lifecycles and idempotency

| Transaction | Lifecycle (server-controlled) |
| --- | --- |
| Revenue record | `recorded → recognized → collected → reconciled` (or `disputed`, `written_off` with approvers) |
| Allocation run | `computed → reviewed → approved → posted` (or `rejected`, `superseded`) |
| Hold | `placed → released` (release approved) or `converted_to_adjustment` |
| Adjustment | `prepared → approved_1 → approved_2 → posted` (or `rejected`) |
| Payout | `requested → eligibility_checked → pending_approval → approved_1 → approved_2 → ready_for_release → releasing → submitted → settled` or `failed` or `returned`; `cancelled` before approval |
| Reconciliation run | `open → matched → exceptions_open → resolved → closed` |
| Period | `open → closing → closed` (no reopen) |

**Idempotency, by layer:** every command carries an `Idempotency-Key` (replay returns the stored answer; reuse with another body is refused); journals have a unique `idempotency_key`; business events are unique on `(source_service, source_event_id)`; provider notifications are unique on `(provider, provider_event_id)`; the provider call for a payout uses the payout id as its idempotency key; allocation posting is unique per run; reversals are unique per original journal. Each posting is committed in the **same transaction** that records the inbox row, so a redelivered event cannot post twice.

## 8. Adjustment authorization

Every adjustment has a reason code from an approved list, an evidence reference (not free text), a preparer, **two distinct approvers**, none of whom may be the preparer or the affected payee, and posts only after the second approval. The design contains **no amount threshold** (none is approved); if the owner wants a different count by size, that is a policy parameter. Clawbacks after payout follow DR-FIN-20 (offset, negative balance or write-off) and are adjustments, never edits.

## 9. Reconciliation model

Three-way, per source and period, using provider references:

| Comparison | Outcomes recorded |
| --- | --- |
| Source statement lines ⇄ ledger revenue/receivable postings | `matched`, `missing_in_ledger`, `missing_in_source`, `amount_mismatch`, `currency_mismatch`, `duplicate_reference` |
| Ledger receivable ⇄ cash (bank or settlement) | `collected`, `uncollected_aged`, `over_collected` |
| Payout ledger ⇄ provider payout statement | `settled`, `in_flight_aged`, `failed_unposted`, `unknown_at_provider` |

Differences become **exception records** with an owner; they are resolved only through the adjustment or write-off path (two approvers); **reconciliation never edits ledger facts and never auto-corrects**. A period cannot close while exceptions are open unless the approved policy lists a tolerance or the owner-approved exception waiver is recorded. Sandbox sources provide statements with injectable discrepancies for tests.

## 10. Provider interfaces (no real implementation)

| Interface | Methods | Sandbox implementation |
| --- | --- | --- |
| `RevenueStatementSource` | `fetch(period)`, `verify_notification(raw, headers)` | Deterministic statements with injectable duplicates, mismatches and late lines |
| `PayoutProvider` | `create(payout_id, destination_ref, amount, currency, key)`, `retrieve(payout_id)`, `verify_notification(raw, headers)`, `cancel(payout_id)` | In-process simulator that signs notifications; modes: success, delayed, failed, returned, duplicate notification, out-of-order, forged signature, amount mismatch, unknown id |
| `BasisProvider` | `finalized(period)` → rows and hash | Fixture provider; the real one is an additive Engagement or Content change needing approval |
| `EligibilityProvider` | `snapshot(period)` → signed rows and hash | Fixture provider; real ones are additive reads on Creators and Business |

A guard test fails the build if any non-sandbox adapter is registered without an approval constant, and the service refuses to start a `live` book without it.

## 11. Financial audit controls

| Control | Mechanism |
| --- | --- |
| Immutable history | Trigger rejecting UPDATE and DELETE on journals, postings, policy versions after submission, approvals, decisions; INSERT-only runtime role (DR-EV-06 model) |
| Tamper evidence | `prev_hash` and `hash` per journal and per audit event; a verification command recomputes chains and ledger sums |
| External anchor | Daily signed digest of chain heads stored outside the Finance database (DR-FIN-08) so a database owner cannot silently rewrite history |
| Complete attribution | Every state change records actor, role grant used, time, policy versions and approvers; the actor's session and MFA state are in the envelope |
| Privileged reads | Statement, payee and payout-destination reads by staff are audited (ids only) |
| Platform audit | Id-only events also reach the Audit service through the existing outbox pattern |
| Reports | Console audit reports from the hash-chained store: who created, approved, released what, and any conflicting-role attempt |
| Separation | Grants are mutually exclusive per account; conflicts are refused in code and detectable by a report |
