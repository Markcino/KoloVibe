# KoloVibe R1 — Codex Instructions

Applies repository-wide. Follow approved R1 contracts and architecture.

## Scope
Eight Django/DRF services: gateway, identity, creators, content, engagement, points, moderation and audit. Flutter (108 screen IDs), Django web, PostgreSQL, RabbitMQ, Cloudflare R2, FFmpeg and AWS Swarm staging.

Deferred: live streaming, business discovery, ticketing and cash payouts. Points are non-cash.

## Token-efficient workflow
- Check HEAD and working-tree changes once at task start. Preserve unrelated work; separate independent changes into branches.
- Locate relevant files with `rg` or `rg --files`. Read targeted source sections and nearby tests.
- Reuse existing implementations, approved contracts and findings. Avoid rereading unchanged files and repeated repository-wide audits.
- Keep changes focused and independently testable. Finish the requested task without unrelated cleanup.
- Batch independent reads and searches; limit output. Inspect failure details instead of dumping full logs or diffs.
- Run focused tests first and required checks before completion. Repeat checks only when changes or unresolved failures justify it.
- Investigate recurring failures rather than retrying blindly; report concrete blockers.
- Keep updates and answers concise. Omit routine command narration and unsolicited large code blocks.

## Security and approval
- Never reveal secrets or embed real credentials in code, fixtures, logs or responses.
- Preserve authorization, MFA, TLS, isolation, scanners and deployment guards.
- Do not implement deferred features or expand scope without authorization.
- Do not merge or deploy without approval; reuse existing approval within its stated scope.

## Completion
Report changes, relevant tests, failures, unresolved work and PR link. Distinguish local tests, CI and deployment evidence. Never invent results or token usage. These instructions cannot enforce a spending limit.
