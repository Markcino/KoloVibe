# Phase 11 — security assessment

**Date:** 25 November 2026. **Product source:** `384f4b5`. **Basis:** 130 new black-box tests over real HTTP through the Gateway, direct probes of the internal service ports, database role tests on a TLS PostgreSQL built from the repository's own schema script, broker tests on a real TLS RabbitMQ, a real Chromium against the console, plus the existing suites and static scanners re-run at this commit. **This is an internal assessment by the team that wrote the tests, not an independent penetration test (NOT RUN).** No Critical finding was made. **One High finding stands (D11-002).** Production remains NO-GO.

## 1. Overall assessment

| Verdict | Basis |
| --- | --- |
| **No Critical or unauthenticated-compromise finding** | Every unauthenticated or wrongly authorized attempt in the tests was refused: anonymous access to every console page and every owner operation, forged and tampered tokens, internal ports and spoofed identity headers, cross-account and cross-business access, path and method tricks |
| **One High finding** | **D11-002**: the service logins own their tables and can disable the append-only guards on the ledger and audit stores. Everything that relies on tamper evidence is only as strong as the service credential |
| **Three Medium findings** | D11-001 poison-pill outage on the Points consumer; D11-003 account enumeration at registration; D11-004 no registration limit |
| **Two Low findings** | D11-005 validation before authorization; D11-006 console reflow |
| **Strong where it matters most** | Authentication and session lifecycle, object-level authorization, privileged MFA, console session and CSRF handling, input hardening, secret hygiene in logs |

## 2. Results by control area

| Area | Evidence (test ids) | Result |
| --- | --- | --- |
| Token integrity | Missing, malformed, flipped, truncated, lengthened tokens and a Basic header all refused (T1_11) | Pass |
| Refresh handling | Rotation; replay refused; **replay revokes the whole family including the access token** (T1_12, T1_13) | Pass |
| Session lifecycle | Logout kills the access token at once; session list is own-only; revoking another session is immediate; another account's session cannot be revoked (404) and is untouched; password change and reset end other sessions; a role change or account disable applies on the next request, and a role change invalidates the old session rather than letting it keep the old role (T1_14 to T1_17, T1_20, T1_22, T1_32, T1_33) | Pass |
| Enumeration | Sign-in failures identical for known and unknown emails (T1_10); reset requests identical (T1_21, T1_96); console sign-in identical (T9_04). **Registration is not** (T1_03) | Pass, **except D11-003** |
| Brute force | Sign-in throttled within the approved 5-per-15-minutes budget (T1_90); verification and reset code guessing throttled (T1_92, T1_93); MFA challenge exhausted after repeated failures (T1_65); resend and reset mail capped at 3 an hour, silently, measured by counting real emails (T1_95, T1_96) | Pass |
| Registration abuse | 40 registrations from one origin, all accepted (T1_94) | **Fail, D11-004** |
| Privileged MFA | Password alone returns a challenge and **no tokens**; wrong code refused; TOTP code single use; recovery code single use; challenge single use; forged and foreign challenges refused; a moderator cannot perform administrator actions (T1_60 to T1_67) | Pass |
| Object-level authorization | Cross-account reads return nothing of another's (T1_30); cross-creator video operations answer **identically to a missing video** (T2_24); **all 26 business-scoped operations answer a stranger identically to a missing business** (T4_10); staff cannot use owner operations (T4_20); points entries are creator-scoped (T3_23) | Pass |
| Authorization ordering | A caller without authority can still reach the validator on two operations (T1_31, T4_23) | **Fail, D11-005 (Low)** |
| Input hardening | Hostile JSON, 2 MB bodies, 70 KB headers, 300 headers, 60 KB query strings, null bytes, long Unicode all answered below 500 with no stack trace, and the service stayed healthy (T1_50, T10_22, T10_24) | Pass |
| Perimeter | Every internal route on every service refuses unsigned requests; spoofed `X-Forwarded-For`, caller and role headers do not help; the Gateway does not expose internal paths (T10_10, T10_11) | Pass |
| Path and method tricks | Encoded slashes, dot segments, case changes, `;` parameters, null bytes, method-override headers never reached an administrator operation (T10_21); TRACE and others refused; no CORS granted to a foreign origin (T10_20) | Pass |
| Console web security | CSRF on every state-changing route tested (T9_12); logout is POST-only (T9_11); stolen cookie dead after logout (T9_10); session fixation prevented (T9_07); idle and absolute expiry enforced (T9_13, T9_14); strict CSP with no script (T9_20); no CSP violations (T9_21) | Pass |
| Database | Cross-service reads denied (T10_01); no superuser, file, program or DDL reach (T10_02); TLS verified, plaintext and wrong host refused (T10_05); secrets are private files and not in process arguments (T10_06) | Pass |
| **Database ownership and guards** | The service login can disable the append-only triggers on the Points ledger, the Audit store and Identity's security events; **117 of 117** tables are owned by a role the login inherits (T10_03, T10_04) | **Fail, D11-002 (High)** |
| Messaging | Engagement can write only to the Points exchange and cannot consume or declare (Phase 10 tests, re-run); a client cannot inject an event; duplicates have one effect; durability and outage recovery (T3_22, T3_30 to T3_32, T3_34). **A malformed envelope kills the consumer permanently** (T3_35) | Pass, **except D11-001** |
| Secrets and logging | No credential, token, MFA factor or recovery code created during the run appears in any service log; no query string leakage (T10_90, T10_91); no secret in repository scan; Bandit 0 medium or high at the final commit | Pass |
| Supply chain | `pip-audit` clean on all four Python lock files (T10_84). **Flutter packages: BLOCKED** (OSV host denied); the CI OSV step is the place it runs | Pass for Python; BLOCKED for Flutter |
| Media handling | Hostile media refused or neutralised (T2_01 to T2_10), including playlist and concat tricks, polyglots and metadata | Pass |
| Mobile security | Keychain and Keystore storage, binary analysis, certificate handling | **BLOCKED** (no device) |
| Edge and TLS termination | Nginx hardening statically sound; no rate limiting in the repository's configuration (T10_80, T10_81); deployed edge not tested | Partly static; **BLOCKED** live |

## 3. Notable positive controls verified (worth keeping)

1. Replaying a refresh token revokes the entire session family and the access token tied to it.
2. TOTP replay protection works (the server refused a code equal to the one used at enrolment).
3. Existence is never revealed: strangers and missing objects get byte-identical answers across 26 Business operations and the creator video routes.
4. Rate limiting on resend and reset is silent by design, so it cannot be used to probe accounts.
5. The console keeps credentials server-side (the browser holds only a session id), and an old cookie is useless after logout.
6. Media conversion forces the `mov` demuxer and whitelists protocols, so playlist-style SSRF and local-file reads did not work.

## 4. Not assessed

An independent penetration test; deployed Cloudflare and Nginx behaviour; live Gunicorn headers; mobile client security; real R2 permissions; deployed broker accounts; the Events, Advertising and Finance designs (no code); denial-of-service at scale; timing side channels (not measured); social engineering and operational security.
