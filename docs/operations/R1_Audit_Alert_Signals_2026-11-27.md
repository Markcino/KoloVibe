# Audit and media alert signals (#145, mandate item 2.3), 27 November 2026

**Status: IMPLEMENTED IN THE REPOSITORY, NOT DEPLOYED, NOT VERIFIED ON STAGING.** Nothing alerts a person yet. That needs a monitoring platform, a notification channel and an on-call path, and choosing them is an owner decision (OD-08, ADR-017).

## What exists now

`services/staging_runtime/signals.py` measures three read-only signals:

| Signal | Emitted by | Values |
| --- | --- | --- |
| `audit_backlog` | every audit-delivery job: `points-audit`, `moderation-audit`, `identity-audit`, plus `content-audit` and `creators-audit` (#292) | undelivered rows, age of the oldest in seconds, highest retry count |
| `media_stalled` | `content-requeue` | videos stalled under the requeue job's reviewed 15-minute rule, and the oldest one's age |
| `queue_depth` | `content-requeue` | ready messages and consumers on `kolovibe.content.media`, read by a passive declare. Content's broker account already has configure rights on that queue only |

- **When a signal is emitted:** after every batch, whether the batch failed or not, so no extra process runs.
- **What a line holds:** each line is one JSON object prefixed `KOLOVIBE_SIGNAL `. It holds names and counts only, never an identifier, a payload or an exception message.
- **When it alerts:** only when the owner has set a threshold. A breach is repeated on stderr, prefixed `KOLOVIBE_ALERT `.
- **When a value can't be read:** the line says `"available": false`, without the cause.

## Thresholds: owner decisions, no defaults

| Variable | Compared with |
| --- | --- |
| `KOLOVIBE_ALERT_AUDIT_MAX_AGE_SECONDS` | age of the oldest undelivered audit row |
| `KOLOVIBE_ALERT_AUDIT_MAX_PENDING` | undelivered audit rows |
| `KOLOVIBE_ALERT_MEDIA_MAX_STALLED` | stalled videos |
| `KOLOVIBE_ALERT_QUEUE_MAX_DEPTH` | ready messages on the media queue |

- **How the variables behave:**
  - If a variable is unset, the signal still reports, with `"alert": null`.
  - If a value is not a whole number, the job refuses to start.
  - The stack file sets none of them.
- **Candidate already on record:** #272's acceptance criterion, "0 undelivered rows older than 5 minutes", is the one recorded candidate for the audit-age threshold (300 s). It is still the owner's to approve.

## Not covered yet

- **Notification:** no platform, channel or paging (OD-08).
- **A job that is not running emits nothing.** Points delivery was failing on staging, which shows why missing-signal detection matters. It needs the monitoring platform, or an operator reading `kolovibe_cluster.py capacity` and the service restart counts.
- **Queue depth for Engagement and Points:** their consumers are Celery workers, not batch jobs, so nothing emits for them. Adding a signal there means either a new process or an owner-approved change to the consumer.
- **Other #145 items:** 5xx rates, authentication-failure alerts, cost anomalies, audit retention and DOC-019.

## Verification

- **Run locally:**
  - `scripts/test_staging_signals.py`: emission, thresholds, no defaults, no cause leaked, emitted after every batch including the final failure;
  - `services/content/tests/test_health_signals.py`: the real Content outbox and stalled-media queries on the test database.
- **NOT RUN on staging:**
  - the passive declare against the live broker;
  - any emitted line.
