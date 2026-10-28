# KoloVibe

KoloVibe brings Liberian original stories, music, culture and creators together in one mobile-first platform.

## Applications

- **Mobile:** Flutter for Android and iOS — `apps/mobile_flutter`
- **Backend:** independently deployed Django services — `services`
- **Contracts:** versioned service interfaces — `contracts`
- **Infrastructure:** private-edge architecture and deployment configuration — `infra`

The mobile interface follows the [approved Figma source](https://www.figma.com/design/ANaV0jnwjZ0LEcByTc98HP/KoloVibe?node-id=0-1). Home is a multi-service dashboard; Explore is for browsing; Videos is a dedicated immersive feed.

## Local development

### Mobile

Install Flutter using the official SDK, then:

```sh
cd apps/mobile_flutter
flutter create --platforms android,ios --project-name kolovibe .
flutter pub get
flutter analyze
flutter test
flutter run
```

The platform directories are generated locally by Flutter and should be committed only after verifying the SDK version and platform settings. The application shell is implemented, but business APIs and media playback are **not connected yet**. Unavailable data displays honest empty states rather than fabricated live engagement.

### Services

Use Python 3.12+ and install development dependencies:

```sh
python -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements-dev.txt
python scripts/check_structure.py
python scripts/test_services.py
```

Each service has a liveness endpoint at `/health/live`, not a business API or database-readiness assertion.

## Engineering standards

Changes go through pull requests, automated checks and security review. No production deployment is authorized until the unresolved architecture decisions, credential handling, database permissions, release controls and restore procedures are validated. See `docs/HOLD_POINTS.md` and `docs/STAGE3_ACCEPTANCE.md`.

Release 1 does not include cash-out, withdrawals, paid tickets or advertising-derived Lone Stars. The website UI work is deferred.
