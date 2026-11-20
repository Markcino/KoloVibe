# Physical iPhone end-to-end checklist (mobile design and live API)

Status: **not yet run on a device.** Nothing in this file has been executed on an iPhone. The Pass / Fail column is blank on purpose. Automated widget tests, the iOS simulator build and the design audit in [mobile-design-coverage.md](../mobile-design-coverage.md) (added by the design audit PR) are not device acceptance.

Companion to the release checklist [R1 iPhone UAT](../operations/R1_iPhone_UAT_Checklist_2026-11-14.md). That document gates R1; this one exercises the redesigned screens (Home M-017 and the audited screens) against the staging gateway.

## Target and build

| Item | Value |
| --- | --- |
| Gateway | `https://mobile-api.cabetechs.shop/api/v1` (all endpoints below are relative to it) |
| Build | Release build from the commit under test, per [apps/mobile/README.md](../../apps/mobile/README.md): `flutter run --release -d <device-id> --dart-define=KOLOVIBE_API_URL=https://mobile-api.cabetechs.shop/api/v1` |
| Devices | One iPhone with a notch and home indicator (390 × 844 class) and, if available, a small iPhone (375 × 667 class, for example iPhone SE) |
| Text size | Run the whole checklist once at the default size and re-run section H at the largest accessibility size |

## Test accounts

Accounts are **provided out of band** by the operator. Do not write emails, passwords, codes, tokens or playback URLs in this file, in screenshots or in the record. Use only the labels below.

| Label | Needed state | Used in |
| --- | --- | --- |
| `NEW-VIEWER` | Mailbox you control; not yet registered | A |
| `VIEWER-1` | Verified email, not a creator, follows nobody | A, B, D, E |
| `VIEWER-2` | Verified email, not a creator, second device or later session | E, F, G |
| `CREATOR-1` | Approved creator, verified email, has at least one published video and one draft | C, E, F, G |
| `CREATOR-2` | Approved creator whose published video `VIEWER-1` can find in trending | D, E |
| Reviewer | Operator-side API access with MFA (no app login) | F, G |

## Record header (fill once per run)

| Field | Value |
| --- | --- |
| Tester / date (UTC) | |
| iPhone model, iOS version | |
| Build commit, Flutter version, build mode | |
| Gateway URL as built | |
| Account labels used | |

For every row record Result (`PASS`, `FAIL` or `N/T`), a screenshot or recording reference, and the UTC time. A FAIL needs a defect identifier. Rows marked **SEC** also gate security sign-off.

## A. Sign-up, verification, login, session restore

| # | Steps | Expected | Endpoints | Result |
| --- | --- | --- | --- | --- |
| A1 | Welcome → Create an account (M-005) as `NEW-VIEWER`. Leave the terms box unticked and submit | Inline message above the button: acknowledge the terms; nothing is sent | none | |
| A2 | Tick the terms and submit valid details | Verify your email (M-006); mail arrives; the screen never shows the password | `POST /auth/register` | |
| A3 | Enter a wrong code | Verification expired (M-008) with a fresh-code form | `POST /auth/verify` | |
| A4 | Request a new code, then press again within two minutes | Neutral confirmation, then a cooldown message that does not reveal account state | `POST /auth/verification/resend` | |
| A5 | Enter the latest code | Make it yours (M-013); the display name is stored | `POST /auth/verify`, `PATCH /me` | |
| A6 | Register again with an existing email | Account already exists (M-012); no hint of password or state | `POST /auth/register` (409) | |
| A7 | Sign in (M-004) with a wrong password | Sign-in problem (M-015); Forgot password offered; password cleared | `POST /auth/login` (401) | |
| A8 | Sign in as `VIEWER-1` | Home (M-017) opens, greeting uses this account's real display name | `POST /auth/login`, `GET /me` | |
| A9 | **SEC-05:** force-close the app without signing out and relaunch from the icon | Home opens without credentials; greeting shows the same name; Profile shows the same email | `POST /auth/refresh`, `GET /me` (one refresh) | |
| A10 | Forgot password → reset with the emailed code; sign in with the new password | Password reset (M-011); older sessions end | `POST /auth/password/reset-request`, `POST /auth/password/reset` | |
| A11 | Airplane mode, relaunch, then restore network and press Try again | You’re offline message with retry; the session is kept | `GET /me` | |
| A12 | Profile → Sign out → confirm | Welcome; relaunch stays signed out; old refresh token is rejected (operator check) | `POST /auth/logout` | |

## B. Home (M-017) — real data only

