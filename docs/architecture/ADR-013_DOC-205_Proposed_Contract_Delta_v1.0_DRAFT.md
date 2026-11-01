# ADR-013 v1.0 — Proposed DOC-205 API Contract Delta

**Status: DRAFT / PENDING ADR-013 APPROVAL — NO BASELINE CHANGE**

This document enumerates the **future** client authentication contract changes implied by [ADR-013 v1.0](ADR-013_Client_Authentication_and_Session_Security_v1.0_DRAFT.md). It is not executable OpenAPI and does **not** alter the current [DOC-205 draft](DOC-205_OpenAPI_3_1_DRAFT.yaml), existing server routes, public ingress, or identity-service capabilities.

## 1. Existing contract: verified repository facts

The existing DOC-205 R1 OpenAPI draft has \`/auth/register\`, \`/auth/verify\`, \`/auth/login\`, \`/auth/refresh\`, \`/auth/logout\` and \`/me\`. Identity endpoints are implemented only for isolated local use; public account deployment remains gated. \`/auth/refresh\` describes the web reading a raw refresh credential from an HttpOnly cookie. \`bearerAuth\` and \`serviceToken\` both say \`bearerFormat: JWT\`, whereas current identity \`accounts.py\` produces a **Django-signed** access credential with a server-side session lookup. This discrepancy must be corrected through an explicit contract revision, not silently described as JWT.

The current web client stores raw access/refresh credentials in HttpOnly local-loopback cookies. The ADR-013 target instead uses a PostgreSQL-backed opaque browser session, with credentials (if any) never stored as reusable raw browser cookies.

## 2. Protocol decisions proposed

| Aspect | Proposed v1.0 contract rule | Change impact |
| --- | --- | --- |
| Mobile access | \`Authorization: Bearer <opaque-signed-Django-access-credential>\`; 300s; \`iss\`, \`aud\`, \`typ\` and live session validated | Clarify \`bearerAuth\`, remove inaccurate \`JWT\` bearer format; no JWT assumption in clients |
| Mobile refresh | One-time rotating \`refresh_token\`, absolute 30d, inactivity 7d | Document family reuse revocation, generic 401, 429 and no-store |
| Browser | Opaque \`__Host-kolovibe_session\` secure cookie; BFF stores only linked session state in PostgreSQL | Replace web refresh-cookie description; add private server-side identity introspection |
| Privileged | Web-only MFA until a separate approval; password-only state cannot access privileged routes | Add MFA-challenge contract and explicit 403/step-up response |
| Session management | List/revoke-own/revoke-all with authenticated principal | New gated routes, ownership tests and audit schema |
| Password reset | Generic request response, 15-minute single-use reset verifier, revoke all on completion | New gated request/complete endpoints and anti-enumeration tests |
| Recovery | Authenticated factor registration/reset, recovery codes, high-assurance review | New gated web-only endpoints, state machine and notifications |
| Workload \`serviceToken\` | ADR-012 remains separate; no assumption that client bearer token is suitable | Do not treat client token as service token |
| Error model | Consistent 401/403/429/503 and no-store; decide rollout from local \`{"detail": ...}\` to Problem schema | Requires explicit backwards-compatible versioning / consumer tests |

\`bearerFormat\` in OpenAPI is a documentation hint, not an authorization mechanism. Proposed v1.0 may omit the bearerFormat hint or describe the signed first-party credential accurately. **Do not** set \`JWT\` unless a JWT implementation has actually been selected, implemented and verified.

## 3. Existing routes: proposed behavior revisions

### \`POST /api/v1/auth/register\` (anonymous)

- The request remains email, password and display name; created accounts remain inactive until email verified.
- Change enumeration-revealing responses to a consistent generic contract where feasible; document whether registration conflict is intentionally exposed after risk review.
- Apply account/IP and edge limits; require approved transactional email delivery; return \`Cache-Control: no-store\`.
- Leave disabled in external staging/production until account gate passes.

### \`POST /api/v1/auth/verify\` (anonymous purpose-bound verifier)

- Accept a one-use high-entropy verifier only, constrained to pending account and action type.
- Preserve current 24h maximum pending reassessment; rate limit verify and resend.
- No privileged login or session granted merely by email verification.

### \`POST /api/v1/auth/login\` (anonymous)

- Mobile normal user: return \`TokenResponse\` containing signed 300s access and rotating refresh credential only after complete successful authentication.
- Privileged: **never return a privileged active session** until MFA is completed. Proposed response is \`202 Accepted\` with purpose-bound, short-lived, single-use \`mfa_challenge_id\`, which is not an access credential. Final route/status format remains an approval and consumer-test item.
- Browser: POST to Django web's CSRF-protected login form; server initiates the identity authentication flow and establishes linked server-side browser session. Do not send a raw refresh credential to the browser in \`Set-Cookie\`.
- After account discovery failures use consistent generic errors and rate limiting, without disclosing whether an email address exists.

### \`POST /api/v1/auth/refresh\` (mobile client only in this proposed design)

- Require \`refresh_token\` (JSON, HTTPS) and validate family, live status, inactivity and absolute deadline.
- On success return one new refresh credential and a short-lived access credential. Old refresh credential becomes invalid immediately. Family reuse yields generic 401 and security event.
- Concurrent refresh double-use must yield exactly one successful rotation and no extra surviving family. \`expires_in\` is the access TTL; include separate \`session_expires_at\` / \`refresh_expires_at\` if approved.
- Do not support a browser cookie as a refresh request transport.

### \`POST /api/v1/auth/logout\`

- Existing route remains current-session revoke; add idempotent revocation semantics that cannot disclose another user's session state.
- For mobile, accept currently authenticated access or currently valid refresh credential under documented rules. After network errors, client clears local credentials and reports unconfirmed server revocation.
- Browser BFF destroys its local Django session and requests identity revocation through authenticated internal transport.
- Must not require a privileged route or fresh MFA merely to log out the current device.

### \`GET /api/v1/me\`

- Continue deriving the account and roles from the authoritative server-side identity/authorization state, not user-supplied role claims.
- Fail closed on identity session revocation, suspended account, expired absolute/idle limit and lost internal identity availability.

## 4. Proposed additional public/client endpoints (NOT IMPLEMENTED)

These route names are **candidate naming choices**, not claims that the current DOC-205 or service already implements them. Adopt names and exact schemas only during post-approval OpenAPI review.

| Method and candidate path | Authentication | Required behavior / restriction |
| --- | --- | --- |
| \`GET /api/v1/auth/sessions\` | Authenticated standard user | Own active sessions, masked/coarse device data only |
| \`DELETE /api/v1/auth/sessions/{session_id}\` | Authenticated + owner; step-up as risk demands | Revoke selected own session only; idempotent, audited |
| \`POST /api/v1/auth/logout-all\` | Authenticated + ≤5-minute reauthentication | Revoke all mobile and web sessions; security event |
| \`POST /api/v1/auth/reauthenticate\` | Authenticated | Verify fresh primary factor and high-risk MFA, issue no unauthorized role upgrade |
| \`POST /api/v1/auth/password-reset/request\` | Anonymous | Generic response even for unknown address; rate limit |
| \`POST /api/v1/auth/password-reset/complete\` | One-use reset token | Reset password, revoke all sessions, notify; no auto-login |
| \`POST /api/v1/auth/mfa/challenge\` | MFA_PENDING web context | Issue short-lived WebAuthn/TOTP challenge; no privileged access |
| \`POST /api/v1/auth/mfa/verify\` | MFA_PENDING web context | Finish MFA; rotate session ID and establish privilege after successful verified factor |
| \`POST /api/v1/auth/mfa/enroll\` | Fresh trusted session / factor check | Enroll factor, verify ownership, show recovery codes one time |
| \`POST /api/v1/auth/mfa/recovery\` | High-assurance recovery context | Single-use recovery code; invalidate old factor sessions |
| \`DELETE /api/v1/auth/mfa/factors/{factor_id}\` | Reauthenticated privileged user | Verify existing factor, prohibit losing last required factor, notify/audit |

**Internal-only identity operations** (not exposed by Cloudflare/Nginx) are also needed to create/introspect/revoke web session references and check factor assurance. Route names and schemas must be designed under ADR-012 authenticated service-to-service trust. A browser-supplied session UUID alone must never authorize an internal lookup or user impersonation.

## 5. Candidate OpenAPI schema requirements

Propose typed schemas (final names to be reviewed): \`TokenResponse\` plus \`session_expires_at\` and \`refresh_idle_expires_at\`; \`SessionSummary\` (\`id\`, \`client_kind\`, \`created_at\`, \`last_active_at\`, \`current\`, \`revoked\`); \`MfaChallenge\` (\`challenge_id\`, \`method\`, \`expires_in\`); \`StepUpRequirement\` (\`required_assurance\`, \`reason_code\`); \`SecurityEventReceipt\` (request ID / generic status). **No response field may contain raw MFA seed, consumed recovery code, token digests, full secret or unrestricted session data.** Factor enrollment may display a secret one time only over a protected workflow.

Security scheme separation:

- \`mobileBearer\`: first-party signed bearer; authenticated through gateway/identity; not JWT by assumption.
- \`webSession\`: host-only browser cookie + CSRF for state-changing requests; Django web BFF only.
- \`serviceCredential\`: internal-only and separately governed by ADR-012.
- \`mfaChallenge\`: a limited challenge state, **never an authentication token**.

For state changes, use POST/DELETE, CSRF on browser operations, exact HTTP status contract and no redirects with credentials. Return \`Cache-Control: no-store\` for login, token refresh, logout, reset, session and factor responses. 401 is unauthenticated; 403 is authenticated but insufficient permission/assurance; 429 indicates throttling; 503 indicates required identity/MFA/dependency unavailable and must fail closed. 204 has no response body.

## 6. Backward compatibility and activation

1. **Before approval:** no change to DOC-205 canonical OpenAPI, currently deployed routes, web cookie behavior, or public ingress.
2. **On approval:** review and sign exact schemas with the Flutter/web consumers; decide whether a new version path or staged contract compatibility period is necessary.
3. **Implementation:** build feature-gated identity, gateway and BFF operations in branches; write contract tests for both current and target behaviors. Do not accept legacy cookie refresh and new BFF session modes in a way that bypasses security.
4. **Staging:** test HTTPS CSRF/cookie, token expiry, MFA, replay, session revocation and negative HTTP response matrix; reject invalid origin and identity-service outages.
5. **Production:** authorize only with complete DOC-206 evidence and release acceptance; no fallback to development settings or legacy privileged login.

## 7. DOC-206 links and reviewer sign-off

Use [ADR-013 DOC-206 proposed verification matrix](ADR-013_DOC-206_Verification_Matrix_v1.0_DRAFT.csv) for negative and compatibility tests. Existing SEC-005/006/007/008/012/015/028/036/039 controls remain authoritative until reviewed update.

| Decision | Status |
| --- | --- |
| Owner selected Django-native identity authority | Recorded 2026-11-01 |
| DOC-205 contract deltas in this file | **Proposed, not approved** |
| Exact wire schemas / credential transport | **Pending review** |
| Consumer and security tests | **NOT RUN against this proposed contract** |
| Production endpoint activation | **Forbidden without separate approval** |
