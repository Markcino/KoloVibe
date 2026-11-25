# R1 maintenance commands: manual runbook (D11-009)

**Status: documentation, written 25 November 2026. Nothing here is scheduled and nothing was run.** Three Django management commands keep tables from growing without bound or recover work a lost message left behind. Two of them now have a **candidate** scheduled role in the Swarm stack at zero replicas (Phase 3 A5, 25 November 2026): `identity-purge` and `content-requeue` in `infra/swarm/staging-aws.yml`, which now declares nine worker and job processes. Neither runs until the owner approves the schedule (O-12) and scales it to 1. The console's `purge_expired_web_sessions` runs in the separate web image and stack and still has no role. Until O-12 is approved, the **documented manual run** below is the control. The tracker row "Scheduled maintenance commands: three unscheduled, one undocumented" is closed by this document only for the *documentation* half; the *scheduling* half stays open with the owner (see the release-readiness package).

## Rules that apply to all three

1. Run each as a **one-off container of the service's own image**, with that service's **runtime** credentials. They need only `SELECT`, `UPDATE` and `DELETE` on the service's own tables, which the runtime role has after the D11-002 ownership change. They need no owner or migration privilege; if one asks for it, stop and report.
2. Each command works in a **bounded batch** and is safe to repeat. Repeat until the first count is `0`.
3. Output is **counts only**. Nothing prints an identifier, token, code or address. Record the three counts, the time (UTC), the image digest and who ran it, in the change record. Do not paste logs that contain anything else.
4. Run outside a deployment, migration or restore window. Take no extra backup for these: they only delete rows that the service itself no longer consults (retention below).
5. A non-zero exit or a traceback is an incident for the owner; do not retry in a loop.

## 1. `purge_expired_security_rows` (Identity)

| | |
| --- | --- |
| What | Deletes expired throttle windows, one-time codes, MFA challenges, refresh-replay markers and finished sessions, a bounded batch per table. Accounts, security events and audit rows are **never** touched. Retention rules: `services/identity/service/retention.py` and `docs/engineering/phase2/P2-02_identity_retention_of_expired_security_rows.md` |
| Run | `python manage.py purge_expired_security_rows --limit 5000` in the Identity image (limit 1 to 10000, default is the module's `BATCH`) |
| Output | one `table: count` line per table |
| Cadence | daily while the platform is in use; anonymous sign-in attempts create throttle rows, so growth is proportional to traffic |
| Done when | every count is `0` |

## 2. `purge_expired_web_sessions` (Console)

| | |
| --- | --- |
| What | Deletes at most 500 expired web credentials and 500 expired browser sessions from the console's own `web` schema. It is the bounded complement of Django's `clearsessions`, and **the existing mention in `apps/web_django/README.md` is the only other place it appears**: this runbook is its first complete description |
| Run | `python manage.py purge_expired_web_sessions` in the console image, with the console's runtime login (`kolovibe_web_app`, `web` schema; see `docs/operations/AWS_Web_Staging_Deployment_2026-11-19.md`). Also run `python manage.py clearsessions` in the same job |
| Output | `Expired web credential rows removed: N` |
| Cadence | daily; console sign-ins are few, so the volume is small, but expired rows are otherwise never removed |
| Done when | the count is `0` |

## 3. `requeue_stalled_media` (Content)

| | |
| --- | --- |
| What | Re-publishes the processing task for videos stuck in `processing` after a lost broker message or exhausted retries: a stored source, no live lease and past the stalled threshold. Safe to repeat: a worker claims each video under a lease, so a duplicate message does nothing while another worker holds it. Design: `docs/engineering/phase3/P3-01_requeue_stalled_media.md` |
| Run | `python manage.py requeue_stalled_media --limit 100 --stalled-minutes 15` in the Content image (limit 1 to 500; threshold 5 to 1440 minutes) |
| Output | `requeued: N` and `failed: M` |
| Cadence | every 15 to 30 minutes during upload activity, and once after any broker or media-worker outage |
| Done when | `requeued: 0`. `failed` above `0` means the broker was unreachable: check the broker, then run again. Do not raise `--limit` to force it |

## What this does not do

It does not start anything, change a retention period, or touch accounts, security events or audit rows. Retention of those is an owner policy decision (ADR-020, OD-08).

### Candidate scheduled roles (off until O-12 is approved)

| Process | Role | Proposed schedule | Network | Notes |
| --- | --- | --- | --- | --- |
| `identity-purge` | `purge-security-rows` (capability `account_management`) | `--interval 3600 --limit 1000` (hourly, the runtime's slowest allowed interval) | service and data only | same flag row and secret mounts as `identity-audit` |
| `content-requeue` | `requeue-media` (capability `media`) | `--interval 900 --limit 100` | service, data and messaging; **no** R2 proxy route | carries the Content R2 settings the runtime validates, but cannot reach R2 |

Both are at `replicas: 0`. The interval and batch values are proposals for the owner to confirm with O-12. To start one after approval: `docker service scale <stack>_identity-purge=1`; to stop: scale to `0`. The console purge stays manual until a web-stack role is designed. Validated offline by `python scripts/validate_staging_stack.py --aws-stack` and `scripts/test_aws_stack.py`.
