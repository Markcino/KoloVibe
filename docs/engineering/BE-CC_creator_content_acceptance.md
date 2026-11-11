# BE-CC creator/content acceptance — 11 November 2026

Baseline: main `6a310136cc56539e9b1462d7413593b0d03c5fd1`. This records local implementation and verification, not a deployment.

## Gaps found before changes

- Creator profiles lacked display_name/location, an owner GET/PATCH endpoint and database-enforced case-insensitive handle uniqueness. Public detail had no published video or follower totals.
- Video rows/API lacked categories, normalized tags, cover selection, posters, failure codes and tombstones. published_at existed but was not exposed.
- Owner edits/deletes were limited to private drafts without reserved media; deletion was physical. No owner publish/unpublish route existed. Upload intents could not replace failed reservations.
- Public reads lacked category/trending composition and batch likes. Content had no ordered public lookup or creator public-count endpoint. The requested engagement client did not exist in this baseline.
- Background processing, moderation and analytics needed tombstone guards to prevent deleted content from returning.
- Existing R2 storage, bounded FFmpeg encoding, moderation receipts, ownership checks and public-only reads were reused.

## Implemented endpoints and behavior

| Surface | Result |
| --- | --- |
| GET/PATCH `/api/v1/creators/me` | Owner identity creator role plus active reviewed profile required; restricted/suspended return 403. Partial display_name ≤80, bio ≤500, location ≤80 and canonical handle updates; case-insensitive conflicts return 409 `handle_taken`. |
| GET `/api/v1/creators/{creator_id}` | Adds display_name/location, live Content published_video_count and nullable engagement follower_count. Content count unavailable returns 503. |
| Creator search | Adds display_name/location and matches display names as well as handles. |
| POST `/api/v1/videos` | Requires category for new drafts; existing rows retain nullable categories. Validates/normalizes tags and optional cover selection. |
| GET `/api/v1/videos` | Existing q/creator_id/cursor behavior plus category and recent/trending sort. Trending reads 20 ranked IDs then ordered public lookup; unavailable ranking/lookup returns 503. Trending rejects cursors and returns next_cursor null. Public items/detail/following pages include nullable batch like_count. |
| GET `/api/v1/creators/me/videos` | Owner cursor pagination and all/draft/in_progress/review/published/rejected/removed/failed filters; in_progress groups uploading and processing. Includes visibility, published_at, poster_url, category, tags and cover metadata. |
| PATCH `/api/v1/videos/{id}` | Partial title/description/category/tags/cover_time_ms edits for owned draft/failed/rejected/published videos. Other creators receive 404. |
| POST `/api/v1/videos/{id}/unpublish` | Idempotently makes an owned published video private while keeping state published. |
| POST `/api/v1/videos/{id}/publish` | Makes an approved private published video public; otherwise 409 `review_required`. Current creator eligibility is rechecked; restricted/suspended cannot publish or create drafts. |
| DELETE `/api/v1/videos/{id}` | Soft deletes any owned state, hides it from reads/moderation/analytics and cancels reservations/leases. No storage purge under ADR-020. |
| Upload intents/status | Fresh idempotency keys replace draft/uploading/failed reservations. Same unexpired key/size remains idempotent; expired/failed retries need a new key. Status exposes short failure_reason or null and boolean retryable. Owners can inspect status without upload eligibility; completing an upload still requires eligibility. |
| Content internal reads | POST `/internal/videos/lookup {ids}` accepts ≤50 UUIDs, preserves order and excludes non-public/deleted rows. POST `/internal/videos/published-count {creator_id}` returns the published/public/non-deleted count. Both require gateway service caller. |

New owner routes are composed in `routes/creator_studio.py` under the media capability. Existing catalog composition keeps public listing always available.

## Data, processing and files

- Creators migration `0004_creator_profile_fields.py`: display_name/location plus a functional unique constraint on Lower(handle). Existing handles remain unchanged; new onboarding/owner handle writes require `^[a-z0-9_]{3,30}$`.
- Content migration `0008_video_metadata_and_soft_delete.py`: category, tags, cover_time_ms, poster_asset_id, failure_reason, deleted_at and a known-millisecond-duration cover constraint. Application validation also bounds covers using legacy duration_seconds when needed.
- Category enum: hipco, afrobeats, comedy, skits, short_films, culture, documentaries. At most five raw tags; trim, remove one optional leading #, lowercase, validate `^[a-z0-9_]{1,30}$`, deduplicate in order.
- Processing renders one JPEG from the encoded rendition at the requested cover, otherwise 1000 ms or 0 for clips ≤1000 ms. JPEG extraction has a 15-second timeout, one thread/frame, file/pipe-only inputs, stripped metadata, a 640-pixel bound and a 1 MiB cap. JPEG/MP4 objects remain private in R2; poster URLs use the existing SigV4 signer for 300 seconds. Existing media encoding/upload limits remain in effect.
- `M-054.json` is absent. The M-054 screen is embedded in `apps/mobile/assets/design/studio.json`; its text says “Save changes” and has no requirement to review changes again. Published metadata edits therefore preserve approval/publication and advance the revision. Cover edits clear the old poster instead of returning an incorrect frame; processed-cover re-rendering is deferred.
- Primary content files: models.py, video_metadata.py, media_api.py, videos.py, moderation.py, analytics.py, media_processing.py, media_encoding.py, media_storage.py, urls.py and tests.
- Primary creators files: models.py, profiles.py, onboarding.py, urls.py and tests.
- Primary gateway files: creators.py, videos.py, media.py, content_client.py, video_validation.py, routes/creator_studio.py and tests. DOC-205 updates Creator/OwnCreator/CreatorUpdate, Video/OwnVideo/OwnVideoDetail/VideoCreate/VideoUpdate/VideoUploadStatus/PageVideos/PageOwnVideos and affected paths with implementation/capability annotations.

