# FL-B discovery and playback acceptance

Gap-first inspection: [FL-B_discovery_playback_gaps.md](FL-B_discovery_playback_gaps.md), committed before code changes. Baseline source tree matches merged main a2e7303d9f914fa3b671d76781e33904d7156a9c (FL-A included).

| Screen | Mode | Endpoint/native condition | Result |
|---|---|---|---|
| M-017 | Live | GET /videos/following; GET /videos?sort=trending; GET /videos | Separate real sections; independent empty/error states and sign-in prompt. |
| M-018 | Live | GET /videos/following?cursor= | Own following feed; preserved cursor on outage; signed-out prompt. |
| M-019 | Live | GET /videos?category= | Seven category chips plus All; real empty state; search entry. |
| M-020 | Live | GET /videos?sort=trending | Server ordering; no fabricated rankings or popularity numbers. |
| M-021 | Live | GET /videos?q=; GET /creators/search?q= | Entered query opens M-022; no fabricated recent searches. |
| M-022 | Live | GET /videos?q=&category=; GET /creators/search?q= | Video and creator results; independent cursors and creator-only retry; reusable M-098 empty state. |
| M-023 | Native/live | GET /videos?q=&category= | Category sheet applies/reset real query; selected category preserved. |
| M-024 | Live/native | GET /videos; GET /videos/{id}; GET /videos/{id}/playback | Vertical PageView; only visible item mounts video_player; swiping disposes previous player. |
| M-025 | Live/native | GET /videos/{id}; GET /videos/{id}/playback | Poster, metadata, server counts, player, creator link; report to route 71 with video id. |
| M-026 | Live | GET /creators/{id}; GET /creators/{id}/follow | Actual display_name, handle, location, bio and nullable counts; public route 26. |
| M-027 | Live | GET /videos?creator_id=&cursor= | Published public creator-filtered paging; generic title, no sample creator. |
| M-028 | Live | PUT/DELETE /creators/{id}/follow | Optimistic state/count, authoritative result validation and rollback; 401 routes sign-in. |
| M-029 | Live | GET/PUT/DELETE /videos/{id}/like | Server like_count; idempotent state requests; failures retain prior count/state; 401 sign-in. |
| M-030 | Live/native | POST /videos/{id}/shares; DeviceBridge.share | Record first, strict HTTPS public share URL, actual native sheet; unavailable feedback. |
| M-031 | Live state | HTTP 404 | Unavailable state M-031; Explore action; no fabricated alternative video. |
| M-032 | Native state | video_player initialization/buffering | M-032 only during actual pending playback/buffering. |
| M-033 | Native state | video_player initialization/runtime error | M-033 playback error; retry obtains a fresh signed grant/controller. |
| M-034 | Native state | Buffering longer than 5 seconds | M-034 slow connection; no claimed rendition or fake quality switch. |
| M-035 | Live state | HTTP 403 | M-035 restriction; Explore/guidelines actions; no bypass. |

## Files and ownership

Owned route: `apps/mobile/lib/app/routes/discovery_routes.dart`. Discovery: `live_video_repository.dart`, `live_video_screen.dart`; new `discovery_catalog_screen.dart`, `vertical_video_feed.dart`. Engagement: `live_video_engagement_repository.dart`, `live_video_engagement_controller.dart`. Public creators: `live_creator_repository.dart`, `live_creator_screen.dart`, `creator_search_screen.dart`. Tests: new `fl_b_repositories_test.dart`, `fl_b_widgets_test.dart`; existing `live_video_engagement_test.dart` adds the now-required like_count response field. Documentation: gap list, this report, appended coverage table.

No backend, native platform, dependency, startup, home/explore recipe-wrapper, or owner-studio files changed. Route 38 is deliberately not handled by discovery; all public creator links in these files use route 26. FL-C owns owner studio routing. FL-D receives report navigation through route 71 and entityId.

