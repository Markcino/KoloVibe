# Events and ticketing — requirements (PRD and SRS content), proposed

**Status: PROPOSED — not approved.** Phase 7A, 25 November 2026. Proposed content for PRD-F13 and DOC-021. Release 3 per the approved PRD; development-only, sandbox payments, closed flags, production NO-GO until the owner decides otherwise ([DR-EV-01](../architecture/events/EVT-Owner_Decisions_Required_PHASE7A.md)). Priority key: **M** must, **S** should, **P** proposed policy needing a value or a decision.

## 1. Purpose and scope

Let verified organizers publish events, let people find events and buy tickets in the Flutter app, issue tamper-resistant tickets, and admit attendees once. Give moderators and administrators protected tools to verify organizers, review and take down events, and handle refunds, disputes and fraud.

**In scope:** organizer onboarding and team; events, venues, categories, publication review; discovery; ticket types and inventory; reservations; sandbox checkout; order and refund states; financial-event records; ticket issuance, QR credential, online check-in; console administration; audit.

**Out of scope (explicit):** live streaming; an event website, ticket web page or emailed ticket link; any real payment provider; payouts and organizer settlement (R4); ticket transfer, gifting, resale; offline check-in (model proposed in ADR-EVT-001 Decision 7, not built); push, SMS or email delivery; seating charts; recurring events; promotion, advertising and paid placement; refunds to anything other than the original payment method.

## 2. Actors

| Actor | Surface | Notes |
| --- | --- | --- |
| Visitor (anonymous) | Flutter | Discovery reads only |
| Buyer / attendee | Flutter | Signed-in account; verified email to buy |
| Organizer owner / manager | Flutter | Per-organizer membership |
| Check-in staff | Flutter | Per-event assignment; scan only |
| Reviewer (moderator with a grant) | Console | MFA; scoped grants |
| Administrator | Console | MFA, step-up; grants, non-rule refunds, restoration |
| Payment provider | Server to server | Sandbox only |
| Audit, Gateway, Identity | Platform | Reused |

## 3. Functional requirements

IDs are `EV-R-nnn`. Slice in brackets.

### E1 Organizer management

| ID | Requirement | Pri |
| --- | --- | --- |
| EV-R-001 | An account registers an organizer only with an administrator grant or invitation (DR-EV-10); the owner is assigned by the server | M |
| EV-R-002 | An organizer has states `pending_verification`, `verified`, `rejected`, `restricted`, `suspended`, `closed`; only the server changes state | M |
| EV-R-003 | Verification is a case with reviewer decision, reason code, resubmission limit and validity period; no files until DR-EV-17 | M/P |
| EV-R-004 | An unverified organizer may draft events but cannot publish; a paid event requires `verified` | M |
| EV-R-005 | Roles `owner`, `manager`, `checkin`; membership by invitation code (one use, TTL); removal and role change need step-up | M/P |
| EV-R-006 | Moderators and administrators cannot hold memberships | M |
| EV-R-007 | `restricted`: no new events, existing sales continue; `suspended`: events hidden, sales paused, paid tickets **not** cancelled automatically; both carry reason code, notice and an appeal path | M/P |
| EV-R-008 | Flutter organizer dashboard: verification status, events by state, sales and attendance counts, refund requests | M |

### E2 Event management

| ID | Requirement | Pri |
| --- | --- | --- |
| EV-R-010 | Create, edit and delete drafts; an event belongs to exactly one organizer; the server derives the organizer from the path and membership | M |
| EV-R-011 | Fields: title, description (plain text, bounded), category, venue, start and end (stored UTC, shown `Africa/Monrovia` by default), capacity, refund policy | M |
| EV-R-012 | Venues are organizer-owned records (name, address line, county, city); coordinates private unless decided otherwise | M |
| EV-R-013 | Publication states are server-controlled: `draft`, `in_review`, `changes_requested`, `approved`, `published`, `unpublished`, `cancelled`, `completed`, `suspended`; a client can only *request* `submit`, `withdraw`, `unpublish`, `cancel` | M |
| EV-R-014 | A reviewer with `event_review` approves or rejects with a reason code; the organizer and reviewer cannot be the same account | M |
| EV-R-015 | Material edits to a published event create a revision that is reviewed; the approved revision stays live meanwhile; capacity cannot go below sold plus reserved | M/P |
| EV-R-016 | Cancellation requires step-up and a reason code; atomically revokes tickets and creates the full-refund obligation (EV-R-061) | M |
| EV-R-017 | Visibility is `draft` or `public` only (DR-EV-16) | M |
| EV-R-018 | Event images: blocked until the shared image pipeline exists (DR-EV-17); placeholder artwork by category | blocker |
| EV-R-019 | Organizer-owned event lists, filtered by state, keyset-paged | M |

