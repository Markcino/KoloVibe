# Events and ticketing — STRIDE threat model (proposed)

**Status: PROPOSED — not approved.** 25 November 2026. Scope: the `events` service, its Gateway routes, the Flutter surfaces and the console pages. Companion to the [Business STRIDE model](../phase6/BIZ-STRIDE_Threat_Model_PROPOSED.md) and DOC-203. Method: each trust boundary and asset is attacked with S, T, R, I, D, E; each threat has a control, a design anchor and a **named test** that must exist before its slice is accepted. The last column maps to the Phase 7 E8 test list.

## 1. Assets and trust boundaries

| Asset | Why it matters |
| --- | --- |
| Inventory counters | Overselling is direct financial and reputational harm |
| Orders and the financial-event ledger | Money truth; tampering is fraud |
| Ticket and QR credential | Entry right; duplicates are fraud |
| Organizer verification and publication state | Trust badge; fake events defraud buyers |
| Membership and reviewer grants | Control of all of the above |
| Provider notification channel | A forged message could mark an order paid |
| Buyer account id and purchase history | Privacy; the only personal link held |

| Boundary | Between |
| --- | --- |
| B1 | Flutter app ⇄ Gateway (internet) |
| B2 | Gateway ⇄ Events (service identity) |
| B3 | Events ⇄ payment provider (sandbox now; internet later) |
| B4 | Events ⇄ Audit (outbox) |
| B5 | Console ⇄ Gateway (reviewers and administrators) |
| B6 | Scanner device ⇄ attendee device (the QR) |

## 2. Threats and controls

