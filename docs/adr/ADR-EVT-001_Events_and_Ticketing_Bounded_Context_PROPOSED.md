# ADR-EVT-001 — Events and ticketing bounded context, money ledger and authorization model

**Status: PROPOSED — needs owner approval. Not an approved ADR.** Phase 7A, 25 November 2026.

**Identifier.** `ADR-EVT-001` is provisional; the DOC-207 register is not altered ([ADR README](README.md): drafts are not silently approved). A register number is assigned only if the owner approves.

**Decision-maker.** Mark Allen Gbalazeh (@Markcino). **Related.** ADR-001 (microservices), ADR-007 (outbox/inbox, idempotent consumers), ADR-009 (non-cash points), ADR-010 (release sequencing and financial separation), ADR-013 (identity), [ADR-BIZ-001](ADR-BIZ-001_Business_Bounded_Context_PROPOSED.md), ADR-020 (retention, open), DEC-001, PRD-F13, DOC-021 (ticketing, R3), [owner decisions](../architecture/events/EVT-Owner_Decisions_Required_PHASE7A.md).

## Context

Events and ticketing are Release 3. The approved documents defer them (DEC-001, ADR-010, DOC-021) and say payment providers must first be verified for Liberia coverage, onboarding, webhooks and fees (PRD §11). The owner has now asked for Phase 7: organizers, events, discovery, inventory, **sandbox** checkout, QR tickets and check-in on the Flutter app, and an extension of the protected Django console. No event website. No live streaming. No real payment provider without separate approval.

What exists and what does not (verified in the repository on 25 November 2026):

| Need | Exists | Consequence |
| --- | --- | --- |
| Accounts, sessions, MFA, roles | Identity (`Account.role` is one global value) | Reuse; add nothing |
| Edge, capability flags closed by default | Gateway `capabilities.py` | Add flags; keep default closed |
| Per-object authority by membership | Business (`ownership.py`, `authz.py`) | Reuse the **pattern**; services cannot share tables |
| Reviewer grants, MFA-gated queues, console | Business grants; `apps/web_django` | Reuse the pattern for event, refund and dispute review |
| Id-only audit with outbox delivery | Audit `PRODUCER_KINDS`; Business/Points audit delivery | Add a producer; reuse the delivery pattern |
| Idempotent operations, service identity, throttles | Business `api.py` (`@operation(... idempotent=...)`), `service_auth.py`, `throttle.py`, `limits.py` | Reuse the pattern |
| Step-up proof for sensitive actions | **Not built.** Business `step_up.py` fails closed; Identity P6B-04 is unapproved | Cancellation and refund approval need it (DR-EV-05) |
| Image upload and re-encode | **Not built.** Content is video-only | Event images are a blocker (DR-EV-17) |
| Money ledger | **None.** Points is explicitly non-cash; ADR-010 calls for a *separate* monetary ledger design | Design one, once (Decision 3) |
| Notification delivery | **None** | In-app status only (DR-EV-18) |
| Database role model | Open finding R-01; Business DR-BZ-32 unresolved | Ledger immutability must not rely on convention alone |

## Decision 1 — Bounded context and service boundary

Create the **Events bounded context** as a new **`events` Django/DRF service** with its own PostgreSQL schema and role, behind the Gateway, using the shared HMAC service identity.

| Option | For | Against | Verdict |
| --- | --- | --- | --- |
| A. New `events` service | Own schema and blast radius; money and check-in load isolated from sign-in and video; ships dark; consistent with ADR-001 and the Business decision | Tenth deployable: image, secrets, nonce table, verifier copy, monitoring; staging capacity unproven | **Recommended** |
| B. Module inside Business | No new deployable | Business is a *directory with no money*; its documents state "no payments, tickets"; mixing a ledger into it contradicts ADR-010 and its threat model; R3 code would ship inside an R2 service | Rejected |
| C. Two services now (`events`, `payments`) | Cleanest long-term for R4 payouts | Eleventh deployable on an unmeasured stack; cross-service saga for every order; cost with no R3 need | Rejected for now; Decision 3 keeps the extraction cheap |
| D. Module in Points | Has an append-only ledger | Points is non-cash by design (ADR-009); mixing money with points breaks ADR-010 | Rejected |
| E. Logic in the Gateway | No new service | The Gateway holds no data and stays thin | Rejected |

