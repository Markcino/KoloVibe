# FP-PAY Payment processing, reconciliation and payouts — requirements (PRD and SRS content)

**Status: APPROVED by the owner on 27 November 2026 at 12:26 UTC ("Approve all as recommended"), with the recommended option for every open choice. The file name keeps its original `_PROPOSED` suffix so links stay stable.** Approval covers development scope only. It does not approve a provider, an account, a value marked `[OWNER VALUE]`, live payments, live ads or store submission. Written in Phase 1 (27 November 2026). Indexed in [FP-000](FP-000_Full_Product_Requirements_Baseline.md). It adds the cross-cutting payment layer that [FIN](FIN-Requirements_PRD_SRS_PROPOSED.md) (F5 sandbox payouts), [EVT](EVT-Requirements_PRD_SRS_PROPOSED.md) (E5 ticket payments) and [AD](AD-Requirements_PRD_SRS_PROPOSED.md) (A7 billing preparation) each assume, so that one provider boundary serves all three. It does not repeat those requirements; it links to them.

Ownership follows the owner's approval of **GD-01** (Finance as a separate service) and **GD-04** (maker, checker and releaser grants in Finance). **[OWNER VALUE]** marks configuration with no default. **Nothing here chooses a provider, sets a fee, currency, threshold or schedule, or makes a legal or eligibility determination.** Development and testing use a sandbox adapter only. Live payment activation needs a separate written owner authorization (mandate section 8; AGENTS.md).

## 1. Store billing rules that constrain the design

Checked on 27 November 2026 against the official pages listed. The column "Status" records what the text decides and what it does not.

