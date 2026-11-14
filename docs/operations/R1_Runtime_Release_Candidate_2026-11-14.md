# KoloVibe R1 runtime release candidate — AWS staging deployment plan and evidence, 14 November 2026

**Decision: NO-GO to deploy, and R1 is not claimed ready.** This record authorizes no deployment, merge, AWS mutation, secret creation or migration. The repository now contains the capability-enabled runtime, the media worker, queue consumers, schedulers, the R2 integration, the AWS-specific stack and the Flutter management actions. What is **not** verified: the capability-enabled stack running on AWS, the media worker with real R2 and FFmpeg, RabbitMQ processing, R2 delivery, and the mobile journeys on a device. Each is listed below as UNVERIFIED or BLOCKED. It supersedes the "Why NO-GO" section of the [14 November evidence record](R1_Release_Candidate_Evidence_2026-11-14.md) for code gaps; the operational findings there still stand unless stated here.

## 1. Owner decisions in force

| Decision | Record |
| --- | --- |
| OPA installation and rehearsal | **APPROVED — WAIVED FOR RESTRICTED R1 STAGING.** Not a release blocker. |
| PostgreSQL backup creation and restore testing | **APPROVED — WAIVED FOR RESTRICTED R1 STAGING.** Not a release blocker. |
| Meaning | Waived for this restricted staging milestone only. Neither waiver authorizes deployment or merging. Existing security controls stay, and destructive data operations stay prohibited. Waivers do not carry to production. |
| In the code | The `aws-staging` profile carries the waiver as a recorded constant (`OPA_WAIVER`); the tool then skips the policy file and the OPA plugin check, opens no policy window, and refuses if an authorization plugin is active. `oracle-staging` still requires OPA. `--restore-point-ref WAIVED-R1-STAGING-20261114` names the backup waiver. |
| What the waivers cost | Without a backup, **schema changes cannot be undone** (section 7). Without OPA, any root or `docker`-group operator can change the Swarm; the tool's other guards (flags, secret ownership, drift, exact-delta, one service at a time) still apply to everything done through it. Both are accepted by the owner for this milestone. |

## 2. What this branch implements

| # | Item | Implementation | Evidence |
| --- | --- | --- | --- |
| 1 | Explicit fail-closed capability policy | `services/staging_runtime/capabilities.py`: seven capabilities, per-service applicability, dependencies, explicit (service, capability, method, path) route rules, reviewer routes also need MFA | `scripts/test_staging_capabilities.py` (18 tests): every registered route is covered, none opens through a capability that is off, methods are exact, reviewer routes need privileged and moderation, unknown paths stay closed |
| 2 | Gateway and middleware enforcement | Middleware shares one pure `route_allowed`; Gateway reads `STAGING_CAPABILITIES` (already present, previously never set); creators search and own-profile routes added | same suite, plus the existing staging runtime tests |
| 3 | Eight services aligned to one flag guard | `configure()` parses the set, refuses a capability on a service it does not apply to, sets each service's feature switches from the set only (never from the environment), and demands the matching secrets (R2, broker, peers, gateway credential). Tool: per-service baseline row **and** R1 row, exact | `ConfigureTests`, `scripts/test_cluster_r1_rollout.py` (21), tool tables checked against the runtime policy |
| 4 | AWS-specific, hostname-pinned stack | `infra/swarm/staging-aws.yml` (not the Oracle stack): seven processes, exact `node.hostname==ip-172-31-16-154`, zero replicas, external secrets, read-only, no capabilities | `validate_staging_stack.py --aws-stack`, `scripts/test_aws_stack.py` (10, with rejection cases) |
| 5 | FFmpeg, bounded media worker, consumers, schedulers | **Celery is the existing approved mechanism** (hash-locked `celery==5.6.3`; `media_tasks`, engagement and points `celery_app`; the `run_media_worker` command). No second mechanism added. New roles in `staging_runtime/roles.py` and `launch --role`: media worker, engagement and points consumers, outbox dispatcher, three audit deliverers, one concurrency, recycled children, bounded interval/batch | `scripts/test_staging_roles.py` (7); FFmpeg added to the one release image (see below) |
| 6 | R2 private bucket | Keys only from owner-only secret files; account and bucket identifiers validated; **pure-Python SigV4 presigner** replaces the glibc-only native signer so the Content API can run on the Alpine image; broker URI only from a secret file with an explicit CA | `test_media.py`: signature equals the AWS CRT reference for upload and playback URLs; header/expiry binding; bad inputs refused |
| 7 | Flutter publish, unpublish, manage | `ownedVideo`, `setVisibility`, `editDetails`, `deleteVideo`; `ManageVideoController`; M-053 screen with M-054 edit, M-055 unpublish and M-056 delete confirmations; library opens it for every non-draft video; M-052 notice link on it | `live_manage_video_test.dart` (26 tests) |
| 8 | Mobile paths, persistent auth, errors | Every distinct Flutter path resolves to a gateway route; session restore, refresh rotation, logout and expiry tests unchanged and passing | section 5 |

