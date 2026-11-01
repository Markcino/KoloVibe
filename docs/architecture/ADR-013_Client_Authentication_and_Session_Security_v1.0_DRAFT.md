# ADR-013 v1.0 — Client Authentication and Session Security Specification

**KoloVibe — architecture/security decision package**

| Document control | Value |
| --- | --- |
| ID | ADR-013 |
| Version | 1.0 — proposed security specification |
| Created | 2026-11-01 |
| Decision status | **DRAFT — PENDING FORMAL APPROVAL** |
| Decision owner | KoloVibe product owner; sole implementation owner |
| Scope | Django-native identity microservice, Django/DRF API gateway, Flutter Android/iOS, Django server-rendered web, session lifecycle and privileged MFA |
| Source of truth | DOC-207 ADR register; this document is a review candidate only |
| Governing controls | DOC-203 STRIDE, DOC-205 OpenAPI draft, DOC-206 security verification, DOC-209 architecture gate, Stage 3 OD-01 / FND-10 |
| Baseline | Django-native client identity authority was selected by the owner on 2026-11-01 |
| Implementation claim | **None**. Policy parameters below are proposals; most require new implementation and execution evidence |
| Deployment authorization | **None**. No production settings, network, credentials, DNS or public account endpoints are authorized by this draft |

## 1. Decision request and executive summary

**Owner-confirmed and already selected:** retain **Django-native client identity**, backed by PostgreSQL in the existing identity microservice. Use the existing Django/DRF gateway and downstream object-authorization boundaries. Do not introduce a managed OIDC identity provider, JWT requirement or a third-party authentication dependency by default.

**Proposed for formal ADR-013 approval:** issue short-lived server-validated mobile access credentials, rotate and revoke refresh credentials, establish PostgreSQL-backed server-side Django web sessions, enforce idle and hard lifetime limits, provide user-visible per-device and global revocation, require MFA for administrators/moderators, and make recovery, reauthentication, incident audit and negative testing release gates.

**Not decided by ADR-013:** inter-service identity issuer, workload credentials and mTLS (ADR-012); Nginx-to-Swarm routing (ADR-014), secret storage topology, PostgreSQL RTO/RPO (ADR-016), personal-data retention (ADR-020), and whether the two-node deployment meets availability objectives. These remain their own approval/evidence gates.

**Proposed approval outcome:** accept the normative functional/security requirements in sections 3–17 after review, then track each implementation and test as independently pending. Approval of this architecture is not acceptance of a deployed system.

## 2. Scope, trust boundaries, and terminology

- **Identity authority:** the Django service in `services/identity`; holds accounts, password hashes, session state, MFA registrations and revocation information in its service-owned PostgreSQL schema. The identity service is authoritative; Django gateway and web are relying parties.
- **Mobile public client:** the Flutter app; holds no client secret and treats its local storage as potentially compromised. Only public HTTPS gateway routes are used.
- **Web BFF:** Django server-rendered web at `kolovibe.cabetechs.shop`. The browser holds only an opaque, secure, host-only session cookie. Django web maintains the corresponding server-side state; sensitive user credentials are not written to browser cookies.
- **API gateway:** sole approved public API boundary at `api.cabetechs.shop`, with Cloudflare Tunnel → host-level VM1 Nginx → approved private gateway route. The identity service is not publicly routable.
- **Workload authentication:** separate service-to-service authorization and protected transport; ADR-012 / ADR-014 must approve this. A session ID is not acceptable evidence of service identity.
- **Current sessions:** existing `LoginSession` and `UsedRefreshToken` are the code foundation, but adding inactivity, browser session coordination and MFA metadata requires reviewed database migrations.
- **Signed access credential:** current code uses `django.core.signing` with `sub`/`sid`, a 300-second max age and session lookup, **not JWT**. This proposal retains the signed, server-validated pattern initially and adds an explicit credential contract. Do not claim OAuth/OIDC compliance merely because the design borrows relevant token-rotation defenses.
- **Session family:** a set of refresh credentials derived from a single login grant. Revocation affects the whole family on reuse; account-wide revocation affects all families and web sessions.

The architecture is intentionally centralized for authentication and decentralized for authorization: every protected Django service must check user roles, object ownership and action scope, regardless of the gateway's initial checks.

## 3. Normative policy: lifetimes and renewals

The following are **proposed KoloVibe policy choices**, not timeouts mandated by Django or OWASP. The identity service and web BFF MUST enforce them on the server using authoritative clock and database state. A mobile timer, cookie expiry or client UI alone MUST NOT extend authentication.

