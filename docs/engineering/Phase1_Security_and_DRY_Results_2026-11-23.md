# Phase 1 — security and DRY foundation: results

**Date:** 23 November 2026. **Base:** `main` at `bb79e1a`. **Scope:** repository changes only. No AWS, staging, migration, RabbitMQ-permission, database-privilege, merge or deployment action was taken. Each item below is its own pull request; none is merged. Plan and acceptance criteria: [Phase 0 baseline §8](Phase0_Implementation_Baseline_2026-11-23.md) (PR #192).

## Outcome in one paragraph
The baseline's authorization, session and data-exposure risks were examined one at a time with safe tests. **One real defect was reproduced and fixed** (no account-level MFA failure lock, P1-04). The other five security items found **no defect** at HEAD and now have regression tests that fail when the control is removed (each was mutation-checked). The staging database-ownership finding got a read-only report for the owner to run; nothing was changed. Two verified duplications were addressed without coupling services.

## Pull requests

| PR | Item | Type | What it proves or changes | Result |
| --- | --- | --- | --- | --- |
| [#193](https://github.com/Markcino/KoloVibe/pull/193) | P1-01 default-deny route contract | test | Every gateway operation not declared anonymous in DOC-205 refuses a credential-less caller (401/404/405) with zero internal calls; every route is declared in DOC-205; the anonymous list is exactly 18 operations | No defect; 6 tests |
| [#196](https://github.com/Markcino/KoloVibe/pull/196) | P1-02 role and MFA matrix | test | 24 privileged routes refuse viewer, creator and privileged-without-MFA callers before any forwarding; administrator-only routes refuse moderators; only 6 listed routes delegate the role decision to Identity/Creators | No defect; 5 tests |
| [#195](https://github.com/Markcino/KoloVibe/pull/195) | P1-03 refresh and logout | test | Replay of a long-rotated token revokes the family and newest token; wrong or guessed tokens cannot revoke or hijack a session; no token material in audit rows; one sign-out leaves other sessions | No defect; 4 tests |
| [#197](https://github.com/Markcino/KoloVibe/pull/197) | P1-04 account-level MFA lock | **fix** | After 10 MFA failures per 15 minutes per account, across challenges and origins, further attempts get 429 even with a correct code; success clears; reuses `LoginThrottle` helpers, no migration, no new audit kind | **Defect reproduced and fixed**; **owner approval required before merge** |
| [#194](https://github.com/Markcino/KoloVibe/pull/194) | P1-05 public response minimisation | test | Twelve injected internal fields, non-public states and inactive creators never reach anonymous callers; upstream error text is not reflected | No defect; 7 tests |
| [#198](https://github.com/Markcino/KoloVibe/pull/198) | P1-06 DB role ownership report | tooling | Read-only SQL showing owners, memberships, per-login schema reach and whether a login can control or truncate append-only tables; tested on disposable TLS PostgreSQL | For the owner to run on staging; no change made |
| [#199](https://github.com/Markcino/KoloVibe/pull/199) | DRY-01 gateway error response | refactor | Five identical gateway `_error` definitions became one `responses.error_response` | Behaviour-preserving; 183 gateway tests unchanged |
| [#200](https://github.com/Markcino/KoloVibe/pull/200) | DRY-02 contract copies | test | Gateway and web validator copies (identical modules) are guarded against drift | 3 tests |

Per-item write-ups with root cause, mutation checks and limits: `docs/security/phase1/` in each PR.

## Local verification
Identity 141, gateway 183 (+7 on #194), P1-01/02/DRY-02 script tests, PostgreSQL preflight module 16: all passed. CI on #192–#197 is green (16 jobs pass; publish and manual jobs skip on pull requests); #198–#200 were still running when this was written (see the PR pages). Flutter was not run (not installed locally).

## Security controls verified (evidence in the PRs above)
Server-side authentication on every non-anonymous route; default-deny against the API contract; role and fresh-MFA enforcement at the gateway for reviewer/administrator routes; refresh rotation, replay-driven revocation and wrong-token safety; secret-free security events; exact-key public responses; account-level MFA lock (once merged). Logging scan of service and web code found only static messages near email delivery failures, no token, password or code in log calls.

## Acceptance criteria
- **Relevant security tests pass:** yes, locally and in CI where complete.
- **No known regression introduced:** full gateway and identity suites pass; the only behavioural change is #197.
- **No secrets exposed:** no secrets added; probes use throwaway test values; report SQL never reads `pg_authid`.
- **Authorization cannot be bypassed from the client:** no bypass found by the new probes; see "not covered".
- **DRY reduces actual duplication:** five gateway helper copies removed (#199); intentional cross-deployable copies are now guarded rather than coupled (#200).
- **Existing APIs compatible:** yes; no route, field or body changed. #197 returns the existing 429 shape.
- **CI and secret scanning pass:** pass on #192–#197 so far; see above for the rest.

## Not covered by Phase 1 (honest gaps)
These objectives were not completed because no verified defect or duplication was identified or because they need a live environment or an owner decision:
- **PostgreSQL least-privilege remediation and RabbitMQ permissions:** report only (#198); no change by design.
- **Concurrent-refresh exactly-once and row-lock behaviour:** needs PostgreSQL concurrency in CI.
- **CSRF, security headers, throttling at the edge, upload and media security:** existing web and media tests were not extended; the web console CSRF/headers suites pass unchanged. Cloudflare rate-limit evidence is an owner item.
- **Audit event integrity:** not changed; append-only triggers are exercised in existing suites, and #198 will show whether runtime logins can bypass them on staging.
- **Flutter API handling and loading/error/empty states, web design components:** no duplication was measured or changed. Flutter cannot be run here; a measured Dart-side analysis should be its own task.
- **Pagination/cursor, idempotency and secure-request helpers:** services own their own and are deliberately not shared; no safe in-service duplication was changed beyond the gateway error helper.

## Owner decisions and actions
1. Review and approve [#197](https://github.com/Markcino/KoloVibe/pull/197) (authentication behaviour) before any merge.
2. Run the #198 report on staging (read-only) and share sections 4 and 6; then decide a remediation plan for runtime-owned objects (Phase 0 B-09).
3. Decide the post-approval video edit policy (R-03/B-08) and whether to remove the legacy `GET /videos` alias (noted in #193).
4. Supply the v0.373.1 commit and image digests (Phase 0 B-01).
5. Merge order if approved: #192 (baseline), then #193–#196, #194, #199, #200 in any order, #198, and #197 last after review.

## Updated implementation tracker
The tracker matrix lives in PR #192; it is not edited here to avoid a conflict. After #192 merges, the Security and Tests cells for gateway routes, sessions, MFA, public discovery and database roles should cite these PRs.
