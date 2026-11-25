# Events — payment and refund policy decisions (proposed)

**Status: PROPOSED — not approved. No real payment provider is selected, contacted or activated.** 25 November 2026. This is the consolidated policy view behind DR-EV-20 to DR-EV-31. Each policy is marked **Decide** (the owner can decide it from product judgement), **Blocker** (needs legal, provider or regulatory input that this repository cannot supply) or **Built-in** (a control the design enforces regardless of the owner's values).

## 1. What Phase 7 will and will not do with money

| Will | Will not |
| --- | --- |
| Compute prices, fees and totals on the server from stored prices | Accept a price, fee, total or currency from a client |
| Run the full checkout, notification, confirmation and refund flow against a **sandbox** adapter | Call any real provider, hold real funds or take real card or mobile-money details |
| Record every money fact once in one append-only ledger | Keep a mutable balance, or a second ledger anywhere |
| Show buyers and organizers order, refund and ticket states | Pay organizers (no payout, transfer or settlement; R4) |
| Block a build that registers a non-sandbox adapter without an owner approval constant | Treat a redirect, client message or unverified notification as payment |

The platform never stores card numbers, mobile-money PINs or provider credentials in the Events schema. With a real provider those would be collected by the provider's own hosted flow; which flows are acceptable inside a Flutter-only product (no web redirect pages are built by us) is part of the provider decision.

## 2. Policy table

| # | Policy | Recommendation | Type |
| --- | --- | --- | --- |
| P-01 | **Merchant model.** Who is the seller of record and who holds the funds | Platform collects, organizer is owed; no settlement in Phase 7 | **Blocker** (legal, provider) |
| P-02 | **Currency.** USD, LRD or both | One currency per ticket type from an approved list; integer minor units; no FX; one currency per order | Decide + **Blocker** (collectable currencies) |
| P-03 | **Platform fee.** Percentage, fixed part, bearer, refundable or not | Versioned configuration; applied to every order; snapshot on the order; development value `0`. Fee **not** refundable on buyer-requested refunds; **refunded** when the platform or organizer cancels | Decide (values) |
| P-04 | **Tax** on tickets and fees | Computed through the same versioned policy if required; value `0` until legal input | **Blocker** |
| P-05 | **Rounding** | Half-up per order line to the minor unit; totals are sums of rounded lines; tests pin it | Built-in once approved |
| P-06 | **Reservation hold** | 10 minutes | Decide |
| P-07 | **Limits** | 6 per order, 10 per account per event | Decide |
| P-08 | **Late payment after expiry** | Re-acquire inventory if still available, else automatic full refund | Decide |
| P-09 | **Free tickets** | Allowed; no payment step | Decide |
| P-10 | **Buyer refund policy** | Per event: `no_refund` or `refund_until` (≥ 24 h before start); inside the window rule-approved; outside → review; one refund per ticket | Decide |
| P-11 | **Partial refunds** | Per ticket only; never above captured minus already refunded | Built-in |
| P-12 | **Organizer cancellation** | Full refund including fee, automatic, idempotent | Decide |
| P-13 | **Postponement** | A reschedule is a material edit; ticket holders keep tickets and have 7 days to request a refund | Decide |
| P-14 | **Refund destination** | Original payment method only | Built-in |
| P-15 | **Refund authority** | Rule-based automatic; otherwise `refund_review` grant; requester ≠ approver; second approver above a threshold | Decide (threshold) |
| P-16 | **Chargebacks and provider disputes** | Cannot exist in a sandbox. Modelled as a `dispute` with outcome `provider_chargeback` only when a real provider is approved | **Blocker** |
| P-17 | **Disputes** | `dispute_review`; outcomes dismiss, refund, reinstate; 14-day target | Decide |
| P-18 | **Settlement and payout to organizers** | None; derived "owed" report only | Decide (confirmed absent) |
| P-19 | **Reconciliation** | A job compares the provider settlement report to the ledger; differences open a `fraud_signal` of kind `reconciliation`, never auto-correct. In Phase 7 the report comes from the sandbox | Built-in |
| P-20 | **Retention and legal hold** | Per legal advice; nothing purged meanwhile | **Blocker** (ADR-020) |
| P-21 | **Real provider selection** | Not made. Needs Liberia coverage, merchant onboarding and KYC, webhook signing method, settlement currency, fees, refund API, settlement reports, a public inbound-webhook design and legal review | **Blocker** |

## 3. Money invariants the build must prove

| # | Invariant | How it is enforced and tested |
| --- | --- | --- |
| I-1 | Order total = sum of order lines + fee + tax, computed on the server from stored prices | Pricing tampering test: any client-supplied amount is ignored or refused |
| I-2 | An order is `paid` only after verified capture | Forged-status test: a notification with a bad signature, a replayed id, a mismatched amount, currency or order ref, or a `retrieve` that says "failed" cannot mark paid |
| I-3 | A payment event posts to the ledger exactly once | Unique `idempotency_key` and unique `(provider, provider_event_id)`; concurrent replay test |
| I-4 | Sum of refunds ≤ captured | Computed from the ledger under row lock; concurrent double-refund test |
| I-5 | No ticket is valid for a refunded order line | Same transaction revokes tickets; admission test |
| I-6 | Cancelling an event leaves no paid order without a refund and no valid ticket | Event cancellation consistency test over many orders, including replays and partial failures |
| I-7 | A ledger row cannot be changed or removed | Trigger and role tests; hash-chain verification detects a doctored row |
| I-8 | Inventory is released once | Reservation status guard; replay test |
| I-9 | Floating point never touches money | Static check plus tests with amounts that break floats (for example 0.1 + 0.2 cases) |
| I-10 | Only the sandbox adapter can run | Guard test fails the build otherwise |

## 4. Refund and cancellation flow

1. **Buyer-requested:** request → rule check against the event's policy and the ticket status → `approved` (inside window) or `under_review` → decision → `processing` (adapter call with the refund's idempotency key) → verified result → `refunded` (ledger `refund_settled`, ticket `refunded`, inventory returned only if the event has not started; a returned ticket becomes sellable again only by an explicit organizer setting, default off).
2. **Event cancelled:** one transaction sets the event `cancelled`, revokes every valid ticket, and creates one `refund` per paid order. A background step then drives each refund through `processing`. The cancellation transaction never calls the provider, so a provider outage cannot leave a half-cancelled event; it leaves refunds `approved`, visible in cancellation oversight, and retried.
3. **Failure:** a verified provider failure sets `failed`, writes `refund_failed`, raises the case in oversight; bounded retries; never a silent drop and never a duplicate post.

## 5. Decisions the owner must make versus things the repo cannot decide

The owner decides P-03 values, P-06 to P-10, P-12, P-13, P-15, P-17, P-18. Legal or provider input is required for P-01, P-02 (collectable currencies), P-04, P-16, P-20, P-21. Until those are answered Phase 7 builds against the sandbox and **documents each blocker in the slice's results file**, as instructed.
