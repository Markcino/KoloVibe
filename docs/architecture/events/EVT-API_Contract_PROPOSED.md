# Events API contract (proposed)

**Status: PROPOSED — not approved; not yet in DOC-205.** 25 November 2026. On approval the operations below become OpenAPI 3.1 in `packages/contracts/openapi` and the existing contract-reconciliation test (as for Business: contract ⇄ Gateway routes ⇄ service registry ⇄ console ⇄ Dart models) is extended to cover them. Paths are under `/api/v1`. The client **never** sends an owner, account, state, price, fee, total or role.

## Conventions

| Item | Rule |
| --- | --- |
| Capability flags | `event_organizer`, `event_discovery`, `event_checkout`, `event_tickets`, `event_checkin`, `event_admin`; all closed by default; with all closed no route below is served |
| Auth | Bearer token authenticated by the Gateway against Identity's live session; the Events service trusts only the signed envelope |
| Flags in tables | **MFA** = `mfa_verified` required; **VE** = verified email required; **ID** = `Idempotency-Key` required (replay returns the stored answer; same key with a different body → 409); **SU** = step-up proof (fails closed until DR-EV-05) |
| Non-entitled caller | **404**, never 403, for object-level denial; 403 only when the Gateway role check refuses before forwarding |
| Pagination | Keyset cursor; bounded page size; no total counts on public lists |
| Errors | `{detail, code}` bounded, no internals, no echo of input |
| Throttles | Per-actor budgets from a `limits.py` equivalent (values per DR-EV-23) |

## E1 — Organizer management (`event_organizer`)

| Operation | Method and path | Caller | Flags | Notes |
| --- | --- | --- | --- | --- |
| `organizer_register` | POST `/organizers` | signed-in account with a grant | VE, ID | Owner is the caller; refused with `grant_required` otherwise |
| `organizer_mine` | GET `/organizers/mine` | member | — | Memberships of the caller |
| `organizer_get` | GET `/organizers/{id}` | member | — | |
| `organizer_update` | PATCH `/organizers/{id}` | owner, manager | — | Allowlisted fields; material changes re-verify |
| `organizer_dashboard` | GET `/organizers/{id}/dashboard` | owner, manager | — | Counts only, no buyer identity |
| `organizer_verification_submit` | POST `/organizers/{id}/verification` | owner | ID | |
| `organizer_verification_get` | GET `/organizers/{id}/verification` | owner, manager | — | Own status and reason codes |
| `organizer_verification_respond` | POST `/organizers/{id}/verification/respond` | owner | ID | Answer to an information request |
| `team_list` | GET `/organizers/{id}/members` | owner, manager | — | |
| `team_invite` | POST `/organizers/{id}/invitations` | owner | ID | Returns a one-time code once |
| `team_invitation_revoke` | DELETE `/organizers/{id}/invitations/{inv}` | owner | — | |
| `team_redeem` | POST `/organizers/invitations/redeem` | signed-in | VE, ID | Single use; throttled |
| `team_role_change` | PATCH `/organizers/{id}/members/{m}` | owner | **SU** | |
| `team_remove` | DELETE `/organizers/{id}/members/{m}` | owner | **SU** | A member may leave (own removal) |
| `organizer_close` | POST `/organizers/{id}/close` | owner | **SU**, ID | Refused with open sales |

## E2 — Event management (`event_organizer`)

| Operation | Method and path | Caller | Flags | Notes |
| --- | --- | --- | --- | --- |
| `venue_create` / `venue_list` / `venue_update` | POST, GET `/organizers/{id}/venues`; PATCH `…/{v}` | owner, manager | ID on create | |
| `event_create` | POST `/organizers/{id}/events` | owner, manager | ID | Verified organizer to publish; draft allowed earlier |
| `event_list_mine` | GET `/organizers/{id}/events` | member | — | Filter by state |
| `event_get_mine` | GET `/organizers/{id}/events/{e}` | member | — | Includes revision and review status |
| `event_update` | PATCH `/organizers/{id}/events/{e}` | owner, manager | — | Optimistic `version`; material edits to published → new revision |
| `event_submit` | POST `…/{e}/submit` | owner, manager | ID | Request, not a state set |
| `event_withdraw` | POST `…/{e}/withdraw` | owner, manager | — | |
| `event_publish` / `event_unpublish` | POST `…/{e}/publish`, `…/unpublish` | owner, manager | ID | `publish` only from `approved` |
| `event_cancel` | POST `…/{e}/cancel` | owner | **SU**, ID | Reason code; creates refunds; atomic |
| `categories_list` | GET `/event-categories` | any | — | Public, static-ish |

