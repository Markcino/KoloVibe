# Simulator application test — 26 November 2026

Every result below was observed in the running app on the iOS Simulator, against a live local backend, and cross-checked with the gateway access log ([gateway-access.log](gateway-access.log), ids replaced by `{id}`). A row is PASS only if the screen and the server response both showed it. Nothing here is staging, device or production acceptance.

## Set-up

| Item | Value |
| --- | --- |
| Commit | `b907486` (`main`, PR #255 merged) |
| Device | iPhone 17 Pro simulator, iOS 26.3 (402 × 874 pt) |
| Host | macOS 15.8.2, Xcode 26.3, Flutter 3.50.1 (the repository's run card names 3.47.8; the lockfile resolved and the build succeeded) |
| App build | `flutter build ios --simulator --debug`, `KOLOVIBE_API_URL=http://127.0.0.1:<gateway>/api/v1`. The simulator supports debug builds only, and the app accepts plain HTTP only for loopback in debug. |
| Backend | The repository's own disposable stack, [`scripts/phase11/stack_up.py`](../../../../scripts/phase11/stack_up.py) with `P11_NO_BROKER=1`: task-owned TLS PostgreSQL with one role per service, Identity, Content, Creators, Moderation, Engagement, Points, Audit, Business, Gateway and the console on loopback, captured mail. All ten answered `/health/live` with 200 ([service-health.txt](service-health.txt)). |
| Not available | Docker (not installed, so `infra/docker` was not used), RabbitMQ (not installed), real Cloudflare R2 storage and media. The harness gives Content throwaway R2 values, so upload transfers and playback cannot complete. |
| Test data | Two accounts created through the app and API (`viewer1@example.test`, `creator1@example.test`; passwords kept out of the repository). The harness seeded 21 published fixture videos; I made them watchable and credited them to the creator with the harness's own `arm_fixture_videos`, then set their titles and categories by SQL so filters could be told apart. These videos have no real media. |

## Results

Counted by table row: **33 PASS, 0 FAIL, 4 BLOCKED, 10 NOT RUN** (a NOT RUN row may group several checklist steps). D1 and F4 count as BLOCKED even though their API calls passed. The defects found are listed in the next section.

### Accounts and session

| Id | Step | Result | Evidence |
| --- | --- | --- | --- |
| A1 | Submit sign-up without ticking the terms | PASS: inline "Accept the Terms of Service and the Privacy Notice to continue"; no request sent | [A1](screenshots/A1_terms_required.png) |
| A2 | Submit valid details with terms ticked | PASS: `POST /auth/register` 201, Verify your email screen, code captured by the mail fixture | [A2](screenshots/A2_verify_email.png) |
| A3 | Enter a wrong code | PASS: `POST /auth/verify` 400, inline "That code didn't work". The checklist expects the M-008 screen; the app shows an inline error instead | [A3](screenshots/A3_wrong_code.png) |
| A4 | Resend and cooldown | NOT RUN | |
| A5 | Enter the right code | PASS: `POST /auth/verify` 200, Sign in with "Email verified" notice and email prefilled | [A5](screenshots/A5_verified.png) |
| A6 | Register an existing email | NOT RUN | |
| A7 | Sign in with a wrong password | PASS: `POST /auth/login` 401, Sign-in problem screen, password cleared, Recover my account offered | [A7](screenshots/A7_wrong_password.png) |
| A8 | Sign in | PASS: login 200, `GET /me` 200, Make it yours (M-013), `PATCH /me` 200, then Home greets "Sim Viewer" | [A8](screenshots/A8_home_signed_in.png), [B1](screenshots/B1_home.png) |
| A9 | Force-close and relaunch | PASS: `POST /auth/refresh` 200 then `/me` 200; Home opens signed in with no credentials asked | [A9](screenshots/A9_relaunch_restored.png) |
| — | Access-token expiry while in use | PASS: three times a request got 401, the app refreshed (200) and retried successfully (report submit, upload create, account status) | gateway log |
| A10 | Password reset | NOT RUN | |
| A11 | Offline relaunch | NOT RUN | |
| A12 | Sign out, then relaunch | PASS: confirmation screen, `POST /auth/logout` 204, Welcome; relaunch stays signed out and calls `GET /app/compatibility` 200. Server-side rejection of the old refresh token was not checked | [confirm](screenshots/A12_signout_confirm.png), [after](screenshots/A12_signed_out.png), [relaunch](screenshots/A12_relaunch_stays_signed_out.png) |

### Discovery and playback

| Id | Step | Result | Evidence |
| --- | --- | --- | --- |
| B1 | Home signed in | PASS with defect SIM-01: wordmark, avatar initial, search, shortcuts, category chips; trending and following blocks load from the API | [B1](screenshots/B1_home.png) |
| B2 | Hero matches trending | BLOCKED: trending stays empty because no qualified views can happen without media (SIM-03) | [B8](screenshots/B8_home_refreshed.png) |
| B3 | Search | PASS with defect SIM-05: `GET /videos?q=` and `/creators/search?q=` return and the result list shows "Sim original 05" | [results](screenshots/B3_search_all_categories.png) |
| B5 | Signed-out Home | NOT RUN: the Welcome screen offers no way to browse signed out | |
| B8 | Pull to refresh | PASS: one reload of `/me`, trending and following | [B8](screenshots/B8_home_refreshed.png) |
| C2 | Following after a follow | PASS: `GET /videos/following` returns the followed creator's videos and Home lists them | [C2](screenshots/C2_home_following.png) |
| C3 | Explore categories | PASS: Comedy sends `category=comedy` and shows only comedy items. Load more not checked | [all](screenshots/C3_explore.png), [comedy](screenshots/C3_explore_comedy.png) |
| C4 | No-result search | PASS: "No stories found. Yet." with Edit search | [C4](screenshots/B3_search_results.png) |
| C5 | Filter sheet, Reset, Apply | PASS: sheet shows the selected chip; Reset selects All categories; Apply re-queries without the category | [sheet](screenshots/C5_filter_sheet.png), [reset](screenshots/C5_reset_results.png) |
| D1 | Open a video, Play original | API PASS, playback BLOCKED: detail, like state and creator load; `GET /playback` 200 and `POST /watch-sessions` 200, then "Playback paused, we couldn't load this video", because the signed URL points at fixture storage with no object | [detail](screenshots/D1_video_detail.png), [play](screenshots/D1_play_original.png) |
| D2 | Vertical Videos feed | PASS for the feed; playback BLOCKED as D1. Swiping moves to the next item and requests playback for that item only | [1](screenshots/D2_videos_feed.png), [2](screenshots/D2_videos_feed_next.png) |
| D4 | Unpublished video | PASS (server side): after the creator unpublished it, `GET /videos/{id}` returned 404; republishing restored 200 | gateway log |
| D3, D5, D6 | Slow network, restricted video, qualified view | NOT RUN (D6 needs real playback) | |

### Engagement and reporting

| Id | Step | Result | Evidence |
| --- | --- | --- | --- |
| E1 | Like | PASS with defect SIM-10: `PUT /like` 200, button becomes Unlike, count 0 → 1. The creator's Manage video later showed Likes 1 | [E1](screenshots/E1_liked.png) |
| E3 | Follow from the creator page | PASS: `PUT /follow` 200, Following, followers 0 → 1 | [before](screenshots/E3_creator_profile.png), [after](screenshots/E3_followed.png) |
| E7 | Share | BLOCKED by configuration and an open owner decision, see SIM-02: `POST /shares` 503 `share_unavailable` because no public web origin is set; the app showed no message | [E7](screenshots/E7_share.png) |
| E2, E4–E6 | Second account, persistence, failed follow, signed-out like | NOT RUN | |
| F8 | Report a video | PASS: six reasons, details screen with 0/2000 counter and privacy notice, `POST /reports` 201, receipt saying reporting does not remove content | [reasons](screenshots/F8_report_reasons.png), [details](screenshots/F8_report_details.png), [receipt](screenshots/F8_report_submitted.png) |

### Creator

| Id | Step | Result | Evidence |
| --- | --- | --- | --- |
| F1 | Viewer opens Creator Studio | PASS: upload eligibility 200 and application 404 lead to the "Viewer account, invitations are issued by KoloVibe" gate | [F1](screenshots/F1_creator_studio_viewer.png) |
| — | Role-aware Profile | PASS: the viewer sees "Roles: viewer" and Become a creator; the creator sees "Creator enabled", Open Creator Studio, Create a video and Lone Stars | [viewer](screenshots/G1_profile.png), [creator](screenshots/CR_signin.png), [menu](screenshots/G1_creator_profile_menu.png) |
| F2 | Studio and library | PASS: profile, 7-day analytics (0 qualified plays, which is correct here) and a library of 21 published videos with Published and In progress filters | [studio](screenshots/F2_creator_studio.png), [library](screenshots/F2_video_library.png) |
| F3 | Pick an MP4 and fill in details | PASS: a 4-second 720×1280 MP4 added to the simulator's library was picked through the system picker and checked locally; title, category and rights attestation filled | [picker](screenshots/F3_picker.png), [file](screenshots/F3_file_selected.png), [details](screenshots/F3_details_filled.png) |
| F4 | Upload | Partial, transfer BLOCKED: `POST /videos` 201 and `POST /upload-intents` 200, then the transfer to storage never progressed; after the 3-minute timeout the app showed "Upload interrupted, story safe on your device" with retry (SIM-09) | [uploading](screenshots/F4_upload.png), [interrupted](screenshots/F4_upload_result.png) |
| F5 | Processing and review | NOT RUN (needs a stored object and the media worker) | |
| F6 | Unpublish and publish | PASS: both confirmations; `POST /unpublish` 200 shows "Approved, not public"; `POST /publish` 200 shows Public | [manage](screenshots/F6_manage_video.png), [confirm](screenshots/F6_unpublish_confirm.png), [unpublished](screenshots/F6_unpublished.png), [republished](screenshots/F6_republished.png) |
| F7 | Lone Stars | PASS for the empty state: `GET /creators/me/points` 200, non-cash wording. Awards need the broker and were not run | [F7](screenshots/F7_lone_stars.png) |
| F10 | Account status (decision F) | PASS for the no-measure state: `GET /me/standing` 200 and `GET /creators/me/restrictions` 200, "Your creator account is active", no notices or measures. Applying a measure was not run | [F10](screenshots/F10_account_status.png) |

### Settings and Businesses

| Id | Step | Result | Evidence |
| --- | --- | --- | --- |
| G1 | Profile, Account settings, Active sessions, Community guidelines | PASS with defect SIM-07: each opens; `GET /me/sessions` 200 lists the current session | [settings](screenshots/G1_account_settings.png), [sessions](screenshots/G1_active_sessions.png), [guidelines](screenshots/G1_community_guidelines.png) |
| G2 | Notification preference survives a relaunch | PASS: `PATCH /me/preferences` 200; after force-close and relaunch, Email notifications was still on | [on](screenshots/G2_email_pref_on.png), [after relaunch](screenshots/G2_pref_persisted_after_relaunch.png) |
| G3–G7 | Revoke, change password, delete request, forced errors, update notice | NOT RUN | |
| BZ1 | Businesses directory | PASS for the empty state: `GET /business-categories` and `GET /businesses` 200, empty-state copy, Your activity links | [BZ1](screenshots/BZ1_businesses.png) |
| BZ2 | My businesses | PASS: `GET /me/businesses` 200, Register a business and Join a business team | [BZ2](screenshots/BZ2_my_businesses.png) |
| BZ3 | Register a business without an invitation | PASS: `POST /me/businesses` 403, "Invitation required"; leaving shows the unsaved-changes guard | [form](screenshots/BZ3_register_business.png), [refused](screenshots/BZ3_register_refused_not_invited.png) |
| — | Invited owner and staff journeys, reviews, questions | NOT RUN: needs an operator invitation and categories created in the console | |

## Defects found

| Id | Severity | Where | What was observed |
| --- | --- | --- | --- |
| SIM-01 | Low | Home greeting, [`home_dashboard.dart:362`](../../../../apps/mobile/lib/features/discovery/home_dashboard.dart) | In the morning the greeting appends ☀️, which renders as two missing-glyph boxes on the iOS simulator |
| SIM-02 | Medium, needs an owner decision | Share, [`services/gateway/service/shares.py`](../../../../services/gateway/service/shares.py) | Share returns 503 `share_unavailable` unless `KOLOVIBE_PUBLIC_WEB_ORIGIN` is set. The standing directive says there is no public website, so share links have no destination. The app gave no visible feedback |
| SIM-03 | Low | Home trending, Creators to know | Both stay empty while 21 public videos exist. The copy "Published originals will appear here" suggests nothing is published. Trending depends on engagement signals, so this is expected locally, but the message is misleading |
| SIM-04 | Low | Explore | After liking "Sim original 17", returning to Explore still showed "0 likes" until it reloaded |
| SIM-05 | Low | Search from Explore | Searching while the Comedy chip was selected sent `category=comedy` and returned "No results" for an existing Short films video. The results screen shows no category chip, so the filter is invisible until the filter sheet is opened |
| SIM-06 | Low | Bottom navigation | When a viewer opens Creator Studio from the Create tab or the Home shortcut, the Profile tab is highlighted instead of Create |
| SIM-07 | Low | Active sessions | The session row has no horizontal padding and touches the screen edge; on Sign out confirmation the button sits directly under the body text with no spacing |
| SIM-08 | Low | Account status | "Publishing is available" appears as both the title and the body of the same card |
| SIM-09 | Low | Upload | With storage unreachable, the progress stayed at 0 % for the full 3-minute timeout before the interrupted state. Observed only against unreachable storage |
| SIM-10 | Low | Video detail | Shows "1 likes" |

No crash, freeze or unhandled error screen occurred, and no service log contained a traceback.

## What this run cannot show

- Real playback, upload transfer, FFmpeg processing, review and poster generation need R2 and the media worker.
- Qualified views, trending, Lone Stars awards and the Engagement → Points path need RabbitMQ.
- Moderation decisions, creator measures, Business invitations and categories need the console with an MFA-enrolled reviewer; not driven in this run.
- Events, Advertising and Finance have no app screens to test.
- Debug-mode performance on this host was slow (typed characters could be dropped during screen transitions), so no performance conclusion is drawn.