| Flow | Google Play | Apple App Store | Status |
| --- | --- | --- | --- |
| Event tickets for real-world events | Play Billing is not required for "physical goods or services", which the policy lists as including tickets for live events ([Payments policy](https://support.google.com/googleplay/android-developer/answer/9858738), [Billing FAQ](https://support.google.com/googleplay/android-developer/answer/10281818)) | 3.1.3(e): goods or services "consumed outside of the app" must use a non-IAP method such as Apple Pay or card entry ([App Review Guidelines](https://developer.apple.com/app-store/review/guidelines/)) | Play text covers it. Apple text is the closest fit but does not name event tickets: **confirm with App Review before submission** |
| Business buys advertising shown inside KoloVibe | Not addressed in the fetched Play text | 3.1.3(g): "buying advertisements to display in the same app (such as sales of 'boosts' for posts in a social media app) must use in-app purchase" | **Apple text requires IAP for in-app purchase of ads shown in the app.** Play: unconfirmed. See choice PAY-D2 |
| Creator payouts from the revenue pool (money from KoloVibe to creators) | Not addressed | Not addressed | Unconfirmed on both stores; outbound payouts are not a purchase in the app. Confirm in writing (PAY-D4) |
| Tips or gifts from viewers to creators | Peer-to-peer payments where the full amount goes to the recipient with no digital benefit fall outside Play Billing (Billing FAQ) | 3.2.1(vii): optional, "100% of the funds go to the receiver"; a gift connected to digital content or services must use IAP | Not in approved scope; listed so it is not built by accident |
| Any digital unlock, feature or currency | Play Billing required | 3.1.1 IAP required; IAP credits may not expire and need restore | Not in approved scope. Points are never bought, sold or converted (DEC-003, FR-016) |
| Steering to another payment method for digital items | Not allowed outside programmes the policy names | 3.1.3 intro: may not encourage non-IAP purchase in the app, with storefront exceptions | KoloVibe never links out for digital items |

Consequence for the design: the provider boundary must support **two payment rails**, a card or wallet provider for physical services (tickets) and, where a store requires it, **store billing** (Play Billing and StoreKit) for in-app purchases. Which rail each flow uses is a configuration per platform and flow (`payments.rail.<flow>.<platform>`), not code.

## 2. Ownership and architecture

| Component | Owner | Notes |
| --- | --- | --- |
| Payment intents, provider events, refunds, disputes, payout instructions, reconciliation | Finance (GD-01) | Own schema and runtime role; no other service writes these tables |
| Ticket order state | Events | Calls Finance through a signed internal request; receives Finance events |
| Advertiser invoices and campaign spend | Advertising | Same pattern as Events |
| Provider adapters | Finance | `PaymentProvider`, `PayoutProvider` and `StoreBillingVerifier` interfaces; `SandboxProvider` is the only adapter in development and staging |
| Webhook intake | Gateway route to Finance | Public route; verifies signature before any parse of business fields |
| Provider credentials | Swarm secrets owned by Finance | Never in Git, never in logs, never in the console |

Money is stored as integer minor units with an ISO 4217 currency code; there is no floating point anywhere in the money path (FN-R-0xx ledger rules apply).

## 3. Roles

| Role | Powers |
| --- | --- |
| Buyer (any signed-in account) | Pay for its own ticket order; see its own receipts; request a refund where the event's policy allows |
| Advertiser (verified Business account with advertiser grant) | Pay its own invoices; see its own payment history |
| Payee (creator with eligibility, FIN F4) | Register a payout destination through the provider's hosted flow; see payout states |
| Finance maker | Prepare a payout batch or a manual adjustment |
| Finance checker | Approve a batch; cannot approve its own (GD-04) |
| Finance releaser | Release an approved batch; must differ from maker and checker |
| Finance reconciler | Resolve reconciliation exceptions; cannot release |
| Administrator | Configure rails and kill switches; cannot hold any Finance grant at the same time as releaser on the same batch |

All console roles need MFA (ADR-013) and every action writes an audit record (Decision D).

## 4. Functional requirements

| ID | Requirement | Pri | Acceptance criterion |
| --- | --- | --- | --- |
| PAY-R-001 | One `PaymentProvider` interface (create intent, retrieve, cancel, refund) and one `PayoutProvider` interface (create recipient via hosted flow, create transfer, retrieve); services other than Finance never import a provider client | M | Static import check; interface tests against `SandboxProvider` |
| PAY-R-002 | Only `SandboxProvider` is loadable unless `payments.live_enabled` is true **and** a live-activation record with the owner's approval id exists; staging refuses live mode at start-up | M | Start-up test fails closed with live keys and no record |
| PAY-R-003 | Every payment intent is created with an idempotency key derived from the order id; a retry never creates a second charge | M | Replayed create returns the same intent |
| PAY-R-004 | Card data never touches KoloVibe servers or the Flutter app's own fields: payment entry uses the provider's hosted page or native SDK sheet | M | Code review and network capture show no card fields sent to KoloVibe |
| PAY-R-005 | Webhooks: signature verified against the raw body before parsing; timestamp tolerance [OWNER VALUE] `payments.webhook_tolerance_seconds`; event id stored and a repeat is a no-op; then a server-side `retrieve` must agree on id, amount, currency and state before any state change (extends FN-R-063 to payments) | M | Tests for bad signature, stale timestamp, replay, and mismatched retrieve |
| PAY-R-006 | Payment state machine: `created → requires_action → processing → succeeded / failed / cancelled`; `succeeded → partially_refunded / refunded / disputed`; transitions only from verified provider facts | M | State machine table test; illegal transition rejected |
| PAY-R-007 | On success Finance posts the ledger entry and publishes `kolovibe.finance.payment.succeeded.v1`; Events issues the ticket only on that event, never on the client's return URL | M | Ticket not issued when the client reports success but the webhook has not arrived |
| PAY-R-008 | Holds: an order reserves inventory for [OWNER VALUE] `events.checkout_hold_minutes`; expiry cancels the intent and releases inventory | M | Expiry test |
| PAY-R-009 | Refunds: full or partial, only by an authorized role or by an event cancellation rule; amount can never exceed the captured amount minus earlier refunds; each refund is idempotent | M | Over-refund rejected; concurrent refunds serialised |
| PAY-R-010 | Event cancellation triggers refunds for all paid tickets as a resumable batch, with progress and failures visible in the console | M | Batch survives a worker restart without double refunds |
| PAY-R-011 | Disputes and chargebacks: provider dispute events create a dispute record, freeze any payable derived from the payment, and notify Finance; evidence submission is manual in the provider dashboard in the first release | M | Dispute freezes the related revenue record |
| PAY-R-012 | Store billing (where PAY-D2 chooses it): purchase tokens from Play Billing and StoreKit are verified server-side with the store before granting anything; acknowledgement or finishing of the transaction happens only after the grant is recorded | M (if chosen) | Verifier tests with store test purchases; unverified token grants nothing |
| PAY-R-013 | Store refunds and revocations (Play voided purchases, App Store server notifications) reverse the grant and post a ledger reversal | M (if chosen) | Revocation test |
| PAY-R-014 | Daily reconciliation per provider and per store: provider balance transactions or settlement reports against the ledger; unmatched, mismatched or aged items become exceptions with an owner | M | Seeded mismatch creates one exception |
| PAY-R-015 | Payout destinations are collected only in the provider's hosted onboarding; KoloVibe stores the provider's recipient id and a masked label | M | No destination details in the database or logs |
| PAY-R-016 | Payout flow follows FN-R-060: request → eligibility → maker → checker → releaser → provider transfer → settlement or failure; each step a distinct account | M | Same-account second approval rejected |
| PAY-R-017 | Eligibility checks that depend on law or provider rules (identity verification, tax forms, sanctions screening, minimum amounts) are delegated to the provider's onboarding state plus [OWNER VALUE] settings; KoloVibe never decides legal eligibility itself | M | Payout blocked while provider onboarding is incomplete |
| PAY-R-018 | Kill switches per rail and per flow (`payments.kill.<flow>`); switching off stops new intents and payouts but lets webhooks for existing ones finish | M | Switch test with in-flight intent |
| PAY-R-019 | Receipts: an in-app receipt per payment and refund (amount, currency, date, order, provider reference); email receipt is a notification (FP-NT NT-EV) | M | Widget and API tests |
| PAY-R-020 | Erasure keeps financial records that law requires for [OWNER VALUE] `finance.retention_years` and pseudonymises the person link; access export includes the person's payments, refunds and payouts | M | Erasure test keeps the ledger balanced |

## 5. Security

- Webhook endpoint accepts only the provider's content type, has a body size limit, rate limit at the edge (#325) and returns a generic answer; errors never echo payloads.
- Provider secrets are separate per environment; a staging secret cannot be used in production and the reverse (environment tag checked at start-up).
- Logs and audit hold ids, states and amounts only; no card, bank, token or provider payload content (FN-R-082).
- Console money actions require MFA re-authentication at the moment of the action.
- Separation of duties is enforced in the database (check constraints on distinct actor ids), not only in views.

## 6. Privacy

Payment data held by KoloVibe is limited to provider ids, amounts, currency, state and masked labels. Store disclosures: Play Data safety and Apple privacy details declare purchase history; Apple's privacy details page says payment information handled entirely outside the app by the payment service need not be disclosed, which applies only if entry uses the provider's hosted flow (PAY-R-004). Lawful basis and retention are [OWNER VALUE] (ADR-020, #136).

## 7. API (proposed; Gateway routes, no DRF)

Buyer: `POST /api/v1/events/{id}/orders`, `POST /api/v1/orders/{id}/payment` (returns a provider client secret or hosted URL), `GET /api/v1/me/payments`, `GET /api/v1/me/payments/{id}`, `POST /api/v1/orders/{id}/refund-request`.
Advertiser: `GET /api/v1/business/me/invoices`, `POST /api/v1/business/me/invoices/{id}/payment`.
Payee: `POST /api/v1/creators/me/payout-onboarding` (returns hosted link), `GET /api/v1/creators/me/payouts`.
Store billing (if chosen): `POST /api/v1/me/store-purchases` (platform, product id, token).
Webhooks: `POST /api/v1/webhooks/payments/{provider}`, `POST /api/v1/webhooks/stores/{store}`.
Console: `GET/POST /api/v1/admin/finance/payout-batches[/{id}/approve|release]`, `GET /api/v1/admin/finance/reconciliation/exceptions`, `POST .../{id}/resolve`, `PUT /api/v1/admin/payments/switches`.

## 8. Event contracts (catalogue in #305)

Published by Finance: `kolovibe.finance.payment.succeeded.v1`, `.payment.failed.v1`, `.payment.refunded.v1`, `.payment.disputed.v1`, `.payout.released.v1`, `.payout.settled.v1`, `.payout.failed.v1`, `.reconciliation.exception.v1`. All carry ids, amount in minor units, currency and the source order or invoice id; no personal data. Consumers: Events (tickets), Advertising (invoice state), Identity notifications (FP-NT), Audit.

## 9. Flutter screens (M-440 to M-459; Figma frames first, #306)

M-440 checkout summary; M-441 provider payment sheet handoff; M-442 payment processing; M-443 payment success with ticket link; M-444 payment failed with retry; M-445 receipts list; M-446 receipt detail; M-447 refund request; M-448 refund status; M-449 advertiser invoice payment; M-450 payout onboarding start (hosted link); M-451 payout onboarding incomplete state; M-452 payout history; M-453 payout detail. Store purchase screens are added only if PAY-D2 chooses store billing.

## 10. Failure scenarios

| Scenario | Required behaviour |
| --- | --- |
| Webhook arrives before the client returns | State updates; client polls and sees success |
| Client returns success, webhook never arrives | Order stays `processing`; reconciliation and a scheduled `retrieve` resolve it within [OWNER VALUE] minutes; no ticket issued meanwhile |
| Duplicate or replayed webhook | No-op |
| Provider outage | New checkouts show an unavailable state; holds expire normally; no partial ledger entries |
| Refund fails at provider | Refund record `failed`, exception raised, retry by authorized role |
| Payout returned by bank | `payout.failed.v1`, payable restored, payee told to update destination |
| Currency mismatch between order and provider answer | Rejected and raised as an exception |
| Store token reused on another account | Rejected; grant stays with the first verified account |

## 11. Non-functional

Webhook handling p95 under 500 ms to acknowledgement on staging; reconciliation of one day's sandbox volume completes within one hour; zero unreconciled sandbox items older than [OWNER VALUE] days at the Phase 10 acceptance run.

## 12. Choices still open

| Choice | Options | Recommendation |
| --- | --- | --- |
| PAY-D1 Payment and payout provider (GD-20) | Owner selects after legal and commercial review; KoloVibe builds to the interface with the sandbox adapter | Keep the sandbox adapter only until the owner names a provider; no provider is assumed here |
| PAY-D2 How businesses pay for ads shown inside KoloVibe | (a) business ad purchases happen only outside the mobile apps (console or invoice outside the store apps; the app never offers or links to purchase); (b) store billing in the apps for ad purchases; (c) both, by platform | (a) for the first release: it avoids selling in-app ads through the app; confirm with Apple App Review and Google Play policy support in writing before release, because 3.1.3(g) names in-app boosts |
| PAY-D3 Ticket payments in the apps | (a) provider payment sheet in the app (Play: live-event tickets exempt; Apple: 3.1.3(e)); (b) tickets bought outside the apps only | (a), subject to written App Review confirmation recorded before submission |
| PAY-D4 Creator payouts | Confirm with both stores that outbound payouts have no store billing implication | Record written confirmation before Phase 10 store submission |
| PAY-D5 Values marked [OWNER VALUE] | Webhook tolerance, hold minutes, retention years, reconciliation ageing | Owner supplies; development uses test values in configuration clearly marked as test |

## 13. Traceability

FP-FN-05, FP-FN-06 and FP-EV payment rows; FN-R-060 to FN-R-065; EV-R E5; AD-R A7; GD-01, GD-04, GD-20; issues #307, #313 to #317, #318 to #320.
