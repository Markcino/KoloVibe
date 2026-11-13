# KoloVibe R1 — Claude Code Instructions

Follow the approved R1 contracts and architecture.

## Development rules
- Work on one independently testable task.
- Inspect only relevant source files.
- Reuse existing implementations.
- Avoid repeated full-repository audits.
- Prefer focused tests.
- Do not implement deferred features.
- Preserve security and authorization checks.
- Stop after repeated unsuccessful fixes and report the blocker.
- Do not merge or deploy without approval.

## Project stack
Django/DRF, Flutter, PostgreSQL, RabbitMQ, Cloudflare R2, FFmpeg and AWS staging.

## Reporting
Summarize actual changes, tests, failures, PR link and unresolved work.

Never invent token usage or claim that prompt instructions enforce a spending limit.
