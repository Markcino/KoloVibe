# Phase 3: core application development completion (25 November 2026)

**Repository-side development only.** Nothing was deployed, no staging, AWS, database privilege, RabbitMQ permission or live secret was changed, and nothing was merged. **Production NO-GO stands.** No result below is live staging or device acceptance.

## 1. Track A outcome

| Task | Item | Classification | Evidence |
| --- | --- | --- | --- |
| A1 | D-P2-01: the poster is re-rendered after a cover edit | **Development complete** (PR #234, not merged) | `services/content/tests/test_cover_rerender.py` (10). Content suite: 145 passed |
| A2 | D11-007: Creators audit outbox and delivery | **Development complete** (PR #235, not merged); deploy needs O-10 | `services/creators/tests/test_audit_evidence.py`. Creators: 95 passed. Audit: 52 passed (new producer-kind contract test) |
| A3 | D11-007: Content audit outbox and delivery | **Development complete** (PR #235, not merged); deploy needs O-10 | `services/content/tests/test_audit_evidence.py`. Content: 144 passed on that branch. PostgreSQL foundations: the 16 new audit tests passed as the runtime login. `scripts/test_audit_delivery_lock_scope.py` covers six commands |
| A4 | M-050, M-051, M-052 upload result screens | **Development complete: already implemented, no change.** The Phase 1 and 2 "gap" was a false positive | `apps/mobile/lib/features/content/live_create_original_screen.dart` `_settled()` renders the three states in-flow. `test/design_audit_test.dart` audits them. `test/creator_upload_routes_test.dart` keeps the direct routes as protected fallbacks. M-045 (cover moment) is live in `live_manage_video_screen.dart` |
| A5 | D11-009: maintenance scheduling | **Development complete** for two of three commands (PR #236, not merged), at `replicas: 0`. **Blocked by approval** to run (O-12) | `identity-purge` and `content-requeue` in `infra/swarm/staging-aws.yml`. `scripts.test_staging_roles` and `scripts.test_aws_stack`: 19 passed. The console `purge_expired_web_sessions` (separate web stack) is still a manual run: **Partial** |
| A6 | Dead-letter handling | **Blocked by approval** (RV2-03 values not provided) | No code. The values are not invented |
| A7 | Identity step-up design (DR-BZ-33) | **Missing** (design-only; not started in this phase) | — |

## 2. Correction to Phase 1 and Phase 2

Phase 1 §2 (rows for M-045 and M-050 to M-052, and items C6 and 3) and Phase 2 Track A4 list the upload result screens as missing. They are not. The states are rendered inside the live upload flow, and the static recipes are deliberate fallbacks for direct routes that have no meaningful cold entry. **Missing in code** from Phase 1 is now only **dead-letter handling**.

## 3. Sections A to G after Phase 3

| Section | Status |
| --- | --- |
| A Identity | Development complete. Privacy processing is **Blocked by approval** (ADR-020). Step-up is **Blocked by approval** (DR-BZ-33). Consent record is **Blocked by approval** (RV2-02) |
| B Creators | Development complete, including audit (PR #235). Creator restriction is **Blocked by approval** (D-8). Creator photos are **Blocked by approval** (D-10) |
| C Video and media | Development complete, including poster re-render (PR #234). Re-review of published-video edits is **Blocked by approval** (RV2-01) |
| D Engagement and points | Development complete. Dead letters are **Blocked by approval** (RV2-03). Points never become money; no change |
| E Moderation and audit | Development complete, including Creators and Content producers. Copyright claimant intake is **Blocked by approval** (D11-008) |
| F Client integration | Development complete (A4 correction) |
| G Security and data integrity (repo side) | Maintenance roles are candidates (PR #236). Observability (ADR-017) and backup and restore (ADR-016) are **Blocked by approval** |
| Events, Advertising, Finance | **Blocked by approval**; no code |
| Live streaming, public website | **Explicitly excluded** |

**Ready for comprehensive testing:** A1 to A5 once merged, on a disposable stack. **Accepted with evidence:** none; that needs staging and device acceptance (Track E).

## 4. Phase boundary report

1. **Verified base:** `main` at the merge of PR #232 (Phase 1). Each PR branches from `main`.
2. **Feature matrix:** Phase 1 §2 with the changes in sections 1 to 3 above.
3. **Files changed:** PR #234 (Content poster task); PR #235 (Creators and Content audit models, migrations `creators 0007` and `content 0011`, delivery commands, Audit producer kind); PR #236 (two Swarm roles, validator and tests); this report and a tracker pointer.
4. **Database and API changes:** two new append-only tables each in Creators and Content (`*_audit_event` with a database trigger, and `*_audit_delivery`). One new Audit producer kind, `creator.invitation_revoked`. One new Celery task, `kolovibe.content.render_cover`. No public API change.
5. **Security:** audit evidence now covers the Creators and Content state changes. The validator still allows an R2 route only for the media worker; the Content requeue job carries only the R2 settings the runtime validates. No control was weakened.
6. **Tests:** the counts in section 1, all run in this container. The full `scripts` suite passes on PR #236 (475 tests, 4 skipped). Flutter was not re-run (no Flutter change); its last run is the Phase 1 run (1,824 passed).
7. **PRs:** #234, #235 and #236, none merged. Phase 2 docs PR #233 is still open.
8. **Outstanding decisions:** RV2-01 to RV2-04, X-01, ADR-016, ADR-017, ADR-020, D-8, D-10, D11-008, DR-BZ-33, and O-10 and O-12 for deploying A2, A3 and A5.
9. **Known defects:** none new. D-P2-01 is fixed in #234. D11-007 is fixed in #235. D11-009 is fixed in #236 except the console purge.
10. **Next-phase prerequisites:** owner review and merge of #234 to #236; the RV2-03 values for A6; Track B operations; then Track E testing.

**STOP AFTER PHASE 3.**
