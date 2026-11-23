# R1 AWS staging reconciliation — 23 November 2026

**Current operator-observed deployed release: v0.357.1. AWS staging: deployment PASS; administrator/moderator UAT PASS (owner-reported); full R1 acceptance OPEN; production NO-GO.**

**Record type:** dated implementation and evidence reconciliation, not a new design approval, security certification, migration authorization, or production go-live decision. This document supersedes the *current-status assertions* in the [17 November staging snapshot](R1_AWS_Staging_Reconciliation_2026-11-17.md), the [R1 application tracker](../engineering/R1_Application_Tracker.md) before this update, and earlier deployment plans. Preserve those records as historical evidence.

## Scope, approval, and stage boundaries

- R1 owner approval dated 10 November selects **Option 3: eight backend services, R1 API contracts, deployment verification, and documented acceptance evidence**, inside approved MVP scope. This is an execution target, **not** blanket implementation or acceptance sign-off.
- DEC-001 approves the MVP **scope**, not every PRD/SRS detail. DEC-003 (qualified engagement and non-cash points), DEC-004 (creator eligibility), DEC-005 (moderation), and OD-07 (private Cloudflare R2 + FFmpeg on-demand video through RabbitMQ/Celery) govern the related restricted-pilot work. Preserve the document-control interpretation in [the DEC-001 register](../requirements/platform_documentation_register_and_DEC001.md).
- R1 includes accounts, creator profiles and eligibility, video upload/processing/playback, verified views/likes, non-cash points, moderation/reporting/appeals, audit and supporting safeguards. **Not in R1:** live streaming, business discovery/verification, event ticketing, and cash payouts/settlement.
- Stage 3 was **declared complete by the owner** on 10 November; outstanding foundation controls remain open. Stages 4 and 5 proceed in parallel; Stage 6 pilot/go-live has **not** been authorized. See [go-live readiness](../planning/go_live_readiness.md).

## AWS staging deployment — verified boundary

The owner ran the v0.357.1 rollout on AWS Swarm VM1 after verifying the immutable images and embedded source revision on VM2. The supplied terminal output reported **16/16 service image updates and six of six public HTTPS smoke checks passing**. A private, root-restricted before-spec snapshot was saved on VM1 for rollback evidence. This documentation change did not rerun the deployment.

