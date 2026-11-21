# Django R1 administration console

This server-rendered client is exclusively for moderators and administrators. `/` redirects to `/admin/` when a browser session is present and to `/login/` otherwise; the admin guard validates that session before rendering. Sign-in and its pending MFA challenge are the only anonymous application flow. Health and bundled static assets remain accessible. Former public, viewer and creator routes return 404.

The console reuses `_api()` and the existing Identity password → MFA → logout flow. Each protected request checks `/api/v1/me`, verifies the role and account against the encrypted server session, and rejects changed or revoked identities. Password-only tokens never enter the console and are revoked when returned. No role-management, payout or creator-publishing UI is included.

## Routes and contracts

All gateway paths below have the `/api/v1` prefix. Every `/admin/` route requires a privileged MFA session, including account forms and logout. All browser mutations require CSRF-protected POSTs.

| Web route | Existing gateway contract / R1 behavior |
| --- | --- |
| `/login/`, `/login/mfa/` | `POST /auth/login`, `POST /auth/mfa/verify` |
| `/admin/` | Navigation and labelled unavailable metrics; no aggregate-count, fraud-hold or recent-audit contract exists |
| `/admin/moderation/videos/` | `GET /moderation/videos?cursor=…` |
| `/admin/moderation/reports/` | `GET /moderation/reports?cursor=…` |
| `/admin/moderation/appeals/` | `GET /moderation/appeals?cursor=…` |
| `/admin/moderation/{videos,reports,appeals}/<uuid>/` | GET re-fetches the originating queue page and selects the record; POST calls the corresponding `/moderation/<kind>/<uuid>/decisions` |
| `/admin/points/` | **Not available in R1**: administrative balances, history and reversal-review contracts are absent |
| `/admin/audit/` | **Not available in R1**: no authorized, filtered audit-read contract |
| `/admin/account/` | Own identity from `GET /me` |
| `/admin/account/profile/` | `PATCH /me` |
| `/admin/account/password/` | `PATCH /me/password`; success clears the browser session |
| `/admin/account/sessions/` | `GET /me/sessions` |
| `/admin/account/sessions/<uuid>/revoke/` | `DELETE /me/sessions/<uuid>`; gateway ownership denials are preserved |
| `/admin/logout/` | `POST /auth/logout`; browser state clears even if server revocation cannot be confirmed |
| `/health/live`, `/static/<asset>` | Liveness and allowlisted bundled assets |

Queue pages validate bounded records, canonical UUIDs, ordering, duplicates and forward-only cursors before rendering. The existing contracts return only the review-video queue or open reports/appeals. Those status filters are provided; other statuses explicitly say **Not available in R1** and unsupported filter values are rejected. Session lists use the existing bounded, non-paginated contract.

There are no reviewer detail-read endpoints. Review pages show only a freshly fetched queue record, with **Full content inspection: Not available in R1**. Links retain the source cursor; a record absent from that page returns 404. Video decisions allow publish/reject/remove, reports allow dismiss/remove, and appeals allow deny/restore. A short-lived signed form intent binds the target, video, account and browser session to a stable gateway `Idempotency-Key`. Repeated submissions reuse that key; decision POSTs re-check identity and roles. Gateway authorization and conflict responses remain authoritative.

## Role matrix and contract gaps

| Operation | Moderator | Administrator | Other roles |
| --- | --- | --- | --- |
| Dashboard and own profile/password/sessions | Allowed with MFA | Allowed with MFA | 403 |
| Moderation queues and decisions | Active explicit resource assignment required; enforced by Moderation | Supervise existing global queues and submit decisions | 403 |
| Points | 403 | Review-only unavailable state | 403 |
| Audit | Own-actions subset required; unavailable | Authorized subset required; unavailable | 403 |
| Role changes or monetary payouts | No UI | No UI | No UI |

DOC-004 requires moderators to work on assigned queues. Moderation now enforces active per-resource assignments for queue reads and decisions, including idempotent replay. The web forwards both reviewer roles to this owning-service authorization. No assignment or role-administration UI is exposed. The broader assignment model/routing policy and SLAs remain open owner decisions. The video scope forwarding is bounded to 1,000 assignments per moderator and fails closed above that limit.

Other missing contracts are global queue totals, active fraud holds, recent/filtered audit reads with role-scoped access, full reviewer content inspection, administrative points balances/history/reversal review, and queue statuses beyond the current open/review queues. These are explicitly unavailable rather than replaced with guessed endpoints, partial totals, creator-owned points, or unrestricted logs. Points reversal is not offered: DOC-004 grants administrators review only and reserves award/reverse execution for the rules engine.

## Sessions and security

Staging retains PostgreSQL database sessions, encrypted credential rows, the independent signing and credential-encryption secret files, the `__Host-kolovibe_session` cookie and existing TLS/security headers. Tokens and MFA challenges never appear in forms, URLs or browser storage. All privileged sessions have a **15-minute absolute** limit and a **30-minute idle** limit; activity and refresh never extend the absolute deadline. Pages use Django autoescaping and fixed, non-enumerating error messages. Admin responses are not cached.

Local development uses the same MFA/session implementation, a local SQLite database and a local-only encryption key derived from the private web signing secret. Staging still requires its independently provisioned encryption key and never selects SQLite. From the repository root, after initializing the existing private `.env`:

```sh
.venv/bin/python scripts/run_local_web.py migrate
.venv/bin/python scripts/run_local_web.py runserver 127.0.0.1:8010
.venv/bin/python scripts/run_local_web.py test tests
```

Real privileged sign-in requires an existing MFA-enabled Identity account and an approved gateway; this client creates neither accounts nor MFA factors. Test suites use synthetic identities and never need live credentials. The CI local-journey fixture checks removed routes, unauthenticated admin access, CSRF and rejection of ordinary viewer tokens against a real gateway; focused web tests cover the privileged MFA and decision contracts.

Staging session cleanup uses the existing `clearsessions` and bounded `purge_expired_web_sessions` commands. Production remains unsupported. This change does not merge, publish or deploy the web app.
