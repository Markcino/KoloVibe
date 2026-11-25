# Phase 11 — infrastructure assessment

**Date:** 25 November 2026. **Scope honesty:** everything below is the **repository's** infrastructure design exercised on a disposable local host (PostgreSQL 16 with TLS, RabbitMQ 3.12.1 with TLS, FFmpeg, Chromium) plus a static review of the repository's deployment files. **Nothing on AWS, Cloudflare, Swarm or any image was tested.** Those items are BLOCKED or NOT RUN in the [matrix](Phase11_Test_Matrix.md).

## 1. Summary

| Area | Result |
| --- | --- |
| Database isolation and TLS | **Sound** across services; **database ownership is not** (D11-002, R-01) |
| Backup and restore | **Drill passed on the fixture** (all tables, all rows, all triggers); **none exists or has been tested on any real system** |
| Migrations | Apply cleanly on a fresh database, idempotent, and the latest migrations of three services reverse and re-apply |
| RabbitMQ | Durable, survives restart and outage, recovers from a killed consumer, least-privilege accounts work; **one poison message permanently stops the consumer** (D11-001); **no dead-letter queue** |
| Workers and jobs | Seven roles with bounded limits (static); process-level restart verified on the Points worker; Swarm restart policy NOT RUN |
| Resource limits | Declared for every worker and job (static); runtime enforcement NOT RUN; **AWS capacity unrecorded** |
| HTTPS and proxy | Repository Nginx is hardened but has **no rate limiting**; live edge BLOCKED |
| Logging and alerting | Logs carry no secrets (tested); **alerting and monitoring: NOT RUN** (no stack) |
| Image vulnerability scans | **BLOCKED** (no Docker daemon, no images, no scanner) |

## 2. Detail

### 2.1 Database (T10_01 to T10_06, T10_30, T10_31)

- **Isolation holds:** 56 cross-service read attempts (each of the eight database-backed service logins against every other service's first table) were all refused; a service login cannot read `pg_authid`, run `COPY ... PROGRAM`, read files, create extensions, roles, schemas or public tables, or alter system settings.
- **TLS is enforced:** plaintext, wrong host name and a wrong password are all refused; the service password files are mode `0600` and no password appears in any process command line.
- **Ownership is wrong (D11-002):** the schema script creates each service schema `AUTHORIZATION kolovibe_<service>`, and each login is a member of that role, so the login inherits ownership of its tables (117 of 117). A service credential can therefore drop or disable the very triggers that make its ledger append-only.
- **Backup and restore drill:** `pg_dump -Fc`, then `pg_restore` into a new database, compared **row counts for every table** (the database held over 50 rows of real test data) and **trigger counts**, then proved the append-only guard still blocks an `UPDATE` after restore. It completed in about a second at this size. This proves the *procedure and the guards survive a restore*; it says nothing about retention, off-host copies, encryption of backups, point-in-time recovery or restore time at production size, none of which exist or were tested.
- **Migrations:** a second `migrate` is a no-op for all eight services; `engagement` (0006 to 0005), `business` (0007 to 0006) and `creators` (0006 to 0005) reverse and re-apply without error.

### 2.2 RabbitMQ (T3_22, T3_30 to T3_35, Phase 10 permission tests re-run in the baseline)

| Behaviour | Result |
| --- | --- |
| Duplicate delivery of the same event | One ledger entry (T3_22) |
| Broker stopped while an event is published | Dispatch fails loudly, the event stays in the outbox, and one award follows recovery (T3_30) |
| Consumer killed with `kill -9` | The message waits in the durable queue; a restarted worker processes it exactly once (T3_31) |
| Broker application restarted with a queued message | The persistent message survives (T3_32) |
| Garbage that is not a Celery task | Discarded; the worker and the next real event are unaffected (T3_33) |
| **Malformed task envelope** (`task` header with a list or dict body) | **The worker dies with `KeyError('id')` and dies again on every restart** until the queue is purged (T3_35, D11-001). There is **no dead-letter queue**, so nothing catches it |
| Least-privilege accounts (from the generator's table) | Engagement can write only to the Points exchange; Points and Content cannot reach each other's queues (baseline real-broker pipeline, 6 of 6) |
| Not run | Sustained load, many-message backlogs, network partition, broker memory or disk alarm behaviour, cluster failover (single node only) |

### 2.3 Workers, jobs and resource limits

Static review of `infra/swarm/staging-aws.yml` and `staging_runtime/roles.py`: every worker and job declares memory limits of **160 to 512 MiB** and CPU limits of **0.5 to 1.0**, runs read-only as user `10001` with all capabilities dropped; the Celery worker is limited to one task at a time, recycled after 20 tasks or 256 MiB, with remote control off; job loops are bounded (5 to 3600 s, 1 to 1000 items) and exit after five consecutive failures so Swarm restarts them. On the local host each service process used roughly **90 to 105 MiB**, well inside those limits. **NOT RUN:** Swarm enforcement, restart policy, and out-of-memory behaviour. **The AWS instance size is not recorded anywhere in the repository and capacity has never been measured.**

### 2.4 HTTPS, proxy and edge

Static review (T10_80 to T10_82): Nginx hides its version, allows TLS 1.2 and 1.3 only, caps request bodies at 8 KiB (gateway) and 16 KiB (console), and **clears** `X-Forwarded-For`, `Forwarded` and the caller and signature headers before proxying; the applications set HSTS (console 30 days, services one hour) and secure host-prefixed cookies in staging. **No `limit_req` or `limit_conn` exists in the repository's Nginx configuration** (T10_81): ADR-013 expected edge limits "tuned against Cloudflare, host Nginx and application behavior", and registration has no application limit either (D11-004). Cloudflare rules are outside the repository and were not seen. **Live TLS, certificates and the deployed edge: BLOCKED.**

### 2.5 Burst behaviour (T10_23)

400 public discovery reads, 32 concurrent: **no 5xx, no throttling**, median 13 ms, 95th percentile about 1 s (single-threaded development server; not representative of Gunicorn). Public reads have no application-level rate limit.

### 2.6 Logging and alerting

Logs: no secret appears in any service log (T10_90), and query strings are not echoed (T10_91). Gunicorn is configured with `accesslog = None` and error output to stderr. **Alerting, dashboards and log shipping: NOT RUN** (none are in the repository to test; the Phase 0 gap list already records this).

### 2.7 Supply chain and images

`pip-audit` on all four Python lock files: **0 vulnerable**. Bandit **0 medium or high** at the final commit. **BLOCKED:** Flutter package advisories (the OSV host is denied by this environment), container image scans (no daemon, no images).

## 3. What a staging run must add

Read back the live database ownership; read back the deployed broker permissions and configure a dead-letter queue; run a real backup and restore of the staging database; confirm Swarm limits and restart behaviour; measure capacity on the AWS instance; verify the Cloudflare and Nginx rate limits; scan the built images; and run the device tests.