**Exit criterion.** If staging cannot carry a tenth service (DR-EV-07), the same code may be deployed as a separately imaged module inside an existing deployable **only by owner decision**; schema, API and authorization are unchanged.

**What stays out of the Events service:** credentials, passwords, MFA, sessions (Identity); video and media (Content); moderation of non-event content (Moderation); points (Points); payouts and settlement (R4, absent).

## Decision 2 — Authorization: organizer membership, not an Identity role

Organizer authority is `OrganizerMembership(organizer_id, account_id, role)` owned by the Events service, with roles `owner`, `manager`, `checkin`. Identity gains **no** role, field or credential store. The Gateway authenticates the bearer against Identity's live session and forwards a signed envelope with `actor_id`, role, `mfa_verified`, `email_verified` and the idempotency key; the Events service resolves membership for the specific `organizer_id` (and, for check-in staff, the specific `event_id`) on **every** request and answers **404** to a caller with no entitlement. The client never supplies an owner or account id. Moderators and administrators cannot hold memberships; their authority is their Identity role plus explicit reviewer grants (`organizer_review`, `event_review`, `dispute_review`, `fraud_review`, `refund_review`).

**Why not a role.** Same reasons as ADR-BIZ-001 Decision 2: global scope, single-role gateway assumption, Identity migrations, stale-claim risk.

## Decision 3 — One financial-event ledger, owned by a `payments` module

All money facts are rows in **one append-only `financial_event` table**, written only by the `payments` module of the Events service, in the same transaction as the state change they describe. Everything else is derived:

- An order's amounts live in an immutable pricing snapshot; its *money state* is the sum of its financial events, not a mutable balance column.
- Refund totals are checked against captured totals **from the ledger** under a row lock.
- "Owed to organizer" is a derived report. There is no payout operation.

**Enforcement.** Application code has no `update`/`delete` path on the table; a database trigger rejects `UPDATE` and `DELETE` (works whatever the role model, DR-EV-06); each row carries `prev_hash` and `hash` over its canonical content so tampering or reordering is detectable by a verification command; `idempotency_key` is unique so a replay cannot post twice.

**DRY.** Points keeps its non-cash ledger untouched. The **pattern** is reused, not the tables: append-only entries, written in the deciding transaction, with an audit outbox. The `payments` package exposes one interface (`post(event)`, `captured_total(order)`, `refunded_total(order)`); no other module imports its models. That boundary is what makes extraction into a service for R4 a move, not a rewrite.

## Decision 4 — Payment adapter and verified confirmation

A `PaymentProvider` interface: `create_intent`, `verify_notification(raw_body, headers)`, `retrieve(intent_ref)`, `refund(payment_ref, amount, key)`. Phase 7 ships **one** adapter, `sandbox`. A guard test fails the build if any other adapter is registered without an approval constant naming the owner decision (modelled on the Gateway prior-release guard).

**Confirmation rule.** A payment is `captured` only when **all** hold, evaluated server-side in one transaction: the notification signature verifies over the raw body with a timestamp tolerance; its `provider_event_id` is new (unique constraint, so replays are no-ops); `retrieve(intent_ref)` returns a successful status; and the retrieved amount, currency and order reference equal the stored order. The notification body is a *trigger*, never the source of truth. A browser or app redirect is a UI hint that causes a status refresh; it never changes an order.

**Sandbox realism.** The sandbox provider is an in-process simulator that signs notifications with a sandbox key and answers `retrieve`, so the production verification path is exercised end to end without a public webhook. A public inbound webhook (the first external inbound call the platform would receive) is an infrastructure and security change that belongs to the real-provider approval, not to Phase 7.

## Decision 5 — Inventory: transactional, with a lazy expiry

`ticket_type` carries `quantity_total`, `reserved_count`, `sold_count`. Reservation is one transaction: lock the event row, then the ticket-type rows in id order, check the sales window, per-order and per-account limits, and the event capacity, increment `reserved_count`, insert the reservation with `expires_at`. A database `CHECK (reserved_count + sold_count <= quantity_total)` is the backstop. **Expiry never depends on a scheduler for correctness:** every reservation or purchase first releases expired holds for the rows it locks; the scheduled `expire_reservations` job (the same pattern as the existing audit-delivery jobs) only keeps counters tidy. Sold-out is derived from the counters, not stored.

## Decision 6 — Tickets and the QR credential