| ID | Subject | Proposed policy | Required server behavior |
| --- | --- | --- | --- |
| ADR013-P01 | Mobile access credential | **300 seconds (5 minutes)** from issue | Reject at or after expiration; verify signature, token purpose, issuer, audience, current live identity session and account status on protected use |
| ADR013-P02 | Mobile refresh family | **30 days absolute maximum** from initial login | Rotation never extends original absolute expiry; future requests require new authentication |
| ADR013-P03 | Mobile inactivity | **7 days** since most recent verified authenticated activity | Reject refresh/access when idle age reaches limit; activity stored server-side and updated without write amplification |
| ADR013-P04 | Mobile refresh rotation | **Every successful refresh** | Single-use, CSPRNG token; atomic replacement; keep consumed digest through family expiry; reuse revokes family |
| ADR013-P05 | Standard web session | **30 minutes idle; 8 hours absolute** | Both independently enforced server-side; browser cookie cannot revive either |
| ADR013-P06 | Admin/moderator web session | **15 minutes idle; 4 hours absolute** | Require completed MFA before any privileged session; deny privileged mobile access until separately approved |
| ADR013-P07 | Sensitive-action freshness | Successful reauthentication / step-up within **5 minutes** | Require again when older or auth strength inadequate; specific action and session checked server-side |
| ADR013-P08 | MFA challenge | **5 minutes**, single-use, at most **5 failed attempts** per challenge | Expire and invalidate challenge; audit suspicious attempts; rate-limit retries |
| ADR013-P09 | TOTP | **30-second** timestep; accept at most current step ±1 | Reject reuse of an accepted timestep, even during adjacent valid windows; time sync monitored |
| ADR013-P10 | Password-reset token | **15 minutes**, single-use | Token verifier protected at rest, purpose-bound, revoked on successful use |
| ADR013-P11 | Email verification | **24 hours maximum** pending separate risk review | Existing code uses 24h; verification token remains single-use and rate-limited; consider shorter expiry before release |
| ADR013-P12 | Security-session rotation | Regenerate browser cookie ID on login, MFA elevation and privilege transition | Old browser session invalidated atomically; no fixation or privilege reuse |
| ADR013-P13 | User-initiated revocation | Current device, selected device, or all devices | Revocation takes effect on the next server-side authorization check; clients cannot override it |
| ADR013-P14 | Administrative recovery | No privileged recovery without high-assurance verification | Existing privileged sessions revoked; factor reset audited, notified and protected against unauthorized downgrade |

**Idle definition:** the identity service maintains `last_authenticated_activity_at`; the web BFF separately maintains browser idle time. For mobile, refreshes and verified protected API calls count as activity, but failed authentication and anonymous traffic do not. To limit PostgreSQL writes, updates may be coalesced to at most once per 60 seconds **without allowing expiry bypass**. Hard absolute expiry is never reset by refresh, polling or rotation. A dormant client must reauthenticate after the mobile inactivity limit even if its access credential has otherwise not expired. Grace windows MUST NOT permit the same refresh credential to succeed twice.

**Clock behavior:** use UTC and trustworthy host time synchronization. A signed-token clock-skew accommodation, if necessary, must be bounded and documented; it must not silently extend a hard server-side session expiration.

## 4. Django-native identity and password requirements

1. Retain Django's custom `Account` model and Django `authenticate()` integration. Use one identity authority; no duplicate password tables in gateway, web or content services.
2. Store password hashes only using maintained Django hashers. **Argon2id is preferred after benchmarking** memory and latency on constrained Oracle VMs; Django PBKDF2 remains an acceptable interim default pending measured acceptance. Never write a custom password hash or store reversible passwords.
3. Minimum password length: **12 characters** for new accounts, maximum **128** accepted input characters as current code permits. Accept passphrases and password-manager-generated values. Use breached-password screening and Django validators without arbitrary composition rules; do not silently truncate passwords.
4. Email addresses are normalized and uniqueness is enforced in PostgreSQL. Registration/login/reset responses should not reveal existence of an account where not operationally required; current registration conflict response must be reviewed for enumeration.
5. Require email verification before first account activation. Email verification is **not MFA**. Deliver mail only through approved SMTP and ensure side effects are consistent with database transactions (e.g. transactional outbox / commit-safe delivery).
6. Password changes, password resets, suspected compromise, role elevation and MFA recovery MUST revoke applicable old sessions, refresh families and pending recovery tokens. Changes must produce an auditable identity event and a user notification.
7. Password recovery MUST use CSPRNG purpose-bound tokens, single-use database-backed verifiers, generic request responses, bounded delivery, and user notification after success. Do not automatically log a user in following password recovery.
8. Disable privileged login until MFA and audit enforcement are verified. Role changes require independent permissions and cannot convert an existing viewer/creator session into a privileged session.

## 5. Mobile access-credential contract

**Proposed initial format:** retain Django's signed timestamped payload, as deployed code already implements, with explicit schema and unique verification context. No JWT is required for the first-party mobile application; the token is an opaque bearer credential to the client. If tokens are exposed to browsers or third-party clients later, reassess the protocol and interoperability requirements in a new ADR.

Proposed signed fields:

| Field | Meaning | Mandatory rule |
| --- | --- | --- |
| `ver` | Credential schema version | Accept only explicitly supported versions; reject downgrade |
| `typ` | `access` | Reject use as refresh, reset, MFA or workload credential |
| `iss` | `kolovibe-identity` | Exact match |
| `aud` | `kolovibe-gateway` | Exact match; never accept this client credential at privileged internal service endpoints |
| `sub` | Canonical UUID of user | DB lookup; no client-controlled role or authorization |
| `sid` | Canonical UUID of login session | DB lookup required for revocation/expiry |
| `auth_time` | UTC authenticated event time | Supports sensitive-action freshness and elevation checks |
| Signature/timestamp | Server-generated Django signer | Max age 300s; unique signing key / domain separation |

