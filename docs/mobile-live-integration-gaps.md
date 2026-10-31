# Mobile live integration gaps

The Flutter app uses `lib/main.dart` only. Its repository interfaces are in `lib/features`, and the default composition in `lib/app` reports unavailable operations. The app does not bundle accounts, content records, points balances, or simulated service results.

## Source of truth

- Product scope: `docs/requirements/platform_PRD_v0_2_scope_approved.md` and `platform_SRS_v0_2_scope_approved.md`.
- Candidate public interface: `docs/architecture/DOC-205_OpenAPI_3_1_DRAFT.yaml`. It is a draft and its server URL is deliberately invalid.
- Decision holds: `docs/architecture/DOC-207_Open_Decision_Log.csv` and `DOC-209_Consolidated_Open_Decisions.csv`.

The deployed Django services currently expose only `GET /health/live`. A health response does not establish user identity, content availability, or readiness of any business operation.

| Mobile boundary | DOC-205 candidate | Gap before live connection |
| --- | --- | --- |
| Account access | `/auth/register`, `/auth/login`, `/auth/refresh`, `/auth/logout`, `/me` | Implement identity endpoints and resolve ADR-013 for mobile token issuance, secure storage, rotation, revocation and session expiry. Registration verification, password reset and account deletion need approved contracts. |
| Discovery and creators | `GET /videos`, `GET /videos/{video_id}`, `GET /creators/{creator_id}` | Implement public, moderated responses. Search, creator follow, and feed personalization need contract decisions. |
| Content and playback | `/videos`, `/videos/{video_id}/upload-intents`, `/videos/{video_id}/publish`, `/videos/{video_id}/playback` | Implement authorized creator flow, provider upload/webhook decisions and media playback. Do not infer publication from a timer or local state. |
| Engagement | `/videos/{video_id}/like`, `/engagement/watch-events` | Implement authenticated requests and server-side deduplication. Client actions must not award points. |
| Lone Stars | `/creators/me/points`, `/creators/me/points/entries` | Implement the append-only non-cash ledger and resolve ADR-019 before any qualified-view calculation. |
| Reports and restrictions | `/reports`, `/moderation/reports` | Implement report submission, moderation decisions and appeal contracts with server authorization and audit. |
| Profile and settings | `/me`, `PATCH /creators/me` | Define and implement personal profile, sessions, privacy requests, preferences and deletion contracts. Resolve retention requirements under ADR-020. |

## Integration rule

Connect each feature repository only after the owning service has an implemented, tested contract and a deployment base URL. A successful response must be parsed into feature-owned models; widgets must not render bundled design copy as live account, content, or points data. The backend remains authoritative for roles, creator eligibility, publication, moderation and points. Keep passwords and codes transient; select an OS secure store only after the session decision is approved.

Before enabling a feature, add contract tests against its service, negative authorization tests, error and expiry handling, and widget tests using controlled test doubles. A fixed test credential is not part of the app.