| Evidence | State | Limits |
| --- | --- | --- |
| GitHub [v0.357.1 CI / publication](https://github.com/Markcino/KoloVibe/actions/runs/45196093209) | **PASS**, commit `807b1edc6e80454bd6bfcb4a78761fa284cd6bee` | Repository tests and image publication are not live feature acceptance |
| VM2 image pull and revision inspection | **PASS 3/3**, operator terminal | Source labels and immutable digests checked before rollout |
| VM1 Swarm update | **PASS 16/16**, operator terminal | All eight APIs, six shared-image background jobs, one media worker, one Django web service; one running replica each at inspection |
| Six HTTPS smoke checks | **PASS 6/6**, operator terminal | Web health 200, login 200, moderator-invitation landing 200, mobile API health 200, public video feed 200, unauthenticated `/api/v1/me` 401; these are **not** authenticated workflows |
| Identity migration `0011_moderator_invitations` | Previously applied, **retained** | No migration needed between v0.355.1 and v0.357.1; do not infer a new database migration from image publication |
| Administrator/moderator UAT on v0.357.1 | **PASS 6/6 by owner report** | Administrator dashboard, video review, reports/appeals, points review, moderator assignment, moderator access. No independent negative authorization or cross-account test was supplied |
| Repository `main` after release | **Ahead of deployed image** at observation | `dbdeb95cb56228e7b1669af936b970d0953029e7` contains additional creator administration/account-lookup changes not evidenced as deployed on v0.357.1. [Its CI](https://github.com/Markcino/KoloVibe/actions/runs/45203111940) was in progress when checked; do not transfer these changes or results to staging |

### Deployed image provenance

| Image family | Tag | Immutable digest |
| --- | --- | --- |
| Eight APIs and six shared-image jobs | `services:v0.357.1` | `sha256:5cc7633745495b723e6821fd1981697e6159031dc761b0adf5874bba99a06779` |
| Media worker | `media-worker:v0.357.1` | `sha256:ed06801b7ca949104d1f7f41a91f9bce940f8bc0805816ae6f19eb5755597a59` |
| Django web | `web:v0.357.1` | `sha256:8619f6cb588756e9a76bb3a7fc3f20d679035a80641f6b8f72a12bb5a0c26e03` |

Prior separate rollout checkpoints v0.346.1, v0.353.1 (including same-origin moderator MFA enrollment QR), and v0.355.1 were reported complete; the latest operator-observed deployed state above supersedes their current-image assertions. Each historical test belongs to its own release and environment.

## Authenticated moderator incident and UAT

On v0.355.1 the owner reported **“Request unavailable”** on most moderator-console pages while Audit and Account worked. Web logs showed 403 (Forbidden), rather than a general 503 outage, for reviewer Videos, Reports, and Points; login/MFA and the dashboard returned 200. Source inspection shows explicit reviewer resource grants and administrator-only operations. The owner's subsequent read-only database check found **one administrator, one moderator, zero active moderator assignments** at that time. This is consistent with the restricted review queues; it is **not** proof that every observed 403 had the same root cause.

The owner then deployed v0.357.1 and submitted **PASS** for administrator dashboard, Videos review, Reports/Appeals, Points, Moderator Assignments, and Moderator Access. Record this as **positive authenticated UAT evidence**, not a blanket permission matrix, BOLA/IDOR, MFA replay, queue-scope or negative assignment test. Keep the expected distinction between administrators and assigned moderators.

## Deployed capabilities versus unclosed acceptance

| Workstream | What is established | Still required to close R1 |
| --- | --- | --- |
| Infrastructure / release | CI publication, 16 service convergence, publicly reachable health/login/feed endpoints | Controlled recovery/restore, backup, alerting and on-call, ingress/origin-bypass checks, load/capacity and production authorization |
| Identity and MFA | Earlier iPhone account journey passed 9/9 by tester report; current console MFA login and reviewer UAT succeeded; session migration `0011` retained | iPhone persistence retest on release build, refresh/replay/revocation negatives, account/MFA abuse rate limits, recovery, device secure-storage and independent security evidence |
| Moderator administration | QR-code enrollment implementation in released code; v0.357.1 administrative review and assignments reported PASS | Live QR enrollment end-to-end receipt; unassigned/assigned/role negative authorization, audit attribution, concurrency, appeal separation-of-duties tests |
| Discovery and content | Public video list returns 200; media worker converged | Real R2 upload, signed limits, FFmpeg conversion, publication/review, authorized playback on physical mobile, lifecycle/cleanup |
| Engagement and non-cash points | Services/jobs deployed; administrator Points page accessible | Server-qualified watch/likes, cap/dedup, noncash posting/reversal, RabbitMQ retry/dead-letter/outbox recovery, mobile balances and security acceptance |
| Creator onboarding | Creator service running; code/contracts exist | End-to-end eligibility, approval and upload authorization; newer main-only admin changes are not yet deployed/UAT |
| Audit, moderation and appeals | Audit and console moderation functions available | Audit event delivery and retention, evidence continuity, report/appeal lifecycle and negative access tests |
| Mobile | Historical physical iPhone signup/verify/sign-in/account/sign-out 9/9, with identified session-restoration issue | Exact current mobile build identification, session restore after force-close, playback, qualified views, likes, points, creator workflows, physical Android UAT |

**Do not transfer the 17 November `26 passed / 0 failed / 19 pending` matrix (v0.187.2) to v0.357.1.** There is no new complete, row-by-row R1 acceptance matrix submitted for this release.

## Open database security finding — 23 November operator read-only audit

The owner queried the staging PostgreSQL catalog. **26 tables and eight sequences were owned by application runtime roles ending `_app`** (34 objects), compared with an earlier reported 23 tables and seven sequences. The query inspected ownership only; it did **not** establish login use, role inheritance, grants, exploitable access, or whether reownership is safe.

| Schema | Runtime-role-owned tables | Runtime-role-owned sequences |
| --- | ---: | ---: |
| content | 2 | 0 |
| creators | 1 | 0 |
| engagement | 6 | 5 |
| identity | 4 | 0 |
| moderation | 6 | 1 |
| points | 4 | 1 |
| web | 3 | 1 |
| **Total** | **26** | **8** |

**Disposition: OPEN / needs DBA-security review.** Inspect `pg_roles`, `pg_auth_members`, effective DDL grants, default privileges, ownership dependencies, deployed connection principals and migration-owner role requirements before proposing any correction. Do **not** execute bulk `ALTER OWNER` or grant runtime schema ownership solely from the aggregate counts. The owner previously chose staging image deployment without a backup; this **does not close the encrypted backup, restore drill, or RTO/RPO production gates**.

The PostgreSQL version **17.11** was reported by the [22 November preflight](R1_AWS_v0_346_1_Preflight_2026-11-22.md), replacing older Oracle-era version assumptions. This release made no PostgreSQL engine upgrade.

## Next evidence order and open decisions

1. Capture a **read-only** role membership/login/ownership and privilege report; plan least-privilege remediation with an owner-approved recovery path and maintenance window before applying DDL.
2. Complete negative privileged UAT: unassigned reviewer cannot see data, a moderator cannot use admin-only endpoints, one moderator cannot access another's assignment, CSRF/session expiry and MFA replay are rejected; preserve redacted evidence.
3. Verify end-to-end **R2 + FFmpeg + RabbitMQ** video upload/review/playback and event delivery on a staging tester account, then mobile qualified-view/points and fraud protections.
4. Retest the iPhone session restore in an identified release build; complete Android device coverage.
5. Finish full security, monitoring, backups/restore, operator runbooks, audit-retention and pilot go/no-go evidence. Coordinate formal architecture/design-baseline changes in [the AWS as-built addendum](../architecture/R1_AWS_Staging_As_Built_2026-11-23.md) and [#169](https://github.com/Markcino/KoloVibe/issues/169).

**No production release, database ownership change, policy exception, or closure of unresolved PRD/SRS detail approvals is implied by this reconciliation.**
