# AWS staging read-only check, 27 November 2026

**Status: RUN, READ-ONLY.** This closes the "runtime staging check" that the Phase 1 report left BLOCKED because the owner's computer was offline. It was run from the owner's Mac over `ssh swarm-manager` (VM1) and `ssh swarm-worker` (VM2) between 11:42 and 11:55 UTC, at `main` `cf88dad`. Nothing on staging was changed: no deploy, no service update, no label change, no secret read, no broker or database write. No file was copied to either VM (the cluster tool was streamed to `python3 -` on stdin). SQL ran inside `BEGIN TRANSACTION READ ONLY … ROLLBACK`.

Raw evidence (names, digests, labels and counts only; no secrets): [VM2 capacity](../evidence/staging-readonly-2026-11-27/capacity-vm2.json). The full release-readback JSON is in the pull request that added this record; it is not committed because its 40-hex `revision` fields are blocking findings for the repository secret scan, and widening that scan's allowlist for a record is not worth it.

## 1. Hosts

| Check | Result |
| --- | --- |
| SSH and sudo | Both VMs reachable as `ubuntu`, passwordless sudo |
| OS, Docker | Ubuntu 24.04.5 LTS, Docker 29.9.3 on both; Swarm 1 manager (VM1, `Drain`, Leader), 1 worker (VM2, `Active`) |
| Uptime and load | VM1 18 d, load 0.00; VM2 18 d, load 0.00 |
| Memory | VM1 1.9 GiB, 1.27 GiB available. VM2 3.8 GiB, 1.86 GiB available |
| Disk | VM1 24% of 19 GiB. VM2 61% of 29 GiB |
| Point-in-time CPU (`docker stats`, one sample) | Every container 0.00–0.16%. This is one sample, **not** the 24-hour measurement proposed in #283, which is still not approved or run |

## 2. Release provenance (D13-005)

