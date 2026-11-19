# R1 image base: shared image moves to Alpine 3.24 — 19 November 2026

**Status record. Nothing is deployed or published by this change, and no scanner exception is added or widened.**

## Why

Run 191 on `main` (after PR #86) and run 190 on the PR both failed the two image scans, with every other job passing. The vulnerability database built on 19 November (v6.1.10) added findings that did not exist on 17 November, when the last full run passed. The failures are in base-image and FFmpeg packages, not in code this repository changed.

| Image | Base | High findings in the 19 November scan | Fixed package listed |
| --- | --- | --- | --- |
| Shared service image | Alpine 3.23 (`libcrypto3`, `libssl3` 3.5.9-r0) | 4 OpenSSL: CVE-2026-95692, CVE-2026-107496, CVE-2026-95691, CVE-2026-88823 | none |
| Media worker image | Alpine 3.24.4 | 29 FFmpeg 9.0.2 (listed below); **no OpenSSL finding** | none |

The media image, already on Alpine 3.24 and already running in staging, shows no OpenSSL finding of any severity. The shared image used an older base only because it had not been moved.

## What changed

- `Dockerfile.service`: the default `PYTHON_BASE` is now `python:3.12.16-alpine3.24` at the same digest the media image already uses. Python stays at 3.12.16. Nothing else in the build changes.
- `ci_cd.yml`: comment only; `MEDIA_PYTHON_BASE` is unchanged.
- `test_shared_service_image.py`: the shared and media bases must be the same digest-pinned Alpine 3.24 image, and no Alpine 3.23 base may remain in the Dockerfile or workflow.
- `.grype.yaml` is **not** changed. The existing guard that allows exactly one approved exception (CVE-2026-107696) is untouched and still passes.

## Not changed and still open

**FFmpeg 9.0.2 in the media image.** 29 High findings with no fixed package. 9.0.2 is the newest upstream release at the time of writing; no 9.0.3 or 9.1 was found. The CVEs are:
125181, 125196, 125202, 125204, 125208, 125210, 125211, 125212, 125213, 125214, 125218, 125219, 125222, 125227, 125229, 125233, 125235, 125239, 125241, 125248, 125249, 125250, 125251, 125256, 125257, 125259, 125260, 125262, 125269 (all `CVE-2026-` prefixed).

Public information found for only two of them: CVE-2026-125229 is reported in the Huffyuv/FFVHUFF decoder and CVE-2026-125222 in the Hap decoder. Neither decoder is compiled into the minimal build (`--disable-everything`; only H.264, HEVC, AAC, MP3, ALAC and PCM decoders and the MOV demuxer are enabled). The component of the other 27 could not be established from the sources reachable here. A scanner exception needs that evidence per CVE and an owner decision; the repository guard deliberately allows only one. None is proposed here.

**Consequence.** The publish job publishes the shared and media images together, so no new image of either can be published until both scans pass. The running staging images are unaffected, and the R1 rollout uses their existing digests.

## Evidence still to attach

- The CI run on this change must show the shared-image scan passing on Alpine 3.24. Until it does, the base move is a candidate, not a verified fix.
- Eight-service smoke and release-evidence jobs run only after both scans pass and have not run on this base.
