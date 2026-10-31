# Mobile UI implementation

The mobile milestone uses the approved Figma layouts and preserves the Flutter/Django monorepo. All 108 screen/state recipes are in `apps/mobile_flutter/assets/design`, grouped by account, discovery, studio, points, moderation, settings and cross-cutting states. The recipes contain native presentation data, never executable HTML or CSS. Original artwork and SVG icons are bundled locally; identical content is stored once. Inter and Plus Jakarta Sans are bundled with their SIL Open Font Licenses.

## Run and review

Use Flutter **3.47.8**, matching CI (Dart 3.13.7). Android and iOS projects are now included; do not rerun `flutter create` over the app.

```sh
cd apps/mobile_flutter
flutter pub get --enforce-lockfile
flutter run
```

The app starts with splash and welcome. Account submissions return honest unavailable-service responses; populated account, content and points screens are guarded until deployed services provide authoritative data. No sample outcomes or credentials are bundled.

The development bundle identifier is `com.kolovibe.kolovibe`; distribution identifiers, launcher artwork and signing require release review. Android release signing is unconfigured; debug keys are not configured for releases. The updated iOS project targets iOS 15.0 or newer.

## Architecture and DRY

Existing feature screen entry points remain under `lib/features`. They compose the common native presentation layer in `lib/shared/widgets`. `lib/core/theme` centralizes the brand theme; numeric recipe styles preserve per-design typography and geometry. `lib/app` owns typed Navigator arguments and dependency composition. Feature repository interfaces are resolved through the composition root, with unavailable adapters as the default.

The feature controller owns transient form state, validation, selections and submission status. Widgets do not make network calls. Passwords/codes are not persisted or logged; sensitive field buffers are cleared after submissions and on disposal. Server authorization, creator eligibility, moderation and points calculation remain authoritative service responsibilities.

Native safe areas, editable text inputs, semantic controls and system back navigation replace simulated device chrome. Layouts scroll and grow for keyboards and larger text. Bottom sheets and confirmations use native routes rather than screenshots of overlays.

## Integration boundaries

Follow the existing DOC-205 draft contracts and open ADRs. No business endpoint is implemented by this milestone. Identity, secure token storage, media selection/provider uploads, playback, native sharing/settings/store launching, privacy requests, real content/search/follow state and backend notification delivery require service/device adapters. No client-side points-award formula or media moderation bypass exists.

The current boundary-by-boundary status is in `docs/mobile-live-integration-gaps.md`. Do not treat the gateway's health check as a live account or content integration.

Policy summaries are design-reference copy; they are not a complete approved legal policy. Business discovery, tickets, real-money rewards and payouts remain deferred under DEC-001.

## Verification commands

```sh
python3 scripts/check_structure.py
python3 scripts/check_mobile_design.py
python3 scripts/verify_dependency_locks.py --python --flutter --ci
cd apps/mobile_flutter
flutter analyze
flutter test
flutter build apk --debug
flutter build ios --simulator --debug
```

See `docs/mobile-design-coverage.md` for per-design traceability and `docs/mobile-asset-manifest.json` for asset hashes and Figma slots.

## Verification record · 31 October 2026

- The single app entry point has no simulation repository, gallery, fixtures, generated captures or sample credentials. Protected account, content and points screens remain unavailable.
- Flutter 3.47.8 analysis: no issues. Widget suite: 37 of 37 passed, including fail-closed sign-in, sensitive-field clearing, registration validation and narrow-display text scaling.
- Design integrity and repository structure checks passed: 108 recipes, 150 assets, eight Django service skeletons.
- Android debug APK built at `apps/mobile_flutter/build/app/outputs/flutter-apk/app-debug.apk`; iOS simulator Debug app built at `apps/mobile_flutter/build/ios/iphonesimulator/Runner.app`. A physical iPhone build still requires the developer's signing certificate and provisioning profile.

### Earlier interface milestone evidence · 29 October 2026

- Figma detailed context and screenshots: 108 of 108 retrieved. Original user exports remain in `docs/designed/`; 150 unique downloaded image assets and two licensed font families are bundled.
- Design integrity: passed (108 entries, 150 local assets, valid route targets and source image slots). Structure and Python/Flutter/CI dependency lock checks passed; `flutter pub get --enforce-lockfile` resolved successfully without changing the lockfile.
- Flutter 3.47.8 static analysis and the earlier 137-test widget suite passed before removal of the simulation path. Those render tests are historical evidence only.
- Existing Django service tests: eight of eight services passed in an isolated Python 3.12 environment with hash-locked dependencies.
- Historical design comparisons used all 108 reference captures at 390 × 844. Those generated captures are removed with the simulation path and are not current runtime evidence.
- Android debug APK built with Flutter 3.47.8 at `apps/mobile_flutter/build/app/outputs/flutter-apk/app-debug.apk`; archive integrity passed. iOS simulator Debug `Runner.app` built at `apps/mobile_flutter/build/ios/iphonesimulator/Runner.app`. Both builds were repeated after the final widget fix. Flutter warns that the current Gradle, Android Gradle Plugin and Kotlin versions will need a future upgrade. These are development builds, not signed distribution artifacts.

This historical evidence verifies the interface milestone only. Live integration, deployment approval and security certification remain open.