Image decision (reviewed, recorded): FFmpeg is installed in the **single shared release image**, not a second image. A separate media image would break the CI invariants "one build, one push, one publication record" and the tool's one-digest release evidence. Cost: the encoder's 113 Alpine packages sit in every service container (no SQLite among them, re-checked in the Dockerfile and CI). Only the media worker executes it, with a fixed minimal `PATH`. If the image scan finds a High CVE in them, the image gate fails and nothing publishes; it is never excepted. A separate hardened media image remains the preferred future step.

### Capability policy

| Capability | Gateway routes opened | Receivers that carry it | Needs |
| --- | --- | --- | --- |
| `account_management` | verification resend, password reset, sessions, change password, reauthenticate, preferences, privacy requests, app compatibility | gateway, identity | accounts |
| `media` | own creator profile, own library, create/edit/delete draft, upload intent, upload status/complete, playback, publish, unpublish | gateway, content, creators | |
| `analytics` | creator and video analytics | gateway, content, engagement | media, engagement |
| `engagement` | like, follow, shares, following feed | gateway, content (lookup), engagement | |
| `points` | creator Lone Stars balance and entries | gateway, engagement, points | engagement |
| `watch` | watch sessions and progress events | gateway, engagement | media, points |
| `moderation` | standing, notices, reports, appeals; **reviewer queues and decisions** | gateway, identity, content, moderation | privileged MFA sessions |

Reviewer and administrative routes are reachable only with `moderation` **and** `KOLOVIBE_STAGING_PRIVILEGED=1`; Identity's MFA session, role and audit checks remain the authority. Creator onboarding keeps its own flag. The `audit` service carries no capability. Public catalogue reads and `GET /creators/search` stay open as before.

## 3. Read-only AWS and GHCR verification (performed 14 November 2026)

Method: SSH (user `ubuntu`) to the manager and, through it, the worker; read-only commands only (`free`, `df`, `docker version/info/node/service/secret/network ls`, `docker stats --no-stream`, `docker service inspect` filtered to four flag variables, `docker ps`). Nothing was created, changed, restarted, pulled or exec'd. No secret, key or environment value other than the four flag names was read or recorded.