The reviewed `release-readback` mode ([#287](https://github.com/Markcino/KoloVibe/pull/287)) ran on VM1 as root against the v0.542.1 publication (run 542, source `38d0380`). It exited 2 because it also checks finished one-shot jobs and a zero-replica service.

| Group | Result |
| --- | --- |
| 8 APIs (audit, content, creators, engagement, gateway, identity, moderation, points) | **PASS**: published services digest `sha256:ab9c0e0d…` and `kolovibe.source-revision` = `38d0380…` |
| 6 running jobs (engagement consumer and dispatch, identity, moderation and points audit, points consumer) | **PASS**, digest and label |
| Media worker `kolovibe-media-worker` (1/1) | **PASS**, media digest `sha256:247b7dfb…` and label |
| Web console `kolovibe-web_web` (1/1) | **PASS**, web digest `sha256:d94fd230…` and label |
| v0.542.1 migration jobs (identity, content) | PASS (completed) |
| `kolovibe-r1-jobs_media-worker` | FAIL on digest and label, but it is at **0/0 replicas** (superseded by `kolovibe-media-worker`); runs nothing |
| 7 completed one-shot jobs from earlier releases (`*-migrate-0011-v03461`, five `v05311-migrate-*`, `web-migrate-v03061`) | FAIL on digest and label, all **0/1 (1/1 completed)**; they are history, not running code |

**Verdict: every running project service is proven to be v0.542.1 by the reviewed tool. D13-005 can close for v0.542.1.** The 8 FAIL rows are stale objects. Removing them (`docker service rm`) is a staging write and needs the owner's yes; a follow-up should also make the readback skip completed jobs and zero-replica services, so a clean cluster exits 0.

**Drift from `main`:** staging runs `38d0380`; `main` is at `cf88dad`, **69 commits** later (CI on `cf88dad` green, run 45991604706). Nothing after v0.542.1 is deployed.

## 3. Services and capacity

19 long-running services at 1/1, all on VM2. The 8 API containers and the web console report `healthy`; the jobs, media worker, PostgreSQL, RabbitMQ and R2 proxy have no health check.

| Check | Result |
| --- | --- |
| VM2 CPU reservations (D13-004, #274) | **2000m of 2000m reserved, 0 free. FAIL:** a 100m one-shot job cannot be scheduled. Unchanged since 26 November |
| VM2 memory reservations | 2304 of 3812 MiB reserved, 1508 MiB free |
| `points-audit` job | **Restarting hourly:** `non-zero exit (1)` at roughly 1, 2 and 3 hours before the check and again 7 minutes before; log says "Points audit delivery failed; evidence retained" (D13-001, #271) |

## 4. Database (PostgreSQL 17.11, database `kolovibe_staging`)

| Check | Result |
| --- | --- |
| Schemas | 9: `audit, content, creators, engagement, gateway, identity, moderation, points, web`. **No `business` schema** (G-01) |
| Latest applied migration vs `main` | identity `0016_erasure_creator_id` (main has `0018_access_exports`, so **0017 and 0018 are not applied**); content `0013`, creators `0009`, points `0006`, moderation `0009`, engagement `0006`, audit `0006`: all equal to `main` |
| Privileged roles | No `kolovibe*` role is superuser, CREATEROLE, CREATEDB or BYPASSRLS (D11-002 still holds) |
| Audit delivery | Identity 323 of 323 and Moderation 135 of 135 delivered. **Points 0 of 11** (D13-001). **Content 0 of 6** (D13-002). Creators 0 events |
| Event outboxes | All empty except Engagement 1, published |
| Erasure jobs | 0 recorded (D13-003 pipeline not on staging) |
| Videos | 3 published public. The video stuck in `processing` since 21 November (D13-007) and one private published video are now **soft-deleted**, so nothing is stuck. #149's stuck-job reconciliation is still not built |

## 5. Broker (RabbitMQ, vhost `/kolovibe`)

| Check | Result |
| --- | --- |
| Alarms | None |
| Queues | `kolovibe.points`, `kolovibe.content.media`, `kolovibe.engagement`: 0 messages, 1 consumer each |
| Policies | **None, so no dead-letter policy** (#311) |

## 6. Edge

| Check | Result |
| --- | --- |
| VM1 listeners | `sshd` 22 public; Nginx **127.0.0.1:80 only**; `cloudflared` active (metrics on 127.0.0.1); Docker Swarm ports on the private address. VM2 listens on 22 and 7946 only |
| Nginx config | `nginx -t` passes |
| Rate limits and client address (D12-001, #325) | **FAIL:** the live host Nginx has **no** `limit_req_zone`, `limit_req`, `set_real_ip_from` or `real_ip_header`, although both repository templates have `limit_req`. Gateway has no trusted-client-address setting |
| Gateway capability flags | `account_management, analytics, audit_read, engagement, media, moderation, points, watch`. No Business capability |
| Anonymous probes, `mobile-api` host | `/api/v1/creators/me` and `/creators/me/points` 401; forged `alg: none` token 401; `/internal/` and `/ops/verify` 403; console-only route `/api/v1/admin/moderation/assignments` 404 |
| `api` host | 401 at root (Cloudflare Access) |
| Console host | `/` and `/admin/` 302 to login, `/login/` 200; CSP `default-src 'none'`, `X-Frame-Options: DENY`, HSTS 30 days, `nosniff` |
| Security headers on `mobile-api` | 200, 401 and 404 responses all carry HSTS (`max-age=3600`), `nosniff`, `X-Frame-Options: DENY` and `Cache-Control: no-store`. (The `api` host's 401 is the Cloudflare Access page, which sets its own headers.) |

## 7. Findings

| ID | Sev. | Finding | State |
| --- | --- | --- | --- |
| D13-001 | P1 | Points audit delivery still fails (0 of 11), job restarts hourly | OPEN, owner's key-rotation choice (#281, #271) |
| D13-002 | P1 | Content audit delivery 0 of 6 | Fixed in repository (#292), not deployed (#272) |
| D13-003 | P1 | No erasure pipeline on staging | Fixed in repository (#294), not deployed (#273) |
| D13-004 | P2 | VM2 CPU 2000m of 2000m reserved | OPEN, capacity decision (#274, #283) |
| D13-005 | P2 | Stale labels | **Resolved for v0.542.1**: all running services pass the readback. 8 stale finished/zero-replica objects remain |
| D13-007 | P2 | Video stuck in processing | No longer stuck (soft-deleted); reconciliation still missing (#149) |
| D12-001 | P2 | Edge rate limits and client address absent on live Nginx | OPEN (#325, #151) |
| G-04 | — | No dead-letter policy | OPEN (#311) |
| ~~D14-001~~ | — | Withdrawn on recheck at 12:00 UTC: the first reading attributed the `api` host's header-less Cloudflare Access reply to `mobile-api`. Gateway 401s carry the headers | Not a defect |
| D14-002 | P3 | Identity migrations 0017 and 0018 are on `main` but not on staging | Expected (nothing after v0.542.1 is deployed); must be in the next release plan |

## 8. What this did not cover

Authenticated journeys (no test-labelled hostname, and no owner-supplied test accounts), device runs, backup and restore, load and failover, the 24-hour CPU measurement (#283, not approved), and Business, Events, Advertising and Finance (not deployed or not built).

## 9. Gate effect

The Phase 1 "runtime staging check" item moves from **BLOCKED** to **DONE (read-only)**. The Phase 1 verdict stays **BLOCKED** on the one remaining exit criterion, the unwritten requirement sets (#307). Staging itself is not accepted: D13-001 to D13-004 and D12-001 remain open, and production is NO-GO.

Any follow-up that writes to staging (removing stale services, label fixes, deploying anything after v0.542.1, Nginx rate limits, broker policies, resizing) needs a concrete plan and the owner's explicit yes first.
