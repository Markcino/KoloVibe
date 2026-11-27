# ADR-FIN-001 — Financial bounded context, single ledger and business-event integration

**Current decision — structural design APPROVED by GD-01 and GD-04, 27 November 2026, 11:31 UTC.** Decision J and approved FP-PAY govern over the historical proposal below. Independent accounting approval of posting templates and controls is **BLOCKED**, not inferred from structural approval (#304, #141).

- Canonical service name: `finance`, Django without DRF. Schema `finance`; migration owner `finance_owner`; runtime `finance_rt` (no DDL, no journal UPDATE/DELETE); broker account `finance`. Credentials are separately scoped, never reused. Audit and dispatcher processes receive minimum grants.
- Finance owns the only monetary ledger **and all payment/payout provider adapters**, intents, verified provider inbox, refunds, reconciliation and settlement. Events and Advertising own operational facts and request Finance operations through authenticated interfaces. They never call a provider or post their own journal. This supersedes historical Events Decision 3/4 and old `events.payment_captured` / `events.refund_settled` ingestion.
- Journal header + lines + source inbox + outgoing event + audit delivery commit atomically. Balanced per book/currency, integer minor units internally; API decimal strings with approved currency exponent. Serializable/locked posting; unique `(producer,event_id)` and business source reference; same id with a different digest is an integrity incident. Reversals reference the original journal; closed periods immutable. Database rejection of UPDATE/DELETE; migration owner separated from runtime. Hash-chain sequence serialized per book, external signed anchors, reconciliation; hashes alone do not prevent a privileged rewrite.
- **Decision J supersedes historical Decision 5:** allocation uses a finalized, immutable eligible-Points snapshot as a relative weight in an approved pool funded only from reconciled collected revenue. Points are neither redeemed, debited nor assigned a fixed money value. The snapshot records period, rule version, eligibility decision and digest. Zero total eligible weight blocks allocation. Decimal computation, deterministic remainder allocation and totals reconciliation require independent accounting review. Share, currency, eligibility and payout values remain unset.
- Sandbox adapter only; staging rejects live mode. Signed raw provider callback + unique provider event id + server retrieve matching id/reference, amount, currency and state before journal posting. Finance's success event is the sole trigger for Events ticket issuance. Late success after inventory expiry creates an exception/compensating refund saga; no oversell or silent loss. Cancellation refunds are resumable batches, never a cross-service transaction.
- Per-operation Finance grants, MFA, purpose/resource/session-bound single-use Identity step-up and maker/checker/releaser distinctness; a second payout approval and release cannot be performed by the maker or the other approver. Own-payee routes resolve the payee server-side; no client-supplied payee authority. Finite policy versions; no guessed financial or legal defaults.
- Provider receipts, disputes, holds, payout state and ledger remain Finance-owned. Masked provider destination references only; no card/bank fields. Erasure pseudonymises required financial evidence subject to approved retention/legal holds, without deleting journal lines. Access exports exclude other payees.

Canonical API: [DOC-205](../architecture/DOC-205_OpenAPI_3_1_DRAFT.yaml). Canonical event catalogue: [events.yaml](../../packages/contracts/events/catalogue.yaml). Structural approval: [GD-01 to GD-06](../governance/phase1/PHASE-01_Governance_Gate_Register.md). No service implementation, deployment or live activation is authorized by this record.

## Historical proposal (25 November; conflicts above are superseded)

**Status: PROPOSED — needs owner approval and independent accounting review. Not an approved ADR.** Phase 9A, 25 November 2026. Identifier provisional; the DOC-207 register is not altered.

**Decision-maker.** Mark Allen Gbalazeh (@Markcino). **Related.** ADR-001, ADR-007 (outbox/inbox, idempotent consumers), ADR-009 (non-cash points), ADR-010 (financial separation), ADR-013, ADR-020, DOC-006 BR-010/011/012, DOC-004, TM-028, TM-031, [ADR-EVT-001](ADR-EVT-001_Events_and_Ticketing_Bounded_Context_PROPOSED.md), [ADR-AD-001](ADR-AD-001_Advertising_Bounded_Context_PROPOSED.md), [owner decisions](../architecture/finance/FIN-Owner_Decisions_Required_PHASE9A.md), [accounting design](../architecture/finance/FIN-Accounting_Design_PROPOSED.md).

## Context

The approved documents already fix much of the shape: a monetary ledger **separate from engagement and points, double-entry, with reconciliation** (BR-011); pools only from **actual reconciled collected revenue** (BR-010); no cash disbursement until provider, legal, fraud, approval and security gates pass (BR-012); two distinct approvers for payout release (DOC-004); percentages, thresholds, reserves and provider **deferred** (DOC-006, PRD §14). Verified in the repository on 25 November 2026:

| Need | State | Consequence |
| --- | --- | --- |
| A monetary ledger | **None.** `points` is a non-cash append-only ledger (`PointsEntry`, integer deltas, `rule_version`, reversals, audit outbox) | Reuse its *patterns* (append-only, idempotent, reversal link, deciding-transaction audit, outbox); not its tables |
| Event integration | Engagement and Points each have a PostgreSQL `event_outbox` and idempotent inbox (`accept_once`) over Celery/RabbitMQ | Reuse for business events into Finance |
| Roles | Identity has viewer, creator, moderator, administrator; no finance role | Finance-owned grants (Business reviewer-grant pattern) |
| Step-up proof | Not built | Sensitive finance actions fail closed |
| Money-producing contexts | Business (no money), Events and Ads (designs, unapproved), no real provider | Finance must work from a **business-event contract** and sandbox sources |
| Console | R1 console excludes payouts and points execution (SRS) | Finance pages need a recorded scope extension |
| Eligibility | Creators `CreatorProfile.status`, Business `verified` | Signed snapshots through interfaces, not table reads |

The earlier packages left two open questions: Phase 7 put the ledger inside Events (DR-EV-03) and Phase 8 kept Ads billing facts without a ledger (DR-AD-03), with the ledger's owner to be decided jointly. This ADR decides it.

## Decision 1 — Bounded context and service boundary

A new **`finance` Django/DRF service** with its own PostgreSQL schema and role, behind the Gateway, using the shared HMAC service identity, owning **the** ledger, revenue records, policies, allocations, holds, payouts, reconciliation, statements and financial audit.

| Option | For | Against | Verdict |
| --- | --- | --- | --- |
| A. New `finance` service | One owner of money; BR-011 separation from Points; independent blast radius, grants and database role; extraction of nothing later | Another deployable on an unmeasured stack | **Recommended** |
| B. Ledger inside Events (Phase 7 proposal) | No new deployable | Ads and payouts could not post without cross-service writes; revenue sharing would live in a ticketing service; a second ledger would appear for Ads | Rejected |
| C. Ledger inside Points | Existing ledger code | Points is non-cash by design; mixing breaks ADR-009, BR-011 | Rejected |
| D. Ledger per producer | Fewer cross-service calls | Violates "one approved accounting source of truth" | Rejected |
| E. Third-party accounting product | Mature controls | Cost, data residency, integration unknowns; not decided | Not now; the interfaces permit later export |

**Exit criterion.** If staging cannot carry it (DR-FIN-06 capacity), deploy as a separately imaged module only by owner decision; schema and API do not change.

## Decision 2 — Integration through signed business events, not shared data

Producers (Events, Ads, later others) record a business event in their own transactional outbox; a Celery task delivers it; **Finance's inbox accepts it once** (`accept_once` on `(source_service, source_event_id)`) and posts in the **same transaction**. Events are versioned, carry decimal-string amounts, are signed by the producer's service identity, and Finance holds an **allowlist of (source, kind)** pairs; anything else is rejected and counted. Finance never reads a producer's tables; producers never read Finance's. Producers keep operational state (an order's status, an invoice's data); Finance keeps accounting truth; a daily reconciliation compares them. **Points events are never in the allowlist.** Phase 7's per-order refund check moves to the Events order record under lock; its append-only ledger table is replaced by the outbox (see the plan's amendment list).

