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

## Run on a physical iPhone

The simulator build does not need a signing certificate. A physical iPhone does. In Xcode, open `ios/Runner.xcworkspace`, then:

1. Sign in under **Xcode > Settings > Apple Accounts** using the Apple Account that will sign this development build.
2. Select the **Runner** project and **Runner** target, then **Signing & Capabilities**. Keep **Automatically manage signing** enabled and select your **Team**. If Xcode reports that `com.kolovibe.kolovibe` is unavailable, choose a unique development bundle identifier for that team.
3. Select the connected iPhone as the run destination. Let Xcode register the device and create a development certificate and provisioning profile; use **Register** or **Set Up Signing** if Xcode offers those actions.
4. Run the app once from Xcode, then retry `flutter run -d <device-id>` from this directory. Follow any trust or Developer Mode prompts on the iPhone.

Signing certificates, private keys, Apple Account credentials and provisioning profiles belong in the local Xcode/keychain setup, not in this repository. A Personal Team can be used for device testing; its provisioning expires and must be renewed periodically.

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

There is no fixed test account. In the demo sign-in form, any valid email and nonempty password pass local validation (for example, `demo@example.com` and `DemoPass123!`); no account is created or authenticated. The normal `lib/main.dart` entry point has no connected sign-in service, so it cannot accept test credentials.

See [implementation and verification](../../docs/mobile-ui-implementation.md) and [design coverage](../../docs/mobile-design-coverage.md).
