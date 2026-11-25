# Phase 11 — comprehensive application test report

**Date:** 25 November 2026. **Product source tested:** `384f4b5f00ba0c4420621ec51f7260ab5cdeb7a0` (no product code changed in this phase). **Harness:** `scripts/phase11/`, added after that commit. **Status: testing executed to the limit of this environment. This is not UAT acceptance, not a release approval and not a production-readiness claim.** Production remains NO-GO.

**Companion documents:** [test matrix](Phase11_Test_Matrix.md) (242 rows) · [defect register](Phase11_Defect_Register.md) · [security assessment](Phase11_Security_Assessment.md) · [infrastructure assessment](Phase11_Infrastructure_Assessment.md) · [release blockers](Phase11_Release_Blockers.md) · raw results in [`results/`](results/).

## 1. Summary

| | |
| --- | --- |
| Tests classified | **242**: **149 PASS, 11 FAIL, 39 BLOCKED, 43 NOT RUN** |
| New black-box tests run against the real stack | **130**: 122 PASS, 8 FAIL |
| Product defects found | **6** (1 High, 3 Medium, 2 Low), plus 3 carried forward from Phase 10 and not retested |
| Release blockers | **2 defects** and a list of unmet gates ([release blockers](Phase11_Release_Blockers.md)) |
| Existing suites re-run at this commit | all pass: nine services **1,089**, console **179**, scripts **459**, 11 local journeys, TLS PostgreSQL, staging runtime, event pipeline, real-broker pipeline **6**, Flutter 3.47.8 analyze clean and **1,823** tests |

**What this phase could not do, in one paragraph.** There is no AWS or staging access, no Cloudflare R2 credentials, no Docker daemon or container images, and **no physical iPhone or Android device**. Everything below ran on one disposable local stack. So **Group 8 (mobile devices) is entirely BLOCKED**, real R2 upload is BLOCKED, deployed-infrastructure checks are BLOCKED or NOT RUN, and **Groups 5, 6 and 7 (Events, Advertising, Financial workflows) are NOT RUN because those modules do not exist as code** (they are unapproved design packages). I did not simulate any of them to make the matrix look fuller.

## 2. Pre-test requirements

| Requirement | Result |
| --- | --- |
| Verify source commit and image digests | **Commit** verified: `384f4b5f…`, working tree clean before the harness was added. Dependency locks recorded by hash (`requirements-dev.txt` `3ed1b2af…`, `requirements-ci.txt` `92de7ce8…`, `pubspec.lock` `38e9cc46…`). **Image digests: not applicable**, no image was built or run (no Docker daemon) |
| Confirm deployed service versions | **Not applicable**: nothing is deployed; the nine services and the console ran as local processes of the same commit |
| Verify required migrations | **Done**: every stack start (more than ten in this phase) applied all 60 migrations to a fresh TLS PostgreSQL; `makemigrations --check` is clean for all services and the console; a second `migrate` is a no-op (T10_31) |
| Confirm staging environment health | **BLOCKED**: no access to AWS staging |
| Verify safe test-account isolation | **Done**: every account is synthetic (`@example.test`), in a disposable database bound to `127.0.0.1`; mail is captured locally; no outbound traffic from the stack; no real data touched |
| Confirm secrets are not printed | **Done and tested**: T10_90 searched every service log for every credential, token and recovery code the harness created (over 40 values) and found none; T10_06 shows no database password in any process command line. Secrets live only in `0600` files in temporary directories |
| Review resource capacity | **Partly**: host 4 vCPU, 16 GiB; each service process about 90 to 105 MiB resident. **The AWS instance size is still unrecorded and capacity unmeasured** (open since R1) |
| Tested backup and recovery plan before destructive or migration operations | **Done on the fixture**: T10_30 dumped the database, restored it into a new one, compared row counts for every table (over 50 rows of data) and trigger counts, and proved the append-only guard still fires after restore; it ran before the migration reversal test (T10_31). The destructive broker and worker tests (stop, kill) touched only disposable processes. **No backup or restore was attempted on any real system, and none exists there** |
| Explicit authorization for deployment or staging changes | **None requested, none made.** No deployment, no AWS action, no production access |

