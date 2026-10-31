# Mobile UI implementation

The mobile milestone uses the approved Figma layouts and preserves the Flutter/Django monorepo. All 108 screen/state recipes are in `apps/mobile_flutter/assets/design`, grouped by account, discovery, studio, points, moderation, settings and cross-cutting states. The recipes contain native presentation data, never executable HTML or CSS. Original artwork and SVG icons are bundled locally; identical content is stored once. Inter and Plus Jakarta Sans are bundled with their SIL Open Font Licenses.

## Run and review

Use Flutter **3.47.8**, matching CI (Dart 3.13.7). Android and iOS projects are now included; do not rerun `flutter create` over the app.

```sh
cd apps/mobile_flutter
flutter pub get --enforce-lockfile
flutter run
```

The sole application entry point is `lib/main.dart`. `flutter run` selects it by default; the explicit equivalent is `flutter run --target lib/main.dart`. IDE launch configurations must use the same entry point.

The app starts with splash and welcome. Account submissions return unavailable-service responses; populated account/content/points screens remain hidden until secure service adapters are connected. There is no built-in test account, state gallery, viewer-role override or simulated upload progression.

The development bundle identifier is `com.kolovibe.kolovibe`; distribution identifiers, launcher artwork and signing require release review. Android release signing is unconfigured; debug keys are not configured for releases. The updated iOS project targets iOS 15.0 or newer.

## Architecture and DRY

Existing feature screen entry points remain under `lib/features`. They compose the common native presentation layer in `lib/shared/widgets`. `lib/core/theme` centralizes the brand theme; numeric recipe styles preserve per-design typography and geometry. `lib/app` owns typed Navigator arguments and dependency composition. Feature repository interfaces are resolved through the composition root, with unavailable adapters as the default.

The feature controller owns transient form state, validation, selections and submission status. Widgets do not make network calls. Passwords/codes are not persisted or logged; sensitive field buffers are cleared after submissions and on disposal. Server authorization, creator eligibility, moderation and points calculation remain authoritative service responsibilities.

Native safe areas, editable text inputs, semantic controls and system back navigation replace simulated device chrome. Layouts scroll and grow for keyboards and larger text. Bottom sheets and confirmations use native routes rather than screenshots of overlays.

## Integration boundaries

Follow the existing DOC-205 draft contracts and open ADRs. The content service has local read-only approved-public video endpoints and the gateway has a signed internal list route; the mobile app is not yet connected. Identity, secure token storage, media selection/provider uploads, playback, native sharing/settings/store launching, privacy requests, real content/search/follow state and backend notification delivery require service/device adapters. No client-side points-award formula or media moderation bypass exists.

The current boundary-by-boundary status is in `docs/mobile-live-integration-gaps.md`. The intended future production host is `kolovibe.cabetechs.shop`; no deployment or production API is configured in this repository.

Policy summaries are design-reference copy; they are not a complete approved legal policy. Business discovery, tickets, real-money rewards and payouts remain deferred under DEC-001.

## Verification commands

```sh
python3 scripts/check_structure.py
python3 scripts/check_mobile_design.py
python3 scripts/verify_dependency_locks.py --python --flutter --ci
cd apps/mobile_flutter
flutter analyze
flutter test
flutter test test/mobile_ui_test.dart --dart-define=CAPTURE_UI=true
flutter build apk --debug
flutter build ios --simulator --debug
```

Snapshot captures are written to ignored `build/ui-review/M-001.png` through `M-108.png`. They capture the current application state for each route, including unavailable-service screens for protected routes; they do not establish visual coverage of every populated design. They are review evidence rather than committed golden baselines. See `docs/mobile-design-coverage.md` for per-design traceability and `docs/mobile-asset-manifest.json` for asset hashes and Figma slots.

## Verification record · 29 October 2026

This is historical evidence from before the alternate entry point and simulation controls were removed. It does not describe the current route captures or a new verification run.

- Figma detailed context and screenshots: 108 of 108 retrieved. Original user exports remain in `docs/designed/`; 150 unique downloaded image assets and two licensed font families are bundled.
- Design integrity: passed (108 entries, 150 local assets, valid route targets and source image slots). Structure and Python/Flutter/CI dependency lock checks passed; `flutter pub get --enforce-lockfile` resolved successfully without changing the lockfile.
- Flutter 3.47.8 static analysis: no issues. Full widget suite: 137 of 137 passed, including all 108 render cases, navigation journeys, destructive-action validation, fail-closed normal mode and enlarged-text/narrow-display checks.
- Existing Django service tests: eight of eight services passed in an isolated Python 3.12 environment with hash-locked dependencies.
- Render captures: all 108 regenerated with Flutter 3.47.8 at 390 × 844. The welcome, home, player and Creator Studio captures were compared visually with their corresponding Figma exports. Native status/navigation areas and the former preview banner account for deliberate framing differences; no pixel-diff threshold is claimed.
- Android debug APK built with Flutter 3.47.8 at `apps/mobile_flutter/build/app/outputs/flutter-apk/app-debug.apk`; archive integrity passed. iOS simulator Debug `Runner.app` built at `apps/mobile_flutter/build/ios/iphonesimulator/Runner.app`. Both builds were repeated after the final widget fix. Flutter warns that the current Gradle, Android Gradle Plugin and Kotlin versions will need a future upgrade. These are development builds, not signed distribution artifacts.

This evidence verifies the interface milestone, not live integration, deployment approval or security certification.

## Service foundation update · 31 October 2026

The local identity service stores accounts with normalized unique email and hashed passwords; public sign-in and token issuance remain closed pending ADR-013 details. The local content service exposes read-only approved-public video metadata. Its empty feed contains no fixture records. The gateway list route uses signed internal transport but has no configured TLS peers; the mobile app does not yet consume these endpoints.

The combined branch passed 68 Django service tests, 18 script tests, 133 Flutter widget tests, Flutter analysis, design integrity and migration drift checks. Local `.env` contains distinct generated service secrets with owner-only permissions and is ignored by Git. The intended production host is `kolovibe.cabetechs.shop`; no production deployment was attempted.
