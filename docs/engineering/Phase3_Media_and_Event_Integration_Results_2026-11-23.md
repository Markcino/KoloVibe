# Phase 3 — media and event integration: results

**Date:** 23 November 2026. **Base:** `main` at `caa0b0e`. Repository changes only. No AWS access, staging run, migration, RabbitMQ permission or declaration change, deployment or merge. Tracker rows: [Phase 3 section](R1_Application_Tracker.md) (this PR is stacked on #205 → #192).

## The routing was preserved, not re-verified live
The instruction named v0.373.1 as having verified the Points routing. No repository file records that release, so I could not check it; what is asserted is the **repository's code**: Engagement publishes qualified views to exchange `kolovibe.points` with routing key `kolovibe.points` and queue `kolovibe.points`, with `no_declare` on both the queue and the exchange (so Engagement neither declares broker resources nor binds the queue), persistent delivery, `task_id` equal to the event id. A test now fails if any of that changes ([#207](https://github.com/Markcino/KoloVibe/pull/207)).

## Pull requests (none merged)

| PR | What | Type |
| --- | --- | --- |
| [#206](https://github.com/Markcino/KoloVibe/pull/206) | `requeue_stalled_media`: re-publish processing for videos stuck in `processing` (lost broker message or exhausted retries), repeat-safe under the worker lease, counts only | feature (operational) |
| [#207](https://github.com/Markcino/KoloVibe/pull/207) | Engagement → Points pipeline across the real services on the disposable TLS PostgreSQL: routing contract, broker interruption and retry, duplicate and concurrent redelivery, worker killed after the receipt, daily cap with withheld awards, audit evidence retention and delivery, append-only and reversal constraints; new CI step | integration test |
| [#208](https://github.com/Markcino/KoloVibe/pull/208) | Self-views never qualify (Engagement and gateway, including progress and no side effects) | test |
| [#209](https://github.com/Markcino/KoloVibe/pull/209) | Upload → R2 → FFmpeg → review → moderation → publication → playback → unpublish as one Content chain with a recording private bucket | integration test |

## Acceptance journey, boundary by boundary
1. Creator upload → R2 grant → completion → FFmpeg → review → moderation → publication → signed playback: **#209** (real encoder when FFmpeg is on the sandbox PATH; run once locally with the real encoder).
2. Playback facts (`creator_id`, `duration_ms`, `revision`) → gateway watch route → Engagement session and qualified view: gateway tests (signed account and server metadata, **#208** for self-views) and existing Engagement watch tests (server elapsed time, de-duplication, revision binding).
3. Engagement outbox → broker message → Points inbox → qualification receipt → append-only ledger: **#207**.

**Not done as one live run:** no single run drives all of this through every service with real R2, RabbitMQ and FFmpeg. That needs your staging environment. **No staging acceptance is recorded.**

## Findings and gaps (not fixed, with reasons)
- **Exactly-once rests on three layers** (receipt state, inbox, unique `source_decision_id`); removing the receipt guard and the inbox together fails three tests, removing the inbox alone does not.
- **Poison messages:** a malformed payload raises and, with `acks_late`, is acknowledged and dropped; no dead-letter queue is configured in the repository. Fixing it needs broker configuration, which is off limits here.
- **Reversals:** only the ledger's constraints are tested; no write path exists and no rule is approved.
- **R2 lifecycle and cleanup:** no deletion exists; it needs a retention rule (OD-07) and a credential allowed to delete. No cleanup was added.
- **Worker resource controls:** the repository already bounds the worker (one task at a time, prefetch 1, 240 s task limit, 10-minute lease, bounded FFmpeg); container memory/CPU limits and the sandbox are infrastructure and unchanged.
- **Self-likes** are accepted and earn nothing; forbidding them is a product decision.
- **Local FFmpeg:** not on the encoder's sandbox PATH on this machine, so the CI media image is where the real encoder runs.

## Verification
Content 124 (+6 on #206), identity unchanged, event pipeline 8 on PostgreSQL 14, engagement and gateway suites OK with the new tests; PR CI results are on each pull request. Flutter was not run.

## Owner actions
1. Review #206–#209; none is merged.
2. Run the journey on staging when you choose, with real R2, RabbitMQ and FFmpeg, and tell me the result to record; I recorded none.
3. Decide: points reversal rule, R2 retention and delete credential, dead-letter policy for the Points queue, self-likes.
4. Schedule `requeue_stalled_media` if you want automatic recovery.
