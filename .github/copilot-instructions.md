# KoloVibe — Copilot Repository Instructions

## Governing mandate
The [full application mandate of 27 November 2026](../docs/governance/Full_Application_Mandate_2026-11-27.md) governs scope, and the [phase execution tracker](../docs/governance/PHASE_EXECUTION_TRACKER.md) records where execution stands. Follow [AGENTS.md](../AGENTS.md).

## Approved scope
The full application in mandate section 2, built on Django/DRF services, Flutter, PostgreSQL, RabbitMQ, Cloudflare R2 and FFmpeg. Points stay non-cash, and Finance is the only monetary ledger. Live streaming is not approved. Live payments, payouts and advertising need their own owner approval.

*History (superseded 27 November 2026):* "Eight Django/DRF services, 108 Flutter screen IDs, Cloudflare R2, FFmpeg, RabbitMQ, PostgreSQL, and non-cash points. Deferred: live streaming, business discovery, ticketing, and cash payouts."

## Token-efficient workflow
- Inspect current HEAD before acting.
- Search relevant files before opening them.
- Read only task-related source and tests.
- Reuse existing implementations and approved contracts.
- Do not repeatedly analyze the entire repository.
- Work on one small, testable task per session.
- Run focused tests before full CI.
- Investigate recurring failures rather than retrying blindly.
- Keep responses concise.

## Security and approvals
- Never reveal secrets.
- Never weaken security controls.
- Never merge or deploy without approval.
- Use separate branches for independent work.

## Completion
Report changed files, tests, blockers, PR link, and measured usage when available.
