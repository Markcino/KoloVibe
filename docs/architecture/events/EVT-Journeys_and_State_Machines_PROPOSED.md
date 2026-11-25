# Events — journeys and server-controlled state machines (proposed)

**Status: PROPOSED — not approved.** Phase 7A, 25 November 2026. States are **server-controlled**: a client never sends a state, only a *request* (`submit`, `cancel`, …) that the server accepts or refuses.

## 1. Organizer journey (Flutter)

1. Receives an administrator grant or invitation → registers an organizer (owner assigned by the server) → state `pending_verification`.
2. Completes organizer profile → submits verification (contact proof and declaration) → reviewer decides in the console → `verified` (or an information request, one resubmission, or rejection with reason code and appeal).
3. Invites a manager and check-in staff (code, single use, 72 h) → staff redeem in their own app.
4. Creates a venue and a draft event → adds ticket types → submits for review → reviewer approves → organizer publishes (or `approved` publishes on schedule).
5. Watches the dashboard: sales, reservations, counts, refund requests.
6. Event day: a check-in staff member opens the event in the app, scans tickets; results appear instantly.
7. Optional: cancels the event (step-up + reason) → tickets revoked, refunds created, buyers see `cancelled`.

## 2. Attendee journey (Flutter)

1. Opens Discover (anonymous allowed) → searches, filters by category, county, date.
2. Opens an event → sees ticket types and availability → chooses quantities (verified email and sign-in required from here).
3. Server creates a **reservation** (10-minute hold) → app shows a countdown that is a *display* of the server `expires_at`.
4. Starts checkout → server computes the total → sandbox payment completes server-side → app polls order status → `paid` → tickets appear in **My tickets**.
5. Event day: opens a ticket, shows the QR; staff scan; ticket shows `admitted`.
6. Before the refund deadline: requests a refund → rule-based decision or review → `refunded`.
7. If something is wrong: opens a dispute from the ticket.

## 3. Reviewer and administrator journey (console, MFA)

Organizer verification queue → claim → request information or decide. Event review queue → approve, request changes or reject; later takedown with reason. Refund review → approve or reject (requester ≠ approver). Disputes → decide within the bounded outcomes. Fraud signals → review, hold or dismiss. Cancellation oversight → list of cancelled events with refund completion, stuck refunds, failures. Audit history → read-only.

## 4. State machines

### 4.1 Organizer

```mermaid
stateDiagram-v2
  [*] --> pending_verification: register (grant)
  pending_verification --> verified: reviewer approves
  pending_verification --> pending_verification: information requested, resubmitted once
  pending_verification --> rejected: reviewer rejects (reason, appeal)
  verified --> restricted: administrator (reason, notice)
  restricted --> verified: administrator restores
  verified --> suspended: administrator
  restricted --> suspended: administrator
  suspended --> verified: different administrator restores
  verified --> closed: owner closes (step-up, no open sales)
  rejected --> pending_verification: appeal upheld
  closed --> [*]
```

### 4.2 Event

```mermaid
stateDiagram-v2
  [*] --> draft
  draft --> in_review: submit (organizer verified)
  in_review --> approved: reviewer approves
  in_review --> changes_requested: reviewer asks
  in_review --> draft: organizer withdraws
  changes_requested --> in_review: organizer resubmits
  approved --> published: organizer publishes (or scheduled)
  published --> unpublished: organizer or reviewer
  unpublished --> published: organizer (revision still approved)
  published --> suspended: reviewer/administrator takedown
  suspended --> published: different reviewer restores
  published --> cancelled: organizer cancels (step-up) or administrator
  approved --> cancelled
  published --> completed: end time passes
  cancelled --> [*]
  completed --> [*]
```

A published event's *material edit* creates a new `event_revision` in `in_review`; the previous approved revision stays public until the new one is approved. The state above is on the event; revision state is `draft`, `submitted`, `approved`, `rejected`, `superseded`.

### 4.3 Reservation and order

```mermaid
stateDiagram-v2
  state "Reservation" as R {
    [*] --> active
    active --> converted: order created
    active --> expired: expires_at passes
    active --> released: buyer cancels
  }
  state "Order" as O {
    [*] --> pending_payment
    pending_payment --> paid: verified capture
    pending_payment --> failed: verified failure
    pending_payment --> expired: reservation expired, no capture
    pending_payment --> cancelled: buyer cancels
    paid --> refund_pending: refund opened
    refund_pending --> partially_refunded: part refunded
    refund_pending --> refunded: full refund
    partially_refunded --> refund_pending
    partially_refunded --> refunded
    expired --> paid: late capture + inventory available
    expired --> refund_pending: late capture, no inventory (auto refund)
  }
```

`failed`, `expired` and `cancelled` release the reservation's inventory exactly once (guarded by the reservation's own status, so a replay cannot release twice).

### 4.4 Ticket

```mermaid
stateDiagram-v2
  [*] --> valid: order paid (or free)
  valid --> admitted: check-in (atomic, once)
  valid --> revoked: event cancelled / dispute upheld / fraud hold
  valid --> refunded: refund completed
  admitted --> admitted: second scan refused (recorded)
  admitted --> [*]
```

`admitted`, `revoked` and `refunded` are terminal for admission. An `admitted` ticket is refundable only by a dispute outcome, never by the buyer rule.

### 4.5 Refund

```mermaid
stateDiagram-v2
  [*] --> requested
  requested --> approved: rule (inside policy window)
  requested --> under_review: outside rule
  under_review --> approved: refund_review (not the requester)
  under_review --> rejected
  approved --> processing: adapter call (idempotency key)
  processing --> refunded: verified provider result
  processing --> failed: verified failure
  failed --> processing: retry (bounded)
```

## 5. Money-event sequence (checkout)

```mermaid
sequenceDiagram
  participant App as Flutter app
  participant GW as Gateway
  participant EV as Events service
  participant PAY as payments module (ledger)
  participant PRV as Sandbox provider
  App->>GW: POST /events/{id}/reservations (key, ticket_type_id, qty)
  GW->>EV: signed envelope (actor, flags)
  EV->>EV: lock event + ticket types, check window/limits/capacity, hold
  EV-->>App: reservation {id, expires_at}
  App->>GW: POST /orders (reservation_id, key)  — no price sent
  EV->>PAY: compute pricing snapshot, create intent
  PAY->>PRV: create_intent(order ref, amount)
  EV-->>App: order {status: pending_payment}
  PRV-->>EV: signed notification (raw body)
  EV->>EV: verify signature, tolerance, unique provider_event_id
  EV->>PRV: retrieve(intent) — server to server
  EV->>EV: amount, currency, order ref equal?
  EV->>PAY: post financial_event(payment_captured)
  EV->>EV: order paid, issue tickets (one transaction)
  App->>GW: GET /orders/{id} (poll)
  EV-->>App: status paid
```

The redirect or return of the app from any payment screen only triggers the `GET` poll above.