Use a dedicated signing secret/key scope for access credentials when migrating from shared `DJANGO_SECRET_KEY` use; stage backward-compatible verification carefully without accepting compromised fallback keys. Never place passwords, email addresses, session secrets, MFA factors or full roles in signed payloads merely because they are signed (signatures are **not encryption**). Account role and object permission are resolved from current trusted data.

On every protected API call, gateway MUST authenticate the signed credential and check the live identity `LoginSession` plus `Account.is_active`, role restrictions and current server-side revocation/expiry. Any identity-service outage MUST fail closed for protected APIs; stale roles or session decisions must not be treated as valid indefinitely. Downstream services MUST make their own authorization decisions and receive authenticated, integrity-protected caller context under ADR-012.

API authentication errors use generic, stable 401/403 and optionally documented 429 responses; expired and revoked sessions cannot reveal private user information. Authentication responses MUST use `Cache-Control: no-store`, `Pragma: no-cache` as compatible, no token-bearing URLs, and restricted logging.

## 6. Mobile refresh protocol and concurrency

**Existing foundation:** `LoginSession.refresh_digest` and `UsedRefreshToken` track one-use refresh material and detect reuse, with a PostgreSQL row lock in `services/identity/service/accounts.py`. These are local-code behaviors, **not evidence of full ADR-013 compliance**.

**Required proposed sequence:**

1. Successful login creates `session_id`, `family_id`, `created_at`, hard `absolute_expires_at`, `last_authenticated_activity_at` and a digest of a high-entropy refresh credential in a service-owned PostgreSQL transaction.
2. Return the one-time **raw** refresh credential only over an approved HTTPS response to the intended mobile client. Persist **only a keyed digest** server-side; hold the digest key separately from the Django application/signing keys.
3. Client sends `POST /api/v1/auth/refresh` through the public gateway over TLS. The identity service validates session status, absolute/idle time, token family, and digest with constant-time comparison.
4. Under a database transaction and `SELECT ... FOR UPDATE` for the family/session, create a new refresh credential, record the old digest in a consumed-token table and replace the current verifier. The **same token cannot succeed twice** under concurrency.
5. If a previously consumed credential is presented, revoke that token family, reject the request and emit a high-severity session-reuse event. Require fresh login. Consider notifying the account owner without leaking tokens.
6. Unknown/malformed credentials return a generic 401 and rate limiting without giving an attacker a revocation oracle to log out other users. Reuse detection must tie the credential's keyed digest to a known family before revoking it.
7. `POST /auth/logout` invalidates the current family; `POST /auth/logout-all` and per-session revocation require the authenticated account, a fresh step-up where warranted, and ownership checks.
8. A failed or interrupted logout MUST clear locally held credentials, warn that server revocation is unconfirmed, and retry secure revocation after connectivity returns where feasible; it MUST NOT claim confirmed server logout.

**Do not use refresh-token rotation to extend the original 30-day absolute lifetime.** Use independent `idle_expires_at` and `absolute_expires_at` checks, and avoid read-modify-write races or unbounded growth of used-token digests. Purge expired consumed-token records only after they can no longer be useful for replay detection.

## 7. Django web BFF and PostgreSQL-backed sessions

**Selected proposed target:** server-side Django browser session with an opaque cookie; **not** two long-lived bearer/refresh cookies.

The current local-only web client sets `kv_access` and `kv_refresh` HttpOnly cookies with `secure=False`, which is confined to its local loopback profile. This behavior MUST NOT be promoted unchanged to HTTPS staging/production. The new web architecture will require separate reviewed code and migration.

### Proposed login and request flow

1. Browser submits a CSRF-protected form to Django web. The web backend authenticates through the trusted gateway/identity service using approved authenticated internal transport.
2. Identity returns a **server-side web session reference** bound to the authenticated user and authentication strength; the web BFF creates a new PostgreSQL-backed Django browser session via `django.contrib.sessions` and `SessionMiddleware`.
3. Browser receives only `__Host-kolovibe_session`: `Secure`, `HttpOnly`, host-only (no `Domain`), `Path=/`, `SameSite=Lax`. Exact allowed host: `kolovibe.cabetechs.shop`. The cookie contains no access or refresh credential.
4. The BFF stores a reference to the identity session and minimal browser state **server-side**; it MUST NOT store a reusable raw refresh credential in ordinary Django session data. If a future migration temporarily requires a backend credential, it must live in a separate restricted, authenticated-encrypted store with its own rotation and deletion policy.
5. Every protected browser request requires (a) a valid Django session, (b) server-enforced web idle and absolute deadline, and (c) validation that the linked identity session is still active. No privileged authorization is derived from a cookie value or stale cached role.
6. On login, MFA elevation or privilege transition, regenerate the Django session ID, invalidate the former session and re-evaluate role/assurance. Use `request.session.cycle_key()` where appropriate and `flush()` on logout.
7. Logout calls an authenticated session-revocation operation, invalidates browser session data and deletes the cookie. Failure to reach identity MUST NOT silently imply confirmed server-side revocation.
8. A global or selected-device revoke in identity MUST invalidate the linked web session on its next protected request, even if the web database row remains. Purge expired browser sessions on a scheduled, bounded job.

