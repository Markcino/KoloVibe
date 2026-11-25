# Events and ticketing — acceptance criteria and delivery plan (proposed)

**Status: PROPOSED — not approved.** 25 November 2026. Implements the Phase 7 instruction: E1 to E8 delivered sequentially as small PRs, each a vertical slice (backend, Gateway, Flutter, console where relevant), focused tests and CI during development, comprehensive staging and device UAT deferred to Phase 11. **No slice starts before its decisions are recorded** ([gate table](../../architecture/events/EVT-Owner_Decisions_Required_PHASE7A.md#what-each-slice-needs-before-it-can-start)).

## 1. Rules for every PR

1. One independently testable slice; reuse existing implementations; no deferred feature (offline check-in, real provider, payouts, images before the pipeline, notifications, event website).
2. Every operation is in the contract, the authorization matrix and the registry-driven tests **in the same PR** that adds it.
3. All new Gateway capabilities closed by default; production NO-GO; no AWS or staging change; no merge or deploy without the owner's approval.
4. Results file per slice in `docs/engineering/phase7/` stating actual changes, tests run, failures, unresolved work and blockers; nothing claimed that was not run.
5. After repeated unsuccessful fixes, stop and report the blocker.

## 2. Wiring checklist (from the Phase 6E defects)

Phase 6E found three integration bugs that no unit test caught (a Gateway local peer table missing the new service, a stale contract enum, an uncaptured fixture). The first slice that adds the service must touch each place Business touched, and a test must fail if one is missed:

| Place | Business precedent | Why |
| --- | --- | --- |
| `services/gateway/service/capabilities.py`, `settings.py`, `urls.py`, `routes/`, `internal_client.py` (local peers) | Present | Flags, routes, peer table |
| `services/staging_runtime/__init__.py`, `capabilities.py`; `scripts/ops/kolovibe_cluster.py` | Present | Empty capability set so nothing opens by accident |
| `services/audit` `events.py`, `models.py`, `service_auth.py`, a producer migration | `0006_business_producer.py` | New producer (**an existing-service change needing approval**) |
| Service-identity tests in every service; `scripts/test_service_identity_drift.py` | Present | Shared verifier must not drift |
| `scripts/check_structure.py`, `scripts/run_local_service.py`, `scripts/test_gateway_role_matrix.py`, `scripts/test_gateway_route_contract.py`, `scripts/probe_*` | Present | Structure, local run, role matrix, route contract |
| `scripts/verify_local_journeys.py` and a new `scripts/events_journey.py` | `business_journey.py` | Real-HTTP end-to-end |
| `.github/workflows/ci_cd.yml` | Present | CI steps for the new tests |
| `packages/contracts/openapi` | DOC-205 | Contract of record |

## 3. Slices and PR order

The instruction orders slices E1 to E8. Two dependencies are noted so the order stays honest: E3's ticket-category selection needs E4's data, and My tickets needs E6's issuance. **E3 therefore ships in three parts** (E3a discovery and detail; E3b ticket selection after E4; E3c booking status and My tickets after E5 and E6). This is a recommendation for approval, not a silent reordering.

| PR | Slice | Backend | Gateway | Flutter | Console | Needs |
| --- | --- | --- | --- | --- | --- | --- |
| P7-E0 | Service skeleton, flags, wiring checklist, audit producer, structure and identity tests | service shell, health, service auth, limits, errors | flags, peers, routes table (empty) | — | — | DR-EV-01 to 04, 06 |
| P7-E1a | Organizer registration, membership, invitations | organizer, membership, grant, invitation | `event_organizer` routes | onboarding, team | grants page | DR-EV-10, 12, 50, 51 |
| P7-E1b | Organizer verification, restriction and suspension | cases, decisions, status transitions | routes | verification status, dashboard | verification queue, restrict/suspend | DR-EV-11, 13 (and 05 for SU actions) |
| P7-E2a | Venues, categories, event drafts, revisions | venue, category, event, revision | routes | event editor, lists | — | DR-EV-14, 15, 16 |
| P7-E2b | Publication review, publish, unpublish, cancel (no tickets yet) | decisions, state machine, listing projection | routes | publication status | event review queue, takedown | DR-EV-14 (05 for cancel) |
| P7-E3a | Discovery, search, filters, event detail | projection reads | `event_discovery` | discover, search, detail | — | DR-EV-15, 52 |
| P7-E4 | Ticket types, inventory, reservations, expiry | ticket_type, reservation, limits, lazy expiry, job | `event_checkout` reservation routes | ticket type editor; ticket selection (**E3b**) | — | DR-EV-20, 23, 24, 31 |
| P7-E5a | Pricing, order creation, sandbox adapter, verified confirmation, idempotent notification handling | order, snapshot, adapter, `provider_notification` | order routes | order status | — | DR-EV-03, 21, 24; **not** DR-EV-22 |
| P7-E5b | Ledger, refunds states, failed/expired payment handling | `financial_event`, `refund`, trigger, hash chain, verify | refund routes | refund request | ledger verify | DR-EV-25, 26, 29, 30 |
| P7-E6a | Ticket issuance, credential, My tickets | ticket, signing keys | `event_tickets` | My tickets, ticket QR (**E3c**) | — | DR-EV-40, 41, 43 |
| P7-E6b | Check-in, duplicate prevention, revocation, organizer scan tools | checkin_event, assignment | `event_checkin` | scan, gate summary | — | DR-EV-43 |
| P7-E7a | Refund review, cancellation oversight, disputes | grants, decisions, SoD, thresholds | `event_admin` | dispute opening | refund, cancellation, dispute pages | DR-EV-27, 28, 05 |
| P7-E7b | Fraud review, audit history, moderation completeness | signals, reconciliation job | routes | — | fraud, audit pages | DR-EV-51 |
| P7-E8 | Security and quality consolidation | cross-cutting tests, mutation checks, contract reconciliation, journey | — | layout audit | route-security | — |
| P7-R | Phase 7 results, tracker, README, owner approval request for flags | docs | — | — | — | — |

Each slice's E8 tests ship in that slice; **P7-E8** adds the cross-cutting suite, the real-HTTP journey and the four-way contract reconciliation, as Phase 6E did, and is not a place to defer missing tests.

## 4. Acceptance criteria

IDs `AC-EV-nnn`. Each lists the evidence the slice's results file must show.

### E1 Organizer management

| ID | Criterion |
| --- | --- |
| AC-EV-001 | Registration is refused without a grant; the owner is the server-assigned caller; a retry with the same key is the same organizer |
| AC-EV-002 | A non-member gets 404 for every organizer operation (registry-driven) |
| AC-EV-003 | Moderators and administrators cannot hold memberships |
| AC-EV-004 | Verification: submit, information request, one resubmission, decision with reason code; the submitter is never the decider; an unverified organizer cannot publish |
| AC-EV-005 | Invitation codes are single use, expire, are stored hashed; redemption is throttled |
| AC-EV-006 | Restrict, suspend and restore follow the state machine; the restorer differs from the suspender; paid tickets are untouched by suspension |
| AC-EV-007 | Step-up operations fail closed until Identity provides the proof |
| AC-EV-008 | Flutter dashboard screens pass the layout audit and show server state only |

### E2 Event management

| ID | Criterion |
| --- | --- |
| AC-EV-010 | A client cannot set `state`; `publish` from any state but `approved` is refused |
| AC-EV-011 | A material edit to a published event creates a revision; the approved revision stays public until the new one is approved |
| AC-EV-012 | A reviewer who is a member of the organizer cannot review it |
| AC-EV-013 | Capacity cannot be reduced below sold plus reserved |
| AC-EV-014 | Organizer-owned lists show only the organizer's events, paged by keyset |
| AC-EV-015 | Images and notifications are absent and recorded as blockers |

### E3 Discovery

| ID | Criterion |
| --- | --- |
| AC-EV-020 | Public reads return only `event_listing` columns; a field-allowlist test fails if a private column is added |
| AC-EV-021 | Cancelled, suspended and draft events are not discoverable; a cancelled event is visible to its ticket holders |
| AC-EV-022 | Search and filters are allowlisted and bounded; no total counts |
| AC-EV-023 | Every discovery screen shows server state only; the Dart parsers pass against captured real service answers (drift test) |

### E4 Ticket inventory

| ID | Criterion |
| --- | --- |
| AC-EV-030 | **Capacity race:** with N concurrent reservations for fewer than N tickets on a real PostgreSQL, sold plus reserved equals capacity exactly and the rest are refused |
| AC-EV-031 | **Duplicate booking:** concurrent identical requests with one key create one reservation; with different keys the per-account limit holds |
| AC-EV-032 | Expired holds are released even if the scheduled job never runs |
| AC-EV-033 | Sales window, per-order and per-account limits are enforced; sold-out is derived |
| AC-EV-034 | Quantity cannot be cut below sold plus reserved; price changes do not alter existing orders |
| AC-EV-035 | Free tickets skip payment through the same path |

### E5 Sandbox checkout

| ID | Criterion |
| --- | --- |
| AC-EV-040 | **Pricing tampering:** any client-supplied amount or price is ignored or refused; the total equals the server computation |
| AC-EV-041 | **Forged status:** bad signature, stale timestamp, replayed event id, mismatched amount, currency or order reference, or a failed `retrieve` never marks an order paid |
| AC-EV-042 | **Webhook replay:** sequential and concurrent replays post exactly one ledger event and issue exactly one set of tickets |
| AC-EV-043 | No client operation can set `paid`; a redirect or poll cannot confirm payment |
| AC-EV-044 | Failed and expired payments release inventory once |
| AC-EV-045 | The adapter guard fails the build if a non-sandbox adapter is registered |
| AC-EV-046 | The ledger rejects UPDATE and DELETE; the hash chain detects a doctored row; the verify command reports it |
| AC-EV-047 | Late payment follows DR-EV-24 and never oversells |
| AC-EV-048 | Money tests include float-breaking amounts; no float type in the money path |

### Refunds (E5 states, E7 review)

| ID | Criterion |
| --- | --- |
| AC-EV-050 | **Invalid refunds:** above captured, second refund of one ticket, refund of an admitted or foreign ticket, refund after the window without review: all refused with bounded codes |
| AC-EV-051 | Concurrent double refund posts once |
| AC-EV-052 | Requester cannot approve; a second approver is required above the threshold |
| AC-EV-053 | **Cancellation consistency:** after cancelling an event with many orders (including replays and an injected provider failure), every paid order has exactly one refund, no ticket is valid, and no ledger event is duplicated |

### E6 Tickets and check-in

| ID | Criterion |
| --- | --- |
| AC-EV-060 | Tickets exist only after verified payment (or free); one per unit; owner-scoped |
| AC-EV-061 | The credential contains no personal data; a forged, edited, truncated, wrong-event or retired-key credential is refused; rotating a key keeps valid tickets valid until retired |
| AC-EV-062 | **QR replay:** the same credential scanned twice, including concurrently on two devices, admits once; the loser sees the first time and gate |
| AC-EV-063 | **Check-in authorization:** unassigned staff, other-event staff, buyers and non-members are refused; removing an assignment stops the next scan |
| AC-EV-064 | Revoked and refunded tickets are refused immediately |
| AC-EV-065 | Every attempt is in the append-only log; scan results never include buyer identity |
| AC-EV-066 | Offline check-in is absent |

### E7 Administration

| ID | Criterion |
| --- | --- |
| AC-EV-070 | Every console route needs MFA and the right grant; the route-security matrix test fails for any unregistered page |
| AC-EV-071 | Decision forms are double-submit safe (claim, confirm step, decision), replay records one decision |
| AC-EV-072 | Evidence and queue reads are audited; audit history is id-only |
| AC-EV-073 | Fraud signals never penalise automatically |

### E8 Cross-cutting

| ID | Criterion |
| --- | --- |
| AC-EV-080 | **Cross-organizer denial** is proved for every organizer-scoped operation from the registry |
| AC-EV-081 | With all flags closed, no Events route is served |
| AC-EV-082 | Four-way reconciliation: contract ⇄ Gateway routes ⇄ service registry ⇄ console and Dart operation lists have no difference; real service answers validate against the schemas |
| AC-EV-083 | Real-HTTP journey: organizer onboarding to published event to purchase to check-in to refund, with a second organizer and a second buyer attacking at each step |
| AC-EV-084 | Mutation checks: removing one authorization or one signature check makes a named test fail |
| AC-EV-085 | Log and audit content tests show no token, credential, payload or free text |

## 5. Test approach

Focused tests per slice (service tests with real PostgreSQL for concurrency, because SQLite cannot prove row-lock behaviour; Gateway tests; Dart unit and widget tests with the layout audit; console tests), then the shared scripts named in §2 and the CI workflow. Concurrency tests use real threads against a disposable PostgreSQL with TLS, as the Business PostgreSQL script does. Everything runs locally and in CI. **Not run in Phase 7:** staging, real devices, load and soak, real providers, penetration testing: these belong to Phase 11 and to the real-provider approval.

## 6. Flutter work

Route numbers from M-145 (Business ended at M-144). Estimated screen groups, to be fixed by the design approval DR-EV-50: attendee discovery, search and filters, event detail, ticket selection, checkout and order status, My tickets, ticket QR, refund and dispute request (about 10); organizer onboarding, verification, dashboard, team, events list and editor, venue, ticket types, orders and refunds (about 13); check-in scan, result, gate summary (about 3); roughly 26 to 30 in total. Reuse the existing design tokens, shared widgets, repositories, secure storage and the drift-tested model approach used for Business.

## 7. Blockers register (documented, not worked around)

| # | Blocker | Affects | Needs |
| --- | --- | --- | --- |
| BL-01 | Real payment provider, Liberia coverage, onboarding, webhook signing, fees, refund API | live payments | DR-EV-22 and a separate approval |
| BL-02 | Collectable currencies, tax, fee values, merchant model | real pricing | legal and owner input (P-01 to P-04) |
| BL-03 | Identity step-up proof | cancellation, refund approval, role changes, closure | DR-EV-05 |
| BL-04 | Image pipeline | event images | DR-EV-17 |
| BL-05 | Notification delivery provider | event notifications | DR-EV-18 |
| BL-06 | Database role model | ledger immutability beyond the trigger | DR-EV-06 |
| BL-07 | Staging capacity for a tenth service | any deployment | DR-EV-07 |
| BL-08 | Retention and privacy orchestration | purge, export, erase | ADR-020, DR-EV-30 |
| BL-09 | Offline check-in model approval | offline mode | DR-EV-42 |
| BL-10 | DOC-023 change request and register updates | governance | DR-EV-01 |
