# FL-C Creator Studio gap matrix (M-036–M-060) and journey 1

Baseline: `origin/main` `d32cb60` (PR #49, the upload journey, is included and untouched). Local verification only: no deployment, device or live R2/staging acceptance is implied. Contract source: DOC-205 (a draft) and the gateway code in `services/gateway/service`.

## How each screen was classified

VERIFIED = live screen, real gateway data, states and tests. PARTIAL = some behaviour is live, parts of the recipe are missing. MISSING = contract exists, no live screen (the route falls back to the protected design placeholder, which shows no sample data in a live build). BLOCKED = a recipe element has no contract or dependency yet.

| Screen | Recipe | Before this PR | After this PR | Contract and dependency |
| --- | --- | --- | --- | --- |
| M-036 | Become a creator | MISSING (an inline form hid inside M-037) | **VERIFIED** (journey 1) | `GET /creators/me/upload-eligibility`, `GET`/`POST /creators/me/application`. Invitations are issued by staff only (`POST /creator-invitations`, moderator/administrator); no creator-facing way to request one. The recipe's "Explore creator guidelines" link is not offered (no confirmed destination). |
| M-037 | Creator Studio | PARTIAL (inline library, no profile) | **PARTIAL** (journey 1) | Real name and actions from `GET /creators/me`. The metrics card needs the analytics client (journey 5); the Lone Stars card belongs to FL-D (M-061+). Neither is faked. |
| M-038 | Creator profile | MISSING | **VERIFIED** except photo | `GET /creators/me`; published count from `GET /creators/{id}` (optional). Profile photo: **BLOCKED**, no contract. |
| M-039 | Edit creator profile | MISSING | **VERIFIED** except photo | `PATCH /creators/me` (display name, bio, location, handle). "Change profile photo": **BLOCKED**, no contract. |
| M-040 | My video library | PARTIAL | PARTIAL | List, paging, draft edit and delete exist. Missing: state filters (`state=all/draft/in_progress/review/published/rejected/removed/failed` is supported), thumbnails (`poster_url`, 300 s signed), opening a video (M-053). Search is **BLOCKED**: no query parameter. Play counts need analytics. |
| M-041–M-044, M-046–M-049 | Upload flow | VERIFIED (PR #49) | VERIFIED | See [FL-C upload acceptance](FL-C_creator_upload_acceptance.md). |
| M-045 | Choose a cover | BLOCKED | BLOCKED | The server accepts `cover_time_ms`, but the app has no video-frame API or extraction dependency. Needs an owner decision (see below). |
| M-050 | Pending moderation | PARTIAL (`review` state shown inside M-049) | PARTIAL | Standalone view needs `GET /creators/me/videos/{id}` (`OwnVideoDetail`, includes `revision`). |
| M-051 | Original is published | PARTIAL (`published` shown inside M-049) | PARTIAL | Same read. |
| M-052 | Video rejected | MISSING | MISSING | `GET /creators/me/videos/{id}/notice` (`VideoNotice`: decision, `reason_code`, `appealable`, appeal), gateway capability `moderation`. Needs approved copy for each `reason_code`; unknown codes must not be guessed. |
| M-053 | Manage video | MISSING | MISSING | Owned detail, `POST .../publish`, `POST .../unpublish`. |
| M-054 | Edit video details | PARTIAL (draft title and description in a dialog) | PARTIAL | `PATCH /videos/{id}` allows draft, failed, rejected and published; category, tags and `cover_time_ms` too. Per DOC-205 a published edit keeps approval. |
| M-055 | Unpublish confirmation | MISSING | MISSING | `POST /videos/{id}/unpublish`; `409 review_required`; allowed for a restricted creator. |
| M-056 | Delete confirmation | PARTIAL (drafts only) | PARTIAL | `DELETE /videos/{id}` is a soft delete in any state (media retained, ADR-020). |
| M-057 | Content status notice | MISSING | MISSING | Same notice read as M-052. |
| M-058 | Creator analytics | MISSING | MISSING | `GET /creators/me/analytics?range=7d|28d` (`CreatorContentAnalytics`); gateway capability `analytics`. |
| M-059 | Video analytics | MISSING | MISSING | `GET /creators/me/videos/{id}/analytics?range=7d|since_published`. |
| M-060 | Analytics empty or unavailable | MISSING | MISSING | Zero-filled responses and 503 map to this state. |

Staging capabilities `media`, `analytics` and `moderation` are closed by default; every client must treat 403, 404 and 503 as normal states.

## Remaining journeys, in priority order

1. **Creator identity (M-036–M-039): this PR.**
2. Library with state filters and paging (M-040). Reuses the existing repository; adds the `state` parameter, `OwnVideoDetail` and the manage entry point.
3. Upload outcomes and status notices (M-050–M-052, M-057). Needs the notice read and approved `reason_code` copy.
4. Video management (M-053–M-056). Publish, unpublish, edit for published and failed states, delete in any state.
5. Analytics (M-058–M-060, then the M-037 summary card).
6. Cover selection (M-045): blocked on an owner decision.

## Journey 1: what changed

| Area | Change |
| --- | --- |
| Defect fixed | The application form accepted `^[A-Za-z0-9_-]{1,40}$`. The gateway and creators service require `^[a-z0-9_]{3,30}$` (DOC-205, `services/creators/service/onboarding.py`), so uppercase, hyphenated, one-character and two-character handles all failed with 400 after the user submitted. The client now enforces the server rule and explains it. The old repository test had encoded the wrong rule (`Storyteller`) and was corrected. |
| Repositories | New `LiveOwnCreatorRepository` (`GET`/`PATCH /creators/me`) with strict `OwnCreator` parsing, field limits and control-character rules mirrored from the gateway, only-changed-field PATCH, and verification that the response echoes the change. Legacy stored handles are preserved (DOC-205 `OwnCreator.handle`). |
| Controllers | `CreatorAccessController` (invited, pending, rejected, restricted, eligible; single in-flight submit; no request when the input is invalid) and `OwnProfileController`. |
| Screens | `LiveBecomeCreatorScreen` (M-036), `LiveCreatorStudioScreen` (M-037), `LiveOwnProfileScreen` (M-038), `LiveEditCreatorProfileScreen` (M-039); routes in `creator_routes.dart`. The old inline onboarding and Studio tiles were removed from `LiveContentScreen`, which is now M-040 only. |
| States | Loading, offline with retry, expired session with sign-in that returns to the same screen, forbidden/restricted ("Not available"), not found, empty bio, handle conflict as a field error, offline and expired while saving keep the typed values. Shared `LiveStateView`. |
| Not shown | No profile photo, sample name, play count, Lone Stars or published count unless the server returned it. |
| Defect caught by the new tests | The app builds `MaterialPageRoute<void>`; `pushNamed<bool>` would have thrown a type error when returning from M-039. The profile screen requests `Object?`. |

## Tests

| Suite | Type | Count |
| --- | --- | --- |
| `test/live_own_creator_repository_test.dart` | Repository contract tests with **mocked HTTP** (`MockClient`) | 10 |
| `test/creator_access_controller_test.dart` | Controller tests with **fake repositories** | 16 |
| `test/live_creator_identity_screens_test.dart` | Widget tests with **fake repositories** and the real design catalog; includes 2.0 text scale | 27 |
| `test/creator_upload_routes_test.dart` | Route dispatch (M-036–M-040 live; M-045 and M-050–M-060 stay protected) | 4 |
| `test/live_creator_upload_test.dart` | Existing; the handle fixture was corrected | 12 |

None uses a real network, gateway, R2, device or secure storage. Not verified: a deployed gateway with the creator-onboarding and media capabilities, a physical device, and screen-reader behaviour beyond live regions.

## Commands

```bash
cd apps/mobile
flutter pub get --enforce-lockfile
flutter analyze
flutter test
cd ../.. && python3 scripts/check_mobile_design.py
```

## Decisions needed

- **M-045 cover:** choose between a gateway endpoint that returns candidate frames, a native frame-extraction dependency, or leaving the server-default cover. Until then the screen stays out.
- **Profile photo:** an upload and storage contract is required before M-038/M-039 can offer it.
- **M-052/M-057:** approved user-facing copy per moderation `reason_code`.
- **M-040 search:** a server-side query parameter, or accept filter-only.
- **M-036 guidelines link:** confirm its destination.
