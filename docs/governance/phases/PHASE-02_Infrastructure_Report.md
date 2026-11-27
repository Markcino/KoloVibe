# Phase 2 report: infrastructure and deployment remediation

| Item | Value |
| --- | --- |
| Phase | 2, Infrastructure and deployment remediation |
| Instruction | Owner's Phase 2 message, 27 November 2026, 11:40 UTC |
| Entry condition | The instruction says to verify that Phase 1 passed first. **It has not:** the Phase 1 verdict is BLOCKED on #307 (requirement sets for notifications, payments, Google mobile ads, distribution and comments). #307 touches no infrastructure, so only read-only work, measurement and repository changes were done, and the owner is asked to rule on the entry condition (section 9) |
| Starting commit | `main` at `cf88dad` |
| Final commit | The head of the pull request that adds this report (branch `claude/project-thread-e57yvk`) |
| **Gate verdict** | **BLOCKED.** Nothing was changed on staging. Six of the nine exit criteria need owner-approved staging changes (plans A to F, section 8), and the capacity criterion also needs the 24-hour measurement, which ends at about **11:58 UTC on 28 November** |
| Next phase authorized | No. Phase 3 does not start until Phase 2 passes |

All runtime facts below were read between 11:42 and 12:05 UTC on 27 November over `ssh swarm-manager` (VM1) and `ssh swarm-worker` (VM2) from the owner's Mac. No secret value was read or printed: secrets, configs and environment were counted or named, never shown. Supporting record: [read-only check](../../operations/R1_AWS_Staging_Readonly_Check_2026-11-27.md).

## 1. Task 1: actual infrastructure state

| Area | State |
| --- | --- |
| Instances | VM1 **t3.small** (2 vCPU burstable, 1.9 GiB), VM2 **c7i-flex.large** (2 vCPU, 3.8 GiB), both us-east-1a, Ubuntu 24.04.5, Docker 29.9.3 |
| Load, memory, disk | Load 0.00 on both. Available memory VM1 1.27 GiB, VM2 1.86 GiB. Disk VM1 24% of 19 GiB, VM2 61% of 29 GiB |
| Network | All traffic through Cloudflare Tunnel; network bytes per minute are part of the 24-hour measurement |
| Swarm | 1 manager (VM1, Leader, `Drain`), 1 worker (VM2, `Active`). Every service is pinned to VM2 by `node.hostname` |
| Services | 19 long-running services at 1/1, plus `kolovibe-r1-jobs_media-worker` at 0/0 (defined at zero replicas in `infra/swarm/staging-aws.yml`; the standalone `kolovibe-media-worker` runs instead) and 9 completed one-shot migration jobs |
| Reservations and limits | VM2 CPU **2000m of 2000m reserved** (APIs and most jobs 100m, PostgreSQL and RabbitMQ 250m, identity-audit and web 0m). Memory 2304 of 3812 MiB reserved. Limits: APIs 1.0 CPU / 256 MiB, jobs 0.5 CPU / 160–384 MiB, media worker 1.0 CPU / 768 MiB, PostgreSQL and RabbitMQ 1.0 CPU / 768 MiB |
| Measured use (one sample) | Every container 0.00–0.16% CPU; container memory about 1.3 GiB in total |
| Hardening per service | Every application service runs as `10001:10001` with a read-only root filesystem, `stop-first` updates with automatic rollback on failure, and a rollback config. The 8 APIs have a Swarm health check; the web console's comes from its image |
| Overlay networks | `kolovibe_services`, `kolovibe_data`, `kolovibe_messaging`, `kolovibe_r2_proxy_clients` are **internal**; `kolovibe_identity_smtp_egress` and `kolovibe_r2_proxy_outbound` are the only egress networks. None is encrypted; acceptable while every task runs on VM2 only, to revisit before any second worker |
| Network isolation | PostgreSQL is only on `kolovibe_data`, RabbitMQ only on `kolovibe_messaging`. Only Content, Engagement, Points, the media worker and their jobs join `kolovibe_messaging`. Only Identity joins the SMTP egress network. Only Content and the media worker reach the R2 proxy |
| PostgreSQL | 17.11; TLS on (minimum TLS 1.2); `pg_hba` rejects every non-TLS network connection and requires SCRAM-SHA-256; 9 schemas, no `business`. No `kolovibe*` role is superuser, CREATEROLE, CREATEDB or BYPASSRLS |
| RabbitMQ | 4.4.0, AMQPS-only on 5671, no alarms (section 4) |
| Nginx (VM1) | Host service, listens on **127.0.0.1:80 only**; `nginx -t` passes. Upstreams are Unix sockets served by the `kolovibe-gateway-bridge` HAProxy container (image pinned by digest, outside Swarm, `unless-stopped`, read-only, non-root). Upstream TLS is verified against the private CA with a fixed server name |
| Cloudflare Tunnel | `cloudflared` active on VM1, token read from a root-only file, metrics on 127.0.0.1, `/ready` returns 200. Hostnames: `kolovibe.cabetechs.shop` (console), `api.cabetechs.shop` (behind Cloudflare Access), `mobile-api.cabetechs.shop` (route allow-list) |
| R2 | From the media worker, through the egress proxy, an unauthenticated request to the account's R2 endpoint reaches R2 (HTTP 400). The proxy refuses any other destination (`example.com` blocked). No object was read or written |
| Swarm secrets and configs | 108 secrets and 3 configs exist; each service references 0 to 14 secrets by name (counts in the [read-only check](../../operations/R1_AWS_Staging_Readonly_Check_2026-11-27.md)). Values were not read |
| Running image digests | Every running service runs the v0.542.1 digests (services `ab9c0e0d…`, media `247b7dfb…`, web `d94fd230…`), proven by the reviewed `release-readback` |
| Migration versions | identity `0016` (`main` has `0018`); content `0013`, creators `0009`, points `0006`, moderation `0009`, engagement `0006`, audit `0006`, all equal to `main` |
| Background workers | Running: engagement consumer and dispatch, identity, moderation and points audit delivery, points consumer, media worker. **`points-audit` exits and restarts about hourly** (D13-001). Not deployed: the 12 processes in `staging-aws.yml` at zero replicas (content and creators audit delivery, erasure dispatchers and consumers, requeue, purge) |
| Deployment provenance | v0.542.1, source `38d0380`; `main` is 69 commits ahead (CI green on `cf88dad`) |
| Host firewall and SSH | `ufw` inactive and `iptables` INPUT policy ACCEPT on both VMs, so exposure rests on the AWS security group. From outside, VM1 answers on **port 22 only** (80, 443, 2377, 5432, 5671, 7946, 8080 and 15672 closed); VM2 has no public address. SSH: password and keyboard-interactive login off, root login by key only. The security group itself could not be read (no AWS credentials in this session) |

