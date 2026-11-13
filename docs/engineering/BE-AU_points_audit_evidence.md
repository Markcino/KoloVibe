# BE-AU points audit evidence — 13 November 2026

Baseline: main `06f941d00d92a52d8f6861b7621590d97b2367e1`. Local verification only; no deployment or release acceptance is implied.

## Gap found

The audit service already accepted `points.*` events from a `points` producer, but the Points service never produced any. Qualified-view awards and daily-cap withholdings were visible only in the ledger and receipts. Audit coverage for creators and content has the same gap and is separate work.

## Implemented

- Points migration `0005_audit_evidence` adds `points_audit_event` and `service_auditdelivery`. Update, delete and truncate guards make events append-only on PostgreSQL (and update/delete on fixture SQLite).
- `apply_qualified_view` records `points.awarded` (ledger entry posted) or `points.withheld` (`DAILY_CAP` outcome) inside the same transaction that decides the outcome. If evidence cannot be written, the ledger entry, cap counter and terminal state roll back and the pending receipt is resumed by the broker retry. Duplicate or replayed events add no evidence.
- Evidence holds only the kind, time and subject (the qualification event id, which is also the ledger entry id for posted awards). It carries no account, creator or video identifier. The actor is null because these are server decisions. A withheld event has no ledger row; its subject is the receipt id.
- `python manage.py deliver_audit_events [--limit N]` sends due events to the audit service: two-second timeout, batch 1..1000, exact acknowledgment required, exponential retry capped at one hour, failed evidence retained indefinitely.
- Server ownership of qualification, the daily cap, and non-cash points is unchanged. No public API, formula or gateway change.

## Not covered

- `points.reversed` and `points.adjusted` are allowed by the audit service but no code path writes reversals or adjustments yet; they are deliberately not emitted. Any future write path must record evidence in its own transaction.
- Legacy outcomes (`legacy` receipts and events consumed before receipts existed) are not backfilled.
- Audit delivery runs only when someone schedules the command. This change installs no scheduler.

## Deployment dependencies and rollback

- Apply Points migration 0005 first. The points database login needs insert/select/update on the two new tables (update on delivery only).
- The staging stack currently gives no Points outbound signing key or peers file. Before delivery works, provision `KOLOVIBE_OUTBOUND_KEY_FILE` and `KOLOVIBE_TRUSTED_PEERS_FILE` (audience `audit`, verified HTTPS) for Points, add a distinct `points` key to the audit caller-key file, and schedule `deliver_audit_events`. Until then evidence accumulates safely in Points and posting is unaffected.
- Rollback: unapplying 0005 drops the evidence tables and loses undelivered events (the PG guard function remains, harmless). Export undelivered rows first under a reviewed plan. Reverting only the code leaves rows in place and stops new evidence.

## Verification

```bash
cd services/points && KOLOVIBE_ENV=local DJANGO_SECRET_KEY=<generated> python manage.py makemigrations --check --dry-run && python manage.py test tests
cd services/audit && python manage.py test tests
```

Results: Points 34 tests and Audit 13 tests passed on SQLite. The Points suite also passed 34/34 on a disposable PostgreSQL 16 cluster (local socket, no TLS). On that cluster, 0005 applied, unapplied and re-applied, and UPDATE, DELETE and TRUNCATE CASCADE were rejected. Removing the two recorder calls makes six new tests fail. Not exercised: TLS PostgreSQL, live signed delivery to a running audit service, deployed permissions and load.
