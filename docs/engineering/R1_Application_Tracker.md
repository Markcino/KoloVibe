# R1 application delivery tracker

**Updated 10 November 2026.** This is the feature tracker. Stage 3 infrastructure acceptance remains in [Stage3_Implementation_Tracker.csv](Stage3_Implementation_Tracker.csv). Status distinguishes staging evidence, code changes, and production acceptance.

| Area | Current status | Evidence | Remaining gate |
| --- | --- | --- | --- |
| Mobile UI | Partial | 108 recipes retained. On the iPhone staging release, account journey UAT passed 9/9 by tester report. Startup session fix is in draft PR #30. Its Flutter analysis and widget test job passed. | Retest SEC-05 on a physical iPhone using the PR build. Expiry-driven refresh, offline recovery, secure-storage evidence, and physical Android UAT remain open. |
| Django web | Partial | Paginated feed, video/creator details, CSRF account forms and HttpOnly cookies; 14 tests plus real local account journeys pass; rotation survives dependency outages and logout reports unconfirmed revocation. | Full creator/reviewer journeys, production cookie/transport profile and full accessibility review. |
| Identity and gateway | Partial - AWS staging exercised | The public API suite passed 15/15. Two verified tester accounts independently signed in, received their own profile, signed out, and received HTTP 401 on `/me` with the former access token. Existing privileged identity and audit controls are implemented in code. | Refresh-token revocation after logout, refresh rotation and replay evidence, throttling, privileged authorization and broader ADR-013 acceptance remain open. |
| Discovery | Partial | Both clients paginate public feeds. AWS staging returned HTTP 200 for video discovery, 400 for an invalid cursor, and 404 for an unknown creator. Existing gateway contract tests cover pagination across 21 records. | Search, recommendation policy, streaming playback, and device acceptance with published content. |
| Creator onboarding | Gated | Profile schema accepts reviewed active records for public read. | Approved eligibility/review/privacy rules and authorized application workflow. |
| Content publishing | Gated | Content metadata model and read-only approved-public routes. | Managed video provider, upload intent/webhook verification, rights review and moderation publish workflow. |
| Engagement | Foundation only | Queue/event primitives exist. | Authenticated idempotent likes/watch intake, qualified event policy and abuse evidence. |
| Non-cash points | Foundation only; product gated | Append-only ledger, constraints and SQLite/PostgreSQL mutation tests. | Owner explicitly keeps ALL points APIs/UI gated, including read-only balances/history, until points decisions are approved. |
| Moderation and audit | Partial | Identity-owned append-only security records, authenticated idempotent audit ingestion, retry and PostgreSQL mutation rejection; privileged MFA APIs implemented. | Reports, decisions, appeals, operational audit scheduling/alerts/retention and deployed security acceptance. |
| Profile/privacy/settings | Gated | Own account read via `/me`. | Approved retention and deletion policy, session management, profile/preferences APIs. |
| Deployment | Partial - AWS staging UAT | The public mobile API and account flow were exercised against AWS staging. The protected backend health route returned HTTP 401 without authorization. The staging evidence below applies to that AWS endpoint. | Production acceptance, Cloudflare rate-limit evidence, audit operations, backup and restore, resilience, and remaining MVP integrations. Oracle Cloud foundation acceptance is tracked separately. |

See the [API test deployment roadmap](API_Test_Deployment_Roadmap.md) for deployment sequencing and earlier environment evidence. No demo data or fixed credential is part of the application.

## AWS staging acceptance on 10 November 2026

| Check | Status | Evidence and next action |
| --- | --- | --- |
| iPhone account journey | Passed, tester-reported 9/9 | App opened, account registration and email verification completed, sign-in and own-profile display worked, and sign-out ended the app session. |
| Public API acceptance | Passed 15/15 | Zero mismatches and zero transport failures on the staging mobile API and protected backend. Covered health, discovery, input validation, unauthenticated profile access, and restricted routes. |
| SEC-09 own-account profile | Passed for `/me` | Both verified testers received their own account details. This evidence covers `/me`. |
| SEC-08 logout revocation | Partial | Both accounts returned login 200, profile 200, logout 204, then profile 401 with the former access token. Refresh-token rejection after logout remains unverified. |
| SEC-05 iPhone session restore | Failed on tested build; fix awaiting device retest | Closing without signing out returned the tester to Welcome and prompted sign-in. [Draft PR #30](https://github.com/Markcino/KoloVibe/pull/30) checks the saved session before routing. Retest on the release build from that branch. A valid session should open Home, and Profile should show the same account without entering credentials again. |
| PR #30 CI | Flutter and Django jobs passed; overall CI failed | Dependency advisory, security and SBOM, and shared-image build and scan jobs failed. [Actions run](https://github.com/Markcino/KoloVibe/actions/runs/42829189953) |
| Remaining acceptance | Open | Complete expiry-driven refresh, rotation and replay handling, offline recovery, secure-storage verification, physical Android UAT, Cloudflare rate-limit evidence, and the remaining publishing, playback, engagement, points, and moderation gates. |

**Next action:** Build PR #30 on the Mac connected to the iPhone, retest SEC-05, and record the device result before closing the item.