## 2. Task 2: capacity (#274)

**Measurement:** started at 11:58 UTC on 27 November, read-only, from the owner's Mac. Every 60 seconds it records `docker stats` for every VM2 container and host CPU, load and network counters on both VMs. Nothing is written on staging. It ends at about 11:58 UTC on 28 November. Gaps (for example if the Mac sleeps) will be reported, not filled in.

**Interim fit (reservations, not use):**

| | CPU | Memory |
| --- | --- | --- |
| VM2 allocatable | 2000m | 3812 MiB |
| Reserved today | 2000m (0 free) | 2304 MiB |
| With the [budget proposal](../../operations/R1_Staging_CPU_Budget_Proposal_2026-11-27.md) and everything already approved but not deployed (Business API, audit delivery, erasure processes) | 1475m (525m free) | about 3360 MiB (about 450 MiB free) |
| Plus Finance, Events and Advertising (GD-01 to GD-03) with one API and two workers each, at today's sizes | about 1775m (about 225m free, under the 500m margin) | about 4130 MiB, **over capacity** |

So with the current reservations, VM2 can hold today's stack plus the approved additions **only if CPU reservations are lowered**, and it **cannot** hold the full application on memory. That is the recommendation to decide after the measurement:

| Option | Change | Approximate on-demand cost, us-east-1 (to confirm in the AWS console before approval) |
| --- | --- | --- |
| 1, right-size only | Lower CPU reservations per the budget proposal and memory reservations to measured p95 plus 25% | No change (about $62 a month for VM2 today) |
| 2, recommended if p95 confirms the current picture | Option 1, plus resize VM2 to **m7i-flex.large** (2 vCPU, 8 GiB) when Finance, Events or Advertising are deployed | About $70 a month (about +$8) |
| 3 | Resize VM2 to c7i-flex.xlarge (4 vCPU, 8 GiB) | About $124 a month (about +$62) |

VM1 (t3.small, burstable) runs only Nginx, `cloudflared`, HAProxy and the Swarm manager; its CPU credit use is in the measurement. Resizing is a stop-and-start of the instance with a staging outage, so it needs its own approved window and spending ceiling. **Nothing is purchased or resized.**

## 3. Task 3: deployment reconciliation (D13-005)

