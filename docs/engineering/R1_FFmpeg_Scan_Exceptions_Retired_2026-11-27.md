# FFmpeg scan exceptions retired (#143), 27 November 2026

**What changed:** all 30 FFmpeg ignore rules were removed from `.grype.yaml`:

- the 14 November rule, CVE-2026-107696;
- the 19 November second set, 29 CVEs.

Every FFmpeg finding is gated again. This only tightens the gate; no exception was added or extended.

## Evidence that no rule still applied

| Run | Media image | Shared image (no FFmpeg) | Reading |
|---|---|---|---|
| `main` run 45872265313, `e82f43e`, 26 Nov 2026, Grype DB built 26 Nov 06:22 UTC | "ignored 10 vulnerability matches" | "ignored 10 vulnerability matches" | The shared image has no `ffmpeg` package. Its 10 are the OpenSSL rules (5 CVEs × 2 packages), so the media image's 10 are the same OpenSSL matches and **0 are FFmpeg** |
| PR #278 run 45949017558, 27 Nov 2026, OpenSSL rules removed, FFmpeg rules kept | No "ignoring" line at all; fails only on the 10 OpenSSL High matches | Fails only on the same 10 | With the FFmpeg rules in place, **none matched**. No FFmpeg finding at or above High appears |

FFmpeg 9.1 fixed the 24 November advisories, and the scanner no longer matches the earlier 30 CVEs to the 9.1 apk. These rules were already marked "to be pruned once the scan shows which still apply" (`.grype.yaml`, version-move note of 25 November). The scans now show that none still apply.

## What stays

- **`infra/docker/ffmpeg/scan-exceptions.json`:** kept as dated evidence, with a `retired` note.
- **The minimal-build guard:** CI still runs `scripts/check_ffmpeg_scan_exceptions.py` against the built binary, so the minimal build stays enforced:
  - no blanket enables;
  - no network protocols;
  - only the listed codecs.
- **If the scanner later matches an FFmpeg CVE again:** the media scan fails closed until the finding is triaged and the owner decides. No rule comes back silently.

## Rollback

Revert this change. That restores the 30 rules, which match nothing today.
