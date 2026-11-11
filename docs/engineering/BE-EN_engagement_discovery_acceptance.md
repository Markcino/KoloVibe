# BE-EN engagement/discovery acceptance — 11 November 2026

Baseline: main `00395099380f6e5b248bc589998e1671c11c6b8a`. Local verification only; no deployment acceptance is implied.

## Gaps found before changes

- Gateway engagement_client.py was the BE-CC None-returning stub. No signed aggregate likes/followers/ranking endpoints existed.
- Like/follow GET/PUT responses omitted aggregate counts, and DELETE returned empty 204 responses.
- No share model, UTC-day deduplication, canonical public origin setting or public share endpoint existed.
- VideoLike lacked creator attribution and creation time. WatchSession retained only its latest qualification, losing older play history as sessions renewed. Existing analytics had only Content state totals, current likes and distinct retained qualified accounts.
- Server-paced qualification, self-view rejection, signed service boundaries and following-feed pagination already existed. Analytics routes already used the analytics capability block; these controls were retained and tested.

## Implementation

| Surface | Implemented behavior |
| --- | --- |
| Gateway engagement_client.py | Public functions are exactly like_counts(video_ids), follower_count(creator_id), trending_video_ids(limit=20), with the requested return types. Signed bounded reads, strict types/IDs/fields, timeout/error/invalid-response → None. Batch likes supports ≤50 input IDs and factual zeros for missing likes. |
| Trending | Engagement ranks retained qualified plays in the preceding rolling seven days, breaking ties by ascending video UUID. Signed cursors retain the cutoff while paging. Gateway reuses Content's existing ordered public lookup to skip private/deleted candidates before applying the requested limit. Bounded to 20 pages of 50 candidates and an eight-second checked budget; exhaustion returns None rather than a partial ranking. Content calls retain their existing bounded transport timeout. |
| Like GET/PUT/DELETE | Exact `{video_id, liked, like_count}`. DELETE now returns 200 JSON so its count can be included. Repeated writes preserve state, count and the original creation time; unlike can remove the owner's state even after a video is hidden. Creator attribution comes from the existing Content public detail read. |
| Follow GET/PUT/DELETE | Exact `{creator_id, following, follower_count}`; repeated follow/unfollow remains idempotent. DELETE now returns 200 JSON. Existing self-follow/role/public-profile checks are retained. |
| POST `/api/v1/videos/{id}/shares` | Authenticated viewer/creator; no body/query accepted. Existing Content public detail checks publication/visibility/deletion first. Records one intent per account/video/UTC day, then returns `{video_id, share_url}`. Canonical URL is configured public origin + `/videos/<id>`. Unconfigured origin returns 503 `share_unavailable` without recording. Non-public video returns 404. No points are emitted. |
| GET `/creators/me/analytics?range=7d\|28d` | Keeps total_videos/videos_by_state. Adds range, qualified_plays, watch_time_seconds, likes, new_followers, shares, daily and ≤5 ranked titled top_videos. Owner identity and creator ownership are bound at gateway. Titles come from existing signed Content owner detail reads; deleted/non-owned top details are omitted. |
| GET `/creators/me/videos/{id}/analytics?range=7d\|since_published` | Content ownership is checked before querying Engagement; non-owned/deleted video is 404. Keeps video_id/state/current_likes/qualified_viewers and adds range, qualified_plays, watch_time_seconds, likes, shares, average_watch_seconds. since_published uses the existing owner detail publication timestamp; unknown legacy timestamp means all retained real activity rather than a guessed date. |

The 7d/28d analytics windows are UTC calendar dates including today; trending is a rolling seven-day window. Future records are excluded. Empty activity yields zeros/empty lists. With plays/likes, daily is a complete zero-filled 7/28-date series. Range likes/follows are current rows created in range; removing a row removes it from those metrics. Share counts represent recorded unique daily intents, not confirmed external delivery. Historical aggregate engagement remains retained after content is hidden, while hidden titles/identifiers are not exposed through top_videos.

## Models, migration and server ownership

