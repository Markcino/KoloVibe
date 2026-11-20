# Mobile design parity review — 20 November 2026

Baseline: `main` at `c8df78b`. Branches: `claude/gracious-darwin-a9a0c3` (harness, M-001–M-035), `…-group-c` (M-036–M-060), `…-group-de` (M-061–M-108 and this document). Tracking issue: #100.

**Result: 8 visually matched, 99 functional with a specified deviation, 1 not verified.** This supersedes the 20 November “3 / 69 / 36” table in `mobile-design-coverage.md`, which was a baseline.

## Method and limits

- Every picture in [`evidence/mobile-parity-2026-11-20/`](evidence/mobile-parity-2026-11-20/) has three panels: the approved Figma export (402 × 874), the Flutter render at 390 × 844 (status bar 47 pt, home indicator 34 pt) and at 375 × 667 (status bar 20 pt, no indicator). 120 pictures: 108 screens plus 12 additional states. Regenerate: `AUDIT_DIR=/tmp/a flutter test test/design_audit_test.dart test/home_dashboard_test.dart` then `python3 scripts/compose_mobile_evidence.py /tmp/a/raw docs/evidence/mobile-parity-2026-11-20`.
- Every capture is also rendered at 2× text size and fails on any layout exception; all pass. Keyboard inset is exercised only for Home (`home_dashboard_test.dart`).
- The live Figma node for M-001 was compared with its local export through the Figma tool; they match, so `docs/designed/` is used for the rest.
- These are **widget-test renders, not device screenshots**: no status bar, no real video frames (an in-memory player is used), scripted repositories, and API-supplied posters replaced by local design artwork through a test-only hook (`posterProviderOverride`). Production always loads signed URLs.
- Fake-gateway tests establish wiring only. Nothing here is authenticated staging acceptance or physical-device acceptance.
- “Visually matched” means layout, type, colour and copy equal the export apart from: status bar and home indicator are not drawn; sample text and imagery differ. Any other visible difference is listed.

## Decisions and gaps

| ID | Screen(s) | Finding | Decision needed |
| --- | --- | --- | --- |
| D-1 | M-006, M-010 | The identity service emails `secrets.token_urlsafe(48)`: a 64-character token, not six digits. | Product/security: either issue a short numeric code with attempt limits (ADR-013 change) or redesign the entry. Until then the boxed single field is used. |
| D-2 | M-045 | `PATCH /videos/{id}` accepts `cover_time_ms` only; no frame thumbnails and the duration is unknown before processing. | Approve a frame-sprite/thumbnail endpoint, or accept the cover-moment slider in Edit details as the design. |
| D-3 | M-034 | The design shows a Data Saver sheet and “lower-data playback”. R1 has one FFmpeg rendition. | Design: replace with a slow-connection state; or add renditions (outside R1). |
| D-4 | M-019 | Curated hero and “Curated collection” label have no endpoint. | Confirm the “Latest original” adaptation, or add curation. |
| D-5 | M-021 | Recent searches are personal data. | Privacy review before device-local history with a Clear control. |
| D-6 | M-027 | No per-creator popularity; the service has global trending only. | Accept “Trending” or add a per-creator popular sort. |
| D-7 | M-078 | The server-eligible statement form has no export. | Design approval of the form; server gating is unchanged. |
| D-8 | Brand | In-app emblem now follows the approved Figma node (red play mark). Launcher icons remain the owner-supplied logo (`docs/mobile-ui-implementation.md`). | Owner: confirm one mark for both. |
| D-9 | Plays | Public video JSON carries no play count; analytics are creator-only. Duration **is** carried (`duration_ms`/`duration_seconds`) and is now shown. | Approve a public view count if plays should appear on cards. |
| D-10 | Photos | No profile-photo endpoint; photo moderation pending. | Product/moderation policy. |

Resolved by this work (the register previously listed them as gaps): creator **handle** on the player caption (`GET /creators/{id}`), public **duration**, and **analytics** (`GET /creators/me/analytics`, `/creators/me/videos/{id}/analytics`, now live as M-058–M-060 and the Studio card).

## Per-screen results