### E3 Discovery (Flutter)

| ID | Requirement | Pri |
| --- | --- | --- |
| EV-R-020 | Discovery list of upcoming public events; search by text; filters by category, county and date range; keyset paging | M |
| EV-R-021 | Event detail with ticket types, price, availability band (`available`, `low`, `sold_out`) and sales window state | M |
| EV-R-022 | Only the single eligibility predicate decides what is public; cancelled events remain visible to ticket holders only | M |
| EV-R-023 | My tickets and booking status screens reflect server state (polled); no local state is trusted | M |
| EV-R-024 | Event notifications: in-app status only (DR-EV-18) | blocker |

### E4 Ticket inventory

| ID | Requirement | Pri |
| --- | --- | --- |
| EV-R-030 | Ticket types: name, price (integer minor units), currency, quantity, sales window, per-order maximum | M |
| EV-R-031 | The sum of ticket-type quantities cannot exceed event capacity; sold plus reserved never exceeds quantity (database check as backstop) | M |
| EV-R-032 | A reservation is one transaction, idempotent per account and key, holds inventory until `expires_at`, and is released on expiry, cancellation or payment failure | M |
| EV-R-033 | Expiry correctness does not depend on a scheduler | M |
| EV-R-034 | Concurrent purchases never oversell; the last ticket goes to exactly one buyer | M |
| EV-R-035 | Limits: per order, per account per event, reservation rate (values in DR-EV-23) | P |
| EV-R-036 | Sold-out is derived; sales outside the window are refused with a distinct code | M |
| EV-R-037 | Free tickets (price 0) skip payment and use the same path (DR-EV-31) | P |
| EV-R-038 | A ticket-type price or quantity change never alters existing orders; quantity cannot fall below sold plus reserved | M |

### E5 Sandbox checkout

| ID | Requirement | Pri |
| --- | --- | --- |
| EV-R-040 | Checkout starts from a live reservation; the client sends ticket-type ids and quantities only, **never a price, fee or total** | M |
| EV-R-041 | The server computes subtotal, fee, tax and total from stored prices and the versioned fee policy, and stores an immutable pricing snapshot on the order | M |
| EV-R-042 | One order per reservation; an idempotency key makes a retry return the same order; reuse of a key with a different body is refused | M |
| EV-R-043 | Only the sandbox adapter exists; registering any other adapter fails a build guard | M |
| EV-R-044 | A payment is captured only after signature verification, replay check, server-side `retrieve` and equality of amount, currency and order reference | M |
| EV-R-045 | A redirect or client report is never payment confirmation | M |
| EV-R-046 | Notification handling is idempotent: a replay answers 200 and changes nothing | M |
| EV-R-047 | Order states `pending_payment`, `paid`, `failed`, `expired`, `cancelled`, `refund_pending`, `partially_refunded`, `refunded`; transitions only by the server | M |
| EV-R-048 | Failed or expired payment releases inventory exactly once | M |
| EV-R-049 | Late confirmation after expiry follows DR-EV-24 | P |
| EV-R-050 | Every money fact is an append-only `financial_event` in the same transaction as its state change | M |

### Refunds and disputes

