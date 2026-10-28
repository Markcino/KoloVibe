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
flutter create --platforms android,ios --project-name kolovibe .
flutter pub get
flutter analyze
flutter test
flutter run
```

Native platform configuration, application identifiers and signing must be reviewed before release. The current app includes the navigation shell and initial feature layouts. Authentication, live data, publishing and video playback integrations are still under development.

### Backend services

Python 3.12+ is required:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
python scripts/check_structure.py
python scripts/test_services.py
```

Run a service locally with an explicit local environment and unique secret:

```bash
cd services/gateway
export KOLOVIBE_ENV=local
export DJANGO_SECRET_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(48))')"
python manage.py runserver 127.0.0.1:8000
```

Current service endpoints include `GET /health/live`; business APIs and managed deployment configuration are not yet implemented.

## Engineering

Code changes are reviewed through pull requests and automated checks. Production environments require separately approved identity, network, database, audit, backup and deployment controls.

- [Engineering standards](docs/engineering-standards.md)
- [Architecture decisions](docs/architecture-decisions.md)
- [Mobile design reference](docs/mobile-design.md)

Lone Stars are non-cash recognition points. Paid tickets, withdrawals and other deferred services are not included in the current release.
