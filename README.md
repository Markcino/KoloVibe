# KoloVibe

**Our stories. Our rhythm. Our vibe.**

KoloVibe is a mobile-first platform for Liberian original entertainment and creators. Viewers discover original videos, connect with creators, and explore the culture shaping our community.

## Product

The mobile application brings together five experiences:

- **Home** — original entertainment and KoloVibe services in one place.
- **Explore** — browse videos, genres and creators.
- **Create** — publish original work through the creator experience.
- **Videos** — immersive short-form playback.
- **Profile** — manage your account and creator identity.

The [approved mobile design](https://www.figma.com/design/ANaV0jnwjZ0LEcByTc98HP/KoloVibe?node-id=0-1) is the visual reference for the application.

## Codebase

| Directory | Responsibility |
| --- | --- |
| `apps/mobile_flutter` | Flutter application for Android and iOS |
| `services` | Django services for identity, creators, content, engagement, points, moderation, audit and gateway |
| `contracts` | API interface definitions |
| `infra` | Infrastructure and deployment configuration |
| `docs` | Architecture, engineering practices and design references |

## Getting started

### Mobile application

Install a compatible Flutter SDK, then run:

```bash
cd apps/mobile_flutter
flutter pub get
flutter analyze
flutter test
flutter run
```

The application entry point is `apps/mobile_flutter/lib/main.dart`. From the mobile directory, `flutter run` launches it by default; use `flutter run --target lib/main.dart` when specifying a target explicitly.

Native platform configuration, application identifiers and signing must be reviewed before release. The app includes native presentation recipes for all 108 designed screens and states and shared widgets. Authentication, live data, publishing and video playback integrations remain unavailable pending secure service adapters.

### Backend services

Python 3.12+ is required:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
python scripts/check_structure.py
python scripts/init_local_env.py  # first setup only; creates ignored .env
for service in gateway identity creators content engagement points moderation audit; do
  python scripts/run_local_service.py "$service" test tests
done
```

Run a service locally with an explicit local environment and unique secret:

```bash
python scripts/run_local_service.py gateway runserver 127.0.0.1:8000
```

The local launcher reads only the selected service's generated secret from `.env`. It requires owner-only file permissions and never prints secret values. Containers and CI continue to inject secrets through their own controls. Identity has a persistent account model but no public registration or token endpoint while ADR-013 is unresolved. Content exposes `GET /videos` and `GET /videos/{id}` for approved public records; no fixture content is seeded. Other business APIs and managed deployment remain open.

## Engineering

Code changes are reviewed through pull requests and automated checks. Production environments require separately approved identity, network, database, audit, backup and deployment controls.

- [Engineering standards](docs/engineering-standards.md)
- [Architecture decisions](docs/architecture-decisions.md)
- [Mobile design reference](docs/mobile-design.md)
- [Mobile UI implementation and verification](docs/mobile-ui-implementation.md)
- [108-screen design coverage](docs/mobile-design-coverage.md)

Lone Stars are non-cash recognition points. Paid tickets, withdrawals and other deferred services are not included in the current release.
