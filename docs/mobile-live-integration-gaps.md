# Mobile live integration gaps

The Flutter app uses `lib/main.dart` only. Its default composition reports unavailable operations unless `KOLOVIBE_API_URL` is set to an approved HTTPS gateway URL ending in `/api/v1` (or debug loopback). The opt-in composition wires account operations and public video and reviewed-creator metadata; it does not bundle accounts, content records, points balances, or simulated service results.

## Source of truth

- Product scope: `docs/requirements/platform_PRD_v0_2_scope_approved.md` and `platform_SRS_v0_2_scope_approved.md`.
- Candidate public interface: `docs/architecture/DOC-205_OpenAPI_3_1_DRAFT.yaml`. It is a draft and its server URL is deliberately invalid.
- Decision holds: `docs/architecture/DOC-207_Open_Decision_Log.csv` and `DOC-209_Consolidated_Open_Decisions.csv`.

The identity service has internal account/session operations; the gateway contains forwarding routes for registration, verification, login, refresh, logout and `/me`. The mobile account adapter is wired when the gateway URL is provided. The [approved ADR-013 design](architecture/ADR-013_Client_Authentication_and_Session_Security_v1.0_APPROVED.md) governs remaining implementation and production acceptance. Content and creators expose only approved-public metadata through signed gateway routes. The mobile app parses it when configured, but playback is not implemented and the feed remains empty until approved records exist. AWS staging account and discovery evidence is tracked in the [R1 tracker](engineering/R1_Application_Tracker.md#aws-staging-acceptance-on-10-november-2026). The separate Oracle Swarm environment still needs private transport and public ingress acceptance.

| Mobile boundary | DOC-205 candidate | Remaining work |
| --- | --- | --- |
| Account access | `/auth/register`, `/auth/verify`, `/auth/login`, `/auth/refresh`, `/auth/logout`, `/me` | The AWS staging account journey passed by tester report. Startup session restore has merged and awaits the physical iPhone retest (SEC-05). Production transport, deployed refresh/revocation and the remaining ADR-013 evidence are open. Password reset and account deletion remain unimplemented and need approved contracts. |
| Discovery and creators | `GET /videos`, `GET /videos/{video_id}`, `GET /creators/{creator_id}` | Approved-public video metadata and reviewed-active creator profile reads exist through signed gateway routes; opt-in mobile parsing is implemented. The feed has no seeded records and playback is unavailable. Staging TLS peer configuration, search, follow and personalization remain open. |
| Creator onboarding | `/creator-invitations`, `/creator-applications`, `/creators/me/application`, `/creators/me/upload-eligibility` | DEC-004 backend implemented. Staging activation and Flutter wiring remain pending. |
| Content and playback | `/videos`, `/videos/{video_id}/upload-intents`, `/videos/{video_id}/upload-status`, `/videos/{video_id}/playback` | The local R2 and FFmpeg candidate uses creator eligibility, private source and playback objects, background encoding and moderated publication. Live storage and worker acceptance and staging activation remain open. Flutter now wires the upload journey (M-041–M-044, M-046–M-049) to the current DOC-205 shapes ([FL-C](engineering/FL-C_creator_upload_acceptance.md)); cover choice (M-045), playback and non-draft management are not wired. |
| Engagement | `/videos/{video_id}/like`, `/videos/{video_id}/watch-sessions`, `/engagement/watch-events` | The local backend supports like/unlike and DEC-003 watch sessions. Flutter must send forward playback progress from the issued session. Staging activation and Flutter wiring remain open. |
| Lone Stars | `/creators/me/points`, `/creators/me/points/entries` | DEC-003 balance and paginated history are implemented locally for approved creators. Staging activation and the Flutter dashboard remain open. |
| Reports and restrictions | `/reports`, `/moderation/reports` | The local DEC-005 backend supports signed-in reports, MFA-protected reviewer decisions and independent appeals. Staging activation and Flutter wiring remain pending. |
| Profile and settings | `/me`, `PATCH /creators/me` | Authenticated account read via `/me` exists. Profile updates, preferences, privacy requests, data export/deletion and retention contracts remain open under ADR-020. |

## Integration rule

Connect each feature repository only after the owning service has an implemented, tested contract and a deployment base URL. A successful response must be parsed into feature-owned models; widgets must not render bundled design copy as live account, content, or points data. The backend remains authoritative for roles, creator eligibility, publication, moderation and points. Passwords and codes stay transient; the configured account adapter stores refresh credentials in the OS secure store. Device storage and lifecycle acceptance remain open.

The local continuation adds serialized account refresh, explicit unconfirmed-logout feedback, 20-item feed pagination with retry preservation, and distinct public-not-found versus outage states for creator/video details. Local contract, widget and PostgreSQL/HTTP evidence is recorded in the [API test roadmap](engineering/API_Test_Deployment_Roadmap.md); it does not authorize production. The DEC-003 routes require a local opt-in; staged rollout and mobile integration require deployment acceptance.

Before enabling a feature, add contract tests against its service, negative authorization tests, error and expiry handling, and widget tests using controlled test doubles. A fixed test credential is not part of the app.

For local like testing on an existing checkout, add `KOLOVIBE_ENGAGEMENT_URL=http://127.0.0.1:8004` to the existing owner-only `.env`. New local environments include it by default. Apply the engagement migration with `python scripts/run_local_service.py engagement migrate` and run that service on `127.0.0.1:8004` alongside the local gateway, identity and content services.
