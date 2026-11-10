# R1 application delivery tracker

**Updated 10 November 2026.** The project owner confirmed that Stage 3 (Technical Foundation) was completed successfully. Stage 4 (MVP implementation) is in progress, with Stage 5 (testing and security verification) running in parallel on AWS staging. See the [Stage 3 tracker](Stage3_Implementation_Tracker.csv) for the detailed foundation record.

| Area | Current status | Evidence | Remaining gate |
| --- | --- | --- | --- |
| Mobile UI | Partial | 108 recipes retained. On the iPhone staging release, account journey UAT passed 9/9 by tester report. Startup session restore merged in [PR #30](https://github.com/Markcino/KoloVibe/pull/30). The Flutter job passed on the reviewed PR and on `main`. | Retest SEC-05 on a physical iPhone using a release build from `main` that includes PR #30. Expiry-driven refresh, offline recovery, secure-storage evidence, and physical Android UAT remain open. |
| Django web | Partial | Paginated feed, video/creator details, CSRF account forms and HttpOnly cookies; 14 tests plus real local account journeys pass; rotation survives dependency outages and logout reports unconfirmed revocation. | Full creator/reviewer journeys, production cookie/transport profile and full accessibility review. |
| Identity and gateway | Partial - AWS staging exercised | The public API suite passed 15/15. Two verified tester accounts independently signed in, received their own profile, signed out, and received HTTP 401 on `/me` with the former access token. Existing privileged identity and audit controls are implemented in code. | Refresh-token revocation after logout, refresh rotation and replay evidence, throttling, privileged authorization and broader ADR-013 acceptance remain open. |
| Discovery | Partial | Both clients paginate public feeds. AWS staging returned HTTP 200 for video discovery, 400 for an invalid cursor, and 404 for an unknown creator. Existing gateway contract tests cover pagination across 21 records. | Search, recommendation policy, streaming playback, and device acceptance with published content. |
| Creator onboarding | Backend implemented. Activation pending. | DEC-004 approved. Account-bound invitations, verified-email applications, reviewer decisions and upload eligibility are implemented. | PostgreSQL and privileged staging acceptance, deployment activation, and Flutter integration deferred. |
| Content publishing | Local R2 and FFmpeg candidate. | Private draft, conditional R2 upload, Celery encoding, DEC-005 review and authorized playback. | Live R2/RabbitMQ acceptance, sandboxed worker image, resource and lifecycle controls, staging activation. |
| Engagement | Likes on main. Qualified views implemented locally. | Signed-in tracked playback checks server elapsed time, current publication revision and account/video deduplication under DEC-003. | PostgreSQL CI, edge throttling and abuse verification, staging activation, and Flutter wiring. |
| Non-cash points | DEC-003 approved. Local backend implemented. | Durable qualified-view awards, per-creator UTC cap, and creator-owned balance and history. | Live RabbitMQ delivery and recovery, deployment activation, and Flutter wiring. |
| Moderation and audit | Local backend implemented. Activation pending. | DEC-005 reports, reviewer decisions, takedowns and independent appeals. Content applies each decision once against the recorded video revision. | AWS staging, PostgreSQL, reviewer MFA acceptance, operational audit scheduling and retention. |
| Profile/privacy/settings | Gated | Own account read via `/me`. | Approved retention and deletion policy, session management, profile/preferences APIs. |
| Deployment | AWS staging deployed. Acceptance partial. | Eight Django services, PostgreSQL and RabbitMQ reached 1/1 each. The public mobile API and protected backend were exercised. See the [AWS rollout record](../operations/AWS_Staging_Deployment_Verification_2026-11-10.md). | Production acceptance, Cloudflare rate-limit evidence, audit operations, backup and restore, resilience, and remaining MVP integrations. Oracle Cloud deployment evidence is tracked separately. |

See the [API test deployment roadmap](API_Test_Deployment_Roadmap.md) for deployment sequencing and earlier environment evidence. No demo data or fixed credential is part of the application.

## AWS staging acceptance on 10 November 2026

| Check | Status | Evidence and next action |
| --- | --- | --- |
| iPhone account journey | Passed, tester-reported 9/9 | App opened, account registration and email verification completed, sign-in and own-profile display worked, and sign-out ended the app session. |
| Public API acceptance | Passed 15/15 | Zero mismatches and zero transport failures on the AWS staging mobile API (`https://mobile-api.cabetechs.shop/api/v1`) and protected backend. Covered health, discovery, input validation, unauthenticated profile access, and restricted routes. |
| SEC-09 own-account profile | Passed for `/me` | Both verified testers received their own account details. This evidence covers `/me`. |
| SEC-08 logout revocation | Partial | Both accounts returned login 200, profile 200, logout 204, then profile 401 with the former access token. Refresh-token rejection after logout remains unverified. |
| SEC-05 iPhone session restore | Failed on tested build; fix awaiting device retest | Closing without signing out returned the tester to Welcome and prompted sign-in. [PR #30](https://github.com/Markcino/KoloVibe/pull/30) merged on 10 November at `ea9fe0aa` and checks the saved session before routing. Retest with a release build from `main` containing the fix. A valid session should open Home, and Profile should show the same account without entering credentials again. |
| CI on PR #30 and reviewed `main` (`b6441bd1`) | Flutter and Django jobs passed. Overall CI failed. | Dependency advisory, security/SBOM and shared-image build/scan jobs failed. Image publication was skipped on `main`. [PR run](https://github.com/Markcino/KoloVibe/actions/runs/42829189953) · [Main run](https://github.com/Markcino/KoloVibe/actions/runs/42830288613) |
| Remaining acceptance | Open | Complete expiry-driven refresh, rotation and replay handling, offline recovery, secure-storage verification, physical Android UAT, Cloudflare rate-limit evidence, and the remaining publishing, playback, engagement, points, and moderation gates. |

**Next device check.** Install a release build from `main` containing `ea9fe0aa` on the physical iPhone. Sign in, force-close without signing out, then relaunch from the app icon. Confirm Home opens and Profile shows the same account without another sign-in. Record the tested commit, device result and any error before closing SEC-05. Use the [physical iPhone instructions](../../apps/mobile/README.md#run-on-a-physical-iphone) to build it.

## DEC-004 staging activation checklist

Creator onboarding defaults off in staging. Only the Gateway and Creators service accept `KOLOVIBE_STAGING_CREATOR_ONBOARDING=1`. Gateway also requires the existing privileged and account capability approvals. Keep Identity's privileged MFA and audit checks enabled when testing reviewer actions. Apply the Identity and Creators migrations, verify the exact gateway ingress paths and rate limits, and capture PostgreSQL and reviewer MFA acceptance before activation. The current production profile remains closed.

## OD-07 local R2 and FFmpeg VOD candidate

Set `KOLOVIBE_LOCAL_MEDIA_ENABLED=1` only for the local candidate. The launcher passes the flag to Gateway and Content. Content receives `KOLOVIBE_R2_ACCOUNT_ID`, `KOLOVIBE_R2_MEDIA_BUCKET`, `KOLOVIBE_R2_ACCESS_KEY_FILE`, `KOLOVIBE_R2_SECRET_KEY_FILE` and the Content AMQPS broker URI `KOLOVIBE_CONTENT_RABBITMQ_URL` from the owner-only environment. Use a dedicated private bucket and scoped object permissions. Install the optional hash-locked dependencies with `python -m pip install --require-hashes -r requirements-media.txt` in the local Gateway/Content development environment. The native signer is outside the shared Alpine image. Install FFmpeg and ffprobe on the local worker and run `python scripts/run_local_service.py content run_media_worker`.

The candidate accepts MP4 uploads up to 50 MiB, with a five-minute duration and 1080p input limit. R2 upload links expire in ten minutes and require the signed size, content type and create-only condition. Upload completion checks the object and records its ETag before queueing. The single worker produces a private MP4 up to 720p, then moves the video to review. Moderation controls publication. Authorized playback links expire in five minutes.

If RabbitMQ is unavailable after completion is recorded, retry the same completion request to enqueue processing. The worker uses a database lease to prevent duplicate processing and recover stale leases. The separate production worker still needs a sandbox and bounded resources, monitored reconciliation of stuck jobs, and an approved R2 lifecycle for expired originals and abandoned renditions. Staging activation and paid provisioning are outside this change.

## DEC-005 local candidate

Set `KOLOVIBE_LOCAL_MODERATION_ENABLED=1` in the existing owner-only local environment. Configure the internal Moderation origin as `KOLOVIBE_MODERATION_URL` and a `KOLOVIBE_MODERATION_OUTBOUND_KEY` distinct from the Gateway signing key. Apply the Content and Moderation migrations before starting the local services. Reviewer routes rely on Identity's existing privileged MFA session validation. Staging and production routes remain closed.

A Content timeout leaves the moderation decision pending. Retry the same operation and idempotency key. Content records a transactional receipt so a response lost after applying a decision cannot reapply it. Use a new key for a different decision. Restoration requires a different reviewer and the same removal revision. Live R2 and media worker provisioning, reviewer MFA on staging and the PostgreSQL concurrency checks remain separate acceptance work.