| ID | STRIDE | Threat | Control (design anchor) | Test (E8) |
| --- | --- | --- | --- | --- |
| T-EV-01 | E | An owner of organizer A reads or changes organizer B's events, ticket types, orders, members or check-in | Membership resolved per request; 404 for non-entitlement; registry-driven test | **Cross-organizer access denial** |
| T-EV-02 | E | Check-in staff scan for an event they are not assigned to, or a buyer calls the scan operation | `checkin_assignment` scope; role check | **Check-in authorization** |
| T-EV-03 | E | A client sets `state`, `organizer_id`, `owner`, `price` or `total` in a body | Allowlist validators reject unknown fields; fields derived server-side | Mass-assignment test over every operation |
| T-EV-04 | E | An organizer publishes without review, or edits a live event's date or price without re-review | Server-only `state`; `publish` only from `approved`; material edit makes a new revision | **Unauthorized event publication** |
| T-EV-05 | E | A reviewer approves their own organizer's event; a suspender restores; a refund requester approves | Separation-of-duties checks | Separation-of-duties tests |
| T-EV-06 | E | A moderator or administrator becomes an organizer member to bypass SoD | Memberships refused for privileged roles | Membership refusal test |
| T-EV-07 | T | Two buyers take the last ticket | Row-locked reservation, `CHECK` backstop | **Capacity race** (N concurrent threads, N > capacity) |
| T-EV-08 | T | A retry or double tap creates two reservations or orders | Idempotency key; unique constraints | **Duplicate booking requests** |
| T-EV-09 | T | A tampered request changes price, quantity above the limit, ticket type of another event, or a negative quantity | Server pricing; bounded integers; ticket type must belong to the event | **Pricing tampering** |
| T-EV-10 | T | A forged "payment succeeded" notification, or a genuine one with altered amount | Signature over raw body, tolerance, `retrieve`, amount/currency/order equality | **Forged payment status** |
| T-EV-11 | T | A notification is replayed to trigger a second ticket issue or ledger post | Unique `(provider, provider_event_id)` and ledger idempotency key | **Payment webhook replay** (sequential and concurrent) |
| T-EV-12 | T | The app redirect or a client "paid" call is treated as payment | No such operation; only the verified path changes `paid` | Test that no client operation can set `paid` |
| T-EV-13 | T | The ledger is edited or rows are removed to hide a theft | Trigger, INSERT-only role, hash chain, `ledger/verify` | Ledger immutability test; doctored-row detection |
| T-EV-14 | T | Refund above captured, or two refunds of one ticket | Ledger totals under lock; unique refund per ticket | **Invalid refund requests** |
| T-EV-15 | T | A cancelled event leaves paid orders without refunds or valid tickets | One-transaction cancellation; idempotent refund creation; oversight page | **Event cancellation consistency** |
| T-EV-16 | T | A late payment after reservation expiry causes oversell | Re-acquire or auto-refund; never issue without inventory | Late-payment test |
| T-EV-17 | T/S | A ticket QR is forged, edited, or taken from another event | MAC under versioned key; server lookup; event match | QR forgery test |
| T-EV-18 | S | A valid QR is screenshotted and used by a second person | Atomic single admission; the second scan is refused and recorded | **Ticket QR replay** |
| T-EV-19 | S | A stolen bearer token buys tickets or views tickets | Live session check at Gateway; verified email; throttles; tickets owner-scoped | Session-revocation test |
| T-EV-20 | S | An attacker enumerates tickets or orders by id | Random ids; 404 on non-ownership; public id random 128-bit | Enumeration test |
| T-EV-21 | R | A reviewer or organizer denies a decision | Append-only decisions and audit in the deciding transaction | Audit-per-state-change test |
| T-EV-22 | R | A buyer disputes a scan result | Append-only `checkin_event` including refusals | Check-in log test |
| T-EV-23 | I | Public discovery leaks private columns (venue coordinates, organizer ids of members, counts) | `event_listing` projection with public columns only; availability bands | Public-field allowlist test |
| T-EV-24 | I | Organizers or staff learn buyer identity | No buyer PII stored; aggregates only | No-PII schema test |
| T-EV-25 | I | The QR credential, notification payloads or tokens appear in logs, audit or error bodies | Redaction by design; id-only audit; `no-store` on credential | Log and audit content test |
| T-EV-26 | I | Error messages or timing reveal that an event or ticket exists | Uniform 404; constant-time compares | Existence-disclosure test |
| T-EV-27 | D | Reservation flooding exhausts inventory ("hold bombing") | Per-account and per-event limits; short hold; lazy expiry; throttles | Hold-flood test |
| T-EV-28 | D | Scanner endpoint flooded at the gate | Per-device throttle sized above real throughput; cheap indexed lookups | Throttle test |
| T-EV-29 | D | Search or list endpoints abused for load | Keyset paging, bounded params, public-read budget | Budget test |
| T-EV-30 | D | A provider outage leaves orders pending forever or refunds stuck | Expiry rules; cancellation never calls the provider inline; oversight page; bounded retries | Provider-outage test |
| T-EV-31 | E | A non-sandbox payment adapter is activated by configuration | Registration guard test and approval constant | **Adapter guard** |
| T-EV-32 | S | A fake organizer sells fake events | Verification gate; paid events need `verified`; takedown; fraud review | Publication-gate test |
| T-EV-33 | T | Ticket-type price or quantity changed after sale to alter existing orders | Orders copy price; quantity floor; snapshot immutable | Post-sale edit test |
| T-EV-34 | E | A flag left open exposes admin or checkout routes | Closed by default; local-only profile; route table test with all flags closed | Closed-flag route test |
| T-EV-35 | E | Admin console pages reachable without MFA or by the wrong grant | MFA on all; grant scope per queue; the Business console route-security matrix pattern | Console route-security test |
| T-EV-36 | T | A service-identity request is replayed to Events | Existing signed envelope, nonce table, bounded retention | Service-identity tests (existing pattern) |
| T-EV-37 | I | Provider secrets or QR signing keys leak or cannot be rotated | Secret references only; versioned keys; retired keys still verify until expiry | Key-rotation test |
| T-EV-38 | T | A reviewer bulk-approves fraudulent refunds | Threshold, second approver, step-up, audit, fraud signal on velocity | Refund-threshold test |
| T-EV-39 | R | Clock manipulation to bypass sales window or hold expiry | Server time only; no client time trusted; `expires_at` is server value | Clock-independence test |

## 3. Residual risks (stated, not hidden)

| Risk | Why it remains | Treatment |
| --- | --- | --- |
| Screenshot sharing before entry | Static QR can be copied until first scan | First-scan-wins and logging; rotating credential is a later option |
| Sandbox is not the real provider | Real webhooks arrive late, out of order, duplicated, with partial captures and chargebacks | Blockers P-16, P-21; a second review and a provider-specific test pack are required before any real provider |
| Offline gaps | Poor venue connectivity; offline check-in not built | DR-EV-42; operational procedure for staff (manual list) is an organizer problem, documented |
| Collusion between organizer and reviewer | Accounts differ but people may not | Audit, fraud signals, grants limited, SoD; cannot be eliminated by code |
| Database role model (R-01) | Open finding | Trigger-based immutability works under any model; DR-EV-06 |
| Capacity of a tenth service | Unmeasured | DR-EV-07 |

## 4. Abuse cases for check-in at the gate

| Case | Expected result |
| --- | --- |
| Same QR scanned on two devices at once | One `admitted`, one `already_admitted` with the first's time and gate |
| Ticket refunded 1 minute before scan | `refunded` result |
| Event cancelled during entry | `revoked` for all remaining valid tickets |
| Credential from event X at event Y | `wrong_event` |
| Edited or truncated credential | `invalid`, recorded |
| Scan before the entry window | `not_open` |
| Scanner removed mid-event | Next request refused (404) |