## 3. Results by area

### 3.1 Backend and API (Groups 1 to 4, 10)

| Group | PASS | FAIL | BLOCKED / NOT RUN | Highlights |
| --- | --- | --- | --- | --- |
| 1 Accounts and security | 40 | 3 | 0 | Registration, verification single-use, sign-in, refresh rotation and **family revocation on replay**, logout revokes the access token immediately, session list and cross-account revoke, password change and reset end other sessions, role change and account disable take effect on the next request, **MFA**: challenge only, wrong code, TOTP replay refused, recovery code single use, challenge exhausted after repeated failures, forged challenge, moderator cannot do administrator actions; brute force throttled (first 429 within the approved budget); resend and reset mail limited to at most 3 an hour **and measured by counting real emails**, identical answers for known and unknown addresses. **FAIL:** D11-003 (registration 409), D11-004 (no registration limit), D11-005 (validation before authorization) |
| 2 Creator and content | 18 | 0 | 1 BLOCKED, 1 NOT RUN | **Real FFmpeg** on crafted files: valid video converts to H.264/AAC faststart; Full HD scaled to 1280x720 with even sides; 4K refused; over five minutes refused; empty, text, truncated, audio-only and junk files refused; **HLS-playlist and concat files that point at local files are refused and produce no output**; appended PHP/ZIP bytes do not survive; GPS and title metadata stripped; bit-flipped file does not hang. API: viewer cannot draft; drafts start private and are not discoverable; input validated; upload intents enforce size and the exact attestation; **another creator's video answers identically to a missing video**; unfinished upload cannot be published; playback is signed and short lived. BLOCKED: real R2 |
| 3 Engagement and points | 19 | 1 | 2 NOT RUN | Likes and follows idempotent and private; self-view refused; faster-than-real-time progress not qualified; backwards, oversized and malformed progress refused; another account cannot use a session; a qualified view reaches **exactly one ledger entry through the real broker**; repeated progress and a second session in the window give one award; **the same event published twice is applied once**; ledger rows are attributable, and `UPDATE` and `DELETE` are rejected while the guard is in place (but see D11-002: the service's own login can remove that guard); **the daily cap of 100 is enforced and the excess is recorded as withheld**; **broker outage loses nothing and one award follows recovery**; **a `kill -9` consumer loses nothing and a restarted one processes once**; **queued messages survive a broker restart**; garbage that is not a task is discarded harmlessly. **FAIL: D11-001** (poison pill) |
| 4 Business | 12 | 1 | 0 | Grant required to register; owner assigned by the server; retries idempotent; **for every one of the 26 business-scoped operations in the contract, a stranger gets exactly the same answer as for a business that does not exist** (no existence leak); staff scope, single-use invitations, leaving ends access at once, removal fails closed (step-up); unverified businesses are not discoverable; search input hardened; public reads expose no owner or legal data. **FAIL:** D11-005 (T4_23). The full verification, listing, inquiry, review and report journey is the existing real-HTTP test (baseline, 11 of 11) |
| 10 Infrastructure and security | 21 | 3 | 6 BLOCKED, 3 NOT RUN | See the [infrastructure assessment](Phase11_Infrastructure_Assessment.md) and [security assessment](Phase11_Security_Assessment.md). **FAIL:** D11-002 (T10_03, T10_04), and the static finding that the repository's Nginx has no rate limiting (T10_81) |

### 3.2 Web dashboard (Group 9)

Real Chromium 158 against the real console and Gateway. **18 PASS, 1 FAIL, 5 NOT RUN.**

| Area | Result |
| --- | --- |
| Authentication | Administrator and moderator sign in with password then MFA and reach the dashboard; session cookie `HttpOnly`, `SameSite=Lax`; session identifier changes at sign-in; external `next` ignored; wrong password and unknown email give the **same page**; wrong MFA code opens nothing; a **viewer cannot sign in** to the console |
| Negative authorization | A moderator is refused administrator-only pages (creators, business access, categories); **every one of 17 console pages redirects an anonymous visitor to sign-in** |
| Sessions | Logout ends the session and **a stolen copy of the old cookie no longer works**; a GET to the logout URL does not sign you out; **POSTs without a CSRF token are refused on all five state-changing routes tested**; an idle session expires after 30 minutes and the 15-minute absolute limit applies even to an active session (server-side records aged) |
| Browser protections | CSP `script-src 'none'`, `frame-ancestors 'none'`, `form-action 'self'`; `no-store`; `nosniff`; same-origin referrer; **no CSP violation or script error on any page**; no stack traces or internals in any page |
| Accessibility (structural) | Every control, link and image has an accessible name; one `h1`, a `main` landmark, a language and title on every page; sign-in works by keyboard alone with a visible focus indicator and sensible tab order; all click targets are at least 24x24 CSS px. **FAIL: D11-006** (13 px horizontal overflow at 320 px, seven pages) |
| Not run | Firefox and Safari/WebKit (not installed); screen readers (none available); event, advertising and financial pages (do not exist); the full reviewer workflows through a browser (covered by the existing real-HTTP console journeys, not re-implemented) |

Honest note on method: my first run of this group had **test errors** (a one-character display name, an expectation that a token was a JWT, a missing cookie `url`, counting an HTTP 403 as a script error, and a link whose accessible name comes from its image `alt`). Each was a defect in my test, found by looking at the actual behaviour, and corrected without weakening any assertion that found a real fault. The two console results that stayed FAIL are genuine.

### 3.3 iOS results (Group 8)

**All 16 areas BLOCKED.** No iPhone, no Xcode, no attached machine. Not tested on a device: installation, launch, authentication, session persistence (including force-close restore, SEC-05), navigation, all journeys, playback, uploads, offline, slow connectivity, error recovery, layout, accessibility with VoiceOver, notifications (none implemented), permission prompts, Keychain behaviour. **What exists instead, and is not a substitute:** Flutter 3.47.8 `analyze` clean and 1,823 widget and unit tests passing, including layout audits at two viewports and 2x text for all 144 screens. The [iPhone checklist and run card](../iphone_e2e_checklist.md) are ready to be executed on a phone.

### 3.4 Android results (Group 8)

**All 16 areas BLOCKED** for the same reason (no device, no Android SDK or emulator). Not tested: install, launch, authentication, persistence, navigation, journeys, playback, uploads, offline, slow connectivity, recovery, layout, TalkBack, permissions, Keystore storage. The [Android checklist](../android_e2e_checklist.md) is ready.

## 4. Defects, blockers, assessments

The six new defects, with reproduction and retest criteria, are in the [defect register](Phase11_Defect_Register.md): **D11-001** (Points worker poison pill), **D11-002** (service logins can disable the append-only guards), D11-003 (registration enumeration), D11-004 (no registration limit), D11-005 (validation before authorization), D11-006 (console overflow at 320 px).

## 5. Limits of this evidence

1. **Local only.** One host, Django's development server for the HTTP services (as the repository's own journey harness uses), not Gunicorn behind Nginx and Cloudflare; headers such as `Server` were not judged for that reason.
2. **Fixture storage.** Playback signing was exercised offline; no object was ever stored or fetched.
3. **Single-message and burst scale.** No load, soak or long-running test was run. The burst test (400 requests, 32 concurrent) saw **no server error and no throttling**; median 13 ms, 95th percentile about 1 s on a single-threaded development server, which says little about production.
4. **Chromium only.** One browser engine.
5. **I wrote the tests and some expectations were wrong at first** (listed above). Every FAIL in the matrix was examined: the six defects are real; three FAIL rows are not product defects (two runner errors of mine, one static finding), and that is stated in the matrix.
6. **Not an independent test.** The same engineering team (here, the same assistant) wrote the code under test and the tests. An independent penetration test is NOT RUN.

## 6. Harness changes made in this phase

`scripts/phase11/` (stack builder, runner, five test modules, matrix generator) and `docs/engineering/phase11/`. **No product code, contract, migration or configuration was changed.** Two of the harness's own gates caught problems in the harness and were fixed: Bandit flagged SQL built from strings in my tests (rewritten with `psycopg` identifiers), and the secret scanner flagged a generated Flutter artifact left by my test run (removed).
