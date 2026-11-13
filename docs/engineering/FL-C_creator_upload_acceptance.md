# FL-C creator upload journey acceptance — 13 November 2026

Baseline: main `4c77c077ab2c6808ac4451a75080c52984412f05`. Local verification only. No deployment, physical-device or live R2 acceptance is implied.

Journey: **a creator uploads an original and follows it to review** (M-041–M-044, M-046–M-049). The rest of FL-C (M-036–M-040, M-045, M-050–M-060) is not part of this change.

## Gaps found before changes

| Area | Gap |
| --- | --- |
| Draft request | Omitted the required `category` and `tags`, so the gateway returns 400 for every real draft (DOC-205 `VideoCreate`, gateway `checked_metadata`). |
| Owned video parsing | `OwnedVideo` rejected any field beyond six, but the gateway always returns `category`, `tags`, `cover_time_ms`, `visibility`, `published_at`, `poster_url` (and optional durations). The draft response, the upload flow and the M-040 library all failed to parse live responses. |
| Upload status | Parser rejected `failure_reason` and `retryable`, which the gateway always sends, so completion and status reads failed. |
| Retry | One idempotency key was reused for every retry; DOC-205 requires a fresh key after an expired or failed reservation. |
| States | No progress, no polling after completion, no server failure reasons, no signed-out/restricted/offline handling; the single "Retry upload" button hid which step failed. |
| Fixtures | Existing tests mocked the pre-contract shapes, so they passed while the real gateway would have been rejected. `live_repositories_test.dart` and `live_creator_upload_test.dart` fixtures were updated to DOC-205 shapes; assertions are unchanged. |

## Implemented

Routes `/mobile/M-041`–`/mobile/M-044` open one live flow (they are its steps). `M-045`–`M-049` stay protected fallbacks as cold routes; their states render inside the flow. Nothing is shown without `KOLOVIBE_API_URL`.

| Screen | Behavior |
| --- | --- |
| M-041 | Eligibility via `GET /creators/me/upload-eligibility`. States: checking, outage with retry, not approved, signed out (shared `LiveStateView`, sign-in to M-004), restricted. |
| M-042 / M-043 | Platform picker; local check of `.mp4`, 12 bytes to 50 MiB and `ftyp` header. Codec, duration and resolution are server-validated (`invalid_media`). |
| M-044 | Title (1–160), description (≤2000), required category (seven DOC-205 values), optional hashtags (≤5, normalized like the server). Errors appear before any request. |
| M-046 | `POST /videos`, `POST /videos/{id}/upload-intents`, conditional `PUT` to the signed R2 URL, `POST /videos/{id}/upload-status`. Real byte progress; screen-reader label. |
| M-047 | Retryable interruption resumes the failed step only. The draft is never re-created; the same reservation key is reused while the grant is unexpired. Expired or conflicting reservations use a fresh key. |
| M-048 | Server `failure_reason` copy. `invalid_media` asks for a different video; other reasons re-upload with a fresh key. |
| M-049 | `GET /videos/{id}/upload-status` polling (3, 5, 8, 13, 20 s, at most 18 reads), a manual check after polling stops, and `retryable` transient preparation failures re-submit completion. Final states (`review`, `published`, `rejected`, `removed`) are shown as the server reports them. No moderation decision or reason is invented. |

Not built: **M-045 cover choice.** The backend accepts `cover_time_ms`, but this app has no video-frame API; the cover stays server-default. The draft is not resumable after the app is closed (it remains in the M-040 library).

## Tests and what they mock

| Suite | Type | Count |
| --- | --- | --- |
| `test/live_creator_upload_test.dart` | Repository contract tests with **mocked HTTP** (`MockClient`) for gateway and R2 | 12 |
| `test/live_upload_controller_test.dart` | Controller tests with a **fake content service** and an in-memory file; polling delay injected | 29 |
| `test/live_create_original_screen_test.dart` | Widget tests with **fake repositories**, an in-memory file and a fake picker; includes 2.0 text scale and screen-reader label | 19 |
| `test/creator_upload_routes_test.dart` | Route dispatch with real design catalog | 2 |

None uses a real network, R2, FFmpeg, RabbitMQ, the platform picker or a device. Not verified: the native picker on iOS or Android, background or lock behavior during a transfer, real R2 conditional PUT, secure-storage refresh during a long upload, and deployed gateway responses.

## Exact commands and results

```bash
cd apps/mobile
flutter pub get --enforce-lockfile
flutter analyze            # No issues found
flutter test               # 648 passed (Flutter 3.47.8, the CI pin)
cd ../.. && python3 scripts/check_mobile_design.py   # 108 entries, valid routes
```

Removing `category` from the draft body, and reusing the old key after a confirmed failure, each make the new tests fail.

## Limits and remaining journeys

- Staging activation of the media capability and live R2/worker acceptance remain open (see the R1 tracker). The gateway contract was read from DOC-205, which is still a draft.
- M-040 library parsing is fixed by the same parser change but its management actions (published/failed/rejected) are separate work.
- Remaining FL-C journeys: M-036–M-039 onboarding and profile, M-045 cover, M-050–M-057 outcomes and management, M-058–M-060 analytics. FL-D (M-061–M-078) is untouched.
