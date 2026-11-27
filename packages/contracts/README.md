# Canonical contracts

One API authority: [DOC-205](../../docs/architecture/DOC-205_OpenAPI_3_1_DRAFT.yaml).
One event authority: [RabbitMQ event catalogue](events/catalogue.yaml).

Version `1.1.0-review` is a Phase 2 review candidate, **not an approved or deployed full-product contract** (#305/#141). The stable `_DRAFT` filename preserves existing links. The former independent `openapi/health.yaml` is retired; health operations remain in DOC-205 and Git retains the old fixture. Per-area Markdown proposals are historical design rationale, never parallel endpoint/schema authorities.

## Lifecycle and compatibility

Existing operations keep their implementation annotations. `x-implementation: planned` means no runtime route, migration or capability exists. CI separately checks implemented path/method parity, anonymous default-deny behavior and non-exposure of planned operations. Marking an existing route planned fails the non-exposure check. New planned operations require ownership, authorization, requirement and approval metadata. Promotion requires the owning service, Gateway, clients, authorization tests, migration plan and explicit contract review; Phase 3+ implementation is not authorized by Phase 2.

Breaking changes require reviewed ADR-022, a new major API/event version and a documented consumer migration period. Additive optional fields must not change authorization or financial meaning. Required-field additions, event meaning changes and relaxed authorization are breaking. Unknown source/type/schema versions fail closed. New target domain events do not silently replace the legacy Celery argument envelope. `events.py` implements delivery; the catalogue documents the actual contract and CI checks allowlist parity.

## Reconciliation choices for review

| Conflict | Candidate canonical resolution | Approval / evidence |
| --- | --- | --- |
| Events-owned ledger/provider vs Finance | Finance alone owns monetary journal, intents, provider adapters, verified callbacks, refunds and settlement; Events owns reservation/order/ticket workflow | Decision J, GD-01/02 and approved PAY-R-001/007 |
| Finance excludes Points snapshot | Immutable finalized eligible-Points snapshot is pool weighting only, never redemption | Decision J; ADR-FIN-001 current section |
| `ads` producer/schema/service name | `advertising`; old `ads.*` names remain historical proposal aliases only | Mandate 12-service list; ADR-AD-001 |
| Order creation variants | `POST /events/{event}/orders`, body reservation id; `GET /orders` and `GET /orders/{id}` for own orders | PAY section 7 takes precedence over old Events proposal; technical review pending |
| Refund request plural/singular | `POST /orders/{id}/refund-request`; Finance performs refund and publishes outcome | Approved FP-PAY; technical review pending |
| Advertiser payment at `/business/me/invoices` vs advertiser membership | No mobile ad payment operation is exposed in the candidate. Advertising owns `/advertisers/{id}/invoices`; Finance owns payment evidence. PAY-D2 chooses outside-mobile purchase, while mandate prohibits a public advertiser portal | **BLOCKED** on compatible sales channel and written store confirmation; #305/#322. M-449 explicitly unavailable. No billing workaround invented |
| Public provider callbacks vs internal-only simulator | Target callbacks documented as planned, Finance-owned and provider-signature protected; sandbox still uses internal simulator. No route activated | Provider-specific schema/signature/headers and ingress review **BLOCKED** until a provider is named (#315) |
| New Notifications preferences vs existing `/me/preferences` | Identity is the only preferences authority; new route is a projection/update to the existing data, not another store | ADR-NT-001; field-level compatibility review pending |
| Google ad report target and comment moderation target | Existing Moderation operations require additive `target_type` and context/appeal schema extensions; not falsely represented as implemented | **Incomplete contract detail**, #305; FP-CM CM-R-020, FP-GA GA-R-013 |

## Security and financial requirements

New money inputs are decimal strings plus currency; no floats, client prices, client beneficiaries or state injection. Approved currency exponents and policies are required before calculation. Posting balances per book/currency and atomically records source inbox, journal, audit/outbox. Uniqueness plus digest catches altered redelivery. Refund totals serialize under Finance locks. Provider signature over raw bytes, timestamp/replay guard and server-side retrieve agreement are mandatory; app redirects grant nothing. Late success after inventory expiry enters an explicit exception/refund saga.

Idempotency scopes actor, operation, resource and request digest. Same key/different body gives 409. Sensitive writes require current role/grant and Decision G proof; financial actors remain distinct. Object denial is 404. No-store private responses, bounded errors, cursor paging, no secrets or private text in logs/events. Existing APIs retain their actual response shapes; planned errors use `{detail, code}`. Finite retry/DLQ policy remains a runtime implementation task (#311), not a completed broker change.

## Known remaining contract detail

The candidate expands the interface inventory but does not satisfy the Phase 2 exit criterion yet. The review candidate now has resource-specific Events, campaign, invoice, statement, allocation, payout and image views; typed policy/revenue/hold/adjustment/batch/configuration inputs; internal Finance pricing/fact requests; a Points snapshot reader and held-comment/context reads. Remaining review gaps include exact per-operation grants/state/error matrices, event revision detail, default comment settings, notification recipient-resolution contracts and additive changes to existing Moderation/report/configuration schemas. Generic action receipts intentionally return id/state/version only; queue/grant/verification projections still need field-level review. Provider-specific callbacks and store billing are intentionally blocked rather than guessed. These are #305 work, not an owner signature that can be invented or a feature deferred to implementation.

Validation: `python -m unittest scripts.test_full_application_contracts scripts.test_gateway_route_contract scripts.test_business_contract_reconciliation scripts.test_contract_copies_in_sync`. These prove schema and bounded invariants, not payment, broker, privacy or product runtime acceptance.