## E3 — Discovery (`event_discovery`, anonymous allowed)

| Operation | Method and path | Caller | Notes |
| --- | --- | --- | --- |
| `event_search` | GET `/events?q=&category=&county=&from=&to=&cursor=` | anyone | Reads `event_listing` only; allowlisted query params; bounded `q` length |
| `event_detail` | GET `/events/{e}` | anyone | Public columns; cancelled shown only to ticket holders |
| `event_ticket_types` | GET `/events/{e}/ticket-types` | anyone | Price, currency, availability **band**, window state; no exact counts |

## E4 — Ticket types and reservations

| Operation | Method and path | Caller | Flags | Notes |
| --- | --- | --- | --- | --- |
| `ticket_type_create` / `update` / `list` | POST, PATCH, GET `/organizers/{id}/events/{e}/ticket-types` | owner, manager | `event_organizer`, ID on create | Cannot cut quantity below sold plus reserved |
| `ticket_type_pause` | POST `…/{t}/pause` | owner, manager | — | |
| `reservation_create` | POST `/events/{e}/reservations` | buyer | `event_checkout`, VE, ID | Body: `[{ticket_type_id, quantity}]` only |
| `reservation_get` | GET `/reservations/{r}` | owner of reservation | `event_checkout` | |
| `reservation_release` | DELETE `/reservations/{r}` | owner of reservation | `event_checkout` | Idempotent |

## E5 — Checkout, orders, refunds (`event_checkout`)

| Operation | Method and path | Caller | Flags | Notes |
| --- | --- | --- | --- | --- |
| `order_create` | POST `/orders` | buyer | VE, ID | Body: `reservation_id` only; server prices |
| `order_get` | GET `/orders/{o}` | buyer | — | Status, totals from the snapshot; **the poll target** |
| `order_list_mine` | GET `/orders` | buyer | — | |
| `order_cancel` | POST `/orders/{o}/cancel` | buyer | ID | Only `pending_payment` |
| `payment_notify` | POST `/internal/payments/{provider}/notifications` | **service-to-service only** (sandbox simulator) | signature, no bearer | Not exposed through the public Gateway in Phase 7; raw body verified; replay → 200 no-op |
| `refund_request` | POST `/orders/{o}/refund-requests` | buyer | VE, ID | Body: ticket ids and reason code; amount computed by server |
| `refund_get` | GET `/refunds/{r}` | requester | — | |
| `organizer_orders` | GET `/organizers/{id}/events/{e}/orders` | owner, manager | `event_organizer` | Aggregates and ids only; **no buyer identity** |

## E6 — Tickets and check-in

| Operation | Method and path | Caller | Flags | Notes |
| --- | --- | --- | --- | --- |
| `ticket_list_mine` | GET `/tickets` | buyer | `event_tickets` | |
| `ticket_get` | GET `/tickets/{t}` | owner of ticket | `event_tickets` | |
| `ticket_credential` | GET `/tickets/{t}/credential` | owner of ticket | `event_tickets` | Returns the signed credential for local QR rendering; `Cache-Control: no-store`; never logged |
| `ticket_dispute_open` | POST `/tickets/{t}/disputes` | owner of ticket | `event_tickets`, ID | |
| `checkin_assign` / `checkin_unassign` | POST, DELETE `/organizers/{id}/events/{e}/checkin-staff` | owner, manager | `event_organizer`, ID | Target must be an active `checkin` member |
| `checkin_scan` | POST `/events/{e}/checkin` | assigned `checkin`, owner, manager | `event_checkin`, ID per scan id | Body: credential, optional gate; **result codes**: `admitted`, `already_admitted` (with time, gate), `revoked`, `refunded`, `wrong_event`, `not_open`, `invalid` |
| `checkin_summary` | GET `/events/{e}/checkin/summary` | assigned, owner, manager | `event_checkin` | Counts only |

