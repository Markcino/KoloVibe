# Mobile live integration gaps

The Flutter app uses `lib/main.dart` only. Its default composition reports unavailable operations unless `KOLOVIBE_API_URL` is set to an approved HTTPS gateway URL ending in `/api/v1`. The opt-in composition wires account operations and public video metadata; it does not bundle accounts, content records, points balances, or simulated service results.

## Source of truth

- Product scope: `docs/requirements/platform_PRD_v0_2_scope_approved.md` and `platform_SRS_v0_2_scope_approved.md`.
- Candidate public interface: `docs/architecture/DOC-205_OpenAPI_3_1_DRAFT.yaml`. It is a draft and its server URL is deliberately invalid.
- Decision holds: `docs/architecture/DOC-207_Open_Decision_Log.csv` and `DOC-209_Consolidated_Open_Decisions.csv`.

The identity service has internal account/session operations; the gateway contains forwarding routes for registration, verification, login, refresh, logout and `/me`. The mobile account adapter is wired when the gateway URL is provided. Production use remains blocked by ADR-013 and missing email, transport and end-to-end acceptance evidence. The content service exposes read-only public video metadata, and the gateway has list/detail routes through signed internal service transport. The mobile app parses this metadata when configured, but playback is not implemented and the feed remains empty until approved records exist. Gateway peer credentials and certificates are not configured for local end-to-end use; no deployed environment is configured. A health response does not establish identity or business readiness.

| Mobile boundary | DOC-205 candidate | Gap before live connection |
| --- | --- | --- |
| Account access | `/auth/register`, `/auth/verify`, `/auth/login`, `/auth/refresh`, `/auth/logout`, `/me` | Identity operations and gateway forwarding routes exist; mobile wiring is opt-in. Resolve ADR-013 and provide email, secure transport and end-to-end contract evidence before production. Password reset and account deletion remain unimplemented and need approved contracts. |
| Discovery and creators | `GET /videos`, `GET /videos/{video_id}`, `GET /creators/{creator_id}` | Approved-public video metadata and gateway list/detail routes exist; opt-in mobile parsing is implemented. The feed has no seeded records and playback/creator profiles are unavailable. TLS peer configuration, search, follow and personalization remain open. |
| Content and playback | `/videos`, `/videos/{video_id}/upload-intents`, `/videos/{video_id}/publish`, `/videos/{video_id}/playback` | Implement authorized creator flow, provider upload/webhook decisions and media playback. Do not infer publication from a timer or local state. |
| Engagement | `/videos/{video_id}/like`, `/engagement/watch-events` | Implement authenticated requests and server-side deduplication. Client actions must not award points. |
| Lone Stars | `/creators/me/points`, `/creators/me/points/entries` | The append-only ledger scaffold and local mutation/reversal tests exist. No public balance/history API or mobile dashboard is connected. Resolve ADR-019 before implementing award calculations. |
| Reports and restrictions | `/reports`, `/moderation/reports` | Implement report submission, moderation decisions and appeal contracts with server authorization and audit. |
| Profile and settings | `/me`, `PATCH /creators/me` | Authenticated account read via `/me` exists. Profile updates, preferences, privacy requests, data export/deletion and retention contracts remain open under ADR-020. |

## Integration rule

Connect each feature repository only after the owning service has an implemented, tested contract and a deployment base URL. A successful response must be parsed into feature-owned models; widgets must not render bundled design copy as live account, content, or points data. The backend remains authoritative for roles, creator eligibility, publication, moderation and points. Keep passwords and codes transient; select an OS secure store only after the session decision is approved.

Before enabling a feature, add contract tests against its service, negative authorization tests, error and expiry handling, and widget tests using controlled test doubles. A fixed test credential is not part of the app.
