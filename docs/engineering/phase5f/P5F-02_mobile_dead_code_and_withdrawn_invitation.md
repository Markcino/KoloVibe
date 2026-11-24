# P5F-02 — mobile: remove unreferenced duplicates, pin the withdrawn-invitation state

**Date:** 24 November 2026. **Scope:** `apps/mobile` only. First recorded run on the CI-pinned Flutter 3.47.8 with `--enforce-lockfile`.

## Evidence
- `flutter analyze`: no issues. `flutter test`: 1,555 pass before and **1,556** after this change.
- A reference scan of every file in `lib/` (by file name, across `lib`, `test` and `integration_test`) found two files nothing references: `shared/widgets/section_header.dart` (`SectionHeader`) and `shared/widgets/empty_section.dart` (`EmptySection`); `main.dart` is the entry point. Both widgets duplicate roles the shared design components already fill, and neither is used by any screen or test. Both were deleted; analysis and the full suite still pass.
- No duplicate screen class names exist among the 92 Dart files; all 108 screens remain reachable through the typed route table (`design_audit_test`, `r1_wiring_test`).
- All six `FutureBuilder` uses were read. The startup builders handle `design.hasError` and `startup.hasError`, the compatibility check falls back to an unknown policy, the account and session screens show explicit failure states, and "Try another story" shows nothing when it has no result.

## Added test
`live_creator_upload_test.dart`: a 404 from `GET /creators/me/application` reads as "no application" (null) and any other failure (503) still surfaces as an error. This pins the behaviour P5F-01 relies on: an applicant whose invitation was revoked is told exactly what a never-invited account is told, so no mobile change was needed.

## Not done
No physical-device run. No visual re-capture of the 108 screens. Decisions D-2 to D-5 in the Phase 5F results still gate M-045, profile photos, M-078 and M-091–M-094.
