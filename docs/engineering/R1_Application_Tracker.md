# R1 application delivery tracker

**Updated 1 November 2026.** This is the feature tracker. Stage 3 infrastructure acceptance remains in [Stage3_Implementation_Tracker.csv](Stage3_Implementation_Tracker.csv). Status describes verified code, not production approval.

| Area | Current status | Evidence | Remaining gate |
| --- | --- | --- | --- |
| Mobile UI | Partial | 108 recipes retained; account refresh serialized; paginated discovery and creator/video retry states; 143 Flutter tests, clean analysis and unsigned iOS simulator build pass. | Simulator boot timed out before app launch/hot reload; playback, publishing, reports, points, settings and device QA remain open. |
| Django web | Partial | Paginated feed, video/creator details, CSRF account forms and HttpOnly cookies; 14 tests plus real local account journeys pass; rotation survives dependency outages and logout reports unconfirmed revocation. | Full creator/reviewer journeys, production cookie/transport profile and full accessibility review. |
| Identity and gateway | Partial | Owner selected Django-native client identity under ADR-013 on 2026-11-01; 101 service tests and six isolated PostgreSQL/HTTP journeys verify mail capture, contracts, refresh concurrency/reuse, revocation and web account forms. Privileged promotion cannot reuse an unprivileged session. | Full ADR-013 token/session/MFA approval, separate workload identity contract, real SMTP, staging secrets and privileged MFA/audit. Test mail never leaves the fixture. |
| Discovery | Partial | Both clients paginate existing 20-item public feeds; real gateway contract tests traverse 21 records without duplication; invalid/stale cursors and malformed/mismatched records fail explicitly. | Search, recommendation policy, streaming playback and deployed transport. |
| Creator onboarding | Gated | Profile schema accepts reviewed active records for public read. | Approved eligibility/review/privacy rules and authorized application workflow. |
| Content publishing | Gated | Content metadata model and read-only approved-public routes. | Managed video provider, upload intent/webhook verification, rights review and moderation publish workflow. |
| Engagement | Foundation only | Queue/event primitives exist. | Authenticated idempotent likes/watch intake, qualified event policy and abuse evidence. |
| Non-cash points | Foundation only; product gated | Append-only ledger, constraints and SQLite/PostgreSQL mutation tests. | Owner explicitly keeps ALL points APIs/UI gated, including read-only balances/history, until points decisions are approved. |
| Moderation and audit | Foundation only | Service skeletons and internal auth. | Reports, decisions, appeals, immutable audit records and privileged MFA. |
| Profile/privacy/settings | Gated | Own account read via `/me`. | Approved retention and deletion policy, session management, profile/preferences APIs. |
| Deployment | Partial - staging preparation only | CI configured to build/test/publish one shared API image; all eight service checks retained. Single Swarm YAML defines eight APIs plus separate RabbitMQ DHI, all zero-replica candidates. Isolated Gunicorn/TLS and startup/route gates pass; Nginx remains metadata-only. | Actual new image/registry, Nginx/private routing, capacity, certificates/workload identity, broker and operations evidence remain pending. Accounts require reviewed identity/SMTP/credential/transport approvals; production remains blocked. |

See the [API test deployment roadmap](API_Test_Deployment_Roadmap.md) for the ordered path to a restricted staging test. No demo data or fixed credential is part of the application.
