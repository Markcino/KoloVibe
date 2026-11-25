# Finance API and event contracts (proposed)

**Status: PROPOSED — not approved; not yet in DOC-205.** 25 November 2026. On approval these become OpenAPI 3.1 in `packages/contracts/openapi` plus versioned JSON schemas for business events, with the same contract-reconciliation test as Business. Paths under `/api/v1`. The client never sends a payee id, amount basis, policy value, role or state.

## Conventions

| Item | Rule |
| --- | --- |
| Flags (closed by default) | `finance_payee` (F4), `finance_admin` (F6 console). Business-event ingestion has no HTTP route (broker only). |
| Money in JSON | `{ "amount": "<decimal string>", "currency": "<approved ISO 4217 code>" }` (a decimal **string**, shape only); integers or JSON floats for money are refused |
| **MFA**, **VE**, **ID**, **SU** | as in the Business, Events and Ads contracts; **GR(x)** = Finance grant x required |
| Non-entitled | 404 on objects; console pages answer 404 when the grant is missing |
| Pagination | Keyset; bounded; period filters mandatory for history |
| Errors | `{detail, code}` bounded; includes `parameter_not_approved`, `not_eligible`, `frozen`, `conflict_of_duties` |

## F4 — Payee operations (`finance_payee`, signed-in, verified email; resolved from the session, no payee id)

| Operation | Method and path | Flags | Notes |
| --- | --- | --- | --- |
| `fin_overview` | GET `/me/finance/overview` | VE | Pending, released, held and settled totals per currency; **no Points data** |
| `fin_revenue_history` | GET `/me/finance/revenue-history?period=&cursor=` | VE | Allocation lines by period |
| `fin_allocations` / `fin_allocation_get` | GET `/me/finance/allocations[/{id}]` | VE | Policy version id and hash shown; own only |
| `fin_statements` / `fin_statement_get` | GET `/me/finance/statements[/{id}]` | VE | In-app data, no download link |
| `fin_payout_eligibility` | GET `/me/finance/payout-eligibility` | VE | Server states eligible or the reason code |
| `fin_destination_add` | POST `/me/finance/payout-destinations` | VE, ID, **SU** | Provider-tokenized; returns mask only |
| `fin_destination_list` / `remove` | GET, DELETE `/me/finance/payout-destinations[/{id}]` | VE, SU on remove | Masked |
| `fin_payout_request` | POST `/me/finance/payouts` | VE, ID, **SU** | Body: destination id, amount; server checks eligibility and payable under lock |
| `fin_payout_list` / `get` / `cancel` | GET `/me/finance/payouts[/{id}]`, POST `…/cancel` | VE, ID on cancel | Cancel only before release |
| `fin_dispute_open` / `list` | POST, GET `/me/finance/disputes` | VE, ID | Subject: own allocation or statement |

## F6 — Console operations (`finance_admin`, MFA on all; page grants in brackets)

| Operation | Method and path | Grant | Notes |
| --- | --- | --- | --- |
| Policy: `policy_draft`, `policy_submit` | POST `/admin/finance/policies…` | `fin_policy_author` | Draft may hold nulls; submission validates structure |
| `policy_approve` / `reject` | POST `…/{p}/approval` | `fin_policy_approver`, **SU** | Approver ≠ author; evidence reference; effective date in the future |
| Revenue: `revenue_sources`, `revenue_records`, `revenue_manual_create` | GET/POST `/admin/finance/revenue…` | `fin_preparer` (create), `fin_approver` (approve), `fin_auditor` (read) | Unique provider reference |
| Reconciliation: `recon_run`, `recon_items`, `exception_prepare`, `exception_resolve` | `/admin/finance/reconciliation…` | `fin_reconciler`, `fin_preparer`, `fin_approver` | No auto-correction |
| Period: `period_close_request`, `period_close_approve` | POST `/admin/finance/periods/{p}/close…` | `fin_preparer`, `fin_approver` | Approver ≠ requester |
| Allocation: `run_get`, `run_review`, `run_approve`, `run_reject` | `/admin/finance/allocation-runs…` | `fin_approver`, `fin_auditor` | Cannot edit figures |
| Holds: `hold_place`, `hold_release_request`, `hold_release_approve` | `/admin/finance/holds…` | `fin_fraud`, `fin_preparer`, `fin_approver` | Release needs approval |
| Adjustments: `adjustment_prepare`, `adjustment_approve` (twice), `adjustment_post` | `/admin/finance/adjustments…` | `fin_preparer`, `fin_approver` | Two distinct approvers; payee excluded |
| Payouts: `payout_queue`, `payout_approve`, `payout_release_batch`, `payout_failed_handle` | `/admin/finance/payouts…` | `fin_approver`, `fin_releaser` | Approver 1 and 2 distinct; releaser a third account; release **SU** |
| Freeze: `freeze_place`, `freeze_lift_request`, `freeze_lift_approve` | `/admin/finance/freeze…` | any approver or fraud (place); two approvers (lift) | Asymmetric |
| Statements: `statement_view` | GET `/admin/finance/statements/{s}` | `fin_auditor`, scoped `fin_approver` | Access-controlled; every view audited |
| Audit reports: `audit_report`, `ledger_verify`, `sod_report` | GET `/admin/finance/audit…` | `fin_auditor` | Chain verification, SoD conflict report |
| Grants: `grant_request`, `grant_approve`, `grant_revoke` | `/admin/finance/grants…` | administrator ×2 | Step-up; exclusivity enforced |