| Screen | Result | Evidence (390 × 844 and 375 × 667) | Remaining difference |
| --- | --- | --- | --- |
| M-001 · Splash Screen | Visually matched | [M-001](evidence/mobile-parity-2026-11-20/M-001.png) | None beyond the common list. |
| M-002 · Welcome Screen | Visually matched | [M-002](evidence/mobile-parity-2026-11-20/M-002.png) | None beyond the common list. |
| M-003 · A world of original voices | Visually matched | [M-003](evidence/mobile-parity-2026-11-20/M-003.png) | Hero is about 5 pt taller; otherwise equal. |
| M-004 · Sign in | Functional, with specified deviation | [M-004](evidence/mobile-parity-2026-11-20/M-004.png) | The export draws the inline-error state (red field, “Check your email and password…”); the app shows that failure on M-015 instead. The default state otherwise matches. |
| M-005 · Create an account | Functional, with specified deviation | [M-005](evidence/mobile-parity-2026-11-20/M-005.png) | No “Confirm password” field (the design has none; show/hide remains). Terms line says “Privacy information”, not “Privacy Policy” (no approved policy page). No green “Password meets…” helper: the service, not the app, checks requirements. |
| M-006 · Verify your email | Functional, with specified deviation | [M-006](evidence/mobile-parity-2026-11-20/M-006.png), [verifying](evidence/mobile-parity-2026-11-20/M-006-verifying.png) | One masked field instead of six digit boxes: the emailed code is a 64-character URL-safe token. DECISION D-1. |
| M-007 · Resend verification | Functional, with specified deviation | [M-007](evidence/mobile-parity-2026-11-20/M-007.png), [sent](evidence/mobile-parity-2026-11-20/M-007-sent.png), [unavailable](evidence/mobile-parity-2026-11-20/M-007-unavailable.png) | Sent and throttled states are drawn as designed. The card adds “If eligible, you will receive a new code.” (privacy-preserving service wording). Resend form before a request has no export. |
| M-008 · Verification expired | Visually matched | [M-008](evidence/mobile-parity-2026-11-20/M-008.png) | None beyond the common list (email value is the signed-in sample). |
| M-009 · Forgot password | Functional, with specified deviation | [M-009](evidence/mobile-parity-2026-11-20/M-009.png), [sent](evidence/mobile-parity-2026-11-20/M-009-sent.png) | Sent state is drawn as designed; adds an “Enter reset code” action so the person can continue. |
| M-010 · Reset password | Functional, with specified deviation | [M-010](evidence/mobile-parity-2026-11-20/M-010.png) | Adds a boxed reset-code field above the passwords (the API requires the emailed token). Requirements note copy shortened. |
| M-011 · Password reset | Visually matched | [M-011](evidence/mobile-parity-2026-11-20/M-011.png), [done](evidence/mobile-parity-2026-11-20/M-011-done.png) | None beyond the common list. |
| M-012 · Account already exists | Visually matched | [M-012](evidence/mobile-parity-2026-11-20/M-012.png), [existing](evidence/mobile-parity-2026-11-20/M-012-existing.png) | None beyond the common list. |
| M-013 · Make it yours | Functional, with specified deviation | [M-013](evidence/mobile-parity-2026-11-20/M-013.png) | Initial avatar, not a photo (no photo endpoint). “Email verified” pill omitted (no verification flag in GET /me). |
| M-014 · Your voice belongs here | Functional, with specified deviation | [M-014](evidence/mobile-parity-2026-11-20/M-014.png) | Sample credit line (“Ama Kollie · Culture · 02:46”) and play button omitted: the artwork is static, not a video or a creator. |
| M-015 · Sign-in problem | Visually matched | [M-015](evidence/mobile-parity-2026-11-20/M-015.png) | None beyond the common list. |
| M-016 · Confirm it’s you | Functional, with specified deviation | [M-016](evidence/mobile-parity-2026-11-20/M-016.png) | Lead copy differs: the app says “Verify your identity before continuing. Nothing is deleted at this step.” (the screen also serves non-deletion confirmations); otherwise equal. |
| M-017 · Multi-Service Home Dashboard | Functional, with specified deviation | [M-017](evidence/mobile-parity-2026-11-20/M-017.png) | Following block added (no other route to M-018); creators come from trending videos; initial avatars; no duration or play counts; all seven categories shown. |
| M-018 · Following Video Feed | Functional, with specified deviation | [M-018](evidence/mobile-parity-2026-11-20/M-018.png) | Real frames are not rendered in the widget capture (black video). @handle now resolves from GET /creators/{id}; creator photo is an initial (no photo contract). Device playback not compared. |
| M-019 · Explore & Discover | Functional, with specified deviation | [M-019](evidence/mobile-parity-2026-11-20/M-019.png) | Hero, “Fresh perspectives” and spotlight come from the newest originals and their creator, not editorial curation: eyebrow reads “LATEST ORIGINAL”, not “CURATED COLLECTION”. Spotlight action is “View”, not “Follow”. No play counts. DECISION D-4. |
| M-020 · Trending originals | Functional, with specified deviation | [M-020](evidence/mobile-parity-2026-11-20/M-020.png), [fresh](evidence/mobile-parity-2026-11-20/M-020-fresh.png) | Trending / Fresh picks tabs and hero are live; no ranks (“01 ·”, “02 ·”) or play counts. Rows have no overflow menu. |
| M-021 · Search | Functional, with specified deviation | [M-021](evidence/mobile-parity-2026-11-20/M-021.png) | No recent searches or suggested chips: nothing stores them and they are personal data. “Browse categories” chips are shown instead. DECISION D-5. |
| M-022 · Search results | Functional, with specified deviation | [M-022](evidence/mobile-parity-2026-11-20/M-022.png), [creators](evidence/mobile-parity-2026-11-20/M-022-creators.png) | Filter chips, results line and creator bio are live. No related searches (no endpoint); no play counts or creator names on video rows. |
| M-023 · Search filters | Functional, with specified deviation | [M-023](evidence/mobile-parity-2026-11-20/M-023.png), [page](evidence/mobile-parity-2026-11-20/M-023-page.png) | Sheet matches. Under the scrim the app bar reads “Search results”, the export “Search filters”. |
| M-024 · Full-Screen Vertical Video Feed / Player | Functional, with specified deviation | [M-024](evidence/mobile-parity-2026-11-20/M-024.png) | Same differences as M-018 (public feed, For You selected). |
| M-025 · Video Details | Functional, with specified deviation | [M-025](evidence/mobile-parity-2026-11-20/M-025.png) | Light detail page with poster, creator row, tags, duration and actions, not the export’s dark player with a bottom sheet; no play count. Redesign not done. |
| M-026 · Ama Kollie | Functional, with specified deviation | [M-026](evidence/mobile-parity-2026-11-20/M-026.png) | No tagline headline, no Videos/About tabs, no Featured original card (creator JSON has no tagline); initial avatar. Metrics, Follow and bio are live. |
| M-027 · Ama’s published videos | Functional, with specified deviation | [M-027](evidence/mobile-parity-2026-11-20/M-027.png) | Grid, count and header are live. Second tab reads “Trending” (global trending filtered to this creator), not “Popular”; no play counts; header action is “Profile”, not Follow. DECISION D-6. |
| M-028 · Follow / Unfollow State | Functional, with specified deviation | [M-028](evidence/mobile-parity-2026-11-20/M-028.png) | Following state, “You’re connected” note and confirmation toast are live. Same profile differences as M-026. |
| M-029 · Like / Unlike State | Functional, with specified deviation | [M-029](evidence/mobile-parity-2026-11-20/M-029.png) | “Liked · Tap heart to unlike” toast and server like count are live. Video frames are not rendered in the capture. |
| M-030 · Native Share State | Functional, with specified deviation | [M-030](evidence/mobile-parity-2026-11-20/M-030.png) | Share sheet follows the design. AirDrop / Mail / Messages chips omitted: they are operating-system targets and not in-app controls. |
| M-031 · Video unavailable | Functional, with specified deviation | [M-031](evidence/mobile-parity-2026-11-20/M-031.png) | No bottom navigation on this error page. “Try another story” shows the service’s newest other original. Row has no overflow menu and shows category and duration, not creator. |
| M-032 · Video Buffering | Functional, with specified deviation | [M-032](evidence/mobile-parity-2026-11-20/M-032.png) | Spinner and text are live; no video frames in the capture. |
| M-033 · Video Playback Error | Functional, with specified deviation | [M-033](evidence/mobile-parity-2026-11-20/M-033.png) | “Playback paused” card is live. The export’s “Use Data Saver” hint is omitted: R1 has one rendition. Rail avatar sits beside the card. |
| M-034 · Low-Bandwidth Playback | Functional, with specified deviation | [M-034](evidence/mobile-parity-2026-11-20/M-034.png) | Slow-connection overlay is live. The export’s Data Saver sheet (toggle, carrier advice) is not implemented: R1 has a single FFmpeg rendition. DECISION D-3. |
| M-035 · Restricted video | Functional, with specified deviation | [M-035](evidence/mobile-parity-2026-11-20/M-035.png) | The bottom navigation is not drawn on this error page; otherwise equal. |
| M-036 · Become a creator | Functional, with specified deviation | [M-036](evidence/mobile-parity-2026-11-20/M-036.png) | No hero image; copy follows the real invitation/application states. |
| M-037 · Creator Studio | Functional, with specified deviation | [M-037](evidence/mobile-parity-2026-11-20/M-037.png), [analytics](evidence/mobile-parity-2026-11-20/M-037-analytics.png) | Analytics card (real last-7-day totals and bars) appears when analytics return data; “Confirmed Lone Stars” card is a list row, and the surface lists Analytics / Library / Profile rows. |
| M-038 · Creator profile | Functional, with specified deviation | [M-038](evidence/mobile-parity-2026-11-20/M-038.png) | No profile photo; fields drawn as rows and a note, not the export’s identity card. |
| M-039 · Edit creator profile | Functional, with specified deviation | [M-039](evidence/mobile-parity-2026-11-20/M-039.png) | Material floating labels and counters; no photo. |
| M-040 · My video library | Functional, with specified deviation | [M-040](evidence/mobile-parity-2026-11-20/M-040.png) | Thumbnails, status colour and state filters (All / Published / In progress) are live. No search field (no query parameter) and no “Upload a new original” button. |
| M-041 · Create an original | Functional, with specified deviation | [M-041](evidence/mobile-parity-2026-11-20/M-041.png) | Headline, card, pills and note match in structure. “Use a stable connection…” footnote not drawn. |
| M-042 · Select a video | Functional, with specified deviation | [M-042](evidence/mobile-parity-2026-11-20/M-042.png) | The export shows an in-app media grid; selection uses the operating-system video picker, which has no in-app screen. |
| M-043 · Check your file | Functional, with specified deviation | [M-043](evidence/mobile-parity-2026-11-20/M-043.png) | File summary row, not the export’s thumbnail hero card (no frame source before upload). |
| M-044 · Tell the story | Functional, with specified deviation | [M-044](evidence/mobile-parity-2026-11-20/M-044.png) | Material floating labels; no thumbnail strip; primary action is “Create and upload” (the service cannot offer a cover before processing). |
| M-045 · Choose a cover | Not verified | [M-045](evidence/mobile-parity-2026-11-20/M-045.png) | No screen: the service accepts only cover_time_ms after the duration is known and returns no frame thumbnails. Implemented instead as a cover-moment slider in Edit details (M-054). DECISION D-2. |
| M-046 · Uploading your original | Functional, with specified deviation | [M-046](evidence/mobile-parity-2026-11-20/M-046.png) | Progress card with real percentage; no thumbnail hero; “Your connection is slow” note and Cancel upload not drawn. |
| M-047 · Upload interrupted | Functional, with specified deviation | [M-047](evidence/mobile-parity-2026-11-20/M-047.png) | Medallion, headline, notes and actions match; the thumbnail summary row is not drawn. |
| M-048 · Upload failed | Functional, with specified deviation | [M-048](evidence/mobile-parity-2026-11-20/M-048.png) | Alert note, copy and actions match; the thumbnail summary row is not drawn. |
| M-049 · Preparing your video | Functional, with specified deviation | [M-049](evidence/mobile-parity-2026-11-20/M-049.png) | Card and copy match; no thumbnail hero; progress is indeterminate. |
| M-050 · Pending moderation | Functional, with specified deviation | [M-050](evidence/mobile-parity-2026-11-20/M-050.png) | Copy and note follow the design; no thumbnail summary row. |
| M-051 · Your original is published | Functional, with specified deviation | [M-051](evidence/mobile-parity-2026-11-20/M-051.png) | Deliberately “approved, not public”: the service’s published state is approval; the export’s “Published successfully / available to viewers” would be untrue until the creator publishes. |
| M-052 · Video rejected | Functional, with specified deviation | [M-052](evidence/mobile-parity-2026-11-20/M-052.png) | Alert note and actions follow the design; no thumbnail summary row. |
| M-053 · Manage video | Functional, with specified deviation | [M-053](evidence/mobile-parity-2026-11-20/M-053.png) | Hero, status badge, qualified plays, likes and rows are live. Rows read “Edit details” and “Unpublish” (not “Edit title and description”, “Unpublish video”); hero lacks creator name. |
| M-054 · Edit video details | Functional, with specified deviation | [M-054](evidence/mobile-parity-2026-11-20/M-054.png) | Edit is a dialog with floating labels, not the export’s full page. |
| M-055 · Unpublish confirmation | Functional, with specified deviation | [M-055](evidence/mobile-parity-2026-11-20/M-055.png) | Dialog matches; body copy is longer than the export. |
| M-056 · Delete video confirmation | Functional, with specified deviation | [M-056](evidence/mobile-parity-2026-11-20/M-056.png) | Dialog and typed DELETE match; body copy is longer than the export. |
| M-057 · Content status notice | Functional, with specified deviation | [M-057](evidence/mobile-parity-2026-11-20/M-057.png) | Shares the M-076 notice implementation; thumbnail summary row and per-notice medallion not drawn. |
| M-058 · Creator analytics | Functional, with specified deviation | [M-058](evidence/mobile-parity-2026-11-20/M-058.png) | Real totals, bars and top originals. No “vs previous period” deltas (not in the API); top originals have no thumbnail; copy says counts, not “illustrative”. |
| M-059 · Video analytics | Functional, with specified deviation | [M-059](evidence/mobile-parity-2026-11-20/M-059.png) | Real totals and averages. No daily chart (the video endpoint returns totals only); header has no thumbnail. |
| M-060 · Creator Analytics — Empty / Unavailable | Visually matched | [M-060](evidence/mobile-parity-2026-11-20/M-060.png), [unavailable](evidence/mobile-parity-2026-11-20/M-060-unavailable.png) | None beyond the common list. |
| M-061 · Lone Stars | Functional, with specified deviation | [M-061](evidence/mobile-parity-2026-11-20/M-061.png) | Hero and ledger rows match; Pending and Withheld are rows, not two tiles; no “History” link or month grouping. |
| M-062 · Confirmed Lone Stars | Functional, with specified deviation | [M-062](evidence/mobile-parity-2026-11-20/M-062.png) | Hero and ledger rows match; no per-row icons or month grouping. |
| M-063 · Pending Lone Stars | Functional, with specified deviation | [M-063](evidence/mobile-parity-2026-11-20/M-063.png) | Hero, note and rows match in structure; no “Why activity is checked” row styling. |
| M-064 · Transaction history | Functional, with specified deviation | [M-064](evidence/mobile-parity-2026-11-20/M-064.png) | Filter chips and rows match; no month heading. |
| M-065 · Transaction details | Functional, with specified deviation | [M-065](evidence/mobile-parity-2026-11-20/M-065.png) | Dark hero and rows match; no per-row icons. |
| M-066 · Withheld points | Functional, with specified deviation | [M-066](evidence/mobile-parity-2026-11-20/M-066.png) | Hero, notes and actions match; icon treatment simplified. |
| M-067 · Reversed points | Functional, with specified deviation | [M-067](evidence/mobile-parity-2026-11-20/M-067.png) | Hero, notes and actions match; icon treatment simplified. |
| M-068 · Engagement eligibility | Functional, with specified deviation | [M-068](evidence/mobile-parity-2026-11-20/M-068.png) | Headline and rows; no icon rows. |
| M-069 · No points activity | Functional, with specified deviation | [M-069](evidence/mobile-parity-2026-11-20/M-069.png) | Hero, notes and actions match; star artwork simplified. |
| M-070 · Report Video Entry | Functional, with specified deviation | [M-070](evidence/mobile-parity-2026-11-20/M-070.png) | Sheet content matches; the dimmed feed shows no video frames in the capture. |
| M-071 · Report a video | Functional, with specified deviation | [M-071](evidence/mobile-parity-2026-11-20/M-071.png) | Thumbnail card and reasons match; reason rows have no hairlines; no creator name on the card. |
| M-072 · Report details | Functional, with specified deviation | [M-072](evidence/mobile-parity-2026-11-20/M-072.png) | Badge, field and note match; thumbnail card has no creator name. |
| M-073 · Report submitted | Functional, with specified deviation | [M-073](evidence/mobile-parity-2026-11-20/M-073.png) | Medallion, copy, card and note match; headline wraps to two lines at 26 pt. |
| M-074 · Report submission error | Functional, with specified deviation | [M-074](evidence/mobile-parity-2026-11-20/M-074.png) | Headline, alert note and actions match; no thumbnail image on the card. |
| M-075 · Already reported | Functional, with specified deviation | [M-075](evidence/mobile-parity-2026-11-20/M-075.png) | Medallion, copy, card and note match; headline wraps to two lines. |
| M-076 · Content restriction notice | Functional, with specified deviation | [M-076](evidence/mobile-parity-2026-11-20/M-076.png) | Medallion, badge, notes and actions follow the design; adds “Request a review” only when the server says appealable; no thumbnail summary row. |
| M-077 · Account status | Functional, with specified deviation | [M-077](evidence/mobile-parity-2026-11-20/M-077.png) | Medallion, notes and actions follow the design; “Sign out” text action not drawn. |
| M-078 · Appeal / Review Request | Functional, with specified deviation | [M-078](evidence/mobile-parity-2026-11-20/M-078.png), [eligible](evidence/mobile-parity-2026-11-20/M-078-eligible.png) | Unavailable state matches. The server-eligible form (statement + Send review request) has no approved export. DECISION D-7. |
| M-079 · My account | Functional, with specified deviation | [M-079](evidence/mobile-parity-2026-11-20/M-079.png) | Initial avatar and no creator badge row details; list rows have no trailing icons; shows roles line. |
| M-080 · Edit personal profile | Functional, with specified deviation | [M-080](evidence/mobile-parity-2026-11-20/M-080.png) | Avatar initial; “Change photo” explains photos are unavailable; note and actions match. |
| M-081 · Account settings | Functional, with specified deviation | [M-081](evidence/mobile-parity-2026-11-20/M-081.png) | Rows have chevrons, not the export’s trailing icons; destructive row not red-icon styled. |
| M-082 · Change password | Functional, with specified deviation | [M-082](evidence/mobile-parity-2026-11-20/M-082.png) | Fields and actions match; no headline “Keep your account yours.” and no note. |
| M-083 · Active sessions | Functional, with specified deviation | [M-083](evidence/mobile-parity-2026-11-20/M-083.png) | Shows the real session list (GET /me/sessions); the export draws only the provider-unsupported state. |
| M-084 · Privacy settings | Functional, with specified deviation | [M-084](evidence/mobile-parity-2026-11-20/M-084.png) | Rows are the real actions, without trailing icons or subtitles. |
| M-085 · Security settings | Functional, with specified deviation | [M-085](evidence/mobile-parity-2026-11-20/M-085.png) | No dark hero card or trailing-icon rows; rows only. |
| M-086 · Notification preferences | Functional, with specified deviation | [M-086](evidence/mobile-parity-2026-11-20/M-086.png) | Real email/push switches and device-permission block; the export’s card layout and notes differ. |
| M-087 · Community guidelines | Functional, with specified deviation | [M-087](evidence/mobile-parity-2026-11-20/M-087.png) | Principle rows lack trailing icons; section titles are 18 pt as designed; no search. |
| M-088 · Terms & Privacy | Functional, with specified deviation | [M-088](evidence/mobile-parity-2026-11-20/M-088.png) | Topic rows and tabs differ in styling; no search or icons. |
| M-089 · Help & Support | Functional, with specified deviation | [M-089](evidence/mobile-parity-2026-11-20/M-089.png) | Help topics lack trailing icons; no search field. |
| M-090 · Logout confirmation | Functional, with specified deviation | [M-090](evidence/mobile-parity-2026-11-20/M-090.png) | Full page, not a dialog over the account page. |
| M-091 · Delete account request | Functional, with specified deviation | [M-091](evidence/mobile-parity-2026-11-20/M-091.png) | Intake page without icon rows and with a different note. |
| M-092 · Confirm account deletion | Functional, with specified deviation | [M-092](evidence/mobile-parity-2026-11-20/M-092.png) | Intake page with proof and typed DELETE; fields and notes differ. |
| M-093 · Deletion request received | Functional, with specified deviation | [M-093](evidence/mobile-parity-2026-11-20/M-093.png) | Receipt card shows the real id, kind, status and UTC time; the export’s icon and layout are simplified. |
| M-094 · Privacy request received | Functional, with specified deviation | [M-094](evidence/mobile-parity-2026-11-20/M-094.png) | Receipt card shows the real id, kind, status and UTC time; the export’s icon and layout are simplified. |
| M-095 · No Internet Connection | Functional, with specified deviation | [M-095](evidence/mobile-parity-2026-11-20/M-095.png) | State panel in a full screen; no notes or secondary actions. |
| M-096 · Slow Connection | Functional, with specified deviation | [M-096](evidence/mobile-parity-2026-11-20/M-096.png) | Placeholder and “Slow Connection” line only; the export shows a page with a notice and actions. |
| M-097 · Loading Skeleton | Functional, with specified deviation | [M-097](evidence/mobile-parity-2026-11-20/M-097.png) | Skeleton bars only, without the surrounding page. |
| M-098 · No search results | Functional, with specified deviation | [M-098](evidence/mobile-parity-2026-11-20/M-098.png) | Panel with headline and Edit search; no search bar, chips or suggested creator. |
| M-099 · Application error | Functional, with specified deviation | [M-099](evidence/mobile-parity-2026-11-20/M-099.png) | State panel; no notes or secondary actions. |
| M-100 · Access denied | Functional, with specified deviation | [M-100](evidence/mobile-parity-2026-11-20/M-100.png) | State panel; the export adds a role note and two actions. |
| M-101 · Session expired | Functional, with specified deviation | [M-101](evidence/mobile-parity-2026-11-20/M-101.png) | State panel; no notes or secondary actions. |
| M-102 · Service unavailable | Functional, with specified deviation | [M-102](evidence/mobile-parity-2026-11-20/M-102.png) | State panel; no notes or secondary actions. |
| M-103 · Rate limit exceeded | Functional, with specified deviation | [M-103](evidence/mobile-parity-2026-11-20/M-103.png) | State panel; no notes or secondary actions. |
| M-104 · Media permission | Functional, with specified deviation | [M-104](evidence/mobile-parity-2026-11-20/M-104.png) | Full screen, not a sheet over the upload step. |
| M-105 · Unsaved Changes Warning | Functional, with specified deviation | [M-105](evidence/mobile-parity-2026-11-20/M-105.png) | Dialog matches; “Save changes” is not offered (the guard is generic). |
| M-106 · Destructive-Action Confirmation | Functional, with specified deviation | [M-106](evidence/mobile-parity-2026-11-20/M-106.png) | Dialog matches the designed layout; shown for ending a session, not cancelling an upload. |
| M-107 · Success Notification | Functional, with specified deviation | [M-107](evidence/mobile-parity-2026-11-20/M-107.png) | Toast matches in style; shown over the sessions page, not the profile page. |
| M-108 · Application Update / Compatibility Notice | Functional, with specified deviation | [M-108](evidence/mobile-parity-2026-11-20/M-108.png) | Required-update screen without the export’s artwork and optional-update layout. |

Totals: 8 · 99 · 1.