| Fact | Observation | Status |
| --- | --- | --- |
| Manager | `ip-172-31-30-236`, t3.small, 2 vCPU, 1905 MiB RAM (1338 MiB available), no swap, drained, Ubuntu 24.04, Docker 29.9.3 (API 1.56), 15 GiB free; one 96 MiB bridge container | PASS (observed) |
| Worker | `ip-172-31-16-154`, c7i-flex.large, 2 vCPU, **3812 MiB RAM, 2254 MiB available**, no swap, 24 GiB free, Docker 29.9.3 | PASS (observed) |
| Placement | All ten services run on the worker, 1/1, eight APIs healthy for 4 days; manager has none | PASS |
| Node labels | Worker carries `kolovibe.workloads=true` and `kolovibe.rabbitmq=true`, manager none. **This contradicts the earlier "no labels" read-back**; the AWS profile and the new stack ignore labels and pin by hostname | Corrected |
| OPA | `Plugins.Authorization` is null; `/etc/docker/policies` does not exist | Consistent with the waiver |
| Images | All eight APIs run `…@sha256:8d6a16e450e6…` (the 1 November image); PostgreSQL and RabbitMQ DHI images | Observed |
| Live flags | Gateway and Identity `ACCOUNTS=1`, `PRIVILEGED=0`; the six others `0`, `0`; no capability variable anywhere | Equals the tool's baseline row |
| Memory in use | APIs 85 to 101 MiB each (limit 256), RabbitMQ 78 MiB (768), PostgreSQL 51 MiB (768) | Observed |
| Networks | `kolovibe_services`, `kolovibe_data`, `kolovibe_messaging` (overlay), plus `kolovibe_identity_smtp_egress` | PASS for the stack's externals |
| Secrets present | Per-service `_django/_db/_tls_cert/_tls_key/_callers/_probe`, `gateway_outbound`, `trusted_peers`, CAs, the 10 November account secrets, PostgreSQL and RabbitMQ secrets | Names only |
| **Secrets absent** | **Every R1 secret** (section 6), and Identity's `identity_mfa_encryption`, `identity_audit_signing`, `identity_audit_peers` (Identity does not run privileged sessions today) | **BLOCKED** |
| GHCR manifest | The package is private: an anonymous pull token is refused; the available token lacks `read:packages`, so manifest existence and pullability for the target digest are **not** verified. The VM's own pull during `update` is the proof | **UNVERIFIED** |
| RabbitMQ and PostgreSQL health | Services 1/1 and up 4 days; queues, alarms, application vhost and per-service broker accounts **not** inspected | UNVERIFIED |
| Live PostgreSQL version, creator-handle collisions | Not read (no database access in this session) | UNVERIFIED |

### Capacity (stop condition: insufficient capacity)

| Item | MiB |
| --- | --- |
| Worker available now | 2254 |
| New processes, worst case (limits): media worker 512; engagement consumer 192 and dispatcher 160; points consumer 192 and audit 160; moderation audit 160; identity audit 160 | 1536 |
| Reservations only | 768 |
| Headroom if every new process hit its limit | 718 |
| Typical expectation (not measured): six small Python processes at about 100 to 150 each plus a media worker at 150 to 400 while encoding | about 800 to 1300 |

Verdict: the plan fits on paper with 718 MiB spare even at the worst case, so this is **not** a stop. It is not a load test: there is no swap, so simultaneous heavy FFmpeg encoding and traffic can trigger an out-of-memory kill; limits contain it to the one container. The image pull adds the FFmpeg layer (disk is ample). The manager has no workload and is untouched. Run the services up one at a time and watch `docker stats`; stop above 85 % of available memory.

## 4. Exact deployment plan (for the owner's separate written approval)