- Engagement migration `0005_discovery_shares_and_qualified_history.py` adds nullable VideoLike.created_at/creator_id, QualifiedWatch and VideoShare, their uniqueness/time constraints and range/video/creator indexes.
- Existing likes retain null creation time/creator attribution: migration does not fabricate dates. New upgraded-gateway likes record actual creation time and Content-derived creator ID. Unknown legacy dates do not enter date-range metrics, but remain in current_likes/like_count.
- QualifiedWatch retains each server-qualified play independently of the renewable WatchSession. The migration preserves each session's latest known qualification, copies recorded watch time only when it belongs to that session, and leaves unknown time null. Older overwritten qualifications cannot be reconstructed. Backfill emits no outbox events or points.
- New qualified records and the existing points outbox event commit in the same transaction. Subsequent validated progress from the same qualifying session can increase its observed watch time. A renewal inside the 24-hour dedupe window cannot create another play or replace the original time.
- Watch threshold/pacing/revision/expiry/self-view policy and the existing two-field `dec003.qualified_view` points payload are unchanged. Neither likes, follows nor shares emit qualification/points. No endpoint accepts client qualification, points, watch timestamps or duration/creator overrides.
- New share day is computed from server time converted to UTC; database uniqueness enforces account/video/day idempotency.
- KOLOVIBE_PUBLIC_WEB_ORIGIN is optional and validated during gateway settings load: HTTPS origin only, no credentials, non-root path, query, fragment, whitespace/backslash or malformed port. The local launcher forwards it only to gateway.

Primary Engagement files: models.py, migration 0005, discovery.py, shares.py, analytics.py, likes.py, follows.py, watch.py, urls.py and tests. Primary Gateway files: engagement_client.py, shares.py, analytics.py, likes.py, follows.py, settings.py, routes/engagement.py and tests. DOC-205 updates Like, FollowState, Share/ShareUnavailable, analytics schemas and affected paths/implementation annotations.

## Exact verification commands and results

Executed with Python 3.12.14, Django 5.2.18 and the existing local dependency directories. OpenAPI validation used available openapi-spec-validator 0.9.0. From repository root:

```bash
export KOLOVIBE_ENV=local
export DJANGO_SECRET_KEY=local-be-en-test-key-at-least-32-characters
export PYTHONPATH=/workspace/scratch/7d4e52b069cd/kolovibe-dec003/deps:/workspace/scratch/7d4e52b069cd/kolovibe-stream.hKze2v/deps:/workspace/scratch/7d4e52b069cd/kolovibe-r2.MHla4M/media-deps:/workspace/scratch/100b9f85b85d/kolovibe-be-en/services
```

| Command | Result |
| --- | --- |
| `(cd services/engagement && python3 manage.py test tests --verbosity 1)` | 32 passed. |
| `(cd services/gateway && python3 manage.py test tests --verbosity 1)` | 107 passed. |
| `python3 -m unittest discover -s scripts -p test_run_local_service.py -v` | 9 passed. |
| `(cd services/engagement && python3 manage.py makemigrations --check --dry-run)` | Passed; no changes detected. |
| `(cd services/gateway && python3 manage.py makemigrations --check --dry-run)` | Passed; no changes detected. |
| `python3 -c "import yaml; from openapi_spec_validator import validate_spec; validate_spec(yaml.safe_load(open('docs/architecture/DOC-205_OpenAPI_3_1_DRAFT.yaml'))); print('DOC-205 OpenAPI 3.1: PASS')"` | Passed. Duplicate keys and updated JSON schemas also checked. |
| `python3 scripts/check_structure.py` | Passed; eight services and approved layout. |
| `git diff --check` | Passed. |

148 tests passed. New coverage includes real aggregate zeros/counts, strict/unavailable clients, ranking cutoff/ties/public filtering, UTC share idempotency and database uniqueness, calendar ranges, owner-only titles/publication timestamps, mixed-membership pagination across requests without duplicates/loss, migration preservation, outbox rollback and rejected client qualification/points overrides.

## Ownership and remaining limits

- **Content service edits: none.** Existing public lookup, public detail, owner media detail and owner analytics endpoints supply current publication, ownership, titles and publication dates.
- The existing `routes/creator_studio.py` analytics gate was already correct and was not rewritten; a regression test proves analytics routes can be selected independently of media capability.
- Cross-ownership edits are the shared local launcher/test and DOC-205. Gateway BE-CC consumer tests explicitly isolate nullable engagement reads now that the client performs real I/O. No identity, creators, content, points service or outbox transport implementation changed.
- Apply Engagement migration 0005 before deploying these APIs; coordinate Gateway/Engagement response changes and consumers expecting old DELETE 204 responses. Rolling back drops the added histories/metadata and requires a reviewed data-preservation plan.
- Configure the actual HTTPS public web origin before share links can be recorded/returned. The target web `/videos/<id>` route and live sharing were not tested.
- Historical metrics are limited to retained facts: overwritten old plays and absent like timestamps are unavailable; unknown old watch time is not estimated. Watch-time averages therefore reflect observed time across retained plays, including zero contribution from unknown legacy time.
- PostgreSQL concurrency, live signed service traffic, AMQPS delivery, deployment permissions and production load were not exercised. Service suites use SQLite. Implementation/capability annotations remain local verification, not authorization to deploy or open new staging capabilities.