### Proposed web Django settings (non-deployable illustration)

~~~python
# Do not copy into the current local-only settings file as-is.
INSTALLED_APPS += ["django.contrib.sessions"]
MIDDLEWARE.insert(1, "django.contrib.sessions.middleware.SessionMiddleware")
SESSION_ENGINE = "django.contrib.sessions.backends.db"
SESSION_COOKIE_NAME = "__Host-kolovibe_session"
SESSION_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_DOMAIN = None
SESSION_COOKIE_PATH = "/"
SESSION_COOKIE_AGE = 8 * 60 * 60
CSRF_COOKIE_SECURE = True
CSRF_COOKIE_SAMESITE = "Lax"
ALLOWED_HOSTS = ["kolovibe.cabetechs.shop"]
DEBUG = False
~~~

**These settings alone do not implement** an 8-hour absolute limit, 30-minute idle limit, linked identity revocation, server-side step-up or authenticated private transport. Middleware and a dedicated session-policy model/check must enforce those on every protected request. `SESSION_SAVE_EVERY_REQUEST` is not a substitute for independent absolute expiry and may cause needless database writes. Django's signed-cookie session backend is disallowed for the proposed BFF because logout cannot reliably invalidate a stolen old signed cookie. A web session database belongs to the Django web service, with least-privilege credentials and an identity-reference boundary; it must not share the identity service's unrestricted database role.

CSRF tokens are required on **every state-changing web operation**, including logout and MFA changes. Validate `Origin` / `Referer` as appropriate, reject untrusted Host and forwarded headers, implement restrictive CORS only if truly required, and allow `SECURE_PROXY_SSL_HEADER` only after exact proxy trust has been demonstrated. Add CSP, security response headers, clickjacking and XSS defenses; SameSite is not a replacement for CSRF protection.

## 8. Mandatory privileged MFA and step-up

Privileged roles include administrators, moderators and any future roles able to moderate users, alter sensitive account data or issue financial/ledger-related decisions. **Until MFA works end-to-end, privileged login must remain denied**, as it is in the current identity service.

### Approved-factor proposal

- **Preferred:** WebAuthn/passkeys (phishing-resistant when RP ID, origin, challenge, user verification and assertion checks are correct). Require exact relying-party ID and allowed HTTPS origins, user verification for privileged operations, single-use cryptographic challenges, credential uniqueness, and careful sign-counter handling; no automatic trust in device labels or attestation unless needed by policy.
- **Fallback alternative:** standards-compliant authenticator-app TOTP for privileged personnel when WebAuthn is unavailable. Use CSPRNG enrollment secret, 30-second steps, at most ±1 accepted drift window, one-time timestep enforcement, rate limits, encryption of TOTP seed at rest and user notification on changes. TOTP is **not phishing resistant**.
- **Recovery:** ten independently generated high-entropy, one-use backup codes per account, presented only at issuance; store password-style verifiers, not the raw codes. Backup-code use revokes previously elevated sessions, triggers re-enrollment review and an audit notification. No security questions or email-only MFA reset.
- SMS/voice OTP is **not approved** as a privileged factor for the initial implementation.

### Privileged authentication state machine

`PASSWORD_VERIFIED → MFA_PENDING → MFA_VERIFIED → PRIVILEGED_SESSION`

Only a completed and freshly verified factor may transition to the privileged state. A password-only attempt cannot receive administrator or moderator tokens, service credentials or privileged route access. A viewer/creator session is not promotable merely by changing a role flag: require new login/step-up, rotate session ID and update the assurance context on the server. Deny protected routes if the MFA service is unavailable.

For changes to password, email, MFA factors, session revocation-all, creator verification approval and privileged moderation operations: enforce **reauthentication within 5 minutes**, appropriate factor strength, exact target authorization and an audit reason where applicable. An API response alone must not set the privileged assurance flag without a verified server event.

Enrollment/change/reset of MFA must have a recovery flow, notifications, owner-verification procedure, anti-enumeration limits and reviewable evidence. No administrator or support agent may silently disable another administrator's MFA.

## 9. Device and global session management

- Support authenticated **list sessions**, **revoke current**, **revoke selected**, and **revoke all** operations. Sessions expose opaque session IDs, client class, coarse device description, creation time, last activity and current-session flag; never expose access/refresh secrets, full IP histories or fingerprint data in responses.
- Session list and revoke are object-authorized: a user can enumerate/revoke only their own sessions. Administrative revocation requires distinct privileged workflow, authorization and audit.
- Each login/session belongs to a specific client category (`flutter_android`, `flutter_ios`, `web`) and a revocation family; the client category and user agent are *metadata*, not cryptographic device proof.
- On confirmed compromise, password reset, MFA reset, major credential changes and privileged role change, revoke **all** sessions and consumed-token families as specified; deny replay and issue user notifications.
- Never rely on a client-supplied `user_id`, `role`, `session_id` or device label to authorize a management action. The authenticated server principal is authoritative.