| ID | Requirement | Pri |
| --- | --- | --- |
| EV-R-060 | Refund states `requested`, `under_review`, `approved`, `processing`, `refunded`, `rejected`, `failed`; one open refund per ticket; amount never above captured minus already refunded, checked from the ledger under lock | M |
| EV-R-061 | Event cancellation creates a full refund (fee included) for every paid order, automatically and idempotently | P |
| EV-R-062 | Buyer-requested refunds follow the event's refund policy (DR-EV-25); rule-based approval is automatic, anything else is reviewed | P |
| EV-R-063 | A refund approver cannot be the requester; amounts above a threshold need a second approver (DR-EV-27) | P |
| EV-R-064 | A refunded or revoked ticket can never be admitted | M |
| EV-R-065 | Disputes are cases with a reason code, evidence references (check-in log, order, ticket) and a bounded set of outcomes (DR-EV-28) | P |

### E6 Tickets and check-in

| ID | Requirement | Pri |
| --- | --- | --- |
| EV-R-070 | Tickets are issued only when the order becomes `paid` (or free), one per unit, owned by the buyer | M |
| EV-R-071 | The QR credential is signed, versioned and contains no personal data | M |
| EV-R-072 | Validation checks signature, event match, ticket status, event window and the scanner's assignment | M |
| EV-R-073 | Admission is a single atomic transition; the second scan is refused with the first admission's time and gate | M |
| EV-R-074 | Revocation or cancellation invalidates the ticket immediately for the next scan | M |
| EV-R-075 | Every scan attempt is recorded append-only, including refusals | M |
| EV-R-076 | Check-in staff see only the result, ticket type and prior-admission details, never buyer identity (DR-EV-43) | M |
| EV-R-077 | Offline check-in is not provided | deferred |

### E7 Event administration (console)

| ID | Requirement | Pri |
| --- | --- | --- |
| EV-R-080 | Pages: organizer verification; event review and moderation (including takedown); ticket disputes; fraud review; cancellation oversight; refund review; audit history | M |
| EV-R-081 | MFA on every page; every state-changing action needs the correct grant and, for refund approval and cancellation override, step-up; double-submit safe (the Business claim, confirm, decision form pattern) | M |
| EV-R-082 | Reviewers see only what their grant scope covers; evidence reads are audited | M |
| EV-R-083 | Audit history is read-only and id-only (no personal data, no free text) | M |

### Cross-cutting

| ID | Requirement | Pri |
| --- | --- | --- |
| EV-R-090 | Every operation: Gateway capability flag (closed by default), service-identity envelope, role check, per-object authorization with 404 for non-entitled callers, allowlist input validation, throttle | M |
| EV-R-091 | Every state change writes an id-only audit event in the deciding transaction, delivered by outbox | M |
| EV-R-092 | The Events service stores no buyer name, email or phone; only `account_id` | M |
| EV-R-093 | Logs and audit never contain tokens, QR credentials, provider secrets, payloads or free text | M |
| EV-R-094 | The service owns its schema and role; no cross-service table access; no foreign keys across services | M |
| EV-R-095 | Provider keys, QR signing keys and webhook secrets are configuration secrets with rotation by version; never in the repository | M |
| EV-R-096 | Retention per DR-EV-30 and ADR-020; until decided nothing is purged | P |

## 4. Non-functional requirements

| ID | Requirement |
| --- | --- |
| EV-N-01 | Correctness over speed for inventory, ledger and admission; tests must prove no oversell, no double post, no double admission under concurrency |
| EV-N-02 | Check-in validation p95 under 500 ms on the staging stack once measured (a target, not a claim; measured in Phase 11) |
| EV-N-03 | Money is integer minor units; no floating point anywhere |
| EV-N-04 | All times stored UTC; display time zone explicit |
| EV-N-05 | Public reads use a projection with no private columns by construction |
| EV-N-06 | Every Flutter screen follows the existing design tokens, accessibility and large-text layout audit used for Business |
| EV-N-07 | Closed flags: with every flag closed, no Events route is reachable |

## 5. Traceability

Each requirement maps to an API operation ([contract](../architecture/events/EVT-API_Contract_PROPOSED.md)), an authorization row ([matrix](../security/phase7/EVT-Authorization_Matrix_PROPOSED.md)), a threat ([STRIDE](../security/phase7/EVT-STRIDE_Threat_Model_PROPOSED.md)) and an acceptance test ([acceptance and delivery plan](../engineering/phase7/EVT-Acceptance_and_Delivery_Plan_PROPOSED.md)).
