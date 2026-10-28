# KoloVibe mobile

Flutter application for Android and iOS, using Material 3 widgets and KoloVibe's brand palette.

Approved visual reference: https://www.figma.com/design/ANaV0jnwjZ0LEcByTc98HP/KoloVibe?node-id=0-1

## Run locally

```sh
flutter create --platforms android,ios --project-name kolovibe .
flutter pub get
flutter analyze
flutter test
flutter run
```

The native Android/iOS directories should be generated with the agreed Flutter SDK version and committed after verifying application identifiers and signing practices.

## Implemented

- App entry point, theme and five primary destinations.
- Multi-service Home layout.
- Explore category selector.
- Dedicated Videos layout with Following / For You selector.
- Create and Profile entry points with accurate unavailable-backend messaging.
- Initial widget tests.

## Still needed

- Pixel-accurate implementation of the approved 108-screen Figma inventory.
- Design imagery and licensed font assets.
- Authentication, service API integrations, secure token storage.
- Actual portrait video player, adaptive streaming, creator upload flows and telemetry.
- Platform-specific configuration, CI SDK pinning and device test execution.

These screens are foundation implementations, not claims that the approved features work end-to-end.
