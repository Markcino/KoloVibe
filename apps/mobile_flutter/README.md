# KoloVibe for Android and iOS

The Flutter application implements KoloVibe's five primary navigation destinations: Home, Explore, Create, Videos and Profile.

The canonical UI reference is the [approved KoloVibe Figma design](https://www.figma.com/design/ANaV0jnwjZ0LEcByTc98HP/KoloVibe?node-id=0-1), comprising 108 mobile screen and state designs.

## Run

```bash
flutter pub get
flutter analyze
flutter test
flutter run
```

Use a team-approved Flutter SDK version and verify Android/iOS signing, bundle identifiers and platform configuration before distributing a build.

## Application structure

- `lib/app` — app configuration.
- `lib/core/theme` — KoloVibe colors and Material 3 theming.
- `lib/features` — mobile product features.
- `lib/shared/widgets` — reusable interface elements.
- `test` — automated widget checks.

All 108 designed screens/states are available in the isolated development demo:

```sh
flutter run --target lib/main_demo.dart
```

Tap the gold DEMO banner for the state gallery. Demo builds simulate local outcomes; live APIs and device/media adapters remain unavailable. Normal mode never presents sample account/content/points data as live data. Demo startup is rejected in release mode.

See [implementation and verification](../../docs/mobile-ui-implementation.md) and [design coverage](../../docs/mobile-design-coverage.md).
