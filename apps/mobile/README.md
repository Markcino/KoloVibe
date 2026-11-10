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

Run these commands from `apps/mobile`. The application uses `lib/main.dart`; `flutter run` selects it by default. The explicit equivalent is:

```bash
flutter run --target lib/main.dart
```

IDE launch configurations must also target `lib/main.dart`.

Use a team-approved Flutter SDK version and verify Android/iOS signing, bundle identifiers and platform configuration before distributing a build.

## Run on a physical iPhone

The simulator build does not need a signing certificate. A physical iPhone does. In Xcode, open `ios/Runner.xcworkspace`, then:

1. Sign in under **Xcode > Settings > Apple Accounts** using the Apple Account that will sign this development build.
2. Select the **Runner** project and **Runner** target, then **Signing & Capabilities**. Keep **Automatically manage signing** enabled and select your **Team**. If Xcode reports that `com.kolovibe.kolovibe` is unavailable, choose a unique development bundle identifier for that team.
3. Select the connected iPhone as the run destination. Let Xcode register the device and create a development certificate and provisioning profile; use **Register** or **Set Up Signing** if Xcode offers those actions.
4. Run the app once from Xcode, then retry `flutter run -d <device-id>` from this directory. Follow any trust or Developer Mode prompts on the iPhone.

Signing certificates, private keys, Apple Account credentials and provisioning profiles belong in the local Xcode/keychain setup, not in this repository. A Personal Team can be used for device testing; its provisioning expires and must be renewed periodically.

### Retest session restore on staging (SEC-05)

Use `main` at a commit containing [PR #30](https://github.com/Markcino/KoloVibe/pull/30) and run from `apps/mobile` after completing signing above. Replace `<device-id>` with the ID shown by `flutter devices`.

```bash
flutter pub get --enforce-lockfile
flutter run --release -d <device-id> --dart-define=KOLOVIBE_API_URL=https://mobile-api.cabetechs.shop/api/v1
```

Sign in with a verified staging tester account, force-close without signing out, then relaunch from the app icon. Expect Home and the same account in Profile without entering credentials again. Record the Git commit and device result in the [R1 tracker](../../docs/engineering/R1_Application_Tracker.md#aws-staging-acceptance-on-10-november-2026).

## Application structure

- `lib/app` — app configuration.
- `lib/core/theme` — KoloVibe colors and Material 3 theming.
- `lib/features` — mobile product features.
- `lib/shared/widgets` — reusable interface elements.
- `test` — automated widget checks.

By default, `lib/main.dart` uses unavailable-service adapters and opens Welcome. A configured build checks the saved account session before routing. A restored session opens Home. An absent or rejected session opens Welcome. A failed check offers Retry. Set the compile-time `KOLOVIBE_API_URL` to a verified HTTPS gateway URL ending in `/api/v1` to opt into account, public-video and reviewed-creator metadata adapters. Debug builds also accept loopback HTTP for local simulator testing. They do not provide media playback, publishing, points or moderation. AWS staging account UAT is recorded in the R1 tracker. Production authentication and transport acceptance remain open. There is no built-in test account.

See [implementation and verification](../../docs/mobile-ui-implementation.md) and [design coverage](../../docs/mobile-design-coverage.md).

The live adapter serializes refresh rotation, retries expired access once, and reports unconfirmed server logout separately from local credential removal. Discovery supports cursor pagination without discarding loaded items on a failed next page. See the [API test roadmap](../../docs/engineering/API_Test_Deployment_Roadmap.md#reproducible-isolated-local-acceptance) for isolated local evidence and remaining device/deployment gates.
