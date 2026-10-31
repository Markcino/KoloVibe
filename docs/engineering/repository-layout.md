# Repository directory alignment (Stage 3)

Status: structural audit record, not an additional architecture approval. Baseline: Stage 3 Technical Foundation Implementation Plan v1.0, section **Repository and service structure**, and DOC-201/DOC-208 design baselines. Scope: Git file/folder placement only; no claim that deferred services or infrastructure are implemented.

| Approved location | Tracked contents / ownership |
| --- | --- |
| `apps/mobile/` | Flutter source, platform projects, design assets and widget tests; production entry `lib/main.dart` |
| `apps/web_django/` | Deferred Django web client placeholder and shared SVG branding under `static/images/` |
| `services/{gateway,identity,creators,content,engagement,points,moderation,audit}/` | Independently owned Django services; each contains `manage.py`, `service/` and `tests/` |
| `packages/contracts/openapi/` | Shared API contracts, not cross-service writable models |
| `infra/docker/` | Existing service image definition |
| `infra/postgres/` | Per-service DB schema-isolation SQL |
| `infra/rabbitmq/` | Private broker configuration (approved execution change from earlier Redis drafting) |
| `infra/swarm/`, `infra/nginx/`, `infra/observability/` | Reserved, explicitly pending infrastructure paths |
| `docs/requirements/`, `docs/architecture/`, `docs/engineering/`, `docs/planning/`, `docs/history/` | Existing controlled documentation by purpose |
| `docs/adr/` | Reserved location for individual ADRs; working DOC-207 register stays in `docs/architecture/` to preserve existing links |
| `scripts/` | Repository-level quality checks and operator scripts |
| `tests/security/` | Reserved cross-service security test directory; service-owned tests stay under each service |

## Corrected historical misplacements

- `apps/mobile_flutter/` contained stray generated local Gradle/Xcode/IDE outputs after the previous directory migration. Those tracked artifacts are removed, not copied. The Gradle wrapper script, Windows script and JAR (required versioned build tooling) are relocated to `apps/mobile/android/` with their original Git blob IDs and executable mode preserved.
- Three branding SVG files previously under `apps/web/static/images/` now belong to `apps/web_django/static/images/`. This does not activate the deferred web app.
- `scripts/check_structure.py` guards against regressions in these directory paths.

## Rules

Preserve Django's existing `service/` module layout and migrations until an explicit approved specification requires renaming; do not rename service package modules just for appearances. Do not move contracts to `docs/` or put shared business models into `packages/`. Do not commit developer-specific build cache, SDK paths, generated Xcode settings or IDE state. Run `python scripts/check_structure.py` in CI and validate Flutter/Android and Django workflows before merge.
