# Phase 12 — final defect register

**Date:** 25 November 2026. **Build:** the Phase 12 commits on branch `claude/blissful-albattani-81b81r` after Phase 11 source `384f4b5`. This register supersedes the [Phase 11 register](../phase11/Phase11_Defect_Register.md) and records the **actual** outcome of every defect, including what is not closed. Nothing here is a production-readiness claim.

## 1. Summary

| ID | Sev. | Class | Status after Phase 12 |
| --- | --- | --- | --- |
| D11-001 | Medium | Reliability defect | **FIXED and verified** (unit, real broker, black-box T3_35) |
| D11-002 | High | Critical security vulnerability / data integrity | **FIXED in the repository and verified on a disposable database. NOT verified on staging** (owner action) |
| D11-003 | Medium | Authentication / authorization (account enumeration) | **OPEN: owner decision.** Not changed, because ADR-013 and the approved M-012 screen keep the `409` |
| D11-004 | Medium | Authentication / authorization (abuse control) | **FIXED in code and verified with a trusted origin. INERT AS DEPLOYED** until D12-001 is closed |
| D11-005 | Low | Authentication / authorization (ordering) | **FIXED and verified** in Identity, Gateway and Business |
| D11-006 | Low | UI / accessibility | **FIXED and verified** (T9_32) |
| D11-007 | Medium | Integration failure | **OPEN** (carried; not retested; owner decision M-1) |
| D11-008 | Low | Functional (product decision) | **OPEN** (carried; owner decision) |
| D11-009 | Low | Documentation / operations | **Documentation FIXED. Scheduling OPEN** (owner approval) |
| **D12-001** | **Medium** | Integration failure (a security control that is configured off) | **NEW, OPEN** (edge configuration and owner) |
| **D12-002** | **High** | Vulnerable dependency (media worker FFmpeg) | **NEW. Fix proposed** (FFmpeg 9.1); closed when the media image scan passes in CI |

## 2. Triage and root cause

### D11-001 — Points worker poison-pill crash loop (Reliability, Medium) — FIXED
**Root cause.** Celery's consumer wraps the task strategy in a handler for `InvalidTaskError`, `ContentDisallowed` and `DecodeError` only. A message with a malformed envelope (a JSON list, or a dict with no valid `id`) raised `KeyError` or `TypeError` inside the strategy, outside that handler, so the consumer stopped. With late acknowledgement the message stayed on the queue, so every restart crashed again: one malformed message permanently stopped points awards.
**Fix.** `staging_runtime.roles` installs a guarded strategy (`app.Task.Strategy`) that converts `KeyError`, `TypeError`, `ValueError`, `AttributeError` and `UnicodeError` from the default strategy into `InvalidTaskError`, which Celery already rejects once without requeue. It is installed by `run_celery`, so every role (Points, Engagement and Content consumers) gets it. No change to valid-message handling.
**Tests (written first, failed before the fix).** `scripts/test_worker_poison_message.py` (5 unit tests: the unguarded strategy lets the error escape, the guarded one never does, and `run_celery` installs it); `scripts/verify_event_pipeline_broker.py` test 7 on a real TLS RabbitMQ (a malformed envelope is rejected and the consumer then processes a valid award); Phase 11 `T3_35` black-box (now PASS).
**Residual.** No dead-letter queue exists, so a rejected message is discarded, not kept for inspection. That is an owner broker decision (G-5).