## 10. Recovery, notifications and lifecycle integrity

1. **Registration/verification:** pending account is inactive until valid single-use email verification. Verification attempts, resend and delivery are rate limited.
2. **Forgot password request:** always generic acknowledgement with comparable response behavior for known/unknown addresses, bounded mail sending and account/IP abuse monitoring. No existence enumeration.
3. **Password-reset completion:** validate purpose, expiry, account, single-use verifier and CSRF when browser-based; set new hash, revoke all device/web sessions and outstanding reset grants atomically; require ordinary login afterward.
4. **Suspicious activity:** force reauthentication or revoke sessions when authenticated risk is high (e.g. refresh replay, unexplained credential rotation or repeated MFA failures). Device/IP changes are supporting signals, not sole proof, and must respect privacy.
5. **Email/address change:** fresh primary credential + appropriate factor, confirm new address, warn existing address and protect against attacker swapping recovery contacts.
6. **Compromised MFA device:** verify using existing factor or one-time recovery evidence; require delayed/high-assurance review when no factor remains; invalidate old sessions and factors, audit and notify.
7. **User consent and privacy:** state what device/session metadata is stored; define final retention with ADR-020 and applicable Liberian privacy/legal review before release.

## 11. Flutter implementation specification (MASVS)

- Use the existing `PlatformCredentialStore` interface and `flutter_secure_storage` backed by Android Keystore and iOS Keychain as the starting point. Verify actual plugin version/configuration, platform key accessibility, backup/restore behavior, biometric gating tradeoffs and secure deletion on physical devices.
- Keep the **access credential only in memory**, if practicable; persist the refresh credential only through OS-backed protected storage. Do not store credentials in SharedPreferences, ordinary SQLite, analytics, exception reports, webviews or device logs.
- Retain the existing serialized refresh behavior in `LiveAccountRepository`; extend it so simultaneous requests, process restarts and retry paths cannot submit the same consumed refresh token concurrently. On 401/replay revoke clear credentials and require login; avoid unbounded silent refresh loops.
- Use only trusted HTTPS origins; reject invalid/expired/wrong-host certificates and do not ship `badCertificateCallback` trust bypass. Evaluate pinning only with a documented rotation/recovery plan; it is not mandatory for launch.
- Mobile logout clears local access and refresh and requests remote revocation. Clearly distinguish *local clearance* from *server revocation confirmed* during network outage. Remove stale tokens after account switch or device transfer.
- Ensure no tokens appear in URL/deep links, screenshots of sensitive views, exported components, crash reports, backups or notification payloads. Apply privacy-aware screenshot/overlay restrictions for especially sensitive operations if appropriate.
- Require a fresh server-side factor when invoking a sensitive operation; local biometric unlock alone does not automatically satisfy remote reauthentication.
- Verify iOS and Android on physical devices (storage, rollback, certificate rejection, restoration, expired sessions, multi-device revoke and lost-device scenarios) against MASVS-AUTH/STORAGE/NETWORK/PLATFORM.

## 12. Threat model: STRIDE and abuse cases

The table is a **proposed ADR-013-specific extension** to DOC-203 (which already records TM-007–TM-011). The residual risk is *not accepted* until mitigations and evidence pass.

| Threat ID | STRIDE | Attack | Required protection | DOC-203 link |
| --- | --- | --- | --- | --- |
| ADR013-TM01 | Spoofing | Stuffed/reused credentials | Per-account and IP limits, breached password screening, generic responses | TM-007 |
| ADR013-TM02 | Spoofing | Stolen mobile refresh token | OS secure storage, one-use rotation, family replay detection, idle/absolute limits | TM-008 |
| ADR013-TM03 | Tampering | Refresh race or double-use | PostgreSQL transaction, unique verifiers, `select_for_update` and family revoke | TM-008 |
| ADR013-TM04 | Spoofing | Cookie theft/session fixation | Host-only secure cookie, CSRF, key regeneration, server-side expiry/revoke | TM-008 |
| ADR013-TM05 | Elevation | Role flag/promoted session bypasses MFA | Role read from DB, fresh MFA, deny privileged mobile, step-up | TM-009 |
| ADR013-TM06 | Elevation | MFA factor replacement or weak recovery | Existing factor or recovery evidence, atomic revocation and notification | TM-009 / TM-010 |
| ADR013-TM07 | Information disclosure | Account existence revealed by login/reset | Generic errors, timing and abuse mitigation | TM-011 |
| ADR013-TM08 | Spoofing | Forged proxy headers or origin | Trusted Nginx boundary and strict Host/CSRF/proxy checks | TM-002 |
| ADR013-TM09 | Information disclosure | Token or PII leaked via logs/CI | Redaction, short retention, secret scanning, no raw token fields | TM-039 |
| ADR013-TM10 | Denial of service | Distributed login/reset/MFA bursts | Layered IP/account/network controls and resilient throttling | TM-007 / TM-006 |
| ADR013-TM11 | Repudiation | Unattributed password/MFA/revocation action | Correlated append-only security audit events | TM-010 |
| ADR013-TM12 | Spoofing | Browser BFF misuses internal session reference | ADR-012 authenticated internal request, account linkage, deny by default | TM-012 |
| ADR013-TM13 | Tampering | Signed access credential used for wrong purpose | Strict `iss`/`aud`/`typ`, signature and live-session validation | TM-008 / TM-012 |
| ADR013-TM14 | Elevation | Cross-user session list or revoke | Server-side ownership and scoped administrator permissions | TM-009 |
| ADR013-TM15 | Information disclosure | Backup exposes session verifier or MFA seed | Encrypted storage/backups, key separation, least privilege, restore test | TM-015 / TM-036 |

