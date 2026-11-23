# P3-02 — Engagement → Points event pipeline, tested across the real services

**Type:** integration test (no production code changed) + one CI step. **Baseline reference:** Phase 0 risk R-08, backlog B-11 (repository part only).

## What it proves
`scripts/verify_event_pipeline.py` (8 tests) runs the real Engagement and Points code, in separate processes (they are both the package `service`, as in production), against the disposable TLS PostgreSQL the CI already uses, one database role per service. The two sides exchange only JSON, as Celery would carry it, through `scripts/event_pipeline_steps.py`.

| Boundary | Test | Result |
| --- | --- | --- |
| Qualified view → outbox → message | message is task `kolovibe.points.event` to exchange `kolovibe.points`, routing key `kolovibe.points`, queue `kolovibe.points`, **no-declare on queue and exchange** (no broker declaration or binding by Engagement), persistent, `task_id` equals event id, payload is exactly `creator_user_id` + `qualified_at` | pass |
| Message → inbox → receipt → ledger | one award, receipt `posted`, one `points.awarded` evidence row | pass |
| Broker interruption | first publish fails, the event stays unpublished, the retry publishes every event, consumption posts each once | pass |
| Duplicate delivery | the same message four times: one entry, one receipt, applied once | pass |
| Concurrent redelivery | six simultaneous workers on one event: one entry, no errors | pass |
| Worker killed after the receipt, before posting | an honest `pending` receipt and no award; redelivery completes it exactly once | pass |
| Daily cap (withheld) | cap seeded at 99: three events → one award, two `withheld` receipts, **no ledger rows for withheld**, counter 100; replays change nothing | pass |
| Audit evidence delivery | delivery failure retains evidence for retry; the next run delivers to `audit /internal/security-events` with exactly the six agreed fields and **no creator identifier** | pass |
| Reversal behaviour the schema enforces | positive, targetless, zero and repeated reversals are refused; one negative reversal of an award is accepted; update, delete and ORM re-save are refused | pass |

Mutation check: removing both the receipt state guard and the inbox check (leaving only the unique ledger constraint) fails three tests. Removing the inbox check alone does **not**, because the receipt state machine independently prevents a second effect; exactly-once rests on three layers (receipt state, inbox, unique `source_decision_id`).

## What it deliberately does not claim
- **No RabbitMQ.** The broker is replaced by a recording publisher. The message shape, exchange, routing key and no-declare flags are asserted; the broker's own permission, confirm and durability behaviour is untested here and stays an owner staging acceptance. Permissions were not touched.
- **Reversals have no write path.** Only the constraint behaviour above is tested; no rule for when a reversal is allowed is approved (Phase 2 report), and none was invented.
- **Poison messages.** `receive_event` raises `ValueError` for a malformed payload and is not retried; with `acks_late` the broker acknowledges the failure and there is no dead-letter queue configured in the repository. Adding one needs broker configuration (owner action) and is recorded as a gap, not changed.

## CI
New step "Cross-service event pipeline (disposable PostgreSQL)" in the Python job runs the script with the PostgreSQL tools on `PATH`, like the other disposable-database checks. The file is named `verify_*` so `unittest discover` does not try to run it without a database.