### D11-002 — Service logins can disable the append-only guards (Critical security / data integrity, High) — FIXED in the repository
**Root cause.** Each service login was a member of the NOLOGIN role that owns the schema and tables, and migrations were run by the same login, so the runtime credential could `ALTER TABLE ... DISABLE TRIGGER` on the Points ledger, the Audit store and the Identity security events (117 of 117 service tables were owned by a role the login inherited).
**Fix.** Two roles per service: `kolovibe_<svc>` owns; `kolovibe_<svc>_rt` has data access only (`SELECT/INSERT/UPDATE/DELETE`, sequence use, and default privileges for future tables), with no ownership, no `CREATE`, no `TRUNCATE`. Runtime logins join `_rt` only. A separate migration login joins the owner role and the migration job sets `KOLOVIBE_DB_MIGRATION_ROLE`, which `staging_runtime.database_options` accepts only if it equals that service's own owner role. `infra/postgres/schema_isolation.sql` provisions it; `infra/postgres/r01_ownership_remediation.sql` converts an existing database (aborts and rolls back if anything remains controllable). Runbook: [R-01 operator runbook](../../operations/R1_Database_Ownership_Remediation_Runbook.md).
**Tests (failed before).** `scripts/test_postgres_foundations.py`: for all nine services the runtime login owns nothing it can control and cannot disable triggers, change owner, truncate, drop or create; `scripts/test_r01_remediation.py`: the conversion on a recreated legacy schema, refusal of an unknown service, a missing login and a superuser, re-run safe; `scripts/verify_r1_db_preflight.py`: the report is clean after the split and still exposes a legacy database; Phase 11 `T10_03` and `T10_04` (now PASS); `T10_31` proves the migration login can reverse and re-apply migrations and that the runtime login can still read every re-created table. Services still pass their suites and the Business, Audit, event-pipeline and journey scripts on the new model.
**Not done.** The live staging database is unchanged. Until the owner approves and runs the runbook, **staging still has the old ownership** and the finding is open there. `T10_94` stays BLOCKED.

### D11-003 — Registration reveals existing accounts (Authentication / authorization, Medium) — OPEN, owner decision
**Why it was not changed.** ADR-013 (approved) states that registration keeps answering `409` for an existing address "because the approved M-012 screen depends on it", and the mobile app uses that `409` to open the approved "Account already exists" screen (M-012). Making registration answer identically for new and existing addresses removes that screen's trigger, so it changes an approved design, which is the owner's call.
**What is ready.** The change is small and understood: answer `201` with a random identifier for an existing address, send the existing owner a notice mail under the existing per-address send limit, update DOC-205 and the app (M-012 would be reached from the sign-in screen instead). `T1_03` fails today and will pass when applied. **Interim control:** D11-004 now bounds how fast one origin can probe addresses, which reduces but does not remove the exposure.

### D11-004 — No limit on registration (Authentication / authorization, Medium) — FIXED in code, inert as deployed
**Root cause.** The ADR-013 budget table had no registration entry, so registration created accounts and sent mail without limit.
**Fix.** Every registration attempt, for a new or an existing address, counts against the per-origin budget that already governs code emails (**20 per hour per trusted origin**) and a spent budget answers `429 {"detail": "Too many attempts"}` and creates nothing. The count commits in its own transaction so a refused or failed attempt still counts, which also bounds address probing. The Gateway forwards the trusted origin and still rejects a caller-supplied `origin`. DOC-205 describes the budget. The figure reuses an approved value; **the owner should confirm it** for shared mobile networks.
**Tests (failed before).** Identity: flood to a 429 within budget with no mail and no account for the refused attempt, another origin unaffected, existing-address probing counted, malformed origin refused; Gateway: origin forwarded only from the trusted header; Phase 11 `T1_94`.
**Residual.** See D12-001: with no trusted header configured the origin is unknown and this budget does not apply. The repository's Nginx has no `limit_req` (`T10_81`).

### D11-005 — Validation before authorization (Authentication / authorization, Low) — FIXED
**Root cause.** The Gateway and Identity validated the lookup body before checking the caller's role, and Business handlers parsed the whole body before checking membership of the named business, so a refused caller could learn the request schema and a staff member could probe owner-only operations by their errors.
**Fix.** Identity and Gateway lookups authorize first. Business operations declare `member_roles`; the dispatcher checks entitlement to the named business before validation or idempotency-key handling, so a refused actor receives the same `404` for any body. A body with no well-formed business id still gets `400` (nothing is disclosed).
**Tests (failed before).** Gateway and Identity lookup tests; `services/business/tests/test_authorization_before_validation.py` (registry-driven: every operation that checks membership must declare it, and a refused actor gets `404` for a malformed body on every owner-only operation); Phase 11 `T1_31` and `T4_23`. One existing test expected a `400` for a body naming a business the caller does not belong to; it now asserts `404`, which is the documented rule.

### D11-006 — Console top bar overflows at 320 px (UI / accessibility, Low) — FIXED
**Root cause.** The bar's title, menu button, role badge and sign-out button had no shrink behaviour. **Fix.** The title can shrink and wrap and is slightly smaller on compact screens. **Verification.** Overflow 13 px before, 0 px after at 320 to 1280 px at normal and doubled text; Phase 11 `T9_32` PASS in real Chromium.