## Business events into Finance (broker, signed, schema-versioned)

Envelope: `{schema_version, event_id (UUID), source_service, kind, occurred_at, subject_id, amounts: [{amount, currency}], payload_hash}`; signature by the producer's service identity; **allowlist of (source_service, kind)**; unique `(source_service, event_id)`.

| Kind | Producer | Effect in Finance |
| --- | --- | --- |
| `events.payment_captured` | Events | Template T3 |
| `events.refund_settled` | Events | Template T4 |
| `ads.invoice_issued` | Ads | Revenue record (recognized per policy) |
| `ads.correction_posted` | Ads | Adjustment request (still needs Finance approvals) |
| `engagement.basis_finalized` | Engagement (if basis (a) is approved) | Registers a `basis_dataset` |
| `creators.eligibility_snapshot`, `business.eligibility_snapshot` | Creators, Business | Registers an `eligibility_snapshot` |

Rejected: any kind not listed, any kind from Points, unknown sources, schema versions not supported, amounts as floats, unknown currencies. Each rejection is counted by reason; payloads are not stored.

## Provider interfaces (internal, sandbox only)

| Interface | Methods | Notes |
| --- | --- | --- |
| `RevenueStatementSource` | `fetch(period)`, `verify_notification(raw, headers)` | Sandbox generator with injectable defects |
| `PayoutProvider` | `create(payout_id, destination_ref, amount, currency, idempotency_key)`, `retrieve(payout_id)`, `verify_notification(raw, headers)`, `cancel(payout_id)` | Confirmation needs a verified signature, a unique provider event id **and** a `retrieve` agreeing on id, amount and currency |
| `BasisProvider` | `finalized(period)` | Returns rows and a hash; immutable |
| `EligibilityProvider` | `snapshot(period)` | Signed rows and a hash |

## Scheduled jobs (management commands, sandbox)

`expire_stale_payouts` (flags aged in-flight payouts as exceptions), `poll_payout_status` (retrieve for in-flight payouts), `verify_ledger` (balance, chain, projection, statement totals), `export_digest` (daily signed digest), `reconcile` (per source). Correctness never depends on a job: the posting path checks its own preconditions.

## Audit kinds (new Audit producer `finance`; an Audit change needing approval)

`policy.drafted`, `policy.submitted`, `policy.approved`, `policy.rejected`, `revenue.recorded`, `revenue.state_changed`, `recon.run_completed`, `recon.exception_opened`, `recon.exception_resolved`, `period.close_requested`, `period.closed`, `allocation.computed`, `allocation.reviewed`, `allocation.approved`, `allocation.posted`, `hold.placed`, `hold.released`, `adjustment.prepared`, `adjustment.approved`, `adjustment.posted`, `payout.requested`, `payout.approved`, `payout.released`, `payout.settled`, `payout.failed`, `destination.changed`, `freeze.placed`, `freeze.lifted`, `grant.requested`, `grant.changed`, `statement.viewed_by_staff`, `dispute.opened`, `dispute.decided`, `sod.conflict_refused`. Ids and codes only. About 55 operations in total; the exact number is fixed when the OpenAPI is written.