## Decision 3 — Accounting method

Double-entry, append-only, hash-chained journals; integer minor units after explicit `Decimal` calculation; no mutable balances; reversals by contra-journal; closed periods immutable; one book per environment (`sandbox`, `live`). Details in the [accounting design](../architecture/finance/FIN-Accounting_Design_PROPOSED.md). Immutability is enforced by database triggers and an INSERT-only runtime role, tamper evidence by hash chains, and a daily external digest.

## Decision 4 — Policy-driven calculation with no embedded values

All rates, shares, periods, thresholds and windows live in immutable, versioned, approved policy objects. The engine has **no default** for any of them and refuses to calculate without them. Every allocation records the policy hashes it used, so any figure is reproducible and attributable to an approval. Sandbox fixtures are labelled and cannot be approved for a live book.

## Decision 5 — Allocation basis and eligibility via interfaces

`BasisProvider` returns a period-final, hashed dataset; `EligibilityProvider` returns a signed snapshot. Finance defines the interface; the owning service implements it (additive changes to Engagement, Creators, Business, each needing approval). The basis is chosen by policy (DR-FIN-15) and is **never the Points ledger**; a static test scans both directions.

## Decision 6 — Providers behind interfaces; sandbox only

`RevenueStatementSource` and `PayoutProvider` interfaces with sandbox implementations (failure injection, signed notifications). No real adapter is registered; a guard test and a `live`-book guard enforce it. Payout execution is idempotent on the payout id; confirmation requires a verified signed notification **and** a server-side `retrieve` that agrees on id, amount and currency, as for ticket payments.