| Field | Content |
| --- | --- |
| Target | AWS staging Swarm: manager `ip-172-31-30-236`, worker `ip-172-31-16-154`, `kolovibe-*` services, public hosts as today |
| Image | **To be named after merge:** the digest published by `main` CI for the merged release commit, with its `published-image-<sha>` artifact as `--release-dir`. Not `…893a4d01…` (it lacks this branch). No other digest is in scope. Verify manifest and pull (section 3) before the first update |
| Services changed (APIs) | audit, identity, creators, content, engagement, points, moderation, gateway, in that order, one at a time, with `update --profile aws-staging --enable-r1-capabilities` (plus `--secret-override` for the Gateway/Identity/receiver secret versions in section 6). Each moves to the new image **and** the reviewed R1 flags, mounts and (content, engagement, points) the messaging network. Nothing else changes |
| Services added | seven processes from `staging-aws.yml` (media worker, engagement consumer and dispatcher, points consumer and audit deliverer, moderation and identity audit deliverers), created at zero replicas and scaled to 1 one at a time |
| Memory limits | APIs unchanged (256 MiB limit, 128 reservation). New processes 512 / 192 / 160 / 192 / 160 / 160 / 160 MiB (1536 total) |
| Migrations | Run separately, per service, by the service-owned migration login in this order: identity (0006 to 0009), creators (0003, 0004), content (0003 to 0008), audit (0004), engagement (new, 0001 to 0005), points (0003 to 0005), moderation (new, 0001 to 0003). The tool never runs them. `manage.py showmigrations` must list nothing pending afterwards |
| Migration effects | Additive tables and columns, unique and check constraints, append-only guard triggers, and two data steps: identity 0006 back-fills `email_verified_at` for verified accounts, engagement 0005 retains known qualifications. Content 0003 adds and 0005 **removes** `stream_upload_id`: net schema-neutral against the deployed image, which has neither. Creators 0004 adds a case-insensitive unique handle constraint and **fails if two existing handles differ only by case**; check first with a read-only query |
| **Irreversibility (stop condition)** | With the backup waived, **no migration can be undone** (reverse operations are no-ops for the triggers and data steps; only Points 0005 was reverse-tested). The owner must approve the migration step **explicitly and separately**, knowing a bad migration means repairing forward, not restoring. Rolling back Points 0005, Moderation 0003 or Audit 0004 destroys evidence tables, so never roll those back |
| Expected downtime | Per API about 30 to 90 s (stop-first, 60 s start period, 30 s monitor); the sequence is roughly 10 to 15 minutes end to end. The Gateway goes last, so end users see the API unavailable for about a minute while it restarts; reads of public videos fail then. Workers and jobs start after the APIs and cause no downtime. Impact: restricted UAT testers only |
| Rollback | **Images, flags, mounts, networks:** `kolovibe_cluster.py rollback --profile aws-staging --services <list> --confirm-rollback <list>`: restores each service's previous spec (old image and old env, secrets and networks), Gateway first. **Added processes:** `docker service scale <name>=0` (nothing is deleted). **Schema and data: none** (backup waived). Keep every old secret version until the soak ends |
| Post-deployment tests | Tool `verify-worker` after each service and `verify-edge`; then the [runbook](R1_Deployment_and_Rollback_Runbook_2026-11-14.md) section 9 and the [iPhone checklist](R1_iPhone_UAT_Checklist_2026-11-14.md) sections A to G. Plus: RabbitMQ publish, consume, redelivery and duplicate suppression (exactly one effect per event id); one R2 upload with a lifecycle that expires originals; FFmpeg output playable from the signed URL; per-view and daily-cap points; reviewer decision with MFA; audit delivered once |
| Stop conditions | Any `BLOCKED:` message; a missing secret; failed `verify-worker`/`verify-edge`; Swarm `rollback_*` or `paused`; a creator-handle collision; available worker memory below 15 %; any migration error; any unexpected service change |

## 5. Test and security evidence (local; CI repeats it on the pull request)

| Check | Result |
| --- | --- |
| `scripts/` unittest discovery (adds `test_staging_capabilities` 18, `test_staging_roles` 7, `test_cluster_r1_rollout` 21, `test_aws_stack` 10, waiver and image tests) | PASS |
| Django, eight services plus web | PASS (content now includes the signature-equals-CRT test) |
| PostgreSQL TLS migrations, isolation, journeys, restricted staging WSGI | PASS (local PostgreSQL 14.15; staging is 16) |
| Flutter `analyze` | PASS |
| Flutter tests | PASS (previous 893 plus 26 new; one existing library test updated to the new Manage entry) |
| Offline stack validation (`--aws-stack`) | PASS; memory budget 1536 MiB |
| Secret scan, Bandit, pip-audit, OpenAPI | re-run on the clean tree before the PR (results in the PR description) |
| Container build, image scan, "no SQLite" check, FFmpeg-on-sandbox-PATH check, eight-service smoke matrix, SBOM, osv-scan | **Not runnable locally** (no Docker). CI on the pull request is the evidence; a High finding in FFmpeg's packages would fail it |

## 6. Inputs the owner or operator must supply (names only; values never in Git)

