# KoloVibe — Copilot Repository Instructions

## Scope
Follow the [full application mandate](../docs/governance/Full_Application_Mandate_2026-11-27.md) and the [phase execution tracker](../docs/governance/Phase_Execution_Tracker.md). The earlier R1 scope (eight services, deferred business, ticketing and payouts) is historical. Live streaming stays excluded, Points stay non-cash, and no live money moves.

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