## Exact verification commands

The following environment was used from the repository root with Python 3.12.14, Django 5.2.18 and the existing pinned service/media dependency directories. OpenAPI validation used available openapi-spec-validator 0.9.0.

```bash
export KOLOVIBE_ENV=local
export DJANGO_SECRET_KEY=local-be-cc-test-key-at-least-32-characters
export PYTHONPATH=/workspace/scratch/7d4e52b069cd/kolovibe-dec003/deps:/workspace/scratch/7d4e52b069cd/kolovibe-stream.hKze2v/deps:/workspace/scratch/7d4e52b069cd/kolovibe-r2.MHla4M/media-deps:/workspace/scratch/100b9f85b85d/kolovibe-be-cc/services
```

| Command | Result |
| --- | --- |
| `(cd services/content && python3 manage.py test tests --verbosity 1)` | 48 passed; includes real FFmpeg encode/JPEG extraction for short and longer clips, end-frame covers and network-free SigV4 JPEG signing. |
| `(cd services/creators && python3 manage.py test tests --verbosity 1)` | 17 passed. |
| `(cd services/gateway && python3 manage.py test tests --verbosity 1)` | 86 passed. |
| `(cd services/content && python3 manage.py makemigrations --check --dry-run)` | Passed; no changes detected. |
| `(cd services/creators && python3 manage.py makemigrations --check --dry-run)` | Passed; no changes detected. |
| `python3 -c "import yaml; from openapi_spec_validator import validate_spec; validate_spec(yaml.safe_load(open('docs/architecture/DOC-205_OpenAPI_3_1_DRAFT.yaml'))); print('DOC-205 OpenAPI 3.1: PASS')"` | Passed. Duplicate YAML keys and updated JSON schemas were also checked. |
| `python3 scripts/check_structure.py` | Passed; eight services and approved layout. |
| `git diff --check` | Passed. |
| `scripts/test_*media*.py` inventory | No matching script files in this baseline; no script suite was skipped. Service media/poster suites ran above. |

151 tests passed. Coverage includes ownership denials, case-insensitive handle collisions, nullable legacy data, metadata bounds, state filters, publication review guards, soft-delete read/worker/moderation safety, retry reservations, public lookup ordering, unavailable engagement, capability gates and strict response validators including large Unicode metadata pages.

## Cross-ownership changes and remaining limits

- `services/gateway/service/engagement_client.py` is the requested BE-EN seam: exactly like_counts(video_ids), follower_count(creator_id), trending_video_ids(limit=20), all returning None. BE-EN must replace this stub with its real client; these changes deliberately provide null counts/503 trending until then.
- `services/gateway/service/following.py` and its fixture test were adapted to the richer public-video validator and batch like_count composition. Following membership/pagination behavior is unchanged.
- Shared DOC-205 contains only the Creator/Content path/schema updates. No identity or engagement-service implementation was changed.
- Apply creators 0004 and content 0008 before rolling out these strict gateway contracts. Legacy handles differing only by case must be reconciled before the unique constraint can be installed; handles are never silently renamed. Rolling back the content migration drops the new metadata/tombstone columns and needs an owner-reviewed data-preservation plan.
- Own creator profile requires the identity creator role as requested; the existing creator onboarding workflow changes profile eligibility, not identity roles. No identity role-promotion mechanism was added here.
- Live R2 transfers, AMQPS delivery, PostgreSQL concurrency and production resource/load behavior were not exercised. The suites use SQLite and local FFmpeg; they do not establish deployment acceptance.
- Re-rendering posters after processed cover edits remains deferred. Existing R2 assets are not backfilled and may have null posters. Previously issued playback/poster URLs can live for 300 seconds, and upload PUT URLs for 600 seconds; deleted/replaced reservations cannot complete or publish. Private orphan objects remain until a separately approved retention/purge policy is implemented.