Additional review topics: hostile mobile devices, malicious browser extensions, user enumeration through timing or 409 responses, attacker-triggered account lockout, recovery-flow bypass, third-party JS, post-logout proxy caches, credential leak from error tracking and web session-store outages.

## 13. Logging, abuse limits, privacy and monitoring

**Proposed minimum rate policy (risk-adjustable, not source-mandated):**

| Operation | Proposed initial budget | Behavior |
| --- | --- | --- |
| Login failure | 5 failures / 15 minutes per account-and-origin key, plus distributed-account and IP budgets | Generic 401; 429 with bounded `Retry-After`; avoid permanent DoS lockouts |
| Network-wide login abuse | Review 30 attempts / 15 minutes per trusted-origin IP and 10 failed attempts / hour per account across origins | Tune by load tests, NAT/shared-network patterns and legitimate failure rates |
| Refresh endpoint | 10 attempts / 5 minutes per session family and risk-based origin limit | Replay leads to family revoke, generic response and security event |
| Email verification/resend | 3 sends / hour per account plus origin limits | No raw token or account-existence leak |
| Forgot-password send | 3 requests / hour per account plus origin limits | Generic acknowledgement for every address |
| MFA challenge | 5 failed responses per 5-minute challenge; additional account/global caps | Invalidate challenge and notify at risk thresholds |
| Session revoke-all | Fresh reauthentication required; 5-minute validity | Audit and idempotent operation; no self-service user impersonation |

These values must be tuned against Cloudflare, host Nginx and application behavior, including users behind shared networks in Liberia. Django-side counters must enforce authoritative limits independent of Cloudflare and must survive worker restarts; database, transactional or appropriately durable shared storage is required. Rate limiting may intentionally slow response paths to avoid easy account enumeration, without logging passwords.

**Security-event schema:** event type, UTC time, pseudonymous subject/session reference, actor and role, target session (if applicable), outcome, reason category, trusted source context, correlation/request ID, component, and retention class. Never log raw tokens, password or MFA secrets, recovery codes, full cookie headers, private signing keys or complete credential-reset links. Track abnormal refresh reuse, MFA failures, recovery, role changes, new device sign-in, global revocation and backend introspection failures.

**Provisional retention to review with ADR-020:** routine auth security events up to 90 days, privileged/audit events up to 365 days subject to legal/business necessity. This is NOT a final approved retention schedule. Encrypt durable logs, restrict access and document deletion/hold procedures.

## 14. Key management, PostgreSQL and DevSecOps

- Keep Django `SECRET_KEY`, access-signing keys, refresh-digest HMAC key, web session service secrets, TOTP encryption keys and service-to-service credentials logically separated, versioned and provisioned only via approved Swarm secrets or a separately approved secret manager. No secrets in Git, image layers, build arguments or GitHub artifact logs.
- Define key IDs and staged rotation. Keep a fallback verification key **only for the bounded necessary migration window**, then retire it; respond to confirmed compromise with immediate revocation. Rotation must be tested against mixed replicas and interrupted deployments.
- Scope PostgreSQL to service-owned schema and runtime read/write permissions only. Reserve schema ownership and migrations for a separate approved login. Enforce TLS `verify-full`, uniqueness of token digests, account/session FK, expiry indexes, row-level transactional locking and cleanup. Test concurrent refresh and rollback under PostgreSQL; do not use SQLite tests as concurrency evidence.
- Authenticated sessions MUST fail closed when identity, DB, transport or required factor-verification service is unavailable. Public metadata endpoints may remain deliberately unauthenticated per R1 contracts.
- CI: hashed dependencies, SAST, secret scanning, API contract lint, Flutter secure-storage tests, destructive negative auth tests only in disposable environments, SBOM/image scans, GHCR immutable digests and release gate checks. No generated secret/token values in artifacts.
- Infrastructure acceptance remains independent: Cloudflare origin bypass, Nginx private gateway TLS, Docker Swarm/OPA fail-open remediation, firewall, PostgreSQL backup/restore, alerting and rollback must pass their own reviews. **Do not use this draft to authorize deployment.**

## 15. Required Django and data implementation backlog (future change only)

