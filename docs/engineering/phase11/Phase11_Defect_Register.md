# Phase 11 defect register

**Prepared for Phase 12.** Date: 25 November 2026. **Product source:** commit `384f4b5` (the test harness in `scripts/phase11/` was added on top and changes no product code). **Image:** none; no container image was built or run in this phase. **Environment (all entries unless stated):** one local, disposable stack on a single host: Python 3.13.18, Django 5.2.18, PostgreSQL 16 with TLS, RabbitMQ 3.12.1 with TLS, FFmpeg, Chromium 158, nine services plus the console started through the repository's own harness entry points. **Not** AWS staging, **not** a device, **not** production. Test ids refer to the [test matrix](Phase11_Test_Matrix.md); the test code is in `scripts/phase11/`.

**Severity scale.** *Critical*: reachable without credentials and compromises data or the platform. *High*: breaks a core security or integrity control, or is a likely path to one. *Medium*: weakens a control or causes an outage that needs a precondition. *Low*: minor disclosure, hardening or accessibility. Release-blocker means it must be fixed or formally accepted before the area it affects is exposed to users.

**Counts:** 6 new defects, each confirmed by a failing test (1 High, 3 Medium, 2 Low); 3 carried forward from Phase 10 and **not retested** here; 4 observations that are not defects.

| ID | Sev. | Release blocker | Title | Test |
| --- | --- | --- | --- | --- |
| D11-001 | Medium | **Yes** (for any shared environment running the Points consumer) | A malformed task message crashes the Points worker, and it crashes again on every restart | T3_35 |
| D11-002 | High | **Yes** | Service database logins own their tables and can switch off the append-only guards on the ledger and audit stores (R-01) | T10_03, T10_04 |
| D11-003 | Medium | No (fix before production) | Registration reveals whether an email is already registered | T1_03 |
| D11-004 | Medium | No (fix before production) | No limit on account registration | T1_94 |
| D11-005 | Low | No | Some operations validate the request body before checking authority | T1_31, T4_23 |
| D11-006 | Low | No | Console top bar overflows 13 px at 320 px width (WCAG 1.4.10) | T9_32 |

---

## D11-001 — Points worker poison-pill crash loop

| Field | Detail |
| --- | --- |
| Feature | Engagement to Points event pipeline (Points consumer) |
| Environment | Local disposable stack; real RabbitMQ 3.12.1 over TLS; production Points worker entry point (`staging_runtime.roles.run_celery`); Celery 5.6.3 |
| Source / image | `384f4b5` / none |
| Reproduction | 1. Start the Points worker against a provisioned broker. 2. As any account with WRITE on exchange `kolovibe.points`, publish one JSON message whose body is `[1, 2, 3]` (or `{"id": "x"}`) with header `task: kolovibe.points.event` and no valid Celery envelope. 3. Watch the worker. 4. Restart the worker. Reproduced with `scripts/phase11/test_g3_engagement.py::test_T3_35` and the standalone experiment recorded in the report |
| Expected | The message is rejected and discarded (or dead-lettered) once; the worker keeps consuming |
| Actual | The worker process dies with `CRITICAL/MainProcess Unrecoverable error: KeyError('id')`. The message is redelivered after every restart (late acknowledgement), so the restarted worker dies again: a **crash loop** until someone purges the queue by hand. A string body, an empty `args/kwargs` dict, and a message with no `task` header do **not** trigger it |
| Severity | Medium. The precondition is write access to the Points exchange, which only a compromised Engagement account (or broker credentials) has; the impact is a persistent stop of all points awards, with the backlog growing in the durable queue. No data is lost and nothing is awarded wrongly |
| Evidence | Worker log lines `Unrecoverable error: KeyError('id')` (repeated per restart); queue state `(ready=1, unacked=0)` after each restart; ledger unchanged |
| Likely owner | Points / `services/points/service/celery_app.py` and `staging_runtime/roles.py` (worker bootstrap); the same pattern exists in Engagement's and Content's consumers; broker policy (no dead-letter queue is configured) |
| Retest criteria | After the fix, `test_T3_35` passes: the malformed message is dropped or dead-lettered, the worker stays alive, the queue drains, and a following valid event is awarded exactly once. Repeat for the Engagement and Content consumers |

## D11-002 — Service logins can defeat the append-only guards (R-01)

| Field | Detail |
| --- | --- |
| Feature | Database ownership and grants; the Points ledger, Audit store and Identity security events |
| Environment | Local disposable PostgreSQL 16 built from the repository's own `infra/postgres/schema_isolation.sql` and migrations |
| Source / image | `384f4b5` / none |
| Reproduction | As the Points service login, `BEGIN; ALTER TABLE points.points_entries DISABLE TRIGGER USER;` succeeds. Same for `audit.service_securityevent` and `identity.service_securityevent`. `SELECT` on `pg_tables` joined with `pg_has_role(login, owner, 'USAGE')` shows every service table is owned by a role its login inherits. `test_T10_03`, `test_T10_04` |
| Expected | Runtime logins have only the DML they need; table ownership sits with a separate migration role the runtime cannot assume; the append-only triggers cannot be disabled by the service that writes the ledger |
| Actual | **117 of 117** service tables are owned by a role their runtime login inherits. The runtime login can disable the triggers that make the ledger and audit stores append-only, so a compromised service credential can rewrite history. (This is the known open finding R-01, now demonstrated rather than inferred.) What does hold: cross-service reads are denied (T10_01), superuser reach is denied (T10_02), TLS is enforced (T10_05) |
| Severity | High. It silently voids the tamper-evidence design that the ledger, audit and the proposed Events, Ads and Finance packages rely on |
| Evidence | Test output: `append-only guards can be disabled by the service's own login: [points, audit, identity]` and `117 of 117 service tables ...`. All changes were rolled back; the fixture is disposable |
| Likely owner | Database provisioning (`infra/postgres/schema_isolation.sql`, runbook DR-BZ-32 / DR-EV-06 model), migration execution role |
| Retest criteria | With a separate owner role and runtime logins that are not members of it, `test_T10_03` and `test_T10_04` pass; migrations still apply (run as the owner) and the services still pass their suites; repeat the read-back on the staging database (T10_94 is BLOCKED until then) |