| # | Steps | Expected | Endpoints | Result |
| --- | --- | --- | --- | --- |
| B1 | Open Home signed in | Wordmark, round initial avatar, "Good morning/afternoon/evening, <your display name>", search bar, hero card, Videos / Explore / Creator Studio tiles, Creators to know, Following, category chips, bottom navigation with Home selected. No name or video that is not in your data | `GET /me`, `GET /videos?sort=trending`, `GET /videos/following`, `GET /creators/{id}` | |
| B2 | Compare the hero card with the first item of Explore → Trending | Same title; poster, category and creator name as the API returns; no duration, plays or other invented figures | `GET /videos?sort=trending` | |
| B3 | Tap the search bar | Search (M-021) opens; entering a term opens Search results (M-022) | `GET /videos?q=`, `GET /creators/search?q=` | |
| B4 | Tap the hero card, the trending row, a creator, See all (creators), See all (Following, which opens the vertical Following feed M-018 with Following / For You tabs), each tile, each category chip, each bottom tab, the avatar | Video details (M-025), creator (M-026), search, Following (M-018), Videos (M-024), Explore (M-019), Creator Studio (M-037, or Become a creator M-036), Explore filtered to that category, Profile (M-079) | as routed | |
| B5 | Sign out; open Home | "Welcome to KoloVibe", Sign in button instead of the avatar, trending still shows, Following asks you to sign in, Follow opens Sign in | `GET /videos?sort=trending` | |
| B6 | With a video-less account or environment, open Home | Each block shows its own empty state; no placeholder content | same | |
| B7 | Airplane mode, pull to refresh | Blocks show their own error with Try again; the rest of the screen stays; recovery works | same | |
| B8 | Pull to refresh with data present | Content reloads once; no duplicates | same | |
| B9 | Rotate to landscape or back to portrait during load | No crash; layout intact | | |

## C. Following (M-018), Explore, search

| # | Steps | Expected | Endpoints | Result |
| --- | --- | --- | --- | --- |
| C1 | As `VIEWER-1` (follows nobody) open Following | Empty state: follow creators to see their originals here | `GET /videos/following` | |
| C2 | Follow `CREATOR-2` (see E), return to Following | Their originals appear as video rows | `GET /videos/following` | |
| C3 | Explore: pick each category chip, then All | Only that category; All restores the list; Load more continues without repeats | `GET /videos?category=&cursor=` | |
| C4 | Search for a term with no match | No search results state (M-098) with Edit search | `GET /videos?q=` | |
| C5 | Search filters sheet: choose a category, Apply, then Reset | Results filter and reset; sheet shows the selected chip | `GET /videos?q=&category=` | |

## D. Playback

| # | Steps | Expected | Endpoints | Result |
| --- | --- | --- | --- | --- |
| D1 | Open a published video from Home, then Play original | Plays through the signed delivery URL; pause and resume work; sound follows the device switch | `GET /videos/{id}`, `POST /videos/{id}/watch-sessions` (or `GET /videos/{id}/playback`) | |
| D2 | Open Videos (M-024), swipe vertically through several videos | Only the visible item plays; the previous player stops | `GET /videos`, playback endpoints | |
| D3 | Poor network (Network Link Conditioner) | Preparing / slow connection state; no claim of a lower rendition | | |
| D4 | Open a removed or unknown video (operator supplies an id) | Video unavailable (M-031); no alternative invented | `GET /videos/{id}` (404) | |
| D5 | Open a video restricted for the account (operator supplies) | Restricted video (M-035) with Explore and guidelines actions | `GET /videos/{id}` (403) | |
| D6 | Watch the qualifying portion as `VIEWER-1` | Progress is reported; no view for skipped time | `POST /engagement/watch-events` | |

## E. Likes, follows and sharing

| # | Steps | Expected | Endpoints | Result |
| --- | --- | --- | --- | --- |
| E1 | Like a video, then Unlike; double-tap quickly | State and count equal the server's; one like per account | `GET/PUT/DELETE /videos/{id}/like` | |
| E2 | Same video on `VIEWER-2` | Count increases by one; each account sees its own state | same | |
| E3 | Follow a creator from Home, from the creator page and from search results | Button shows Following; the follower count on the creator page changes by one; repeat taps do not double count | `GET/PUT/DELETE /creators/{id}/follow` | |
| E4 | Unfollow; background and reopen | State persists | same | |
| E5 | Force a failed follow (airplane mode before tapping) | Button rolls back; message says the change could not be confirmed | same | |
| E6 | Signed out, tap Like or Follow | Sign in opens; returning shows the original screen | | |
| E7 | Share a video | Native share sheet with the public video URL | `POST /videos/{id}/shares` | |

## F. Upload, library, points, moderation (creator and reviewer)

