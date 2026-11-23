# P2-02 — Bounded retention of expired Identity security rows

**Type:** fix (no migration, no model change). **Backlog:** Phase 2 gap analysis; relates to ADR-020/OD-08 (retention) without deciding them.

## Problem
Identity keeps several short-lived tables and never deleted from any of them: `LoginThrottle`, `UsedRefreshToken`, `ReauthenticationToken`, `MfaChallenge`, `EmailVerification`, `PasswordReset` and finished `LoginSession` rows. The first is created by **anonymous** login attempts (one row per email+origin, before the password is checked), so an unauthenticated caller could make it grow without bound; the others grow with normal use. Only the web console had a purge job.

## Change
- `services/identity/service/retention.py`: `purge_expired(now, batch)` removes at most `batch` (default 1,000, max 10,000) expired rows per table, each table in its own transaction, and returns counts only.
- Grace periods keep anything the service may still read: throttle windows one day (a stale window is just reset), refresh-replay markers one day past session expiry (replay is only consulted while a session can refresh), reauthentication tokens and MFA challenges one day, email-verification and password-reset rows seven days, sessions thirty days after expiry or revocation (then their reauthentication tokens cascade).
- `maybe_purge()` runs it opportunistically from `login` at most every five minutes per process and swallows `DatabaseError`, so no login can fail because of it. It ships with the image: no job, no infrastructure change.
- `manage.py purge_expired_security_rows [--limit N]` lets the owner run or schedule it explicitly; it prints counts only.
- **Never touched:** accounts, security events, audit deliveries, moderator invitations, privacy requests, TOTP factors and recovery codes. Their retention is a policy decision (ADR-020, OD-08) and is not made here. Unverified-account clean-up is likewise a policy question and is not done.

## Tests (`services/identity/tests/test_retention.py`, 8)
Old rows go and recent ones stay; rows inside their grace stay; revoked sessions kept one month then removed; accounts/events/deliveries untouched even when ancient; one run removes at most one batch and invalid batches are rejected; a live session's replay is still detected after a purge (a mutation that over-purges replay markers fails three tests); login triggers a rate-limited purge and a failing purge never blocks login; the command prints counts only and validates `--limit`.

Whole identity suite 147 tests OK, `makemigrations --check` reports no changes, drift test OK.

## Notes
- No audit event is written for the purge: it deletes only expired throwaway rows, adding a kind would require a coordinated Audit deployment, and the purge logs counts only (no identifiers).
- Runtime role needs `DELETE` on these tables; it owns them today (see the Phase 0 B-09 and #198 caveat).
