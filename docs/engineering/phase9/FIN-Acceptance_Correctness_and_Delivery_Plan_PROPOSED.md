# Finance — accounting correctness specification, acceptance criteria and delivery plan (proposed)

**Status: PROPOSED — not approved.** 25 November 2026. Delivers F1 to F6 one independently testable capability at a time; focused tests and CI per slice; no automatic merges or AWS deployments; live financial acceptance and activation deferred to separate authorization. **No slice starts before the accounting design is approved** and its decisions recorded ([gate table](../../architecture/finance/FIN-Owner_Decisions_Required_PHASE9A.md#what-each-slice-needs-before-it-can-start)).

## 1. Rules for every PR

1. One capability; reuse existing patterns (outbox/inbox, idempotency, grants, claim-confirm-decision forms, id-only audit); no deferred feature (real provider, live book, FX, Points conversion, payee portal).
2. Every operation lands with contract entry, control-matrix row, registry-driven tests and its Flutter or console counterpart in the same PR.
3. Flags closed by default; production NO-GO; the owner approves every merge and deployment.
4. **No financial value in code, defaults or docs.** A CI check scans for numeric rate, share and threshold literals in finance modules and for float types in money paths; test fixtures live under a clearly named non-policy path.
5. A results file per slice in `docs/engineering/phase9/`: actual changes, tests run, failures, unresolved work, blockers. Nothing claimed that was not run.
6. After repeated unsuccessful fixes, stop and report the blocker.

## 2. Accounting correctness specification (what the correctness report must demonstrate)

These invariants are the acceptance basis of the "accounting correctness report". Each has a verifier (SQL or job) and a test; the report lists result, evidence and gaps per invariant.

| ID | Invariant | Verified by |
| --- | --- | --- |
| INV-01 | For every journal and currency, debits equal credits | Constraint trigger; verifier; property test with random journals |
| INV-02 | Journals, postings, policy versions (after submission), approvals, decisions, audit events cannot be updated or deleted | Trigger and role tests; direct-SQL attempt tests |
| INV-03 | Account balance equals the sum of its postings; any projection equals that sum | Verifier job; fault-injection test |
| INV-04 | Every posting's currency equals its account's currency; no mixed-currency journal; no implicit conversion | Unit and property tests |
| INV-05 | No float type or operation on a money path | Static scan; tests with float-hostile values |
| INV-06 | A revenue record is counted once: unique `(source, provider_reference)` | Replay and concurrency tests |
| INV-07 | A business event or provider notification takes effect once | Replay, redelivery and concurrent-delivery tests |
| INV-08 | A reversal exists at most once per original journal and exactly negates it | Reversal tests |
| INV-09 | Closed periods accept no postings; corrections post later with a reference | Period tests |
| INV-10 | Allocation conservation: `Σ allocations = distributable`, per currency, exactly | Property tests over random bases and weights |
| INV-11 | Allocation determinism and input-order independence: identical `run_hash` | Repeat and shuffle tests |
| INV-12 | No allocation without an approved policy, basis, eligibility snapshot and cut-off; every parameter present | Refusal tests (each missing item) |
| INV-13 | Every figure is attributable to policy version hashes | Report from stored run data |
| INV-14 | A payee's open and settled payouts never exceed the released payable | Concurrency test against one payable |
| INV-15 | One settlement per payout; failed or returned funds restore payable exactly once | State-machine and replay tests |
| INV-16 | Approvals bind to content hashes; distinct accounts across prepare, approve, release and payee | Combination tests |
| INV-17 | Ledger-to-statement reproduction: every statement total equals the ledger | Verifier |
| INV-18 | Reconciliation never modifies ledger facts | Test that recon writes no journal |
| INV-19 | Finance has no read or write path to Points | Static scan both ways; runtime event test |
| INV-20 | No live book or live adapter can run | Guard tests; startup refusal |
| INV-21 | Chain integrity: journal and audit chains verify end to end; external digests match | Verifier; tamper tests |
| INV-22 | Payee data isolation: each payee operation returns only that payee's rows | Registry-driven cross-account test |

## 3. Slices and PR order

| PR | Capability | Backend | Flutter | Console | Needs |
| --- | --- | --- | --- | --- | --- |
| P9-F0 | Service skeleton, flags, wiring, guards, no-value scan, audit producer, books | shell, health, service auth, book, currency | — | — | DR-FIN-01, 02, 06, 07 |
| P9-F1 | **Ledger core:** accounts, journals, postings, immutability, decimal and currency rules, idempotency, hash chain, verifier | ledger | — | ledger verify page | DR-FIN-03, 04 (accounting design approved) |
| P9-F2a | Revenue sources, records, recognition rules, duplicate prevention, business-event inbox | records, inbox, T1/T2/T3/T4 | — | revenue pages | DR-FIN-10 to 12, 30 |
| P9-F2b | Statement sources, three-way reconciliation, exceptions, corrections | recon, exceptions, adjustments | — | reconciliation, exceptions | F2a, DR-FIN-20 |
| P9-F3a | Policy versions and approvals | policy | — | policy pages | DR-FIN-04, 05 |
| P9-F3b | Periods, basis and eligibility interfaces, deterministic allocation, holds, reversal and correction runs | runs, allocations, holds | — | allocation review, holds | F3a, DR-FIN-13 to 17 |
| P9-F3c | Statements and disputes | statements, disputes | — | statement view (controlled), disputes | DR-FIN-21, 22 |
| P9-F4 | Creator financial experience | `/me/finance` | ~20 screens | — | F3 data, DR-FIN-40, 42 |
| P9-F5a | Destinations, payout request, eligibility, approvals | payout, approvals | request flow | payout approval | DR-FIN-05, 18, 19 |
| P9-F5b | Sandbox provider, release, notifications, failure handling, payout reconciliation | adapter, release, T7-T9 | status and failure screens | release, failed-handling | DR-FIN-31 (interface) |
| P9-F6 | Administration completion: grants, freeze, SoD report, audit reports, exception handling polish | grants, freeze, reports | — | remaining pages | DR-FIN-41 |
| P9-SEC | Cross-cutting security and correctness suite, four-way contract reconciliation, real-HTTP journey, mutation checks | tests | layout audit | route security | — |
| P9-R | Accounting correctness report, sandbox results, approvals and implementation matrix, flag-opening request | docs | — | — | — |

Console pages ship with the slice they belong to; F6 completes what remains. Each slice's security tests ship in that slice; P9-SEC consolidates.

## 4. Acceptance criteria

IDs `AC-FN-nnn`.

| ID | Criterion |
| --- | --- |
| AC-FN-001 | Books: `live` cannot be created without an approval constant; sandbox data cannot be referenced from a live book |
| AC-FN-002 | INV-01 to INV-05 hold under property tests and direct-SQL attack tests (**balance manipulation**) |
| AC-FN-003 | Business-event handling: allowlist, signature, schema, unique inbox; replay and concurrent redelivery produce one journal (**payment replay**) |
| AC-FN-004 | Revenue: duplicates, estimates and unrecognized records never reach shareable revenue |
| AC-FN-005 | Reconciliation: each outcome kind is produced by a fixture; ledger unchanged by reconciliation; exceptions resolved only by approved adjustment |
| AC-FN-006 | Policies: immutable, versioned, approved by someone else with evidence, prospective only; draft or fixture policies cannot run in live; **no default values exist** |
| AC-FN-007 | Allocation: INV-10 to INV-13; every missing input produces `parameter_not_approved` or a named refusal |
| AC-FN-008 | Holds: reasons, release by approval, no release by the placer alone |
| AC-FN-009 | Statements reproduce the ledger (INV-17) and are immutable once issued |
| AC-FN-010 | Control model: every row of the SoD conflict table in the [control model](../../security/phase9/FIN-Control_Model_and_Authorization_Matrix_PROPOSED.md#5-separation-of-duties-conflicts-the-system-must-refuse) is refused (**unauthorized adjustments**, **privilege escalation**) |
| AC-FN-011 | Payee isolation: every payee operation passes the registry-driven cross-account test (**cross-account financial access**) |
| AC-FN-012 | Payout: INV-14 and INV-15 under concurrency; duplicate settlement impossible (**duplicate settlement**, **concurrency**) |
| AC-FN-013 | Provider notifications: bad signature, stale, replayed, wrong amount, wrong currency, unknown id, out-of-order, delayed and duplicate cases handled per state machine (**forged provider events**) |
| AC-FN-014 | Currency: mixed, unknown, zero-decimal and float inputs refused or handled exactly (**incorrect currency handling**) |
| AC-FN-015 | Audit: chains verify; tampering, truncation and reordering are detected; digests match (**audit integrity**) |
| AC-FN-016 | Leakage: response allowlists, log and audit scans, console fields, statement access show no destination detail, token, payload or other payee's data (**sensitive financial data leakage**) |
| AC-FN-017 | Flutter: Finance section shows no Points data and Points shows no Finance data; `Money` type has no `double`; amounts are decimal strings; layout audit passes |
| AC-FN-018 | Console: MFA and grant on every route; wrong grant answers 404; forms safe against double submit; approvals bind to content |
| AC-FN-019 | Guards: no real provider, no live book, no Points reference, no numeric policy literal, no float money |
| AC-FN-020 | With all flags closed no Finance route is served |
| AC-FN-021 | Four-way reconciliation of contract, Gateway routes, service registry and clients has no difference; real answers validate against schemas |
| AC-FN-022 | Real-HTTP journey (sandbox): policy approved by two people → revenue recorded and reconciled → period closed → run approved → statements → payee requests payout → two approvals → release by a third → sandbox settles → reconciled; each actor's forbidden shortcuts refused |
| AC-FN-023 | Mutation checks: removing one distinctness check, one balance check, one signature check, one lock or one idempotency key makes a named test fail |

## 5. Implementation matrix (current status)

| Capability | Contract | ERD | Policy | Threat model | Code | Tests | Flutter | Console | Status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| F1 Ledger and accounting design | Proposed | Proposed | Needs DR-FIN-03, 04 | Proposed | Not started | Specified (INV) | n/a | Planned | **Designed; awaiting approval** |
| F2 Revenue records and reconciliation | Proposed | Proposed | Needs DR-FIN-10 to 12, 30 | Proposed | Not started | Specified | n/a | Planned | Designed; blocked by policy |
| F3 Revenue sharing | Proposed | Proposed | **Parameters unset by design** (DR-FIN-13 to 17, 20 to 22) | Proposed | Not started | Specified | n/a | Planned | Designed; blocked by policy and by three additive changes (basis, eligibility, events) |
| F4 Creator experience | Proposed | n/a | Needs DR-FIN-21, 22, 40 | Proposed | Not started | Specified | ~20 screens, M-300+ | n/a | Designed; blocked by F3 and designs |
| F5 Sandbox payouts | Proposed | Proposed | Needs DR-FIN-18, 19 structure | Proposed | Not started | Specified | Planned | Planned | Designed; **real provider blocked**, sandbox unblocked after approval |
| F6 Administration | Proposed | Proposed | Needs DR-FIN-05, 41 | Proposed | Not started | Specified | n/a | ~14 page groups | Designed; awaiting approval |

**Accounting correctness report, automated test evidence and sandbox integration results: not produced, because nothing has been implemented.** This document specifies what they will contain (INV-01 to INV-22, AC-FN-001 to 023). No result is claimed.

## 6. Amendments to the Phase 7 and 8 packages if DR-FIN-02 is approved

| Package | Item | Change |
| --- | --- | --- |
| Phase 7 | DR-EV-03 "one ledger in Events' payments module" | Superseded: Finance owns the ledger; Events keeps order and payment state and emits `events.payment_captured` and `events.refund_settled` |
| Phase 7 | ADR-EVT-001 Decision 3; ERD `financial_event`; P7-E5b | The append-only `financial_event` table and hash chain move to Finance. Events keeps an outbox and per-order `captured_minor` and `refunded_minor` counters with `payment_attempt` rows; the "refund ≤ captured" check runs on those under the order lock; invariants I-4 and I-7 are re-expressed accordingly; a daily Events-to-Finance reconciliation covers drift |
| Phase 7 | DR-EV-29 (no organizer settlement) | Unchanged; organizer proceeds are only a liability (account 2200) until a payout policy exists |
| Phase 8 | DR-AD-03 | Answered: Ads emits `ads.invoice_issued` and `ads.correction_posted`; Finance records the receivable and never lets Ads post |
| Phase 8 | Billing corrections | Ads proposes; Finance's approvals decide any ledger effect |
| Both | Capacity (DR-EV-07, DR-AD-05) | One question now covers Business, Events, Ads and Finance |

## 7. Additive changes to existing services (each needs its own approval)

| Service | Change | Needed for |
| --- | --- | --- |
| Audit | `finance` producer kinds and a migration | Audit events |
| Gateway | `finance_payee` and `finance_admin` flags, routes, local peer, validators | All access |
| Staging runtime and ops tables | Empty capability set | Dark deployment |
| Engagement or Content | A period-final, hashed **basis dataset** read (if basis (a) or (b) is approved) | Allocation (F3) |
| Creators and Business | Signed **eligibility snapshot** reads | Allocation (F3) |
| Events and Ads (when built) | Business-event emitters through their outboxes | Revenue records (F2) |
| Identity | Step-up proof (DR-EV-05) | Sensitive actions |

Points, Engagement behaviour and Moderation are **not** changed.

## 8. Blockers register

| # | Blocker | Affects | Needs |
| --- | --- | --- | --- |
| BL-FN-01 | Independent accountant not named; accounting design unsigned | Everything | DR-FIN-04 |
| BL-FN-02 | Every policy value (pool, reserve, share, thresholds, periods, windows, tolerances, minimums) is unset by design | Any allocation or payout figure | DR-FIN-10 to 22 |
| BL-FN-03 | Allocation basis not chosen | Allocation | DR-FIN-15 |
| BL-FN-04 | Legal: tax, withholding, KYC/AML, sanctions, data protection, retention | Live payouts, statements | DR-FIN-19, 22, 08 |
| BL-FN-05 | Payout provider selection and due diligence | Any real payout | DR-FIN-31 |
| BL-FN-06 | Revenue-source providers (for example AdMob eligibility, see Phase 8) | Real revenue records | DR-FIN-30 |
| BL-FN-07 | Identity step-up proof | Grants, destinations, release, policy approval | DR-FIN-06 |
| BL-FN-08 | Producers (Events, Ads) not built | End-to-end integration | Phases 7 and 8 approvals |
| BL-FN-09 | Database role model; capacity for another service; broker vhost | Any deployment | DR-FIN-06 |
| BL-FN-10 | External digest store | Audit integrity beyond the database | DR-FIN-08 |
| BL-FN-11 | DOC-023 change request and SRS console-scope amendment | Governance | DR-FIN-01 |
| BL-FN-12 | Independent security test and live acceptance | Activation | Separate authorization |

## 9. Test approach

Service tests on real PostgreSQL for constraints, locks and concurrency (SQLite cannot prove them); property-based tests for conservation, determinism and balance; fault injection for the verifier; simulator tests for providers and producers; Gateway, Dart and console tests; shared scripts and CI. **Not run in Phase 9:** staging, devices, load, any real provider or bank, penetration testing, live acceptance.
