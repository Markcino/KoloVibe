# KoloVibe R1 physical iPhone UAT checklist

**Run only after an approved deployment.** The runtime now carries the capability policy, media worker, consumers and schedulers ([R1 runtime release candidate](R1_Runtime_Release_Candidate_2026-11-14.md)), but nothing is deployed or verified on AWS yet, so every row is NOT TESTED until it is run. A section whose capability is not enabled in the approved deployment is recorded **NOT TESTED**, never PASS.

**Prerequisites (operator, before the tester starts):** R2 bucket and keys provisioned; a reviewer account with MFA enrolled (`enroll_privileged_mfa`); a creator invitation for the tester; the worker, consumer and job processes scaled to 1 and healthy; SMTP delivering.

## Record header (fill once per run)

| Field | Value |
| --- | --- |
| Tester / date (UTC) | |
| iPhone model, iOS version | |
| App build: git commit, Flutter version, build mode (release) | |
| API base URL (`KOLOVIBE_API_URL`, HTTPS, ends in `/api/v1`) | |
| API release digest(s) from `docker service inspect` | |
| Test accounts used (labels only, no passwords) | |

Build per [apps/mobile/README.md](../../apps/mobile/README.md#run-on-a-physical-iphone) from the release commit. The build must be a **release** build from a commit that contains PR #30 (session restore).

For every row: record Expected, Actual, PASS / FAIL / NOT TESTED, a screenshot or screen recording reference, and the UTC time. Do not record passwords, codes, tokens or playback URLs.

## A. Account and persistent session

| # | Step | Expected |
| --- | --- | --- |
| A1 | Register a new account | Neutral confirmation; verification email arrives |
| A2 | Verify with the emailed code; try resend before two minutes | Account verified; resend shows the cooldown without disclosing account state |
| A3 | Sign in | Home opens; Profile shows this account |
| A4 | **SEC-05:** force-close the app without signing out, relaunch from the icon | Home opens without credentials; Profile shows the same account |
| A5 | Leave the app idle past access-token expiry, then open a feed or Profile | Silent refresh; no sign-in prompt; one refresh only |
| A6 | Airplane mode, open a signed-in screen, then restore network and retry | Offline message with retry; recovery without losing the session |
| A7 | Sign out | Welcome screen; relaunch stays signed out |
| A8 | Sign out, then use the former access token against `/me` (operator side) | 401; refresh with the old refresh token rejected |
| A9 | Two devices or accounts: each sees only its own `/me`, sessions and data | No cross-account data |
| A10 | Account already exists, wrong password, unverified account sign-in | Defined error screens; no account enumeration |

## B. Settings and sessions (needs the account route allow-list extended)

| # | Step | Expected |
| --- | --- | --- |
| B1 | Password reset request and reset | Neutral response; old sessions end after reset |
| B2 | My account: active sessions list; revoke another session | Revoked session rejected on next use |
| B3 | Change password, preferences, privacy request | Saved; re-authentication prompt where required |

## C. Creator onboarding and profile (needs onboarding and media capabilities)

| # | Step | Expected |
| --- | --- | --- |
| C1 | Become a creator: application, then reviewer decision (API, with MFA) | Eligibility becomes active only after approval |
| C2 | Edit creator profile; handle conflict case-insensitively | Saved; conflict stays on the form |

## D. Upload, processing, moderation, publish, playback (needs media worker, R2, moderation)

| # | Step | Expected |
| --- | --- | --- |
| D1 | Select an MP4 within limits (50 MiB, 5 min, 1080p); check file; reject an unsupported file | Limits enforced before and after upload |
| D2 | Upload to R2; interrupt the network mid-upload, resume | Interrupted state, then completion; one object |
| D3 | Preparing state, then FFmpeg result | Playable MP4 up to 720p; poster generated; status polling bounded |
| D4 | Reviewer decision (API, MFA) approves | Video published; unlisted from others until approved |
| D5 | Playback from another account | Plays from the R2 delivery path; link expires at about 300 s; not logged |
| D6 | Rejected or removed video | Rejection notice; no playback |
| D7 | After approval the video shows "Approved, not public": Manage video, **Publish**, confirm; then **Unpublish**, confirm; then Publish again | Public only after Publish; Unpublish hides it from another account; each step asks first; a video still in review offers neither |
| D8 | Edit details of the published video, then delete a draft and a rejected video | Edits show at once; deleted videos leave the library; no raw service text in any error |

## E. Engagement and points (needs engagement, points, consumers)

| # | Step | Expected |
| --- | --- | --- |
| E1 | Like and unlike (including repeat taps, two devices) | Server count equals the number of distinct accounts |
| E2 | Watch past the qualifying threshold; replay; seek forward without watching | One qualified view per account/video; no view for skipped time |
| E3 | Creator Lone Stars balance and history | Balance equals ledger; one award per qualified view; daily cap 100 per creator |
| E4 | Withheld points explanation | Matches the server ledger entry |

## F. Moderation and audit (needs moderation capability)

| # | Step | Expected |
| --- | --- | --- |
| F1 | Report a video | Receipt; appears in reviewer queue |
| F2 | Reviewer decision and creator notice, then appeal | Decision applied once; independent appeal reviewer |
| F3 | Operator checks audit rows for the above | Delivered once; no loss after an induced outage |

## G. Resilience and security observations

| # | Step | Expected |
| --- | --- | --- |
| G1 | Offline and server-error states on each screen used | Clear message, retry, no raw errors |
| G2 | Secure storage: credentials survive restart; no credential in logs or screenshots | |
| G3 | Network trace (operator): HTTPS only; no HTTP fallback | |

## Sign-off

| Result | Count |
| --- | --- |
| PASS / FAIL / NOT TESTED | |

Open defects each get an identifier, the journey row, the build commit and the evidence reference. The owner signs the outcome; a FAIL in sections A or D to F keeps R1 NO-GO.
