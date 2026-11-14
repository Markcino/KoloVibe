# R1 AWS staging deployment plan and approval request — 13 November 2026

**Status: NOT APPROVED, NOT EXECUTED.** Nothing was deployed, changed or contacted on AWS. This is a plan, built from the repository at `main` `aa9881f0b2ecd0daf43c5bac705be3b9f505de37` and the owner-supplied [10 November AWS record](AWS_Staging_Deployment_Verification_2026-11-10.md). The Oracle Cloud topology was not assumed.

> **Corrections of 14 November 2026 (this plan's text below is kept as the historical record).**
> * Section 1 and 3 item 1 (image pin, no published digest): superseded. The deploy tool no longer pins an image (PR #60), the `sqlite-libs` scan failure is fixed by the PostgreSQL-only release target (PR #54), and CI run `43516806784` published `ghcr.io/markcino/kolovibe/services@sha256:887c9a05…98e8` from `92e5a55` with evidence. GHCR manifest existence and pullability from the AWS nodes are **UNVERIFIED**; publication authorizes nothing ([remediation plans](R1_Remediation_Plans_2026-11-14.md) section 4).
> * Worker labels: the AWS worker has **no Swarm labels** and services are pinned by hostname. The `kolovibe.workloads` label and the "~956 MiB" RAM figure in the repository describe the **Oracle** VMs, not AWS. The AWS instance size is unrecorded.
> * Backup: no PostgreSQL backup exists or has been restored in any environment. Nothing in the repository documents an existing encrypted backup; the "existing encrypted overlays" in the Oracle record are network encryption.
> * Section 3 items 2 to 4 (staging capability gates, worker services, FFmpeg/R2) remain open and are re-verified against source in the [R1 release-candidate evidence record](R1_Release_Candidate_Evidence_2026-11-14.md).

## 1. Preconditions

| Precondition | Met? | Evidence |
| --- | --- | --- |
| Reviewed release candidate | Partly | Work through PR #52 is merged on `main`; no candidate commit has been designated. |
| Required CI checks passed | **No** | [Run 43437183116](https://github.com/Markcino/KoloVibe/actions/runs/43437183116) on `aa9881f`: Django, Flutter, Security scans and SBOM, and osv-scan pass; "Build and scan shared service image" fails on four High `sqlite-libs 3.53.4-r0` CVEs with no fixed version (see the [Stage 4A record](../engineering/R1_Stage4A_security_ci_acceptance.md)). The eight-service smoke matrix and `publish` are skipped. |
| Approved image digests | **No** | No image has been published since `be03dbcc`. The only digest in use is `ghcr.io/markcino/kolovibe/services@sha256:8d6a16e450e6a7825c7d501069cd54fa3a75776afc2819e5664499bcef85ea14`, 93 commits behind `main`. |
| Explicit deployment approval | **No** | Requested in section 8. |

Gates are not bypassed: publication stays blocked until the image scan passes.

## 2. Actual AWS staging architecture (owner-reported, not observed here)

AWS VM1 is the Swarm manager (drained) with host Nginx; VM2 is the workload worker. Eight Django services, a PostgreSQL DHI service and a RabbitMQ DHI service run as Swarm services, behind Cloudflare hosts `api.cabetechs.shop`, `mobile-api.cabetechs.shop/api/v1` and a web placeholder (HTTP 503). Deployment is operator-run on the VMs by `scripts/ops/kolovibe_cluster.py` (`worker-preflight`, `plan`, `deploy`, `verify-worker`, `verify-edge`) with hidden-prompt GHCR credentials. **This session has no `aws` CLI, SSH or Docker daemon, so it cannot inspect or change the environment; every step below is for an operator, and every result must be pasted back as evidence.**

## 3. Why `main` is not deployable to staging as it stands

1. **Image pin.** The deploy tool hard-codes the 1 November digest and commit and only *creates* missing services; it cannot move running services to a newer image. A reviewed change is needed.
2. **Staging runtime blocks most R1 routes.** `staging_runtime/middleware.py` allows only public video and creator reads, accounts (`KOLOVIBE_STAGING_ACCOUNTS`), privileged routes and creator onboarding, plus audit ingest. Uploads, likes, follows, watch sessions, points, reports and moderation have no staging capability flag, and newer account routes (password reset, sessions, settings) are not on the list.
3. **No worker processes in the stack.** `infra/swarm/staging.yml` has the eight APIs and RabbitMQ only. There is no media worker, no Celery consumers for engagement and points, and no scheduler for `dispatch_engagement_events`, `deliver_audit_events` or `deliver_security_audit`.
4. **FFmpeg and R2.** The shared image contains neither FFmpeg nor the optional media dependencies (`requirements-media.txt`); a separate sandboxed worker image does not exist.
5. **Schema distance.** Since `be03dbcc`: audit 0004; content 0003–0008; creators 0003–0004; identity 0006–0009; points 0003–0005; and brand-new apps engagement (0001–0005) and moderation (0001–0003), which had no migrations in the deployed image. Creators 0004 installs a case-insensitive unique handle constraint and fails if legacy handles collide.
6. **Recovery.** Backup and restore evidence is still open (FND-16), so a pre-migration restore point is unproven.

Items 1 to 4 are reviewed-code changes, not operator steps; they are outside this stage's rule of deploying only reviewed images.

## 4. Secrets and configuration (names only; values never recorded)

Existing Swarm secrets per service: `<svc>_django`, `<svc>_db`, `<svc>_tls_cert`, `<svc>_tls_key`, `<svc>_callers`, `<svc>_probe`; identity additionally `identity_smtp_user`, `identity_smtp_password`, `identity_mfa_encryption`, `identity_audit_signing`, `identity_audit_peers`, `identity_approvals`. Newly required by current code, none provisioned in the stack: R2 account id, media bucket, access-key file, secret-key file; the Content AMQPS URL; engagement and points broker URLs; a Moderation outbound key distinct from the gateway key; outbound signing keys and `audit` peer files for points, moderation (and creators and content when they gain producers); matching distinct caller keys in the audit caller file; DB logins with the new tables' privileges. Operator check: confirm each object exists and is mode 0400 without ever printing it, e.g. `docker secret ls --format '{{.Name}}'` and the tool's `worker-preflight`, which reports without values.

## 5. Migration and rollback plan

1. Before anything: owner-approved restore point (per-schema `pg_dump` or volume snapshot) **and a tested restore**, which does not exist yet.
2. Resolve creator handle collisions case-insensitively (report only; never rename silently).
3. Apply migrations per service with the service-owned migration login, never the runtime login, in order: identity, creators, content, audit, engagement, points, moderation. Runtime logins get SELECT-only on migration history and only the new object privileges.
4. Per-service `makemigrations --check` equivalent: `manage.py showmigrations` must list every migration applied and none pending.
5. Roll out one service at a time; Swarm `rollback_config` (stop-first, monitor 30 s, `failure_action: rollback`) restores the previous image on a failed update.

Rollback: image rollback is `docker service rollback <name>` or re-pinning the prior digest. **Schema rollback is not verified for most migrations**; reverse operations were checked only for Points 0005 (apply, unapply, re-apply on PostgreSQL 16). Treat all other migrations as forward-only and use restore-from-backup. Rolling back Points 0005, Moderation 0003 or Audit 0004 destroys evidence tables, so export pending rows first. Old images tolerate additive tables, but this was not tested against the new schema.

## 6. Deployment sequence (after approval) and acceptance tests

| Phase | Action | Pass criteria |
| --- | --- | --- |
| A | On VM2 `worker-preflight`; on VM1 `plan` (dry run) | Evidence JSON fresh; planned services match; the working gateway is preserved |
| B | Backup, restore test, migrations (section 5) | No pending migrations; no errors in service logs |
| C | `deploy` of the approved digest | Each service 1/1, health 200, `verify-worker` all PASS |
| D | `verify-edge` and auth: unauthenticated 401, authorized 200, cross-account `/me`, logout then 401, refresh after logout rejected, replay detected | All as expected; evidence with timestamps |
| E | Creator onboarding and publication: invite, application, reviewer decision with MFA, eligibility, draft, upload, review, publish | Only possible once capability flags exist (item 2) |
| F | R2 upload, FFmpeg, signed playback | Needs the worker image and R2 secrets (items 3 and 4); playback URL expires at 300 s; no URL logged |
| G | RabbitMQ: publish, consume, redelivery, duplicate suppression, dead letter, restart recovery | Exactly one effect per event id |
| H | Qualified view, like, follow, points | Server-owned qualification; one award per event; daily cap 100; balance equals ledger |
| I | Report, reviewer decision, appeal, audit delivery | Audit rows delivered once; retry on outage; no row lost |

Phases E to I cannot start while the staging profile blocks those routes. Each run records: command, UTC timestamp, HTTP status, image digest per service (`docker service inspect`), and redacted log excerpts. A phase that fails is reported as failed; no acceptance is claimed for anything not run.

## 7. Blockers

1. Image scan (`sqlite-libs`) blocks any publishable digest.
2. Items 1 to 4 in section 3 need reviewed changes and a new worker image.
3. No verified backup and restore.
4. No environment access from this session.

## 8. Approval checkpoint

Approval is requested for none of the phases yet. To proceed I need the owner to decide:

1. How to resolve the `sqlite-libs` finding (wait for an Alpine fix, build a PostgreSQL-only image, or a time-boxed risk acceptance), so CI can publish a digest.
2. Whether the staging capability gates, worker services and media worker image are in scope as reviewed changes, and who reviews them.
3. A named operator to run the VM commands and paste back evidence, plus an approved backup and restore point.
4. A designated release commit and its published digest. Approval must name that digest.