One `ticket` row per purchased unit, created in the same transaction that marks the order paid, owned by the buyer's `account_id`. The QR payload is `v1.<ticket_public_id>.<credential_version>.<mac>` where `ticket_public_id` is a random 128-bit value and the MAC is HMAC-SHA-256 under a versioned signing key held only by the Events service (key rotation by version, as the Business signing-key tests do). It contains **no personal data**. Validation is always online: verify MAC, load the ticket, check event match and status, then admit with one conditional `UPDATE ... WHERE status = 'valid'`; zero rows updated means someone else was admitted first. Every attempt, including refusals, is written to an append-only `checkin_event`.

## Decision 7 — Offline check-in: not built; model for approval

The instruction permits offline check-in only if its conflict and reconciliation model is approved. Because venue connectivity in Liberia is often poor, a model is proposed here so the owner can decide knowingly. **Nothing is built in Phase 7.**

| Aspect | Proposal |
| --- | --- |
| Manifest | A scanner device with an active `checkin` assignment downloads a signed, time-boxed manifest for one event: for each ticket, only a keyed hash of `ticket_public_id`, ticket type, and status at download time; no personal data; encrypted at rest on the device with a per-device key |
| Device trust | Per-device registration under step-up; revoking an assignment revokes the device key; the manifest expires at event end plus a short grace |
| Offline scan | The device decides `admit` or `refuse` from the manifest, records an append-only signed local log (ticket hash, time, device, gate) and never overwrites |
| Reconciliation | On reconnection the log is uploaded; the server replays it in **device time order within a bounded skew**; the **first valid scan wins**; any later admission of the same ticket from another device is recorded as a **conflict**, never silently dropped |
| Known residual risks (shown to staff) | Two devices can admit the same screenshot while both are offline; revocations and refunds issued after download are not seen; clocks can be wrong. The conflict list goes to the organizer and to `fraud_review`; it never auto-penalises an attendee |
| Verdict | Recommended **later**, as its own task, after online check-in has run in a pilot |

## Decision 8 — Client surfaces

Flutter for visitors, buyers, organizers and check-in staff; the protected Django console for moderators and administrators only; **no event website, no ticket web page, no emailed ticket link**. The QR is rendered only inside the app. No browser origin, cookie session or CORS exists for this service (DR-BZ-21 carried over). Anonymous discovery reads are a mobile convenience and must never be treated as a website.

## Decision 9 — Listing projection and search

Public reads use an `event_listing` projection holding only public columns, written transactionally when the eligibility predicate changes (published, current approved revision, organizer in good standing). One predicate function is used by every public query. Search is substring plus category and date filters with a keyset cursor over `(starts_at, id)`, as the Business pilot decision DR-BZ-30 did; an index is a measured later decision. No search engine or cache is introduced.

## Consequences

**Positive.** One money ledger and one place that can post to it; inventory correctness does not depend on a scheduler; the payment path is exercised fully in the sandbox without any real provider; no PII beyond `account_id` in the new service; dark by default and removable without touching R1/R2.

**Negative and risks.** A tenth service on an unmeasured stack; the membership logic is a second copy of a pattern (mitigation: shared-identity drift test, structure check and one authorization test matrix); step-up and image pipeline dependencies are unapproved, so cancellation, refund approval and event images are partly blocked; sandbox success is **not** evidence of a real provider's behaviour (webhook ordering, partial captures, delayed settlement, chargebacks); offline check-in is a real operational gap at venues.

**Mitigations.** Closed flags for every operation; ledger trigger plus hash chain plus a verification command; adapter-registration guard test; reconciliation test comparing the sandbox settlement report to the ledger; the explicit blocker list in the owner decisions.

## Compliance with the instruction

| Rule | How the design complies |
| --- | --- |
| Reuse Identity, Gateway, Audit, media controls, design tokens, API patterns | Decisions 2, 8; Audit producer; no new auth; media/image blocked rather than duplicated |
| No duplicate auth, no ledgers in multiple services | Decision 3: one ledger, one writer, Points untouched |
| No real provider; no redirect as confirmation | Decision 4 |
| Server-controlled publication states | [State machines](../architecture/events/EVT-Journeys_and_State_Machines_PROPOSED.md); client never sends a state |
| Offline check-in only if approved | Decision 7: not built |
| No event website, no live streaming | Decision 8; none planned |
| No migrations, no AWS change in 7A | Documentation only |

## Approval record

**Not approved.** Awaiting the owner's decisions DR-EV-01 to DR-EV-07 and the gates that follow.
