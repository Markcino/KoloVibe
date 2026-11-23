# P2-01 — Bound the internal request nonce tables

**Type:** fix (shared verifier, all eight services). **Backlog:** operations/data-minimisation gap found during the Phase 2 gap analysis; relates to Phase 0 risks R-09/R-14 (resource limits).

## Problem
Every authenticated internal request inserts one row into the receiving service's `internal_request_nonce` table, for replay protection. Nothing ever deleted them (no `delete`/purge in any verifier copy, migration or management command), so each service's table grows by one row per internal call, indefinitely.

## Why it is safe to forget old nonces
A request is accepted only if its signed timestamp is within 60 seconds of now, and that check runs **before** the nonce insert. A nonce older than the retention (10 minutes, ten times the window) can therefore never match a valid timestamp again; deleting it cannot enable a replay.

## Change
In the shared service-identity verifier (identical in every service, guarded by `scripts/test_service_identity_drift.py`):
- `_purge_expired_nonces()` deletes at most `NONCE_PURGE_BATCH` (5,000) rows older than `NONCE_RETENTION_MINUTES` (10), at most once per `NONCE_PURGE_INTERVAL` (60 s) per process, after the request's own nonce is stored.
- It runs in its own transaction and swallows `DatabaseError` (logging a fixed message only), so a purge problem can never deny or fail a valid request.
- PostgreSQL uses `ctid` batching with `make_interval`; SQLite (local tests) uses `rowid` and `datetime('now', …)`.
- No migration, no new table, no new job: it needs no infrastructure change and starts working when the image is deployed.

## Tests (the shared `tests/test_service_identity.py`, identical in all eight services)
Expired nonces removed while the accepted request's nonce remains and replay still fails; one purge removes at most one batch and a second request inside the interval does not purge; nonces younger than retention are never purged; a failing purge (invalid batch parameter) still accepts the valid request and still blocks its replay. 4 tests × 8 services.

Also verified on a real PostgreSQL (the CI TLS fixture) with the service login roles: batch limit honoured, recent rows kept, `received_at` is `timestamptz`.

## Suites
gateway 187, identity 143, creators 76, content 127, engagement 71, points 68, moderation 71, audit 48: all OK. Drift test OK.

## Dependency on database privileges
The runtime login must be able to `DELETE` from its nonce table. Today it owns the table, so this works. If the owner later re-owns objects (Phase 0 B-09, report in #198), the runtime role must keep `DELETE` on `internal_request_nonce`; otherwise the purge logs an error and the table grows again (requests are still served).
