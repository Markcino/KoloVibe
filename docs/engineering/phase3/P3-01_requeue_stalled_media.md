# P3-01 — Recover videos stalled in `processing`

**Type:** operational recovery command (no migration, no API change). **Baseline reference:** Phase 0 risk R-09 (stuck-job reconciliation).

## Problem
A video enters `processing` when the creator completes the upload and a Celery message is published. Two failure paths leave it there with nobody working on it: the broker message is lost (the publish is outside the database transaction), or the worker exhausts `max_retries` on a transient storage/encoder/database fault. Today the only recovery is the creator repeating the completion request; the Phase 0 baseline lists monitored reconciliation of stuck jobs as missing.

## Change
`manage.py requeue_stalled_media [--limit N] [--stalled-minutes M]` re-publishes the processing task, through the existing `_enqueue` (the scoped `kolovibe.content.media` exchange and routing key, nothing new declared), for videos that are:
- in `processing`, not deleted, with a confirmed source (`source_etag`);
- without a live lease (none, or expired);
- past the stalled threshold (default 15 minutes after the reservation's end, which is later than processing could have started).

Safe to repeat: the worker claims each video under a lease, so a duplicate message waits (`LeaseBusy` retry) or does nothing, and a finished video is no longer `processing`. The command changes no video state, prints counts only (`requeued`, `failed`), and counts a broker failure instead of raising it (no address or credential text can surface). Limit 1–500, threshold 5–1,440 minutes.

## Tests (`services/content/tests/test_requeue_stalled_media.py`, 6)
Selection excludes live leases, fresh reservations, unconfirmed sources, deleted videos and every other state; oldest first with a bounded limit; broker failure counted, video untouched; database unchanged by a requeue; argument validation; command output is counts only. Content suite and `makemigrations --check` pass.

## Not done (needs decisions or live evidence)
- **R2 object lifecycle** (deleting originals after processing, abandoned uploads, superseded renditions): needs an approved retention rule (OD-07) and a bucket credential that may delete; Cloudflare bucket lifecycle rules are the likely owner-side control. No deletion was added.
- Scheduling this command (a Swarm job or cron) is an owner infrastructure action; it is not added to any stack file.