## E7 — Administration (`event_admin`, console only; MFA on every operation)

| Operation | Method and path | Caller (grant) | Flags | Notes |
| --- | --- | --- | --- | --- |
| `admin_organizer_queue` / `case_get` | GET `/admin/organizers/verification…` | reviewer (`organizer_review`) | MFA | Audited evidence reads |
| `admin_organizer_claim` / `decide` | POST `…/claim`, `…/decision` | reviewer (`organizer_review`) | MFA, ID | Claim then decide; double-submit safe |
| `admin_organizer_restrict` / `suspend` / `restore` | POST `/admin/organizers/{id}/…` | administrator | MFA, SU, ID | Restorer ≠ suspender |
| `admin_event_queue` / `get` | GET `/admin/events/review…` | reviewer (`event_review`) | MFA | |
| `admin_event_decide` | POST `/admin/events/{e}/revisions/{r}/decision` | reviewer (`event_review`) | MFA, ID | Reviewer ≠ organizer member |
| `admin_event_takedown` / `restore` | POST `/admin/events/{e}/suspend`, `/restore` | reviewer (`event_review`) | MFA, ID | Different reviewer restores |
| `admin_event_cancel` | POST `/admin/events/{e}/cancel` | administrator | MFA, SU, ID | For fraud or safety takedown beyond suspension; same atomic refunds as the organizer path; reason code |
| `admin_cancellations` | GET `/admin/events/cancellations` | administrator, `refund_review` | MFA | Stuck or failed refunds |
| `admin_refund_queue` / `decide` | GET, POST `/admin/refunds…` | reviewer (`refund_review`) | MFA, **SU** on decide, ID | Requester ≠ approver; second approver above threshold |
| `admin_dispute_queue` / `decide` | GET, POST `/admin/disputes…` | reviewer (`dispute_review`) | MFA, ID | Bounded outcomes |
| `admin_fraud_queue` / `decide` | GET, POST `/admin/fraud…` | reviewer (`fraud_review`) | MFA, ID | Hold or dismiss; never auto-penalise |
| `admin_grants` | GET, POST, DELETE `/admin/event-grants` | administrator | MFA, SU | |
| `admin_ledger_verify` | GET `/admin/ledger/verify` | administrator | MFA | Hash-chain check, read-only |
| `admin_audit_read` | existing Audit reader | administrator | MFA | New `events` producer kinds |

## Audit kinds (new producer `events`; Audit's `PRODUCER_KINDS` gains one entry — a change to an existing service that needs approval)

`organizer.registered`, `organizer.membership_granted`, `organizer.membership_revoked`, `organizer.invitation_created`, `organizer.invitation_redeemed`, `organizer.verification_submitted`, `organizer.verification_decided`, `organizer.status_changed`, `event.created`, `event.submitted`, `event.review_decided`, `event.published`, `event.unpublished`, `event.suspended`, `event.cancelled`, `ticket_type.changed`, `reservation.created`, `reservation.expired`, `order.created`, `order.paid`, `order.failed`, `order.expired`, `payment.notification_received`, `payment.notification_replayed`, `payment.notification_rejected`, `refund.requested`, `refund.decided`, `refund.settled`, `ticket.issued`, `ticket.revoked`, `checkin.admitted`, `checkin.refused`, `dispute.opened`, `dispute.decided`, `fraud.signal_decided`, `ledger.adjustment_posted`, `admin.queue_read`, `admin.case_read`. Every event carries ids and codes only: no names, contacts, credentials, payload bodies or free text.

## Open contract questions (for approval)

1. `payment_notify` is internal-only in Phase 7. A public provider webhook needs an ingress and TLS change (infrastructure) and is part of the real-provider approval (DR-EV-22).
2. `ticket_credential` returns the credential to the app so the QR renders offline-from-network on the phone; this is **not** offline check-in. A rotating credential is a later option (DR-EV-40).
3. About 75 operations (counted from the tables above, grouped operations counted by method); on approval they are split over six flags as Business's 57 were over five. The exact number is fixed when the OpenAPI file is written.