| # | Steps | Expected | Endpoints | Result |
| --- | --- | --- | --- | --- |
| F1 | `VIEWER-1` opens Creator Studio | Become a creator (M-036); application states are real | `GET /creators/me/upload-eligibility`, `GET /creators/me/application` | |
| F2 | `CREATOR-1`: Creator Studio on the deep navy surface; open My video library | Studio (M-037) and library (M-040) list own drafts and originals | `GET /creators/me`, `GET /creators/me/videos` | |
| F3 | Create an original (M-041–M-044): select an MP4 under 50 MB, check, add title, description and category | Local checks run; an unsupported file is refused with a clear message | `POST /videos` | |
| F4 | Upload; interrupt the network mid-way and resume | Real progress; Upload interrupted then resumes; one object | `POST /videos/{id}/upload-intents`, signed `PUT`, `POST /videos/{id}/upload-status` | |
| F5 | Wait for preparing and pending review; reviewer approves (operator, MFA) | Preparing → pending moderation → "Approved, not public" | `GET /videos/{id}/upload-status` | |
| F6 | Manage video (M-053): Publish, confirm; Unpublish, confirm; edit details (once processed, choose a cover moment with the slider and confirm the new poster after processing); delete a draft | Each step asks first; public only after Publish; another account stops seeing it after Unpublish | `GET /creators/me/videos/{id}`, `POST /videos/{id}/publish` and `/unpublish`, `PATCH /videos/{id}` (details, cover moment), `DELETE /videos/{id}` | |
| F7 | Lone Stars (M-061–M-069) as `CREATOR-1` | Balance equals ledger; non-cash wording; withheld and reversed explained; empty state for a new creator | `GET /creators/me/points`, `GET /creators/me/points/entries` | |
| F8 | Report a video as `VIEWER-1` (M-071–M-073): choose reason, add details, submit | Receipt; reporting again shows Already reported (M-075) | `POST /reports`, `GET /me/reports` | |
| F9 | Offline during Submit | Report submission error (M-074); text kept for retry | `POST /reports` | |
| F10 | Reviewer removes a `CREATOR-1` video (operator); `CREATOR-1` opens the notice and account status (M-076, M-077) | Decision, reason code and date shown; a **Request a review** button and the M-078 statement form appear only when the server says the decision is appealable; sending posts once and the notice then shows the request | `GET /creators/me/videos/{id}/notice`, `GET /me/standing`, `POST /videos/{id}/appeals` | |

## G. Settings and system states

| # | Steps | Expected | Endpoints | Result |
| --- | --- | --- | --- | --- |
| G1 | Profile (M-079): open Account settings, Privacy, Security, Notifications, Active sessions | Each opens; rows show titles and chevrons; Sign out confirms first | `GET /me`, `GET /me/preferences`, `GET /me/sessions` | |
| G2 | Change a notification preference, relaunch | Persisted; device permission is managed in iOS Settings only | `PATCH /me/preferences` | |
| G3 | Revoke another session on a second device | That device is rejected on next use | `DELETE /me/sessions/{id}` | |
| G4 | Change password | Re-authentication where required; other sessions end | `PATCH /me/password`, `POST /me/reauthenticate` | |
| G5 | Delete account request flow (do not complete on shared accounts) | Confirm it's you (M-016) then confirmation; intake only | `POST /me/privacy-requests` | |
| G6 | Induce 401 (operator revokes), 403, 429, 503 | Session expired, Access denied, Rate limit, Service unavailable states with the right action | | |
| G7 | Compatibility notice (operator sets a newer minimum) | Update required blocks; optional update can be dismissed | `GET /app/compatibility` | |

## H. Layout, text size and keyboard (design conformance)

| # | Steps | Expected | Result |
| --- | --- | --- | --- |
| H1 | Compare Home, Search, Sign in, Create an account, Profile, Lone Stars and a system state with the exports in `docs/designed/` | Colours, fonts (Plus Jakarta Sans and Inter), spacing and navigation match, apart from the deviations listed in [mobile-design-coverage.md](../mobile-design-coverage.md) (added by the design audit PR) | |
| H2 | Largest accessibility text size on every screen visited | Nothing clipped or overlapping; every control still reachable by scrolling | |
| H3 | Open the keyboard on Sign in, Create an account, Edit profile, Report details, Create an original | The focused field and the primary button stay reachable; dragging the page closes the keyboard | |
| H4 | Notch and home indicator areas | Content clears the status bar and the home indicator; the bottom navigation sits above the indicator | |
| H5 | Small iPhone (375 × 667), if available | Same screens, no horizontal scrolling | |
| H6 | Light mode only | The app follows its light theme regardless of the iOS appearance setting | |

## Sign-off

| Result | Count |
| --- | --- |
| PASS / FAIL / N/T | |

Sections A and D to F keep the R1 NO-GO rule from the R1 UAT checklist. Until a person fills this table on a device, device acceptance is **not** claimed.
