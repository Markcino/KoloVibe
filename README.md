# KoloVibe


Approved 108 mobile screen design: https://www.figma.com/design/ANaV0jnwjZ0LEcByTc98HP/KoloVibe?node-id=0-1

## Current work
Eight isolated Django process skeletons: gateway, identity, creators, content, engagement, points, moderation, audit. Liveness endpoints only, without business APIs or service identity.

## Local development smoke tests
Prerequisite: Python 3.12+.
```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
python scripts/check_structure.py
python scripts/test_services.py
```
To run one service locally:
```bash
cd services/gateway
DJANGO_SECRET_KEY=local-development-key python manage.py runserver 127.0.0.1:8000
```
Request `GET /health/live` and expect `{"status":"ok"}`. This does not verify database readiness.

## Holds
Dependencies are not pinned yet (FND-02). No production images or deployment automation.
Unresolved provider, private TLS, database topology, event rules, points qualification and video callbacks are hold points in `docs/HOLD_POINTS.md`. No payouts or active future services in Release 1.

Website UI is deferred. Flutter application initialization is next, guided by the approved Figma design.
