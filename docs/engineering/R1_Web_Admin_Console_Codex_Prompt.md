# Codex prompt — R1 web administration console completion

Paste the **Common brief** plus exactly one **Task** into a new Codex session. Run tasks in order, one branch and PR per task. Requirement IDs are in `docs/requirements/platform_SRS_v0_2_scope_approved.md` §4.1.

## Common brief

You are working in `Markcino/KoloVibe` (Django/DRF services, Django-rendered web client in `apps/web_django`, PostgreSQL, RabbitMQ, Cloudflare R2). Start from current `main` (or the merged web console PR #127) and create a new branch for this task.

Scope: the web client is an administration console for moderators and administrators only. It has no landing page and no public, viewer or creator pages. Do not implement deferred features (live streaming, business discovery, ticketing, cash payouts), role administration, or points award/reversal execution.

Rules:
- Do only the one task below. Inspect only the files it needs; search before opening; reuse existing implementations and approved contracts (`docs/architecture/DOC-205_OpenAPI_3_1_DRAFT.yaml`, `docs/requirements/DOC-004_RBAC_Matrix_DRAFT.md`, `apps/web_django/README.md`).
- Authorization is enforced server-side in the owning service. The web client never decides permissions, never guesses endpoints, and shows "Not available in R1" for any contract that does not exist.
- Preserve existing security controls: MFA, `__Host-` cookie, encrypted server sessions, CSRF, idempotency keys, audit events, security headers. Never weaken them, never log tokens, never reveal secrets.
- Add or update OpenAPI for any new endpoint, plus migrations and tests (cross-account/IDOR denial, idempotent replay, audit record, MFA and role checks).
- Run focused tests first, then the repository's CI-equivalent checks. If a fix fails twice, stop and report the blocker.
- Do not merge or deploy. Open a PR using `.github/PULL_REQUEST_TEMPLATE.md`.
- Final report: changed files, tests run and results, blockers, PR link, measured usage if available. Do not invent usage figures.

## Tasks

### W1 — Moderator assignment authorization (FR-024)
In `services/moderation`, add an assignment model (moderator, queue scope, active) and enforce it on queue reads and decisions. Moderators see and decide only assigned items; administrators keep global supervision; unassigned moderators receive 403, audited. Update OpenAPI. Then enable moderator access in `apps/web_django` (queue views and decision POST) and update its role matrix and tests. Open question to leave documented, not decided: assignment model and SLAs.

### W2 — Reviewer content detail read (FR-026)
Add a moderation reviewer detail endpoint per video/report/appeal: metadata, rights status, report and decision history, and a short-lived authorized preview URL (no raw R2 keys). Authorize by role and assignment, audit every read. Replace the web review page's "Full content inspection: Not available in R1" with the detail view and add tests, including out-of-scope denial and HTML escaping.

### W3 — Queue totals, statuses and fraud holds (FR-027)
Add moderation/engagement contracts for queue totals, additional statuses and active fraud holds, scoped to the caller's role. Wire the `/admin/` dashboard and status filters; unsupported filters stay rejected. Tests cover counts versus fixtures and scope.

### W4 — Audit read contract and `/admin/audit/` (FR-028)
In `services/audit`, add a read-only, filtered, cursor-paginated endpoint scoped by role (moderators: own actions; administrators: authorized subset), with redaction of sensitive fields and no edit/delete path. Add the `/admin/audit/` view and tests.

### W5 — Administrative points review (FR-029)
In `services/points`, add read-only administrator endpoints for balances, history and reversal-review state, with no cash value and no write path reachable from the web client. Add `/admin/points/` and tests (403 for other roles, balance recomputes from ledger).

### W6 — Hardening and release evidence (NFR-015, NFR-002, NFR-011)
Add ASVS 5.0 L2 `WEB-SEC-*` and `WEB-ADM-*` test evidence, header/cache/escaping tests, keyboard and 390px layout checks, update `scripts/verify_local_journeys.py`, `docs/engineering/repository-layout.md` (no longer a "deferred placeholder") and the root `README.md` web description. Update the SRS traceability rows from Partial/Not started to actual status only where evidence exists.
