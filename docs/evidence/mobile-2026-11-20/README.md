# Figma versus Flutter evidence, 20 November 2026

Each picture is three panels, left to right: the approved export from `docs/designed/`; the Flutter render at 390 × 844 (status bar 47 pt, home indicator 34 pt); the Flutter render at 375 × 667 (iPhone SE class, status bar 20 pt, no home indicator). Renders come from `apps/mobile/test/design_audit_test.dart` and `home_dashboard_test.dart` with scripted repositories and the bundled brand fonts. They are **simulated renders, not device screenshots**: they have no status bar, no real video frames (an in-memory player is used) and sample data.

Regenerate: `cd apps/mobile && AUDIT_DIR=$PWD/build/design-audit flutter test test/design_audit_test.dart test/home_dashboard_test.dart`.

Classes follow [mobile-design-coverage.md](../../mobile-design-coverage.md): **Visually matched**, **Functional but visually different**, **Not verified**. A screen is not called matched merely because it renders without overflow.

## Visible differences by journey

Differences common to all pictures and not listed again: no status bar or home-indicator bar in the render; sample text and images differ from the export; posters fall back to a navy gradient when no image loads; people have an initial instead of a photo (the API has no profile photo).

### Sign-up, verify, sign-in

| Screen | Class | Visible differences |
| --- | --- | --- |
| [M-004](M-004.png) Sign in | Visually matched | None beyond the common list. The export’s inline error appears only after a failed attempt (it then opens M-015). |
| [M-005](M-005.png) Create an account | Visually matched | None beyond the common list. |
| [M-006](M-006.png) Verify your email | Functional, different | One masked field (the emailed code is a long token), not six digit boxes; no envelope medallion; no “Verifying…” progress note. |
| [M-013](M-013.png) Make it yours | Functional, different | No photo (not supported); the three status pills are not drawn; display-name error appears under the field. |
| [M-015](M-015.png) Sign-in problem | Functional, different | No wordmark row; otherwise note, fields and actions match. |

### Home, Following, player

| Screen | Class | Visible differences |
| --- | --- | --- |
| [M-017](M-017.png) Home | Visually matched | Data-driven only: initial avatar for the photo, poster fallback, “Waterside at dawn · Short films” has no duration, trending row has likes not plays. Added: a Following block between the trending row and the chips. At 375 pt “Creator Studio” wraps to two lines. |
| [M-018](M-018.png) Following | Functional, different | Tabs, search icon and bottom navigation match. Video area is black in the render (no frames). The side rail (creator avatar, like count, share, more), the `@handle` line, description and progress bar are not drawn; controls are text buttons at the bottom. |
| [M-024](M-024.png) Player | Functional, different | Same as M-018 with For You selected. |
| [M-019](M-019.png) Explore | Functional, different | Search, chips and rows match in style. No curated hero, “Fresh perspectives” grid or creator spotlight (no endpoints). |
| [M-021](M-021.png) Search | Functional, different | Search field and filters icon match. No recent searches or suggestion chips (none stored or invented); a one-line hint is shown. |
| [M-022](M-022.png) Search results | Functional, different | Videos and Creators sections; no All/Videos/Creators chips, no “Results for” line, no bio line or related searches. |
| [M-025](M-025.png) Video details | Functional, different | Poster card, badges and actions; the export is a dark player with a bottom sheet, plays and duration. |
| [M-026](M-026.png) Creator | Functional, different | Name, handle, bio, follower and video cards, Follow. No tagline, tabs or featured card; counts are cards, not large numerals. |

### Creator onboarding, upload, manage

| Screen | Class | Visible differences |
| --- | --- | --- |
| [M-036](M-036.png) Become a creator | Functional, different | No hero image; copy differs; states are the real invitation / application states. |
| [M-037](M-037.png) Creator Studio | Functional, different | Deep navy surface and red action match. No analytics chart or Lone Stars card (analytics not wired). |
| [M-041](M-041.png) Create an original | Functional, different | Select step is plain: no illustration, no 1·2·3 pills. |
| [M-044](M-044.png) Tell the story | Functional, different | Material floating labels and counters; no thumbnail strip; primary action is Create and upload because the cover step (M-045) cannot be offered before processing. |
| [M-053](M-053.png) Manage video | Functional, different | Actions only: no hero card, plays/likes stats or analytics rows. |

### Points, report, appeal, status

| Screen | Class | Visible differences |
| --- | --- | --- |
| [M-061](M-061.png) Lone Stars | Functional, different | Hero card, ledger rows with star and signed amount match. Pending and Withheld are rows, not two tiles; no month grouping. |
| [M-065](M-065.png) Transaction details | Functional, different | Dark hero and recognition note match; no per-row icons. |
| [M-071](M-071.png) Report a video | Functional, different | Reason list and primary action match; title card replaces the thumbnail card. |
| [M-073](M-073.png) Report submitted | Functional, different | No medallion or thumbnail card; actions present. |
| [M-074](M-074.png) Report error | Functional, different | No medallion or thumbnail card. |
| [M-075](M-075.png) Already reported | Functional, different | No medallion or thumbnail card. |
| [M-076](M-076.png) Content restriction notice | Functional, different | No thumbnail or medallion; adds Request a review only when the server says the decision is appealable. |
| [M-078](M-078.png) Appeal / review request | Functional, different | Copy and states follow the export’s “availability not confirmed” screen. Proposal with no export: [eligible state](M-078-eligible.png) with a statement field and Send review request. |

### Account and system states

| Screen | Class | Visible differences |
| --- | --- | --- |
| [M-079](M-079.png) My account | Functional, different | Avatar initial, badge, studio card and icon rows; no photo or originals count. |
| [M-083](M-083.png) Active sessions | Functional, different | Real session rows; the export’s provider note and medallion are for the unsupported state. |
| [M-095, M-099 to M-103](M-101.png) State views (M-101 shown) | Functional, different | Medallion, headline, message and action match; the export adds a note card and a secondary action. |

## Not captured here

Video playback and its error states (M-031 to M-035), dialogs and snack bars (M-054 to M-057, M-105 to M-107), upload progress states (M-046 to M-052), analytics (M-058 to M-060) and the populated privacy receipts (M-093, M-094) are **Not verified**. They need a device or fixtures that were not built.
