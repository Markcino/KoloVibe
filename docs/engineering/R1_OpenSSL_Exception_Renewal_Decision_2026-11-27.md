# OpenSSL scan exception: renewal decision needed (#143), 27 November 2026

**Status: DECIDED, 27 November 2026 06:04 UTC.** The owner chose option 1: renew the same 10 exact-package rules for seven days, to **2026-12-05 UTC**. The answer was recorded in the project thread. The previous exception ([R1_OpenSSL_Seven_Day_Scan_Exception_2026-11-21.md](R1_OpenSSL_Seven_Day_Scan_Exception_2026-11-21.md)) would have expired on 2026-11-28 UTC. This is a fresh risk acceptance, not a silent extension. Any further renewal needs another written owner decision.

## What was checked

| Check | Result | Evidence |
|---|---|---|
| Newest Alpine 3.24 `libssl3` / `libcrypto3` | `3.5.9-r1`. Every image build runs `apk upgrade` and still installs 3.5.9-r1 | PR #278 CI, 27 Nov 2026 about 06:15 UTC: shared image job 140340285578, staging web job 140340285724. Main run 45872265313 on 26 Nov showed the same |
| The five CVEs without the exception | All five still match, as High, on both packages, with **no fixed version** listed | The same two jobs fail at `Failed minimum severity level`. The table lists exactly CVE-2026-124709, CVE-2026-107494, CVE-2026-121482, CVE-2026-84786 and CVE-2026-107493, and no other High or Critical finding |
| Direct check of the Alpine package index or security tracker | **NOT RUN.** This session's network refuses `dl-cdn.alpinelinux.org`, `pkgs.alpinelinux.org` and `secdb.alpinelinux.org`. The CI builds above are the only fix-availability evidence | |
| Media worker image | Ran in the same PR. It uses the same Alpine 3.24 base and OpenSSL package | PR #278 CI |

So no patched package exists to remediate with. The removal in draft PR #278 makes the three image scans fail. Do not merge it until Alpine publishes a fix.

## Exposure

This is unchanged from the 21 November record:

- **What uses OpenSSL:** it provides TLS and cryptography in the shared service image (8 APIs and the workers), the staging web console image and the media worker. These are reachable through legitimate TLS traffic.
- **No mitigation claimed:** nothing claims that the vulnerable code is absent or unreachable.
- **Where it runs:** restricted AWS staging only. Production is not authorized.

## Compensating controls in place

None of these is shown to mitigate any individual CVE.

- Private overlay networks. Only host Nginx is public.
- Authenticated Gateway.
- Signed internal requests with replay protection.
- Database TLS with verification.
- No production deployment.
- Every other High and Critical finding stays blocking.

## Options

1. **Renew the same 10 exact-package rules for a short period. Proposed: 7 days, to 2026-12-05 UTC.** The scope, the daily fix check and the fail-closed expiry test stay the same. CI and main publication keep working. The residual risk stays open and is accepted again in writing.
2. **Do not renew.** From 28 November every PR and every main run fails the three image scans. No new images are published until Alpine ships a fix. The deployed staging release stays as it is.
3. **Remediate by changing the base distribution** (for example a Debian-based Python image). That is a larger image change with its own scan, reproducibility and FFmpeg build work. Whether a Debian OpenSSL build fixes these CVEs has **not been checked**. It cannot land before 28 November.

**Recommendation: option 1**, with the fix checked daily and the rules removed the day a patched package appears. Draft PR #278 already holds that removal, ready to re-run.

## Applying option 1

The renewal PR does all of the following:

- restores the 10 rules exactly as before;
- changes only the expiry comment and the two test dates;
- links the owner's written decision.

Nothing else changes.

## Follow-up

- Check every day for a patched Alpine `libssl3` / `libcrypto3`. Draft PR #278 holds the removal; re-run its CI to check.
- On or before 2026-12-05 UTC, either remove the rules (once a fix exists) or put a new decision to the owner. The tests fail closed on that date.
