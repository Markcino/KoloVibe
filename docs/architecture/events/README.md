# Events and ticketing (R3) — Phase 7A design package

> **Update, 27 November 2026 (records correction):** the "not approved" statements below are superseded for **development scope**. Owner Decisions H (Events), I (Advertising) and J (Finance) of 25 November 2026 ([record](../../planning/Owner_Decisions_A-J_2026-11-25.md)) approve these scopes for **sandbox development only**. Real payments, live payouts, live ads and production activation stay **not authorized**. Decision J and X-01 supersede any Events- or Advertising-owned monetary ledger: **Finance owns the one ledger**, and Points stays non-cash. Every policy value (rates, shares, thresholds, periods, windows, currencies) stays an unset owner decision. The original text is kept below as history.

**Status: PROPOSED — not approved.** 25 November 2026. This package is the design and decision stage that must precede Phase 7 implementation, mirroring Business Phase 6A. **It contains documents only: no code, migration, flag, AWS or staging change.** Events and ticketing are Release 3 and are still *deferred* in the approved records (DEC-001, ADR-010, DOC-021, PRD-F13); [DR-EV-01](EVT-Owner_Decisions_Required_PHASE7A.md) asks the owner to reconcile that. Production remains NO-GO. No real payment provider is selected or activated.

## Deliverables

| # | Deliverable | File |
| --- | --- | --- |
| 1 | **Exact owner decisions required (gates G, A, B, C, D; what each slice needs)** | [EVT-Owner_Decisions_Required_PHASE7A.md](EVT-Owner_Decisions_Required_PHASE7A.md) |
| 2 | Event PRD and SRS content | [EVT-Requirements_PRD_SRS_PROPOSED.md](../../requirements/EVT-Requirements_PRD_SRS_PROPOSED.md) |
| 3 | Event architecture decision | [ADR-EVT-001](../../adr/ADR-EVT-001_Events_and_Ticketing_Bounded_Context_PROPOSED.md) |
| 4 | Database ERD | [EVT-ERD_PROPOSED.md](EVT-ERD_PROPOSED.md) |
| 5 | API contracts | [EVT-API_Contract_PROPOSED.md](EVT-API_Contract_PROPOSED.md) |
| 6 | Organizer, attendee and reviewer journeys; state machines | [EVT-Journeys_and_State_Machines_PROPOSED.md](EVT-Journeys_and_State_Machines_PROPOSED.md) |
| 7 | Authorization matrix | [EVT-Authorization_Matrix_PROPOSED.md](../../security/phase7/EVT-Authorization_Matrix_PROPOSED.md) |
| 8 | Payment and refund policy decisions | [EVT-Payment_and_Refund_Policy_PROPOSED.md](EVT-Payment_and_Refund_Policy_PROPOSED.md) |
| 9 | STRIDE threat model | [EVT-STRIDE_Threat_Model_PROPOSED.md](../../security/phase7/EVT-STRIDE_Threat_Model_PROPOSED.md) |
| 10 | Acceptance criteria, slice and PR plan, blockers register | [EVT-Acceptance_and_Delivery_Plan_PROPOSED.md](../../engineering/phase7/EVT-Acceptance_and_Delivery_Plan_PROPOSED.md) |

## Reading order for the approver

0. [Owner decisions required](EVT-Owner_Decisions_Required_PHASE7A.md): the short list, with a recommendation for each.
1. [ADR-EVT-001](../../adr/ADR-EVT-001_Events_and_Ticketing_Bounded_Context_PROPOSED.md): the service boundary, the single ledger, verified payment confirmation, the offline check-in model.
2. [Payment and refund policy](EVT-Payment_and_Refund_Policy_PROPOSED.md): which policies the owner can decide and which are blockers.
3. The rest as reference.

## Key design points in one paragraph

A new `events` service (tenth deployable, own schema, closed flags). Organizer authority is per-organizer membership, not an Identity role. One append-only `financial_event` ledger owned by a `payments` module (*superseded by Decision J / X-01: Events posts to the Finance ledger and keeps no ledger of its own*); Points stays non-cash and untouched. A payment counts only after a verified signature, a replay check, a server-side `retrieve` and amount/currency/order equality; redirects never confirm anything. Inventory is reserved in one row-locked transaction with a database `CHECK` as backstop and lazy expiry. The QR is a signed opaque credential; admission is one atomic transition (first scan wins). Online check-in only; the offline model is documented for approval but not built. No event website, no live streaming, no buyer identity beyond `account_id`.

## What is blocked and why

Real payment provider, currencies, tax and fee values, Identity step-up, event images, notification delivery, the database role model, staging capacity and retention are open items; see the [blockers register](../../engineering/phase7/EVT-Acceptance_and_Delivery_Plan_PROPOSED.md#7-blockers-register-documented-not-worked-around). Each blocks only the functionality that depends on it.