## D11-003 — Registration reveals existing accounts

| Field | Detail |
| --- | --- |
| Feature | Accounts: registration |
| Environment / source | Local stack, Gateway to Identity; `384f4b5` |
| Reproduction | `POST /api/v1/auth/register` for an email already registered returns `409 {"detail": "Account already exists"}`; for a new email it returns `201`. `test_T1_03` |
| Expected | ADR-013: registration, login and reset responses should not reveal whether an account exists "where not operationally necessary"; the review topics explicitly list "user enumeration through timing or 409 responses". Sign-in (T1_10) and reset (T1_21) pass this check |
| Actual | Anyone can test whether an email is registered |
| Severity | Medium (privacy and targeting for phishing or credential stuffing; mitigated for sign-in by throttles) |
| Likely owner | Identity, `services/identity/service/accounts.py:369`; DOC-205 declares the 409 |
| Retest criteria | A duplicate registration returns the same status and body shape as a new one (and the owner of the existing address is told by mail); update DOC-205; `test_T1_03` passes |

## D11-004 — No limit on registration

| Field | Detail |
| --- | --- |
| Feature | Accounts: registration |
| Reproduction | 40 registrations in a row from one address, all `201`. `test_T1_94`. Each registration sends a verification email |
| Expected | A per-origin budget for registration (the approved ADR-013 table lists sign-in, refresh, resend, reset and MFA budgets but none for registration, which is itself a policy gap) |
| Actual | Unbounded account creation and verification mail to arbitrary addresses. The repository's Nginx config also defines no `limit_req` (see the infrastructure assessment), so no layer in the repository limits it |
| Severity | Medium |
| Likely owner | Identity (policy and counters), `infra/nginx/*.conf` |
| Retest criteria | A documented budget exists and `test_T1_94` shows a 429 within it, without breaking users behind a shared network |

## D11-005 — Validation before authorization

| Field | Detail |
| --- | --- |
| Feature | Gateway admin lookup; Business verification submit |
| Reproduction | A viewer `POST /api/v1/admin/accounts/lookup` with `{}` gets `400 Invalid request`, with a well-formed body `403` (`test_T1_31`). A business staff member submitting verification gets `404` for a valid body and `400` for a malformed one (`test_T4_23`) |
| Expected | An actor without authority gets the same refusal whatever the body |
| Actual | A caller without authority learns the request schema and that the route exists |
| Severity | Low |
| Likely owner | Gateway and Business request handlers (order of checks) |
| Retest criteria | `test_T1_31` and `test_T4_23` pass; the Business cross-owner test (T4_10) still passes |

## D11-006 — Console top bar overflows at 320 px

| Field | Detail |
| --- | --- |
| Feature | Administration console layout |
| Reproduction | Chromium at 320x700, any `/admin/` page: `scrollWidth - clientWidth = 13`; `.topbar-end` ends at 333 px. `test_T9_32` |
| Expected | WCAG 2.2 AA 1.4.10 reflow: no horizontal scrolling at 320 CSS px |
| Actual | 13 px horizontal scroll on all seven pages tested |
| Severity | Low (the console is a desktop tool; it matters for zoom users) |
| Likely owner | `apps/web_django/static` topbar CSS |
| Retest criteria | `test_T9_32` passes |

---

## Carried forward from Phase 10 (confirmed there, NOT retested in Phase 11)

| ID | Sev. | Issue | Retest |
| --- | --- | --- | --- |
| D11-007 | Medium | Creators and Content register 18 audit kinds but emit none (FR-015); creator approvals and video publication leave no audit event | Perform an approval and a publication; the audit history shows both |
| D11-008 | Low | `POST /copyright/reports` has no client in the app | Owner decision first |
| D11-009 | Low | `requeue_stalled_media`, `purge_expired_security_rows`, `purge_expired_web_sessions` have no scheduled role; the last is undocumented | Roles or documented manual run |

## Observations (not defects)

1. The `Server` header on the local fixture (`WSGIServer/0.2 CPython/3.13`) comes from Django's development server that the repository's journey harness uses; the production Gunicorn runtime was **not** header-tested (NOT RUN).
2. Public discovery reads have no application-level rate limit (400 requests, 32 concurrent, no 5xx; latency in the report). Edge limiting is a Cloudflare and Nginx concern and is unverified.
3. The Nginx configuration in the repository has `server_tokens off`, TLS 1.2 and 1.3 only, 8 KiB and 16 KiB body limits and strips spoofable forwarding headers; it has **no** rate limiting. HSTS is set by the applications (30 days for the console, one hour for services).
4. No dead-letter queue is configured for any queue (owner broker task); D11-001 makes this matter.
