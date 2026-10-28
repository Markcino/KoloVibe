# Mobile UI implementation

The mobile milestone uses the approved Figma layouts and preserves the Flutter/Django monorepo. All 108 screen/state recipes are in `apps/mobile_flutter/assets/design`, grouped by account, discovery, studio, points, moderation, settings and cross-cutting states. The recipes contain native presentation data, never executable HTML or CSS. Original artwork and SVG icons are bundled locally; identical content is stored once. Inter and Plus Jakarta Sans are bundled with their SIL Open Font Licenses.

## Run and review

Use Flutter **3.35.0**, matching CI (Dart 3.9.0). Android and iOS projects are now included; do not rerun `flutter create` over the app.

```sh
cd apps/mobile_flutter
flutter pub get --enforce-lockfile
flutter run
flutter run --target lib/main_demo.dart
```

Normal mode starts with splash and welcome. Account submissions return honest unavailable-service responses; populated account/content/points screens are not exposed as live data. The separate demo entry point simulates navigation and local outcomes using sample design data. Tap the gold **DEMO** banner to open the 108-state gallery and the viewer-role preview toggle. Upload progress advances through simulated processing to pending moderation; published/rejected/error states are individually selectable in the gallery. Playback is a static visual preview, explicitly identified in the player.

Demo startup throws in release mode. `main.dart` has no import of demo implementations. The development bundle identifier is `com.kolovibe.kolovibe`; distribution identifiers, launcher artwork and signing require release review. Android release signing is unconfigured; debug keys are not configured for releases.

## Architecture and DRY

Existing feature screen entry points remain under `lib/features`. They compose the common native presentation layer in `lib/shared/widgets`. `lib/core/theme` centralizes the brand theme; numeric recipe styles preserve per-design typography and geometry. `lib/app` owns typed Navigator arguments and dependency composition. Feature repository interfaces are resolved through the composition root, with unavailable adapters as the default. The demo adapter is imported only by its own entry point.

The feature controller owns transient form state, validation, selections and submission status. Widgets do not make network calls. Passwords/codes are not persisted or logged; sensitive field buffers are cleared after submissions and on disposal. Server authorization, creator eligibility, moderation and points calculation remain authoritative service responsibilities. Demo role checks are presentation checks, never security enforcement.

Native safe areas, editable text inputs, semantic controls and system back navigation replace simulated device chrome. Layouts scroll and grow for keyboards and larger text. Bottom sheets and confirmations use native routes rather than screenshots of overlays.

## Integration boundaries

Follow the existing DOC-205 draft contracts and open ADRs. No business endpoint is implemented by this milestone. Identity, secure token storage, media selection/provider uploads, playback, native sharing/settings/store launching, privacy requests, real content/search/follow state and backend notification delivery require service/device adapters. No client-side points-award formula or media moderation bypass exists.

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

Snapshot captures are written to ignored `build/ui-review/M-001.png` through `M-108.png`. They exclude simulated OS status bars, include the demo identification banner, and are review evidence rather than committed golden baselines. See `docs/mobile-design-coverage.md` for per-design traceability and `docs/mobile-asset-manifest.json` for asset hashes and Figma slots. Actual verification results are recorded separately; implementation does not imply deployment approval or security certification.
