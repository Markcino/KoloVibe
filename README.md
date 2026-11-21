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
| `apps/mobile` | Flutter application for Android and iOS |
| `apps/web_django` | Django administration console for moderators/administrators only |
| `services` | Django services for identity, creators, content, engagement, points, moderation, audit and gateway |
| `packages/contracts` | API interface definitions |
| `infra` | Infrastructure and deployment configuration |
| `docs` | Architecture, engineering practices and design references |

## Getting started

### Mobile application

Install a compatible Flutter SDK, then run:

```bash
cd apps/mobile
flutter pub get
flutter analyze
flutter test
flutter run
```

The application entry point is `apps/mobile/lib/main.dart`. From the mobile directory, `flutter run` launches it by default; use `flutter run --target lib/main.dart` when specifying a target explicitly.

Native platform configuration, application identifiers and signing must be reviewed before release. The app includes native presentation recipes for all 108 designed screens and states and shared widgets. Without `KOLOVIBE_API_URL`, the app uses unavailable-service adapters. Opt-in account, public-video and reviewed-creator metadata adapters exist, but publishing, media playback, points, moderation and other live integrations are not complete.

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

The local launcher reads only the selected service's generated secret from `.env`. It requires owner-only file permissions and never prints secret values. Containers and CI continue to inject secrets through their own controls. Identity has internal account/session operations, and the gateway contains forwarding routes for registration, verification, login, refresh, logout and `/me`. AWS staging has recorded account and public API UAT. Production use requires implementation and verification against the approved ADR-013 design, including transport and end-to-end acceptance. Content exposes read-only approved-public video metadata; the creators service exposes reviewed-active profiles through the signed gateway path. No fixture content is seeded. All eight APIs and the media worker are reported deployed to restricted staging on v0.187.2; full business-journey and production acceptance remain open.

The Django web client is an administration console with no landing page or public/viewer/creator pages. It uses existing MFA and encrypted server-side credentials, owning-service assignment authorization, audited reviewer detail/previews, scoped operational counts, redacted audit reads and read-only points review. Run `.venv/bin/python scripts/run_local_web.py test tests`; see [routes, roles and activation requirements](apps/web_django/README.md) and [security evidence](tests/security/README.md). Staging activation requires explicit capabilities/credentials and owner review; production remains gated.

## Delivery status

The [17 November reconciliation](docs/operations/R1_AWS_Staging_Reconciliation_2026-11-17.md) records v0.187.2 publication and operator-reported deployment. The assessment remains **26 passed / 0 failed / 19 pending**. Full functional and security acceptance is incomplete.

Stage 3 was completed by owner declaration on 10 November 2026. Stage 4 MVP implementation and Stage 5 testing and security verification are in progress. See the [R1 application tracker](docs/engineering/R1_Application_Tracker.md) for AWS staging evidence and the [Stage 3 execution record](docs/engineering/Stage3_Current_Status.md) for outstanding Oracle and foundation evidence.

## Engineering

Code changes are reviewed through pull requests and automated checks. Production environments require separately approved identity, network, database, audit, backup and deployment controls.

- [Engineering standards](docs/engineering-standards.md)
- [Architecture decisions](docs/architecture-decisions.md)
- [Mobile design reference](docs/mobile-design.md)
- [Mobile UI implementation and verification](docs/mobile-ui-implementation.md)
- [108-screen design coverage](docs/mobile-design-coverage.md)
- [API test deployment roadmap](docs/engineering/API_Test_Deployment_Roadmap.md)

Lone Stars are non-cash recognition points. Paid tickets, withdrawals and other deferred services are not included in the current release.
