# KoloVibe R1 independent security review — Stage 4B

Date: 13 November 2026. Baseline: `main` at `9e95610`.

Method: read-only inspection of source, tests and CI configuration. No live or network testing, no deployed-environment testing and no device testing was performed. No code was changed and no security check was weakened. Findings are confirmed by source inspection only.

## Scope that determines severity

In this checkout the media, upload, playback, moderation, points, watch, analytics and engagement routes are closed in staging. `services/gateway/service/capabilities.py:35-44` returns `False` for any capability in staging unless it is in `STAGING_CAPABILITIES`, which is never defined. `services/staging_runtime/middleware.py:36-52` allowlists only public reads, accounts, MFA and creator onboarding. Findings 1 and 2 therefore apply to local, CI and any future enablement. Finding 3 is reachable in staging today.

## Findings

| # | Severity | File | Lines | Vulnerability | Confidence |
|---|----------|------|-------|---------------|------------|
| 1 | MEDIUM | `services/gateway/service/internal_client.py` | 41-49 | One gateway signing key is shared by every internal peer | 8/10 |
| 2 | MEDIUM | `services/content/service/media_api.py` | 110, 137-158 | A creator can rewrite metadata of an approved public video with no re-review | 8/10 |
| 3 | LOW | `services/gateway/service/creators.py` | 31, 161, 168 | Public creator endpoints return the internal account UUID `user_id` | 9/10 |

### 1. Shared gateway signing key (MEDIUM)

- The gateway signs every internal call with a single key, whatever the audience. Each receiving service stores the same value under `"gateway"` in its caller-keys file (`infra/swarm/staging.yml:79,268`; `services/*/service/service_auth.py`).
- The signature binds the audience name, so a captured request cannot be replayed to another service. The key itself is shared by identity, content, creators, moderation, engagement and points.
- Exploit path: an attacker who reads `caller_keys["gateway"]` in any one container can sign requests to every other service. Moderation trusts `role` and `mfa_verified` from the gateway envelope (`services/moderation/service/workflow.py:347-360`), so a forged call could claim an administrator with MFA verified. The same applies to `/internal/points/*` and `/internal/auth/standing`.
- Evidence: single `key` variable with no per-audience selection at `internal_client.py:41-49`. Identity's audit delivery uses a separate key (`staging.yml:138`), which shows the gateway key is the exception.
- Proposed test: in `scripts/verify_staging_runtime.py`, assert that the `gateway` value differs across the caller-keys files for content, creators, moderation, engagement and points.
- Suggested fix: per-peer gateway keys, and have moderation verify reviewer identity itself.

### 2. Post-approval metadata edits (MEDIUM)

- `_manage(..., "edit")` accepts `Video.State.PUBLISHED`. It updates title, description, category and tags and bumps `moderation_revision`, but keeps `state=published`, `visibility=public` and `moderation_approved_at`. The only gate is the moderator's one-time approval of the original metadata.
- Exploit path: an approved creator publishes a benign video, then calls `PATCH /api/v1/videos/{id}` with `{"title": "<abusive text>"}`. The new text is served publicly and in search without review. The remaining control is user reports.
- Evidence: the code comment at `media_api.py:150` says this is intentional. It is also documented in `docs/engineering/BE-CC_creator_content_acceptance.md:39` and DOC-205 (`DOC-205_OpenAPI_3_1_DRAFT.yaml:1394`), citing M-054 "Save changes".
- Proposed test: edit a published video and assert it returns to `review` or its metadata becomes pending until a moderator approves it.
- Suggested fix: route edits to published content through a pending-metadata review, or record explicit risk acceptance for R1.

### 3. Internal account identifier in public responses (LOW)

- `creator_detail` and `search_creators` return the creators-service profile, which includes `user_id` (the identity `Account.id`). `services/creators/service/profiles.py:23` includes it in `_profile_data`.
- Exploit path: anonymous `GET /api/v1/creators/{id}` or `/api/v1/creators/search?q=x`, both allowed by `infra/nginx/staging.conf.template:21` and the staging allowlist.
- Suggested fix: strip `user_id` from public responses; keep it internal for self-view checks.
- **Status (13 November 2026, branch `security/public-creator-no-user-id`, not merged or deployed):** fixed in code. The gateway removes `user_id` from `GET /creators/{id}`; Creators no longer returns it from search, and the gateway rejects a search page that carries it. The internal profile read keeps `user_id` for the follow and watch self-checks. `GET`/`PATCH /creators/me` still returns the caller's own `user_id` (DOC-205 `OwnCreator`). The mobile and web clients no longer require it. Local checks only; no staging or device evidence.

