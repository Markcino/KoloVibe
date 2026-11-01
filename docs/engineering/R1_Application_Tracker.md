# R1 application delivery tracker

**Updated 1 November 2026.** This is the feature tracker. Stage 3 infrastructure acceptance remains in [Stage3_Implementation_Tracker.csv](Stage3_Implementation_Tracker.csv). Status describes verified code, not production approval.

| Area | Current status | Evidence | Remaining gate |
| --- | --- | --- | --- |
| Mobile UI | Partial | 108 designed recipes retained; opt-in live account, video and creator metadata paths; Flutter analysis and 137 tests pass locally. | Playback, creator publishing, reports, points dashboard, settings and full live journey QA. |
| Django web | Partial | Server-rendered public feed, video and creator details, account forms, CSRF and HttpOnly cookies; 7 local tests pass. | Full R1 creator/reviewer journeys, production cookie/transport profile and accessibility review. |
| Identity and gateway | Partial | Local registration/verification, login, refresh rotation/replay revocation, logout and `/me`; privileged login denied without MFA; gateway routing and tests. | ADR-013 approval, SMTP, staging secrets, end-to-end email/session tests and privileged MFA/audit. |
| Discovery | Partial | Signed gateway→content and gateway→creator reads; only approved public records; empty/404 behavior; local creator/gateway tests pass. | Search, pagination client journey, recommendation policy, streaming playback and deployed transport. |
| Creator onboarding | Gated | Profile schema accepts reviewed active records for public read. | Approved eligibility/review/privacy rules and authorized application workflow. |
| Content publishing | Gated | Content metadata model and read-only approved-public routes. | Managed video provider, upload intent/webhook verification, rights review and moderation publish workflow. |
| Engagement | Foundation only | Queue/event primitives exist. | Authenticated idempotent likes/watch intake, qualified event policy and abuse evidence. |
| Non-cash points | Foundation only | Append-only ledger, constraints and SQLite/PostgreSQL mutation tests. | Approved qualified-view formula, audited posting, own-balance/history APIs and client display. |
| Moderation and audit | Foundation only | Service skeletons and internal auth. | Reports, decisions, appeals, immutable audit records and privileged MFA. |
| Profile/privacy/settings | Gated | Own account read via `/me`. | Approved retention and deletion policy, session management, profile/preferences APIs. |
| Deployment | Pending | Local tests and read-only VM audit runbook; image delivery workflow exists. | Staging settings, green exact-commit CI, VM evidence, TLS, secrets, backup, monitoring and acceptance. |

See the [API test deployment roadmap](API_Test_Deployment_Roadmap.md) for the ordered path to a restricted staging test. No demo data or fixed credential is part of the application.