## Contracts and integration boundaries

- Public video pages are `{items,next_cursor}`, at most 20 unique published/public records; category matching and creator matching are validated. Trending preserves server order and requires a null cursor. Following pagination allows the server scan cursor to differ from the last returned item.
- Nullable category, poster_url, like_count and published_at remain honest unknowns for legacy rows. Tags are normalized server-side and validated on read. Signed poster URLs use HTTPS; invalid fields, mismatched identifiers/cursors, duplicates and unsafe URLs fail closed. Current gateway creator ids/user ids and active status remain required for public creator records.
- Creator detail includes display_name/location/bio and nullable follower_count/published_video_count. Follow responses are exactly `{creator_id,following,follower_count}` with nonnegative integer count; successful mutations must confirm the requested state. Like responses include `{video_id,liked,like_count}`. Legacy empty 204 unlike remains compatible with an unavailable count.
- Playback uses the gateway's HTTPS signed URL and expiry. Authenticated playback creates an account-bound watch session with the existing POST `/videos/{id}/watch-sessions` contract; progress POST `/engagement/watch-events` carries only video_id, session_id and observed position_ms. Qualification and points remain entirely server-owned. Self/restricted tracking may fall back only through the existing authorized playback endpoint.
- The CURRENT gateway requires authentication for GET `/videos/{id}/playback`. Public metadata remains browseable while signed out; the server's 401 prompts sign-in for playback. Anonymous streaming would require a backend contract change, not a client bypass.
- Only the visible vertical page plays. Controller/session lifecycle is reset on retry, disposed when swiping away, and paused on app background or navigation through creator/report actions. Initialization has a 15-second timeout. Buffering uses actual player state and a five-second threshold; there is no alternate rendition or quality-control API, and none is claimed.
- POST shares returns exactly `{video_id,share_url}`; URL must be HTTPS without credentials/query/fragment and have path `/videos/<id>`. Native sharing receives only that URL. Configuring KOLOVIBE_PUBLIC_WEB_ORIGIN and native share availability remain deployment/device responsibilities. A failed share does not claim success.
- The M-098 component from FL-A is reused for empty search results. Existing unavailable-dependency recipe captures remain unchanged. No invented plays, follower counts, creator biographies or sample video rows are used by these live views.

## Validation

Flutter commands run from `apps/mobile`; script/diff checks run from the repository root.

| Exact command | Result |
|---|---|
| `FX=/tmp/fl-a-fx; $FX analyze` | PASS — zero issues. |
| `FX=/tmp/fl-a-fx; $FX test --reporter expanded` | PASS — 582 tests, including all 108 unavailable-dependency design captures. |
| `python scripts/check_mobile_design.py` | PASS — 108 entries, 150 assets, valid routes/source slots. |
| `git diff --check` | PASS. |

The 157 new tests cover filters/queries, strict parsing, failure statuses 401/403/404/409/429/503/offline, paging recovery, signed-out prompts, follow rollback, server like counts, share URLs and native delegation, route 26/27/71 entity ids, route-38 ownership, visible-player disposal, buffering/slow/error states and actual-position watch events without client qualification or points. The original 425-test suite also remains passing.

Toolchain: Flutter 3.47.8 / Dart 3.13.7. FX=/tmp/fl-a-fx invokes the pinned SDK with CI=true BOT=true FLUTTER_SUPPRESS_ANALYTICS=true, preventing metadata probing and suppressing analytics. HTTP and native/player fixtures exercise real repository parsing and controller behavior; no deployed-backend, signed media byte delivery, or physical-device acceptance is claimed.

## Remaining acceptance work

Physical-device playback/share, real R2 signed URL delivery/expiry and deployed engagement progression require device/backend UAT. Native provider and server behavior are deliberately represented by fixtures in widget tests. Anonymous playback remains gated by the existing gateway as described above. No lower-data rendition can be selected with the current media contract.