### D11-007 — Creators and Content emit no audit events (Integration failure, Medium) — OPEN
Carried from Phase 10 and not changed. Delivering these events needs a credential provisioned by the owner for the Audit service (owner decision M-1). Until then creator approvals and video publication are absent from the audit history. Disposition: **owner decision and provisioning**; owner: Product owner.

### D11-008 — No app client for copyright reports (Functional, Low) — OPEN
Carried from Phase 10. A product decision (whether claimants use the app or another channel) must come first. Disposition: **owner decision**; owner: Product owner.

### D11-009 — Maintenance commands unscheduled and one undocumented (Documentation / operations, Low) — documentation FIXED, scheduling OPEN
[Maintenance commands runbook](../../operations/R1_Maintenance_Commands_Runbook.md) documents all three. Scheduling them needs a reviewed change to `infra/swarm/staging-aws.yml` and an owner approval. Disposition: **manual runbook accepted for a restricted pilot; scheduler required before general release**; owner: Infrastructure owner.

### D12-001 — Per-origin limits are inert as deployed (Integration failure, Medium) — NEW, OPEN
**Finding.** Every per-origin budget (sign-in, verification and reset codes, resend, and now registration) depends on the Gateway receiving a trusted client address, which it believes only from the header named by `KOLOVIBE_TRUSTED_CLIENT_IP_HEADER`. No deployment manifest, profile or runbook in the repository sets it (`T10_87`, static). ADR-013 already says this must be configured and tested before the origin limits count; it was never done. As deployed, only address-level limits apply.
**Action (edge, owner).** Choose the header the edge overwrites on every request (for example Cloudflare's), make Nginx pass it through and drop any client-supplied copy, set the variable on the Gateway, and test with a real request through the edge. Retest: `T10_87` and `T1_94` through the real edge.

### D12-002 — FFmpeg 9.0.2 in the media worker image carries 11 High/Critical advisories (Vulnerable dependency, High) — NEW, fix proposed
**Finding.** The vulnerability database dated 24 November 2026 added advisories CVE-2026-135722 to -135743 against FFmpeg before 9.1. The media worker scan (`T10_92`) has failed on every main build since (first `e9bb068`, latest `c11f1a6`, CI run 45619859049): 11 High or Critical findings on `ffmpeg 9.0.2-r0`, two Critical (CVE-2026-135736 in `vf_deband`, CVE-2026-135743 in `af_dynaudnorm`). The other image scans pass.
**Why an exception is not enough.** At least two affected components are compiled into the minimal build: the `scale` filter (CVE-2026-135739) and the WAV muxer (CVE-2026-135722). Component data is from the CNA records as mirrored by cve.threatint.com and summarised by Rescana (24 November 2026), not verified against FFmpeg source here.
**Fix.** Build FFmpeg 9.1 (released 20 November 2026; the advisories' affected ranges end before 9.1). The source is pinned by the SHA-512 Alpine's aports master APKBUILD records for `ffmpeg-9.1.tar.xz`. The existing scoped exceptions move from `9.0.2-r0` to `9.1-r0` unchanged in premise, and CI re-checks each premise against the 9.1 binary. Rules that 9.1 no longer needs are to be pruned once the scan shows which findings remain. **Owner review needed** for the version move of the exceptions.
**Verification.** The media image job (build, minimal-build checks, exception premises, end-to-end media pipeline test, Grype gate) on the pull request.

## 3. Test-harness corrections made in Phase 12 (not product defects)

1. The broker test helper could generate a password beginning with `-`, which `rabbitmqctl` read as an option, failing a stack start about once in 32 passwords. It now always starts with a letter. The failed first attempt is kept in `results/superseded/`.
2. `T10_31` ran migrations with the runtime login; it now uses the migration login (the runtime login can no longer alter tables, by design) and also checks runtime access to re-created tables.
3. `T1_94` sends the trusted-origin header the test Gateway is configured to trust.
4. `verify_r1_db_preflight` expected the report to show login-owned objects from the old fixture; it now checks both the clean fixture and a recreated legacy state. `test_stage3_foundations` checks the new shared helper instead of a literal string.
5. A group 10 re-run on its own failed `T10_90` because that test requires the secrets registered by the other groups in the same stack; the full groups 2, 9 and 10 run was repeated and passes. Both files are kept.

No test was disabled, skipped or weakened to obtain a pass; each change above is listed so a reviewer can check it.