| Order | Work item | Owner/component | Blocker / verification |
| --- | --- | --- | --- |
| A13-I01 | Explicit identity credential schema and signing-key separation | Identity / gateway | Token version, issuer, audience, purpose negative cases |
| A13-I02 | Add `last_authenticated_activity_at`, `absolute_expires_at`, client kind, revocation and MFA metadata to session models | Identity / PostgreSQL | Reviewed migrations; concurrency; no expiry extension |
| A13-I03 | Harden refresh concurrency, consumed-token replay family revocation and purge | Identity | PostgreSQL concurrent/replay tests |
| A13-I04 | Add authenticated session list, per-session revoke and revoke-all | Identity / gateway | Account ownership, role and atomic revocation |
| A13-I05 | Django web BFF backed by PostgreSQL sessions, opaque browser cookie, idle/absolute middleware | Web / identity | HTTPS, CSRF, linked revocation, no raw refresh cookie |
| A13-I06 | WebAuthn and TOTP MFA factor registry, challenges, enrollment, fallback and recovery | Identity / web | Approved library and threat review; no privileged bypass |
| A13-I07 | Generic reset and recovery endpoints, secure notifications and privileged step-up | Identity | SMTP, anti-enumeration, factor recovery, atomic revocation |
| A13-I08 | Flutter session lifecycle, one-refresh-at-a-time, secure-store configuration | Flutter | MASVS device and failure-mode tests |
| A13-I09 | Structured security-event stream and layered auth throttles | Identity / gateway / operations | DOC-206 logs/abuse tests, ADR-020 retention |
| A13-I10 | Update OpenAPI contracts and DOC-206 verification mapping only after approval | Architecture/security | Approved ADR-013 and API compatibility tests |

All changes are subject to the existing branch/CI security process and owner review. No task above is marked implemented by this document.

## 16. DOC-205 OpenAPI impact and versioning

**Current DOC-205 remains an approved draft baseline, not edited by this proposal.** A separate proposed delta file describes exactly how to reconcile existing routes, authentication schemes and new routes without accidentally enabling them.

Main incompatibilities requiring conscious migration:

1. Existing `bearerAuth` and `serviceToken` security schemes declare `bearerFormat: JWT`, but the local identity service issues a signed Django access credential, not a JWT. Correct the eventual client scheme and document that internal service identity belongs to ADR-012.
2. Existing `/auth/refresh` description says the web client reads refresh credentials from an HttpOnly cookie; the proposed BFF removes that cookie and manages a linked server-side identity session.
3. Existing `/auth/logout` revokes current session only; new per-device and all-session revocations require scoped routes and consistent idempotency and audit semantics.
4. Add MFA enrollment/verify/recovery, fresh reauthentication and session-management operations as **gated candidates only**. The draft OpenAPI global bearer security must not accidentally apply to anonymous register/login/reset; secure routes must explicitly declare their intent.
5. Agree on a consistent error schema, 401/403/429/503/204 semantics and no-store headers; current local `{"detail": "..."}` and DOC-205 candidate Problem schema are not identical. Do not break deployed clients through a silent schema replacement.
6. Contract tests must assert public routes stay disabled until owner-accepted security requirements, and that privileged routes remain inaccessible before MFA.

See: [ADR-013 DOC-205 proposed delta](ADR-013_DOC-205_Proposed_Contract_Delta_v1.0_DRAFT.md).

## 17. DOC-206 security verification and evidence

The companion [ADR-013 DOC-206 verification matrix](ADR-013_DOC-206_Verification_Matrix_v1.0_DRAFT.csv) contains test cases, negative conditions, ownership, criticality, expected response and evidence requirements. All rows begin **NOT RUN**, regardless of previously passing local unit tests, because this exact policy and end-to-end acceptance have not been implemented or executed.

Primary existing DOC-206 controls to link: **SEC-003, SEC-005, SEC-006, SEC-007, SEC-008, SEC-010, SEC-012, SEC-015, SEC-017, SEC-028, SEC-036, SEC-039**. Local tests are useful evidence only after requirement equivalence and exact commit/environment are recorded. Cross-reference DOC-203 TM-007 through TM-011 and related proxy/workload threats. Source historical DOC-203/DOC-206 records still say NOT RUN; no claim of completed verification is made.

**Test environments:** disposable PostgreSQL integration fixtures, Django client/DRF contract tests, simulated network failures, bounded rate-load tests, a private restricted staging environment after infrastructure approvals, and physical Android/iOS device checks. Do not run destructive or lockout tests on public accounts.

**Required pass gates:** no critical/high unresolved auth finding; every mandatory negative test passes; server-side single-use refresh and revocation proven under concurrency; privileged APIs inaccessible before MFA; web BFF/session/CSRF and cookie checks proven; physical MASVS token-storage evidence; trusted proxy/origin, identity service outage and recovery tested; security logs redacted and retrievable; privacy/retention owners sign off. Exceptions require explicit dated risk acceptance, never test-status substitution.

## 18. Rollout, reversal and go/no-go

**Phase 0 — record decision (now):** retain Django-native identity selection; circulate this v1.0 proposal. No code settings or live endpoints change.