## Controls verified (source and tests)

- Identity: access tokens are revalidated against the live session; refresh tokens are digested and rotated with family revocation on replay; reset and password change revoke sessions; reauthentication proofs are single-use and session-bound; privileged sessions require TOTP with replay protection; security events are audited in the owning transaction.
- Internal authentication: HMAC over caller, audience, timestamp, nonce, method, path and body hash; ±60 s window; database-backed nonce table; verified TLS and pinned peers.
- Ownership: the gateway derives creator and account IDs server-side; content queries filter on creator and deletion state; cross-creator access returns 404; publication needs eligibility plus moderation approval.
- Upload and playback: presigned PUT signs content type, length and `If-None-Match: *` with a 50 MiB cap; completion re-checks the stored object; FFmpeg runs without a shell with a protocol whitelist, timeouts and size limits; playback is issued only for published, public, approved videos with 300 s URLs.
- Engagement and points: qualified views are decided server-side with pacing checks and 24 h deduplication; the points ledger is append-only (triggers and model guard) and idempotent; audit is ingest-only with append-only triggers including TRUNCATE.
- Infrastructure and CI: Dockerfile pins the base image by digest, installs with hashes and runs as UID 10001; Swarm uses read-only root and secrets; workflows use `pull_request`, SHA-pinned actions and least-privilege permissions; secret scan, Bandit, pip-audit, OSV and Grype are enforced; no `nosec` annotations and no committed secrets were found.
- Mobile: HTTPS enforced, refresh token in secure storage, serialized refresh, strict upload-grant validation.

## Remaining risks (below reporting threshold or not verified)

- MFA lockout is per challenge only; an attacker holding a moderator password gets about 25 TOTP guesses per 15 minutes. Add an account-level MFA failure lockout.
- The login throttle keys on email plus remote address; behind the gateway it is effectively per email.
- Registration returns 409 for existing accounts; reset and resend have a timing side channel.
- The `points_entries` guard has no TRUNCATE trigger. The runtime role is not granted TRUNCATE in the verification script, but real grants were not verified.
- `requirements-media.txt` is hashed but outside the lock-verification and audit gates. FFmpeg is not pinned or built in the repository and has no sandboxing beyond timeouts and size limits.
- The CI "Generate dependency locks" job installs `uv==0.9.15` without hashes in a `contents: write` job limited to `security/ci-hardening`.
- The Android manifest sets no `allowBackup=false` and no network-security config.
- Nothing sets `Account.role = "creator"`, so role-gated routes (`GET/PATCH /creators/me`, moderation `notice`) would return 403 for approved creators unless roles are provisioned out of band. Nothing sets `restricted_at` or suspended status, so creator-level restriction is not enforceable in code.
- `apps/mobile/lib/features/content/live_upload_controller.dart` lacks disposal checks after awaits in the upload pipeline. This is reliability only: no data exposure and no extra authority.
- Not verified (outside the repository): RabbitMQ users and permissions (events are unsigned), real R2 enforcement of signed headers, Postgres role grants, TLS and secret provisioning, device behaviour, FFmpeg patch level.

## Release recommendation: GO WITH CONDITIONS

For the restricted-staging scope (public reads, accounts, MFA, creator onboarding) no critical, high or currently exploitable issue was found in the reviewed code.

1. Before enabling any media, moderation, points, watch or engagement capability, fix or formally accept finding 1 and settle finding 2 with a re-review rule or explicit risk acceptance.
2. Fix finding 3 before wider exposure.
3. Resolve the creator-role provisioning gap and the missing creator restriction path before relying on suspension as a control.
4. Provide a pinned, scanned and sandboxed FFmpeg worker image and bring `requirements-media.txt` under the lock and audit gates.
5. Confirm the unverified deployment items above.
