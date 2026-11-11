# BE-ID identity/settings acceptance — 11 November 2026

Source baseline: `8d5603172df96b688d6249ddb913f4ac241f9090` (main). Local verification only; this is not deployment acceptance.

## Gaps found before changes

- No public/internal reauthentication endpoint or session-bound single-use proof model.
- Privacy intake accepted only `current_password`, returned existing requests with 200 and enforced uniqueness across closed as well as open requests. Gateway accepted only `received` and at most two receipts.
- Password change revoked the caller's session as well as other sessions. Password changes had no shared password-attempt throttle, and reset delivery failure could disclose an eligible account through a different status.
- Audit ingestion rejected the already-produced preferences/privacy event kinds. Session listing had no audit event.
- No app compatibility endpoint or environment policy configuration.
- MFA replay tests generated a fresh TOTP for each assertion. Crossing a 30-second boundary could turn an intended replay into a valid new code.
- Access revocation was already enforced: gateway `current_account` calls identity `/internal/auth/validate`, whose `_session_for_access` checks live session revocation, expiry, account state and role/MFA state. No stateless-token bypass was found or introduced.

## Implementation

- `POST /api/v1/me/reauthenticate` → identity `/internal/auth/reauthenticate`: current password, generic 400 failure, account-wide five-attempt/fifteen-minute budget (429), keyed token digest, account/session binding, five-minute expiry and one-use consumption. Successful issuance records `account.reauthenticated` through `SecurityEvent` + `AuditDelivery` in the owning transaction. Failed and throttled proof checks are audited without credentials.
- Privacy intake prefers `reauth_token` and retains `current_password` compatibility. A supplied bad token never falls back to the password. Valid tokens are consumed even for an open-request conflict (409, `code: request_open`). Receipts remain exactly `{id, kind, status, created_at}`; list returns the newest 40. Status values are `received|in_review|completed|declined`; existing `received` data is already canonical and remains unchanged. Only open requests block another request of the same kind. Deletion remains intake-only under ADR-020.
- Identity model `ReauthenticationToken`, explicit `PrivacyRequest.Status` choices and migration `0009_reauthentication_open_privacy_requests.py`: token table plus replacement of unconditional privacy uniqueness with an open-status conditional constraint.
- Password reset revokes every session and invalidates proofs; password change requires the current password, shares the attempt budget, preserves the current session, revokes other sessions and invalidates outstanding proofs. Profile/preferences/session mutations recheck session state under account/session locks. Logout has an empty 204 body. Account responses prevent caching.
- MFA tests freeze issuer/verifier clocks and use a fixed test-only factor. They still assert password insufficiency, challenge reuse rejection and consumed-TOTP rejection, and separately prove a new timestep works. Production MFA verification is unchanged.
- `GET /api/v1/app/compatibility?platform=ios|android&version=X.Y.Z`: public gateway-only `compatibility.py`, strict SemVer 2.0 parsing/precedence, required unique query parameters, per-platform optional bounds, validated HTTPS store URL and settings-load rejection of malformed/inconsistent configuration. Unconfigured platforms return the exact unknown/null response. Version statuses are `update_required|update_available|supported|unknown`.
- Gateway settings load all six `KOLOVIBE_APP_MIN_VERSION_IOS|ANDROID`, `KOLOVIBE_APP_LATEST_VERSION_IOS|ANDROID`, `KOLOVIBE_APP_STORE_URL_IOS|ANDROID` names. The local launcher forwards them only to gateway.
- DOC-205 adds local Identity request/response schemas and the Operations-tagged compatibility operation.

Primary files: identity `accounts.py`, `models.py`, `preferences_privacy.py`, `security_audit.py`, `urls.py`, migration 0009 and tests; gateway `accounts.py`, `preferences_privacy.py`, `compatibility.py`, `settings.py`, `routes/identity.py` and tests.

## Exact verification commands and results

Commands ran with Python 3.12.14, Django 5.2.18, cryptography 50.0.2, pyotp 2.10.0 and openapi-spec-validator 0.9.0. The existing local dependency directories were reused. From repository root, the environment and commands below reproduce the executed configuration:

```bash
export KOLOVIBE_ENV=local
export DJANGO_SECRET_KEY=local-be-id-test-key-at-least-32-characters
export PYTHONPATH=/workspace/scratch/7d4e52b069cd/kolovibe-dec003/deps:/workspace/scratch/7d4e52b069cd/kolovibe-stream.hKze2v/deps:/workspace/scratch/100b9f85b85d/kolovibe-be-id/services
```

| Command (from repository root) | Result |
| --- | --- |
| `(cd services/identity && python3 manage.py test tests --verbosity 1)` | 55 passed |
| `(cd services/gateway && python3 manage.py test tests --verbosity 1)` | 72 passed |
| `(cd services/audit && python3 manage.py test tests --verbosity 1)` | 9 passed |
| `python3 -m unittest discover -s scripts -p test_run_local_service.py -v` | 8 passed |
| `(cd services/identity && python3 manage.py makemigrations --check --dry-run)` | Passed; no changes detected |
| `(cd services/gateway && python3 manage.py makemigrations --check --dry-run)` | Passed; no changes detected |
| `python3 -c "import yaml; from openapi_spec_validator import validate_spec; validate_spec(yaml.safe_load(open('docs/architecture/DOC-205_OpenAPI_3_1_DRAFT.yaml'))); print('DOC-205 OpenAPI 3.1: PASS')"` | Passed |
| `python3 scripts/check_structure.py` | Passed; eight services and approved layout |
| `git diff --check` | Passed |

144 tests passed. Tests exercise proof expiry/replay/cross-session/cross-account rejection, shared throttling, outbox rollback, open/closed request constraints, reset/change/logout revocation, verification resend replacement/failure, gateway live validation, version policy/configuration and audit ingestion.

## Cross-ownership edits and remaining limits

- Audit: `services/audit/service/events.py` and `tests/test_events.py` align the ingestion allowlist and test idempotent receipt of the identity settings/security kinds.
- Shared launcher: `scripts/run_local_service.py` and its test add gateway-only configuration forwarding.
- Shared contract: only the Identity and Operations additions in DOC-205; no other service behavior was changed.
- Suites used SQLite. PostgreSQL concurrency/deployment checks and live TLS audit delivery were not run. Apply identity migration 0009 before activating the endpoints in a deployed environment.
- Reverting migration 0009 after multiple closed requests exist for an account/kind requires an owner-reviewed data reconciliation before the old unconditional uniqueness constraint can be restored. No automatic receipt deletion or account/data purge is provided.
- These changes do not deploy services or enable privacy request processing.