## Decision 7 — Control model

Maker-checker-releaser with mutually exclusive grants and per-transaction distinctness, described in the [control model](../security/phase9/FIN-Control_Model_and_Authorization_Matrix_PROPOSED.md). It applies to policies, manual revenue, adjustments, allocation approval, holds, payouts, freezes and grants. No break-glass path.

## Decision 8 — Client surfaces

Flutter for payees (creators and eligible businesses) in a **Finance section separate from Points**; the protected Django console for administrators and moderators holding finance grants only; no payee web portal, no emailed statements, no payout page on a website. Payee endpoints take no payee identifier.

## Consequences

**Positive.** One ledger, one owner; Events and Ads need no ledger; accounting correctness is testable in isolation; policy values come only from approvals; Points are structurally separate; the sandbox exercises the whole payout path without funds.

**Negative and risks.** Another service on an unmeasured stack; correctness depends on an independent accountant who is not yet named; producers do not exist, so integration is proven only against contracts and simulators; allocation inputs (basis, eligibility) need additive changes in three services; sandbox success says nothing about real provider behaviour; hash chains need external anchoring to resist a database owner; the Phase 7 and 8 packages need amendments if this is approved.

**Mitigations.** Reconciliation and invariants as acceptance gates; interface contracts with simulator tests; fail-closed defaults; the amendment list; explicit blockers.

## Compliance with the instruction

| Rule | How |
| --- | --- |
| No real payouts or transfers | `live` book guard, provider guard, sandbox adapters only |
| Points are not cash; no automatic conversion | Decision 5; static and runtime tests |
| Do not invent rates, percentages, thresholds, guarantees, commissions, periods | Decision 4; no values anywhere; engine refuses without approved parameters |
| Every rule has an approved, explicit version | Policy objects and hashes on every run |
| One source of truth; no ledger in Events, Ads, Points | Decisions 1 and 2 |
| Interfaces and business events, no cross-service reads | Decisions 2 and 5 |
| Separation of duties | Decision 7 |
| Precise decimal types | Accounting design §2 |
| Approval before implementation | Documentation only in 9A |

## Approval record

**Not approved.** Awaiting DR-FIN-01 to 08 and the named independent accounting approver.
