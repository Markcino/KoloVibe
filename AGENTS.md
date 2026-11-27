# KoloVibe — Agent Instructions

**Read first:** the [full application mandate](docs/governance/Full_Application_Mandate_2026-11-27.md) (owner, 27 November 2026) and the [phase execution tracker](docs/governance/Phase_Execution_Tracker.md). The mandate's phase execution rules are binding. Work only on the phase the owner has authorized.

KoloVibe is no longer an MVP. The earlier R1 scope boundary is a historical record; it no longer limits development scope. Nothing is approved merely because that boundary is gone (live streaming stays excluded).

## Development rules
- Work on one independently testable task, in a small focused PR.
- Inspect the latest repository state and the relevant source files before changing anything.
- Reuse existing implementations; do not duplicate logic, contracts, security controls or financial accounting.
- Implement only approved scope; policy-dependent work needs approved requirements.
- Prefer focused tests; never weaken, skip or delete a test to pass.
- Preserve security and authorization checks; the server is the authority.
- Stop after repeated unsuccessful fixes and report the blocker.
- Do not merge or deploy without approval. Do not change AWS, secrets, staging database privileges or RabbitMQ permissions without an approved operations plan.
- No live payments, payouts, advertiser charging or live ads. Points never become money.

## Project stack
Django/Python, Flutter, PostgreSQL, RabbitMQ, Cloudflare R2, FFmpeg, Docker Swarm on AWS staging.

## Reporting
Summarize actual changes, tests, failures, PR link and unresolved work. At a phase boundary, produce the phase completion report the mandate defines.

Never invent test outcomes or token usage, or claim that prompt instructions enforce a spending limit.
