# P5-01 — Console route security matrix

**Type:** regression guard (test only; no production code changed). **Scope items:** secure login, privileged MFA, session validation, permission matrix, CSRF, session expiry, cross-account access, administrator-only pages.

`apps/web_django/tests/test_route_security_matrix.py` (10 tests) walks the console's URL table, so a route added without being classified fails the first test. The gateway is replaced by a recorder (only `/me` answers), so every assertion also proves that **no business request was made** on behalf of a request that should have been refused.

| Failure mode | Proven for | Result |
| --- | --- | --- |
| No session | every privileged route, GET/POST/PUT/PATCH/DELETE | redirect to `/login/` (or 405), zero gateway calls |
| Account without a privileged role (viewer) | every privileged route, GET and POST | 403/405/redirect, **no call beyond identity validation** |
| Password stage only (MFA pending, code never verified) | every privileged route | redirect to login, zero gateway calls |
| MFA flag not true | every privileged route | rejected (two independent layers check it: the view guard and the server-session validator; mutating **both** fails the test, mutating one alone does not, by design) |
| Idle (31 min) and over-age (16 min) server session | every privileged route | rejected and the server record is deleted |
| Missing CSRF token | all 12 state-changing routes (profile, password, session revoke, logout, team, creators, three decision pages, three assignment pages) | 403 before any gateway call |
| CSRF token from another session | same 12 routes | 403 before any gateway call |
| Safe methods | every privileged route | a GET never makes a non-GET gateway request |
| Moderator on administrator-only pages | creators and the three assignment routes | refused **by the console itself** (403/405) with **zero** gateway calls: defence in depth on top of the owning service |
| Moderator on `team` | team | the console forwards and the gateway and Identity decide; the refusal is shown as a non-2xx page that does not echo the service's detail, after at most the one refused request |

## How administrator-only pages are protected
Two patterns exist and the test pins both so a change in either direction is a visible decision: `creators` and the assignment views check the administrator role in the console as well as in the owning service; `team` delegates entirely to the gateway and Identity (which refuse a moderator) and the console surfaces that refusal. Nothing is decided in a template or in the browser. This write-up originally described all of these pages as delegated; that was wrong for four of the five and is corrected here.

Mutation checks: removing `@privileged` from `points` fails the matrix; removing both MFA-flag layers fails it.

Whole web suite: 111 tests OK (101 before).
