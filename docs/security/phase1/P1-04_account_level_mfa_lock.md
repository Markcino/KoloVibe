# P1-04 — Account-level MFA failure lock

**Type:** security fix (small production change + regression tests). **Baseline reference:** Phase 0 risk R-04, backlog B-05; 13 November review residual risk. **Owner approval required before merge** (changes authentication behaviour under ADR-013).

## Problem (reproduced)
MFA guessing was limited per challenge (5 failures) and, indirectly, per `email + origin` (each privileged password success consumes one of five login slots per 15 minutes). Neither bounds total guesses against one account: a caller who holds a moderator's or administrator's password can obtain challenges from different network origins, each with its own login throttle key and its own 5-failure budget.

Reproduction (`test_account_level_lock_stops_guessing_across_challenges_and_origins`, failing before the fix): ten wrong codes across two challenges and two origins, then a **correct** code from a third origin returned `200` with a session instead of being refused.

## Root cause
`verify_mfa` counted failures only on the `MfaChallenge` row. No counter was keyed on the account.

## Fix (`services/identity/service/mfa.py`)
- After the challenge checks and before the code is examined, `verify_mfa` refuses with `429 Too many MFA attempts` when the account already has 10 MFA failures in the current 15-minute window (`MFA_ACCOUNT_FAILURES`, `MFA_ACCOUNT_WINDOW`). Because the check precedes code verification, a correct code cannot end the lock early.
- Each failed code (TOTP or recovery) adds one to the account's counter; a success clears it.
- The counter reuses the existing `LoginThrottle` table and the existing `_bucket_full`, `_bucket_add` and `_guard_key` helpers (`code-guard` hashed key), so there is **no migration**, no new table, and no new abstraction.
- The lock is audited with the existing `login.throttled` kind, which Identity and Audit already share, so deployment order between the two services does not matter.

## Tests (`services/identity/tests/test_mfa_audit.py`)
- Account lock across challenges and origins; correct code refused during the lock; no session or token in the refusal; audited; lock expires after its window and a fresh challenge then succeeds.
- Failures below the limit never block, and a success clears the count (three rounds of four failures each succeed).
- Whole Identity suite: 141 tests OK. Service-identity drift test OK.

## Compatibility and risk
- API: no new fields or routes. A locked account receives the existing `429` shape already returned for per-challenge exhaustion; clients that handle that case need no change.
- Availability trade-off: someone who knows a privileged account's password can lock that account's MFA for up to 15 minutes by failing ten times. Passwords are a precondition, privileged accounts are few, and the lock is bounded; the alternative (unbounded guessing) is worse. A legitimate user with a correct code within the window is refused until it expires, and recovery is waiting or an administrator action.
- Residual: the per-origin value still comes from the gateway-supplied origin; hardening origin attribution is separate.

## Not done
No staging activation, no migration, no change to TOTP step handling or recovery-code policy.
