# R1 AWS staging deployment and verification — 26 November 2026

**Record type:** dated staging deployment, test execution and defect record for the owner's mandate "Full staging deployment, end-to-end testing and defect tracking" (26 November 2026). It is evidence, not an approval, a security certification or a go-live decision. **Production is NO-GO.** The development completeness gate (EXECUTION_PROGRESS Phase 09) has **not** passed, so this is diagnostic and smoke evidence, not formal whole-application acceptance.

Every result below comes from commands run in this session against AWS staging (VM1 `ip-172-31-30-236`, VM2 `ip-172-31-16-154`) or a disposable local stack. No secret, token or personal data is reproduced. Signing keys were compared only by an 8-hex keyed fingerprint.

## 1. Release selection

| Item | Value |
| --- | --- |
| Candidate release | **v0.542.1**, `main` CI run 542 ([45850836406](https://github.com/Markcino/KoloVibe/actions/runs/45850836406)), source `38d038056cf77df4d4193e0aecef472dc7226aea`, all 16 executed jobs green, including the three image scans and SBOMs |
| Services image (8 APIs, 6 jobs) | `ghcr.io/markcino/kolovibe/services@sha256:ab9c0e0d6172d747b29d6d1b4a3f3bae61428d5cdbab99e394b6d937f6844caf` |
| Media worker image | `ghcr.io/markcino/kolovibe/media-worker@sha256:247b7dfbd5a537b272eb0ff236c0f2f2bd486dd5d763676ef6495a547b634e21` |
| Web image | `ghcr.io/markcino/kolovibe/web@sha256:d94fd230f1e198d1f06b6bde2b32ec47feb2728258e40fbdaefd0ea7d61abae4` |
| Provenance check | All three pulled by digest on VM2: `amd64`, user `10001:10001`, OCI revision label `38d0380…`, equal to the run 542 `published-image-*` and `published-web-image-*` artifacts |
| Why not `main` HEAD | `d9993ea` ("update", mobile iOS project and `pubspec.lock` only) has **no CI run and publishes nothing**; it also breaks the Flutter CI job (D13-006). v0.542.1 is the newest consistent published set |
| Release manifest service set | `services.json` lists the eight original APIs. **Business is not in the release manifest**, has no schema on staging and no capability flag, so it was not deployed (gap G-01) |

## 2. Pre-deployment state (read-only)

| Check | Result |
| --- | --- |
| SSH, sudo | Both VMs reachable as `ubuntu`, passwordless sudo |
| OS, Docker | Ubuntu 24.04.5 LTS, x86_64, 2 vCPU each; Docker 29.9.3; Swarm active, 1 manager (VM1, `Drain`), 1 worker (VM2) |
| Memory and disk | VM1 1.9 GiB (1.2 GiB available), 24% of 19 GiB disk. VM2 3.8 GiB (1.8 GiB available), 59–61% of 29 GiB disk |
| Live release | **v0.531.1**, rolled out earlier on 26 November: services `sha256:fa00b7f4…` (run 531, source `677eec3a`), media worker `sha256:80de4ad7…`, web `sha256:6cc8abed…`, all equal to the run 531 publication artifacts |
| Replicas | 19 running services at 1/1 (8 APIs, 6 jobs, media worker, web, PostgreSQL, RabbitMQ, R2 proxy). No restart loops; `points-audit` exited once at 16:14 UTC (D13-001) |
| PostgreSQL | 17.11; 9 schemas (no `business`); Identity at `0015_erasure_jobs`, Content at `0012_published_edit_review` |
| RabbitMQ | Running, no alarms, AMQPS-only listener (5671), vhost `/kolovibe`, queues `kolovibe.points`, `kolovibe.engagement`, `kolovibe.content.media` each with 1 consumer and 0 messages; 4 users; **no dead-letter policy** |
| Edge | Host Nginx config valid, listening on **127.0.0.1:80 only** (no direct origin exposure); `cloudflared` active. Hostnames: `mobile-api.cabetechs.shop` (allow-listed API routes), `kolovibe.cabetechs.shop` (console), `api.cabetechs.shop` (401 at root) |
| Rollback snapshot | `docker service inspect` of all 30 services saved to `/root/kolovibe-v05421-20261126T164812Z/` on VM1 (root-only, with SHA-256 list) |
| Backup | Restricted-staging waiver `WAIVED-R1-STAGING-20261114` (owner, 14 November). No backup was taken; see section 3 for why the migrations are safe without one |

## 3. Deployment executed

| Step | Result |
| --- | --- |
| Cluster tool `update-plan` (8 APIs) | **BLOCKED:** `Gateway differs from the working pinned baseline`. Cause: v0.531.1 was rolled out outside the tool and the services kept the v0.341.1 `kolovibe.source-revision` and pin-proof labels, so the guard could not prove the live image (D13-005) |
| Reviewed fix | [#269](https://github.com/Markcino/KoloVibe/pull/269) adds the v0.531.1 digest to `reviewed_releases` (merged by the owner); [#270](https://github.com/Markcino/KoloVibe/pull/270) fixes the secret-scan hit in its test (merged). A read-only plan with the change passed for all eight APIs with no other blocker |
| Migration plans | One-shot jobs cloned from the v0.531.1 migration jobs (same migration logins, secrets, networks and placement, new image): Identity plans only `0016_erasure_creator_id` (add nullable `creator_id`); Content plans only `0013_message_ledgers` (a SQLite-only `RunPython`; on PostgreSQL the tables already exist from `schema_isolation.sql`, verified) |
| Scheduling | The jobs could not start: VM2 CPU reservations are **2000m of 2000m** (D13-004). The one-shot jobs were given a zero CPU *reservation* (their 1-CPU limit kept); no running service was changed |
| Migrations applied | **Identity `0016` OK (17:06 UTC), Content `0013` OK (17:07 UTC)**, both by the service-owned `_migrate` logins. Additive only; the running v0.531.1 code is unaffected |
| API rollout (tool `update`) | *Superseded, see the 27 November update below.* **PENDING** at the time of writing. The tool requires a GHCR `read:packages` token typed at a hidden prompt (`--registry-user`), which only the operator may enter. The ready-to-run command re-creates fresh worker evidence first (the tool rechecks the five-minute window after the prompt). Nothing was changed by the attempt; the services are still on v0.531.1 |
| Jobs, media worker, web | **PENDING**, after the APIs (they share the release; the tool moves only the services image) |

**Deployed state at the time of writing (superseded, see the update below):** v0.531.1 images with the v0.542.1 database schema. This combination is safe (additive changes), but v0.542.1 was **not deployed** at that point.

## 4. Tests executed

### 4.1 Staging, credential-free black-box (v0.531.1)

Script kept with the session evidence; it sends no credentials. **63 run, 63 PASS, 0 FAIL.**

| Group | Checks | Result |
| --- | --- | --- |
| S1 Anonymous access to 12 protected API routes (`/me`, sessions, creator, points, privacy requests, moderation queues, legal, playback, following, step-up) | 12 | 401 on all |
| S2 Forged/malformed tokens (short, oversized, `alg: none` JWT, Basic) | 4 | 401 on all |
| S3 Internal and ops surfaces, path traversal (`/internal/*`, `/ops/verify`, `..`, `%2e%2e`) | 6 | 400/403/404 |
| S4 Anonymous writes (report, watch events, upload intent; like/follow PUT) | 5 | 401 (POST on like/follow refused by Nginx 403) |
| S5 Injection-shaped input in `q`, `category`, `cursor` and the video id path | 13 | No 5xx, no reflected markup; strict 400s |
| S6/S7 Headers and CSRF | 8 | API HSTS (`max-age=3600`), `nosniff`; console CSP `default-src 'none'`, `X-Frame-Options: DENY`, HSTS 30 days, `csrftoken` Secure+HttpOnly, CSRF-less POST 403 |
| S8 Console pages anonymously (`/admin/`, points, audit, team, privacy requests, business, creators) | 7 | 302 to `/login/` (429 after a short burst: throttling active) |
| S9 No public user web surface on the console host | 4 | 404 |
| S10 20-request feed burst | 1 | 20×200, no 5xx |
| S11 TLS | 1 | TLS 1.2 negotiated at the Cloudflare edge |

### 4.2 Staging, read-only infrastructure and data checks

| Check | Result |
| --- | --- |
| D11-002 append-only guard on staging | **PASS.** Every `_app` login is a member only of its `_rt` role; all objects are owned by NOLOGIN owner roles (the 23 November finding of 26 runtime-owned tables is gone); `_app` has no TRIGGER, TRUNCATE or schema CREATE on the Points ledger, Audit store or Identity security events; no `kolovibe_*` role is superuser, CREATEROLE, CREATEDB or BYPASSRLS |
| Audit delivery backlog | Identity 320/320 and Moderation 135/135 delivered. **Points 11 of 11 never delivered** (D13-001). **Content 6 of 6 never delivered** (D13-002). Creators 0 events |
| Event outboxes | Identity 0, Content 0, Engagement 1 (published) |
| Media pipeline evidence | 4 published videos (3 public, 1 private) exist from earlier UAT, so upload → R2 → FFmpeg → publish has worked before. **1 video stuck in `processing` since 21 November** with its source uploaded and no lease (D13-007) |
| D12-001 client-address trust | **Not deployed:** live Nginx has no `set_real_ip_from`/`real_ip_header`, and the Gateway has no `KOLOVIBE_TRUSTED_CLIENT_IP_HEADER`, so per-client limits see one shared address |
| Capability flags (live) | Gateway: accounts, privileged, creator onboarding, `account_management,analytics,audit_read,engagement,media,moderation,points,watch`. No Business capability |

### 4.3 Local (disposable stack, `main` at `68d8df6`)

| Suite | Result |
| --- | --- |
| `scripts/verify_local_journeys.py` (real HTTP through the Gateway, mail, console) | 11 of 11 OK |
| `scripts/verify_event_pipeline.py` | 8 of 8 OK |
| `verify_staging_runtime` (eight staging profiles, TLS, MFA, signed audit retry, refresh/revocation, key rotation) | PASS |
| Cluster tool suites (7 modules) | OK |
| `flutter analyze` (Flutter 3.50.1) | 94 infos (`deprecated_member_use`), 0 errors or warnings |
| `flutter test` | **BLOCKED** after 872 passing tests: the workstation disk filled (`No space left on device`, 1.6 GiB free of 233 GiB). Not an application defect |
| CI on the #269 head (manual run [45863618946](https://github.com/Markcino/KoloVibe/actions/runs/45863618946)) | Django services, security scans, all image builds and scans: success. Flutter: failure (D13-006) |

### 4.4 Not executed, and why

| Area | Reason |
| --- | --- |
| Authenticated staging journeys (registration, login, upload, playback, likes, points, reports, appeals, privacy, console MFA) | Registration needs a real inbox (codes are stored only as keyed hashes) and `mobile-api.cabetechs.shop` is not a test-labelled hostname, so this session may not submit credentials to it. Needs owner-supplied test accounts run by the owner, or a test-labelled hostname |
| Physical iPhone/Android, simulator against staging | Not run. The 26 November simulator run (local stack) remains the latest app evidence |
| Figma comparison | The Figma connector is not authorized in this session |
| Load, failover, restore | Out of scope for a non-disruptive run; restore drill is #144 |
| Business, Events, Advertising, Finance on staging | Not deployed (Business) or not implemented (others) |

## 5. Defects and gaps found (new IDs continue the Phase 12 register)

| ID | Sev. | Title | Root cause | Status | Issue |
| --- | --- | --- | --- | --- | --- |
| D13-001 | P1 | Points audit events never reach Audit | **Confirmed:** Points signs with `kolovibe_points_outbound_key_r1_v1`; Audit's caller map (`kolovibe_audit_callers_auditread_20261122_v1`, rotated 22 November) holds a different key for `points` (fingerprints differ). A diagnostic signed request returns Audit's middleware 403; Audit logs nothing | OPEN, owner secret action | [#271](https://github.com/Markcino/KoloVibe/issues/271) |
| D13-002 | P1 | Content and Creators audit delivery cannot run on staging | **Confirmed:** `staging_runtime/roles.py` has no `deliver-audit` role for content or creators, `staging-aws.yml` has no job, and Audit's caller map has no `content`/`creators` entry | OPEN (updates D11-007) | [#272](https://github.com/Markcino/KoloVibe/issues/272) |
| D13-003 | P1 | Account erasure pipeline (Decision C) cannot run on staging | **Confirmed:** the Identity, Content, Creators and Business event dispatchers and consumers have no runtime role, stack entry, broker user or queue. Requests are recorded but never processed. Matches the plan's "broker plan must be approved and applied first" | OPEN, needs approval | [#273](https://github.com/Markcino/KoloVibe/issues/273) |
| D13-004 | P2 | VM2 has no CPU reservation headroom | **Confirmed:** reservations total 2000m of 2000m (memory 2.3 of 3.8 GiB). No extra task (migration job, Business, erasure or maintenance workers) can be scheduled without stopping a service; the v0.531.1 rollout scaled the stack to zero | OPEN, capacity decision | [#274](https://github.com/Markcino/KoloVibe/issues/274) |
| D13-005 | P2 | Release rolled out outside the reviewed tool with stale labels | **Confirmed:** v0.531.1 services keep v0.341.1 labels; the jobs stack label still names v0.205.1 | Tool unblocked by #269/#270; process OPEN | #269 |
| D13-006 | P1 | `main` cannot publish a release: Flutter CI fails | **Confirmed:** `d9993ea` regenerated `apps/mobile/pubspec.lock` with Flutter 3.50.1; CI pins 3.47.8, whose SDK pins `test_api` 0.7.12, so `pub get --enforce-lockfile` fails. The publish job needs the Flutter job | **CLOSED** (27 Nov update): PR #277 merged; `main` CI run 45872265313 (`e82f43e`) passed, including publishing | [#275](https://github.com/Markcino/KoloVibe/issues/275) |
| D13-007 | P2 | Video stuck in `processing` since 21 November | **Under investigation:** source uploaded, no lease, no requeue job running (`content-requeue` is off pending O-12). Next step: read the media worker's history for that job id and run the documented requeue command once | OPEN | [#149](https://github.com/Markcino/KoloVibe/issues/149) |
| D12-001 | P2 | Per-client limits inert | Repository fix not deployed on staging (section 4.2) | OPEN on staging | [#151](https://github.com/Markcino/KoloVibe/issues/151) |
| D11-002 | — | Runtime logins could disable append-only guards | Verified fixed on staging (section 4.2) | **Verified on staging** | [#146](https://github.com/Markcino/KoloVibe/issues/146) |

| Gap | Classification |
| --- | --- |
| G-01 Business on staging | IMPLEMENTED BUT UNVERIFIED (not in the release manifest; no schema, role, secrets, capability or rollout approval DR-BZ-32) |
| G-02 Static policies and deletion-request page | IMPLEMENTED BUT UNVERIFIED, not hosted (`apps/policies/README.md`: hosting is an owner decision); blocks Android distribution |
| G-03 Maintenance jobs `identity-purge`, `content-requeue` | APPROVED DEFERRED (O-12), also blocked by D13-004 |
| G-04 Dead-letter handling (RV2-03) | NOT IMPLEMENTED (no DLQ policy on the broker) |
| G-05 Finance (J), Events (H), Advertising (I) | NOT IMPLEMENTED |
| G-06 Monitoring and alerting | NOT IMPLEMENTED (health endpoints only; #145) |

## 6. Verdicts

| Area | Verdict | Basis |
| --- | --- | --- |
| Infrastructure readiness | **FAIL** | Healthy and private, but no CPU headroom (D13-004), no backup/restore drill, no alerting |
| Deployment readiness | **BLOCKED** at the time of writing (superseded: v0.542.1 was deployed at 17:55 UTC, see the update below) | Images verified and migrations applied; service rollout waits for the operator's registry token |
| Backend readiness | **FAIL** | D13-001, D13-002, D13-003 |
| Flutter readiness | **NOT TESTED** on staging; local run blocked by disk; CI broken (D13-006) |
| Administration dashboard readiness | **NOT TESTED** beyond anonymous redirect, CSRF and header checks |
| Database readiness | **PASS** for privilege separation and migration state; restore untested |
| Security readiness | **FAIL** | 63/63 edge probes pass, but D12-001 is undeployed and authenticated negative tests are not run |
| Development completeness | **FAIL** | Phase 09 gate not passed; G-01 to G-06 |
| Staging acceptance | **NOT TESTED** | Authenticated journeys not executed |
| Production readiness | **FAIL — NO-GO** | |

## Update, 27 November 2026 (records correction; no new staging commands)

This section corrects the record above from later evidence. Nothing was run on staging for it. The superseded lines are kept and marked.

- **v0.542.1 is deployed.** According to the owner's update on #169 (26 November, 17:55 UTC), v0.542.1 (`38d0380`, CI run 542) runs on all 16 staging application services:
  - the 8 APIs, through the reviewed cluster tool;
  - the 6 jobs, the media worker and the web console, by pinned digest.

  The update reports 63/63 edge probes, public smoke 7/7, queue consumers back, no error logs and no failed tasks. The registry-token blocker and "service rollout pending" no longer apply.
- **D13-006 / #275 is closed.** PR #277 merged, and `main` CI run [45872265313](https://github.com/Markcino/KoloVibe/actions/runs/45872265313) at `e82f43e` passed all jobs, including publishing. It is no longer an active blocker.
- **Unchanged:**
  - D13-001 (#271): Points audit still undelivered. The correction plan is `R1_Points_Audit_Key_Correction_Plan_2026-11-27.md` and waits on the owner.
  - D13-002 and D13-003.
  - D13-004 (#274): the capacity report and budget proposal are in `R1_Staging_CPU_Budget_Proposal_2026-11-27.md` and wait on the owner.
  - D13-005: release labels and proof after the rollout outside the tool; to be reconciled.
  - Production stays **NO-GO**.
- **Not re-verified here:** the 26 November 17:55 UTC deployment readback. It is reported on #169 and not repeated in this session.
