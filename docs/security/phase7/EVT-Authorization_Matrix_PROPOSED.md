# Events — role and object-level authorization matrix (proposed)

**Status: PROPOSED — not approved.** 25 November 2026. Companion to the [API contract](../../architecture/events/EVT-API_Contract_PROPOSED.md) and the Business [RBAC and object-authorization matrix](../phase6/BIZ-RBAC_and_Object_Authorization_Matrix_PROPOSED.md). Every operation must name a row here; the same contract-reconciliation test that checks Business (every operation names a real matrix row) is extended to Events.

## Rules that apply to every row

1. **Default deny.** No grant, no access. All flags closed by default.
2. **Object-level, derived on the server.** Authority is resolved per request from the stored membership, assignment or grant. The client never supplies an organizer, account, role or state.
3. **404, not 403, for non-entitlement** on object routes, so existence is not revealed.
4. **Separation of duties.** The submitter of a case is never its decider; a suspender is never the restorer; a refund requester is never its approver; a reviewer cannot review an organizer or event they are a member of (and moderators/administrators cannot hold memberships at all).
5. **MFA** on every console operation; **step-up** (when Identity provides it) on cancellation, refund approval, team-role change, organizer closure, grants.
6. **Check-in staff are scoped to events** through `checkin_assignment`, not to the whole organizer.
7. **No buyer identity** reaches organizers, staff or check-in results.

## Legend

`✔` allowed · `own` only objects the caller owns · `m` as a member of the object's organizer · `—` denied (404 on objects, 401/403 otherwise) · `G(x)` needs reviewer grant `x` · `SU` step-up

## Actors

| Code | Actor |
| --- | --- |
| ANON | Anonymous visitor |
| BUY | Signed-in account (verified email to buy) |
| OWN | Organizer `owner` |
| MGR | Organizer `manager` |
| CHK | Organizer `checkin` member **with** an assignment to the event |
| NON | Signed-in non-member of the organizer |
| MOD | Moderator without a relevant grant |
| REV | Moderator with the named grant, MFA |
| ADM | Administrator, MFA |
| SVC | Service identity (sandbox provider, Audit) |

## Matrix

| Operation group | ANON | BUY | OWN | MGR | CHK | NON | MOD | REV | ADM | SVC | Object rule |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Register organizer | — | ✔ with grant | — | — | — | — | — | — | grants | — | Owner = caller; limit per account |
| Read/update own organizer | — | — | ✔ | read; update limited | read | — | — | — | — | — | `organizer_id` must match an active membership |
| Dashboard | — | — | ✔ | ✔ | — | — | — | — | — | — | Counts only |
| Verification submit/respond | — | — | ✔ | — | — | — | — | — | — | — | Own organizer |
| Verification queue/decide | — | — | — | — | — | — | — | G(organizer_review) | — | — | Not a member of that organizer; claim then decide |
| Team invite/remove/role change | — | — | ✔ SU | — | — | — | — | — | — | — | Cannot remove the last owner |
| Redeem invitation | — | ✔ | — | — | — | — | — | — | — | — | Code single use, throttled, constant-time compare |
| Venue CRUD | — | — | ✔ | ✔ | — | — | — | — | — | — | Own organizer |
| Event draft CRUD, submit, withdraw | — | — | ✔ | ✔ | — | — | — | — | — | — | Own organizer; server-only `state` |
| Event publish/unpublish | — | — | ✔ | ✔ | — | — | — | — | — | — | `publish` only from `approved`; organizer in good standing |
| **Event cancel** | — | — | ✔ SU | — | — | — | — | — | ✔ SU | — | Reason code; atomic refunds |
| Event review decision | — | — | — | — | — | — | — | G(event_review) | — | — | Reviewer not a member of that organizer |
| Event takedown / restore | — | — | — | — | — | — | — | G(event_review) | ✔ | — | Different reviewer restores |
| Organizer restrict/suspend/restore | — | — | — | — | — | — | — | — | ✔ SU | — | Restorer ≠ suspender |
| Ticket type CRUD, pause | — | — | ✔ | ✔ | — | — | — | — | — | — | Cannot cut below sold+reserved; price edits never touch orders |
| Discovery reads | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | — | `event_listing` only |
| Cancelled event detail | — | own tickets | own tickets | — | — | — | — | — | ✔ | — | |
| Reservation create/get/release | — | own | — | — | — | — | — | — | — | — | Verified email; limits |
| Order create/get/list/cancel | — | own | — | — | — | — | — | — | — | — | Owner of order |
| Provider notification | — | — | — | — | — | — | — | — | — | ✔ (signed) | Signature + replay + retrieve |
| Refund request/get | — | own | — | — | — | — | — | — | — | — | Own order; policy window |
| Organizer order aggregates | — | — | ✔ | ✔ | — | — | — | — | — | — | No buyer identity |
| My tickets, credential | — | own | own | own | own | own | own | own | own | — | Owner of ticket only |
| Open dispute | — | own | — | — | — | — | — | — | — | — | Own ticket |
| Assign check-in staff | — | — | ✔ | ✔ | — | — | — | — | — | — | Target is an active `checkin` member |
| **Scan / check-in** | — | — | ✔ | ✔ | ✔ assigned | — | — | — | — | — | Event must match the assignment; result excludes buyer identity |
| Check-in summary | — | — | ✔ | ✔ | ✔ assigned | — | — | — | — | — | Counts |
| Refund queue/decide | — | — | — | — | — | — | — | G(refund_review) SU | ✔ SU | — | Requester ≠ approver; second approver above threshold |
| Dispute queue/decide | — | — | — | — | — | — | — | G(dispute_review) | ✔ | — | Bounded outcomes |
| Fraud queue/decide | — | — | — | — | — | — | — | G(fraud_review) | ✔ | — | |
| Grants | — | — | — | — | — | — | — | — | ✔ SU | — | |
| Ledger verify | — | — | — | — | — | — | — | — | ✔ | — | Read-only |
| Audit history | — | — | — | — | — | — | — | — | ✔ | ✔ ingest | Id-only |

## Cross-organizer isolation (the first E8 test)

A caller who is a full `owner` of organizer A must receive **404** for every organizer-scoped operation on organizer B, on B's events, ticket types, orders, check-in, invitations and members; and a CHK for event X must be refused for event Y of the *same* organizer. The test is generated from the operation registry so a new operation cannot ship without an entry.