| Needed | Names | State |
| --- | --- | --- |
| **R2 credentials** (stop condition: missing) | Account identifier (32 hex), private bucket, and two scoped keys (object read/write on that bucket only): `kolovibe_content_r2_access_key_r1_v1`, `kolovibe_content_r2_secret_key_r1_v1`. A bucket lifecycle expiring originals and abandoned renditions | **BLOCKED: not provided** |
| Broker URIs (AMQPS, one least-privilege RabbitMQ account per service, queues `kolovibe.content.media`, `kolovibe.engagement`, `kolovibe.points`) | `kolovibe_content_rabbitmq_url_r1_v1`, `kolovibe_engagement_rabbitmq_url_r1_v1`, `kolovibe_points_rabbitmq_url_r1_v1`; CA is the existing `kolovibe_rmq_ca` | BLOCKED: absent; broker accounts and vhost permissions unverified |
| Service-to-audit identity for Points and Moderation | `kolovibe_points_outbound_key_r1_v1`, `kolovibe_points_audit_peers_r1_v1`, `kolovibe_moderation_outbound_key_r1_v1`, `kolovibe_moderation_peers_r1_v1`; a new `audit_callers` version with distinct keys for points and moderation | BLOCKED: absent |
| Identity privileged sessions | `identity_mfa_encryption`, `identity_audit_signing`, `identity_audit_peers` | BLOCKED: absent |
| Gateway peers and per-peer keys | `kolovibe_gateway_trusted_peers_r1_v1` (identity, content, creators, engagement, points, moderation), `kolovibe_gateway_outbound_r1_v1` (one distinct key per audience), matching new versions of each receiver's `_callers` | BLOCKED: absent |
| Approvals with MFA and audit references | `kolovibe_account_approval_r1_v1` for Gateway and Identity | BLOCKED: absent |
| Non-secret | `R2_ACCOUNT_ID`, `R2_MEDIA_BUCKET`, SMTP host/port/from (as today), runtime DB logins | R2 values missing |
| A reviewer account with MFA enrolled (`enroll_privileged_mfa`) and a creator invitation, for UAT | | Not created |

## 7. Gates

| Gate | Status |
| --- | --- |
| Capability policy, enforcement, per-service flag guard, tool rollout, AWS stack spec (offline) | **PASS** (tests above) |
| Flutter publish, unpublish, manage; paths; persistent auth; error handling (unit and widget level) | **PASS** locally; device **UNVERIFIED** |
| Container image build, vulnerability scan, FFmpeg present, smoke matrix | **UNVERIFIED** until CI on this pull request |
| Immutable release digest for this branch | **BLOCKED**: published only by `main` CI after merge |
| GHCR manifest and pull from AWS | **UNVERIFIED** (token lacks `read:packages`) |
| AWS capacity, placement, node and service state | **PASS** (read-only snapshot, section 3); load behaviour UNVERIFIED |
| OPA | **WAIVED — approved** (not a blocker) |
| Backup and restore | **WAIVED — approved** (not a blocker); consequence: migrations are irreversible |
| R2 integration live; FFmpeg on real uploads; R2 delivery | **BLOCKED**: no R2 credentials; **UNVERIFIED** |
| RabbitMQ processing end to end | **UNVERIFIED**; secrets and accounts missing |
| Creator-handle collision check (creators 0004), PostgreSQL version | **UNVERIFIED**: needs read-only DB access |
| Mobile full R1 journey on a physical iPhone | **BLOCKED**: nothing is deployed |
| Owner approval of this exact plan, of the irreversible migrations and of each AWS mutation | **BLOCKED**: not requested yet |

## 8. Remaining approvals and stops

1. Supply the R2 credentials and create every secret in section 6 (the tool stops naming the first missing one).
2. Merge this pull request after CI is green; use the digest `main` CI then publishes; verify the manifest with a `read:packages` credential or by the pull in step 4.
3. Provide read-only database access (or run two queries) for the creator-handle collision check and the PostgreSQL version.
4. Written approval of the exact plan in section 4, including the explicit acknowledgement that migrations are irreversible without a backup, and of each mutating command (secret creation, `update`, `docker stack deploy`, scaling, migrations).
5. A named operator, a window, and the physical iPhone UAT.

R1 stays **NO-GO** until 1 to 4 are satisfied and the capability-enabled stack, media worker, RabbitMQ processing, R2 integration and mobile journeys are each verified.