**Phase 1 — isolated implementation:** implement separate identity and web feature branches with migrations, contract changes behind capability flags, existing non-privileged auth tests, TOTP/WebAuthn checks and security-event tests. Keep existing public account access gated.

**Phase 2 — integration acceptance:** execute DOC-206 security matrix against disposable PostgreSQL and restricted staging; prove account recovery, key rotations, replay family revocation, web-cookie behavior, MFA and device logout. Resolve ADR-012 / ADR-014 / SMTP / privacy gates.

**Phase 3 — controlled activation:** with explicit deployment authorization, publish immutable GHCR images, deploy a reviewed Swarm stack, confirm health, perform canary and measured rollback. Recovery must leave old tokens invalidated appropriately; rollbacks cannot re-enable deprecated credential grants or bypass MFA.

**Rollback rule:** on critical auth fault, disable new account/privileged routes and revert to safe read-only metadata behavior while preserving revocation records and audit evidence. Do not downgrade signing-key verification, turn off TLS/CSRF or run with `KOLOVIBE_ENV=local` on any VM.

## 19. Approval checklist and signatures

| Decision / evidence | State at creation | Required for |
| --- | --- | --- |
| Django-native client identity provider | **Owner-selected, 2026-11-01** | Establish authority |
| Exact mobile and web session lifetime policy | **Proposed — approval pending** | Full ADR-013 |
| Refresh/replay and global revocation rules | **Proposed — approval pending** | Full ADR-013 |
| Privileged MFA/WebAuthn/TOTP/recovery | **Proposed — approval pending** | Full ADR-013 |
| Token schema, key lifecycle and cryptographic choices | **Proposed — approval pending** | Full ADR-013 |
| DOC-205 API contract update and backward-compatibility plan | **Pending** | Account endpoint implementation |
| DOC-206 exact test execution and security evidence | **NOT RUN for this specification** | Deployment |
| ADR-012 service identity, ADR-014 upstream transport | **Separate approval pending** | Deployment |
| ADR-020 privacy/retention and real SMTP | **Separate approval pending** | Account activation |
| Product/architecture/security acceptance | **Not signed** | Unconditional Stage 2/3 gate |

**Requested decision for owner:** Approve, request changes, or reject this exact **ADR-013 v1.0 security policy**. Owner approval of this document will approve the policy design only; it will not mark DOC-206 tests as run or authorize staging/production activation. Document the date, approved commit SHA and any exceptions in DOC-207 and DOC-209. One developer may fulfill multiple delivery roles, but self-review is not independent third-party assurance.

| Role | Sign-off |
| --- | --- |
| Product / decision owner | **PENDING** |
| Architecture review | **PENDING** |
| Security review / residual-risk acceptance | **PENDING** |
| Release / operational acceptance | **NOT REQUESTED** |

## 20. References and provenance

### Project sources

- [DOC-207 ADR Register](DOC-207_ADR_Register.csv) and [ADR-013 identity selection record](ADR-013_Django_Native_Identity_Selection_2026-11-01.md).
- [DOC-203 STRIDE](DOC-203_STRIDE_Risk_Register.csv); [DOC-205 OpenAPI draft](DOC-205_OpenAPI_3_1_DRAFT.yaml); [DOC-206 control matrix](DOC-206_Control_Verification_Matrix.csv); [DOC-209 gate criteria](DOC-209_Gate_Criteria.csv).
- Current implementation: [identity session code](../../services/identity/service/accounts.py), [identity models](../../services/identity/service/models.py), [Flutter secure storage](../../apps/mobile/lib/core/security/credential_store.dart), [Flutter account flow](../../apps/mobile/lib/features/account/live_account_repository.dart), and [local web client](../../apps/web_django/web/views.py).
- [Stage 3 decisions](../engineering/Stage3_Open_Decisions.csv) and [current status](../engineering/Stage3_Current_Status.md).

### External security references

- OWASP ASVS 5.0.0 — https://asvs.owasp.org/
- OWASP MASVS-AUTH — https://mas.owasp.org/MASVS/07-MASVS-AUTH/
- OWASP Session Management Cheat Sheet — https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html
- OWASP Authentication Cheat Sheet — https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html
- OWASP Multifactor Authentication Cheat Sheet — https://cheatsheetseries.owasp.org/cheatsheets/Multifactor_Authentication_Cheat_Sheet.html
- OWASP Forgot Password Cheat Sheet — https://cheatsheetseries.owasp.org/cheatsheets/Forgot_Password_Cheat_Sheet.html
- Django sessions documentation — https://docs.djangoproject.com/en/5.2/topics/http/sessions/
- Django security documentation — https://docs.djangoproject.com/en/5.2/topics/security/
- RFC 9700 (OAuth security best current practice) — https://www.rfc-editor.org/rfc/rfc9700.html

**Reference note:** RFC 9700 is cited for applicable public-client refresh rotation and replay-defense principles, not as a claim that the present Django-signed proprietary token scheme is OAuth 2.0 or OpenID Connect compliant.

---

**Document status: DRAFT / PENDING APPROVAL. DO NOT MODIFY PRODUCTION BASED ON THIS DOCUMENT.**