| Item | State |
| --- | --- |
| Running services vs v0.542.1 publication | **PASS**: digest and `kolovibe.source-revision` label on all 16 running project services (8 APIs, 6 jobs, media worker, web) |
| Stale objects | 9 completed one-shot migration jobs from v0.346.1 to v0.542.1 stay listed. They run nothing, but make the readback exit 2. `kolovibe-r1-jobs_media-worker` (0/0) still names an older media digest; the next stack deploy updates it |
| Live config drift | The **live VM1 Nginx file is not in the repository**: the repository has only an `api` template and a console vhost, while the live file also serves `mobile-api` with 40 route rules. Fixed on the repository side by this change (section 5) |
| Running release vs `main` | 69 commits behind. Needs a reviewed release (plan D): publish from `main`, apply Identity `0017` and `0018` through the reviewed migration jobs, roll out with the cluster tool, finish with `release-readback` |
| Guards | Not bypassed. The rollout path is the cluster tool's `update-plan` and `update`, which needs the operator's registry token at a hidden prompt |

**D13-005: can close for v0.542.1** (every running service proven). The process fix (every rollout ends with a passing readback) stays.

## 4. Task 4: RabbitMQ and workers

| Control | State |
| --- | --- |
| Virtual host | One, `/kolovibe`; no `guest` user |
| Users and permissions | `kolovibe_content_r1`, `kolovibe_points_r1`, `kolovibe_engagement_r1` are scoped by regular expression to their own exchange and queue names (Engagement may also write to Points, as the points flow needs). **`kolovibe_celery` has `.*` configure, write and read on the whole vhost** and has no connection; it is a leftover and should be removed (plan C) |
| Queue ownership and durability | `kolovibe.points`, `kolovibe.engagement`, `kolovibe.content.media`: durable classic queues, each bound to its own durable direct exchange, 0 messages, 1 consumer |
| Publisher confirms | `confirm_publish` on in every publisher (Identity, Content media, Creators, Moderation, Engagement, Points, Business); messages persistent (`delivery_mode=2`); outboxes mark rows published only after the broker accepts |
| Consumer acknowledgement | Manual acks, prefetch 1, `acks_late` and `reject_on_worker_lost` on every consumer |
| Retry | Publish retry 3 times; consumer tasks retry on database errors with backoff (10 times; Points without a limit); inbox table makes processing idempotent |
| Dead-letter and replay | **Missing.** No policy, no dead-letter exchange or queue, so a message rejected after its retries is dropped. Repository work is #311 (Phase 3) |
| Backlog monitoring | Missing (no alerting, #145; alert thresholds and channel are owner decision OD-08) |
| Worker scheduling | Blocked by CPU (section 2) |

Nothing was activated for modules that are not built. The broker plan for erasure queues and users (D13-003) and the dead-letter policy wait on plan C.

## 5. Task 5: ingress and network security (#151, #325)

| Check | Result |
| --- | --- |
| Private exposure | PASS: only SSH is public; Nginx on loopback; PostgreSQL and RabbitMQ on internal overlays only |
| TLS | PASS: TLS at Cloudflare; Tunnel to loopback Nginx; Nginx to Gateway and web over verified TLS; PostgreSQL TLS-only; RabbitMQ AMQPS-only |
| Internal service authentication | Enforced: Audit refuses Points' signed requests because the keys differ (that is D13-001, a rotation decision, PR #281) |
| Anonymous probes | PASS: protected routes 401, forged token 401, `/internal/` and `/ops/` 403, console-only route 404 on the mobile host, console 302 to login, CSP and frame headers present. All `mobile-api` replies, 401 included, carry HSTS and `nosniff` |
| **Rate limits and trusted client address (D12-001)** | **FAIL on staging:** the live Nginx has no `limit_req`, `limit_conn`, `set_real_ip_from` or `real_ip_header`; the Gateway has no `KOLOVIBE_TRUSTED_CLIENT_IP_HEADER` |
| Firewall | Host firewall off; relies on the AWS security group, which could not be read |

**Repository fix in this change:** [`infra/nginx/vm1-kolovibe-staging.conf`](../../../infra/nginx/vm1-kolovibe-staging.conf) is the complete live VM1 file (captured read-only, SHA-256 `462f35fc…01e2e3`) with the D12-001 controls added to all three vhosts: one shared 10 r/s zone (burst 40 for the console, 20 for the APIs), 20 connections per client, `429` answers, `CF-Connecting-IP` believed only from 127.0.0.1 and then overwritten, and `X-Forwarded-For`, `X-Real-IP` and `True-Client-IP` cleared. Nothing else changes. **It passes `nginx -t` with VM1's own Nginx and certificate paths** (checked from a root-only temporary file in `/dev/shm`, deleted at once; the live file was not touched). `scripts/test_edge_client_origin.py` now also checks this file.

## 6. Task 6: deployment and rollback verification

**NOT RUN.** A controlled deployment and a rollback drill both change staging, so they wait for plan D and plan F.

## 7. Exit gate

| Criterion | Result | Basis |
| --- | --- | --- |
| Capacity measured and adequate, or an approved plan implemented | **BLOCKED** | Measurement ends 28 Nov about 11:58 UTC; reservations full today; plan A |
| All existing required services healthy | **FAIL** | `points-audit` restarts hourly and delivers 0 of 11 (D13-001); Content audit 0 of 6 (D13-002). Everything else is up |
| Deployment provenance matches running images | **PASS** | `release-readback`, all running services |
| Migration jobs can execute safely | **FAIL** | A 100m job cannot be scheduled (capacity check FAIL); the v0.542.1 jobs only ran with a zero CPU reservation |
| RabbitMQ correctly isolated and configured | **FAIL** | Over-broad `kolovibe_celery` user; no dead-letter handling |
| Ingress and rate limiting verified | **FAIL** | No rate limits live; candidate ready (plan E) |
| Deployment and rollback demonstrated | **NOT RUN** | Plans D and F |
| No unresolved mandatory infrastructure blocker | **FAIL** | D13-001 to D13-004, D12-001 |
| Documentation and GitHub issues updated | **PASS (on merge)** | This report, the read-only record, issue comments |

Counts: 1 PASS, 1 PASS on merge, 5 FAIL, 1 BLOCKED, 1 NOT RUN.

## 8. Change plans that need the owner's yes

Each plan writes to staging, so none has been run. Each is small, ordered, reversible and checked by a readback.

| Plan | What | Rollback | Needs |
| --- | --- | --- | --- |
| **A. Capacity** | After the measurement: set reservations by the budget-proposal rule (p95 rounded up to 25m, at least 500m free), stack jobs through a reviewed `staging-aws.yml` PR and `docker stack deploy`, the 8 APIs one at a time with `docker service update --reserve-cpu`; then `capacity` must PASS and a 100m job must complete | Previous reservations, recorded from the readback | Measurement result, then a yes. A resize (section 2, option 2 or 3) needs a separate yes with a spending ceiling and an outage window |
| **B. Stale jobs** | `docker service rm` the 9 completed migration jobs, after saving each `docker service inspect` to a root-only folder on VM1 | Re-create from the saved spec (they are finished jobs; nothing depends on them) | Yes |
| **C. Broker** | Remove the unused `kolovibe_celery` user. Later, with #311's code, add the dead-letter exchange, queues and policy, and the erasure users and queues for D13-003 | Re-add the user from the definitions export taken first | Yes for the removal; the rest after #311 and the D13-003 plan |
| **D. Release from `main`** | Publish from `main`, run `update-plan`, apply Identity `0017` and `0018` through reviewed migration jobs, roll out the APIs with the cluster tool (`stop-first`, automatic rollback), then jobs, media and web by digest, then `release-readback` must exit 0. Includes the Gateway's `KOLOVIBE_TRUSTED_CLIENT_IP_HEADER` through the reviewed R1 rollout table | The tool's recorded rollback file and `rollback` mode; migrations are additive | Yes, plus the operator's registry token typed at the hidden prompt. Plan A first, so the migration jobs can schedule |
| **E. Ingress** | Back up the live file, install `infra/nginx/vm1-kolovibe-staging.conf`, `nginx -t`, `systemctl reload nginx`, then probe: normal requests 200 or 401, a burst gets 429, the Gateway sees the caller's address. Only after D adds the Gateway header setting | Restore the backup and reload (seconds; reload keeps connections) | Yes. The 10 r/s figure is a first value to confirm |
| **F. Rollback drill** | As part of D, roll one API back to v0.542.1 with the tool's `rollback` mode, confirm health and readback, then forward again | It is the rollback | Yes, inside D's window |
| **G. Points audit key (D13-001)** | PR #281's rotation | As in #281 | The owner's choice in #281 |

## 9. Outstanding decisions

1. **Entry condition:** Phase 1 is BLOCKED on #307 only, which touches no infrastructure. Proceed with Phase 2 staging changes before #307 closes, or wait?
2. Plans A to G above.
3. Already pending: Points to Audit key rotation (PR #281); alert thresholds and channel (OD-08); mTLS versus per-caller keys (#138).

## 10. Defects and next-phase prerequisites

Open: D13-001 (P1, #271), D13-002 (P1, #272), D13-003 (P1, #273), D13-004 (P2, #274), D12-001 (P2, #325, #151), no dead-letter handling (#311), no alerting (#145), host firewall off with the security group unread (new, P3), `kolovibe_celery` over-broad (new, P3). Closed for v0.542.1: D13-005. No longer stuck: D13-007's video (soft-deleted; #149 reconciliation still missing).

Phase 3 prerequisites: this gate passes, which needs the measurement, plans A to F applied and verified, and D13-001 resolved.
