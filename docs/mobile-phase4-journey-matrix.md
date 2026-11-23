# Mobile screen matrix after Phase 4 — 23 November 2026

**Scope of this record.** It states what was verified in the Phase 4 session and what was not. It supersedes no earlier record: the 20 November [design parity review](mobile-design-parity.md) remains the screen-by-screen evidence (8 visually matched, 99 functional with a specified deviation, 1 not verified), and the FL-A to FL-D matrices remain the per-feature gap records. **No physical-device result exists for any row.**

## What Phase 4 found
All 108 screens and states already have an implementation reachable from a typed route. The remaining differences from the Figma exports are recorded deviations, most of which depend on owner decisions or on product features that do not exist. Only one verified, implementable gap remained and it is now closed: **M-040 library search** (the backend `q` parameter shipped in Phase 2). It reuses the existing repository, `ApiClient`, session manager and chip/list components; no new API client, model family or design system was created. No page was removed, so no obsolete-duplicate cleanup was needed.

Corrections to stale records found while checking: the **M-070 options sheet exists** (`live_video_screen.dart`, route `M-070`, asserted by `vertical_feed_tabs_test.dart`), although the FL-D matrix still lists it as not rebuilt; and the FL-C row for M-040 predates the state filters and now this search.

## Verification environment (read before trusting any number)
- **SDK.** The only SDK on this machine is Flutter **3.50.1** (Dart 3.14.0). CI pins **3.47.8**. Results below come from 3.50.1 and are **not** a CI run; the pull request's CI is the authoritative 3.47.8 result.
- **Lockfile.** `flutter pub get --enforce-lockfile` **failed** against the committed `pubspec.lock` on 3.50.1 (the lock is for 3.47.8). Tests ran in a throwaway worktree with freshly resolved packages; the lockfile in the repository was not changed and the owner's uncommitted `pubspec.lock` change was not touched.
- **Analysis.** `flutter analyze`: **0 errors and 0 warnings**; 72 info findings, all `deprecated_member_use` for `package:flutter/material.dart` (SDK 3.50 deprecation, not present on 3.47.8).
- **Tests** use fake repositories and `MockClient`; no production credentials, no network, no device, no secure-storage hardware.

## Journey verification (one run of each journey's test files, SDK 3.50.1)

| Journey | Screens | Test files | Tests passed | Result |
| --- | --- | --- | ---: | --- |
| J1 Accounts, settings, privacy | M-001–M-016, M-079–M-094 | `fl_a_account_repository`, `fl_a_account_widgets`, `six_digit_code`, `startup_restoration_regression`, `live_settings_repository` | 245 | pass |
| J2 Discovery | M-017–M-035 | `fl_b_repositories`, `fl_b_widgets`, `home_dashboard`, `explore_latest`, `search_history`, `vertical_feed_tabs`, `live_repositories`, `live_video_engagement`, `play_counts` | 257 | pass |
| J3 Creator Studio | M-036–M-060 | `live_creator_upload`, `live_create_original_screen`, `live_content_screen` (+2 new), `live_manage_video`, `manage_cover`, `live_own_creator_repository`, `live_creator_identity_screens`, `live_upload_controller`, `live_analytics`, `creator_access_controller`, `creator_upload_routes` | 163 | pass |
| J4 Points | M-061–M-069 | `live_points_repository`, `live_points_screens`, `points_controller` | 73 | pass |
| J5 Trust and moderation | M-070–M-078 | `live_report_repository`, `live_report_screens`, `report_controller`, `live_notice_screens`, `live_appeal_screen`, `live_moderation_repository`, `live_standing_repository`, `standing_controller`, `trust_routes` | 124 | pass |
| J6 System states, accessibility and layout | M-095–M-108 | `fl_a_system`, `slow_connection`, `accessibility_layout`, `design_system_widgets` | 72 | pass |
| Navigation shell and 108-screen audit | all | `app_shell`, `mobile_ui`, `journeys`, `live_journeys`, `r1_wiring`, `design_audit` | 621 | pass |
| **Whole suite, one run** | | 47 files | **1,555** | **pass** (2 min 2 s) |

Each journey run covers repository/API-adapter tests, widget tests and, through `r1_wiring`, `trust_routes` and `creator_upload_routes`, navigation dispatch. Accessibility and layout evidence is `accessibility_layout_test` plus the 2× text-scale and two-viewport renders in `design_audit_test`.

## Screen status by journey (from the 20 November parity record, plus this session)

| Journey | Screens | Visually matched | Functional, specified deviation | Not verified | Changed in Phase 4 |
| --- | ---: | ---: | ---: | ---: | --- |
| J1 Accounts, settings, privacy | 32 | 7 | 25 | 0 | none |
| J2 Discovery | 19 | 0 | 19 | 0 | none |
| J3 Creator Studio | 25 | 1 | 23 | 1 (M-045) | **M-040 search added** |
| J4 Points | 9 | 0 | 9 | 0 | none |
| J5 Trust and moderation | 9 | 0 | 9 | 0 | none (M-070 sheet already present) |
| J6 System states and dialogs | 14 | 0 | 14 | 0 | none |
| **Total** | **108** | **8** | **99** | **1** | |

Several decisions in that record (D-1, D-3 to D-7, D-9) have implementing commits dated 20 November (six-digit codes, truthful slow-connection state, "Latest original" Explore, device-local recent searches, public play counts and creator Popular, eligible appeal states). The screen rows above were **not re-captured** in Phase 4, so their wording in the parity record may predate those commits.

## Screens that cannot be completed without a decision or a missing capability
| Screen | Why | Needed |
| --- | --- | --- |
| M-045 Choose a cover | The service accepts only `cover_time_ms` after duration is known and returns no frame thumbnails; the cover-moment slider in Edit details stands in (D-2) | Approve a frame-thumbnail endpoint, or accept the slider as the design |
| Profile photos (M-013, M-026, M-028, M-038, M-039, M-080) | No profile-photo endpoint and no photo moderation policy (D-10) | Product and moderation policy |
| M-078 appeal submit | The approved design says the screen does not submit; the API accepts a submission and the app shows an eligible form only when the notice says appealable | Owner decision on which is intended |
| Brand mark (D-8) | In-app emblem follows Figma; launcher icon is the owner logo | Owner confirmation |
| M-094 / M-091–M-093 completion | Retention, deletion and export policy (ADR-020) | Policy |

## Physical-device acceptance
No row above has been run on a phone. Acceptance instructions: [iPhone checklist](engineering/iphone_e2e_checklist.md) and [run card](engineering/iphone_run_card.md) (update the branch, commit and Flutter-version lines to the commit under test; they still name an older branch and Flutter 3.47.8), and the new [Android checklist](engineering/android_e2e_checklist.md). A device PASS may be written only by the person holding the device, per row, with evidence.
