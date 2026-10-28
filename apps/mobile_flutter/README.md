# KoloVibe for Android and iOS

The Flutter application implements KoloVibe's five primary navigation destinations: Home, Explore, Create, Videos and Profile.

The canonical UI reference is the [approved KoloVibe Figma design](https://www.figma.com/design/ANaV0jnwjZ0LEcByTc98HP/KoloVibe?node-id=0-1), comprising 108 mobile screen and state designs.

## Run

```bash
flutter create --platforms android,ios --project-name kolovibe .
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

The UI structure is in place. Account services, live content, streaming and upload workflows require backend integration. Empty-content states are intentional while those integrations are unavailable; sample engagement metrics are not passed off as live data.
