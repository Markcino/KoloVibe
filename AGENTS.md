# KoloVibe — agent instructions

## Governing mandate
- The [full application mandate of 27 November 2026](docs/governance/Full_Application_Mandate_2026-11-27.md) governs all work. Read it, then the [phase execution tracker](docs/governance/PHASE_EXECUTION_TRACKER.md) and the [documentation index](docs/README.md), before acting.
- Follow the phase gates in mandate section 10. Do not begin a phase until the owner authorizes it. End each phase with the section 11 completion report.
- Owner decisions A to J and the later rulings stay in force. Do not ask for them again ([record](docs/planning/Owner_Decisions_A-J_2026-11-25.md)).
- Follow the approved contracts and architecture. Change them only by a reviewed decision.

## Development rules
- Work on one independently testable task.
- Inspect only relevant source files.
- Reuse existing implementations.
- Avoid repeated full-repository audits.
- Prefer focused tests.
- Do not implement unapproved scope, such as live streaming. Approved full-application functionality is not deferred (mandate section 2).
- Never invent policy, legal, financial or infrastructure values. Make them configurable and record them as owner decisions.
- Never treat BLOCKED, NOT RUN, SKIPPED or PARTIAL as PASS, and never fabricate evidence.
- Preserve security and authorization checks.
- Stop after repeated unsuccessful fixes and report the blocker.
- Do not merge or deploy without approval. Development approval does not authorize live payments, live advertising, destructive data changes or production publication.

## Project stack
Django (no DRF is used), Flutter, PostgreSQL, RabbitMQ (not Redis), Cloudflare R2, FFmpeg, Docker Swarm with host Nginx and Cloudflare ingress, and AWS staging.

## Reporting
Summarize actual changes, tests, failures, PR link and unresolved work. At a phase boundary, produce the phase completion report the mandate defines.

Never invent token usage or claim that prompt instructions enforce a spending limit.

*History (superseded 27 November 2026 by the full application mandate):* the file was titled "KoloVibe R1 — Claude Code Instructions". It said "Follow the approved R1 contracts and architecture" and "Do not implement deferred features", and the stack line named "Django/DRF, Flutter, PostgreSQL, RabbitMQ, Cloudflare R2, FFmpeg and AWS staging".
