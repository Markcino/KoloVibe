# P1-03 — Refresh rotation, replay and revocation regression tests

**Type:** regression guard (test only; no production code changed). **Baseline reference:** Phase 0 risk R-05 (SEC-08), backlog B-04.

## Issue examined
Existing Identity tests covered one rotation followed by one replay, and logout followed by refresh. They did not prove: replay of a token rotated several generations ago; that a wrong or guessed refresh token cannot revoke or hijack a session whose id is known; that security events carry no token material; or that signing out one session leaves the account's other sessions untouched.

## Tests added (`services/identity/tests/test_account_api.py`)
- `test_replay_of_an_old_refresh_token_revokes_the_family_and_the_newest_token`: A→B→C rotation, replay of A returns 401, C's refresh and access are then rejected, revoke-by-C is rejected, one `session.replay` event is recorded.
- `test_replay_events_and_audit_rows_carry_no_token_material`: no access or refresh token (or its secret part) appears in stored security events; the event table has no column that could hold a credential.
- `test_a_wrong_refresh_token_cannot_revoke_someone_elses_session`: tampered secret, reversed secret, unknown session id, empty secret and bare session id are all rejected by refresh and by logout-by-refresh; the genuine session stays valid and can still rotate.
- `test_signing_out_one_session_leaves_the_account_other_sessions_valid`: second logout of the same session is 401; the other session still validates and refreshes.

## Result
No defect found at HEAD `bb79e1a`. Mutation check: making a non-replay digest mismatch revoke the session fails the wrong-token test; reverted.

## Not covered (needs PostgreSQL concurrency or staging)
- Two simultaneous refresh requests with the same token produce exactly one success. The implementation uses `select_for_update` on the session row; the SQLite test database cannot exercise row locks. Candidate for the CI PostgreSQL job (`scripts/test_postgres_foundations.py`).
- Deployed-stack refresh/logout behaviour (SEC-08 device evidence) remains an owner staging test.
