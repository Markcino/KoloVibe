# R1 image base: shared image moves to Alpine 3.24 — 19 November 2026

**Status record. Nothing is deployed or published by this change.** The base move adds no exception. The separate, owner-approved FFmpeg exceptions described below are scoped, expiring and checked against the built binary on every build.

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
- `.grype.yaml` gains the FFmpeg exceptions described below. The scan gate itself (fail on High) is unchanged.

## FFmpeg findings: owner-approved, scoped, expiring exceptions (decision of 19 November 2026)

The media image's scan reported 29 High findings in FFmpeg 9.0.2, which has no fixed release (9.0.2 is the newest; no 9.0.3 or 9.1 found). The owner chose scoped, expiring exceptions **only where the vulnerable component is not built into the minimal FFmpeg**.

- **All 29 were traced to a component** (FLIC, PSD, Hap, Huffyuv and VVC decoders; GIF, APNG, DVB-subtitle, Nellymoser, ProRes, OpenEXR and FFV1-Vulkan encoders; libwebp, libaribcaption, liboapv and LCEVC libraries; VAAPI, VDPAU, DXVA, Vulkan, VideoToolbox, V4L2 and Quick Sync hardware paths; and two bitstream filters). None is in the build, which is `--disable-everything --disable-autodetect` with only the H.264, HEVC, AAC, MP3, ALAC and PCM decoders, the MOV demuxer, and the x264, AAC and MJPEG encoders. Five also apply only to big-endian, 32-bit or RISC-V builds; the build targets x86_64 and aarch64.
- **Evidence quality.** Component names come from VulnCheck's CVE records as mirrored by cve.threatint.com, with some cross-checks against Red Hat and Debian trackers. These are third-party mirrors, not NVD, and were not checked against FFmpeg source here. This is the weakest part of the argument, which is why the next point exists.
- **The binary is the proof.** `infra/docker/ffmpeg/scan-exceptions.json` lists each CVE with its component. A new CI step (`scripts/check_ffmpeg_scan_exceptions.py`) runs `ffmpeg -version`, `-decoders`, `-encoders`, `-hwaccels` and `-bsfs` on the built image and fails if any listed component is present or any listed option was used. A test also pins the enabled codec list exactly.
- **Scope.** Each rule matches only apk `ffmpeg` at exactly `9.0.2-r0`. Any other FFmpeg version, any other CVE and every other package stay fully gated. The earlier CVE-2026-107696 exception is unchanged.
- **Expiry.** 2026-12-31 (about six weeks), enforced by a test, so the set is re-triaged or removed when FFmpeg ships fixes.
- **Residual risk.** The vulnerable code is absent from the compiled binary, so these findings do not apply to the running worker. They are still real in upstream FFmpeg: if the build ever enables one of these components, CI fails. The batch is still being published; **new findings from the same batch will fail the scan until they are traced the same way.**

**Consequence.** The publish job publishes the shared and media images together, so both scans must pass. Running staging images are unaffected, and the R1 rollout uses their existing digests.

## Evidence still to attach

- Manual run 192 (before the FFmpeg exceptions): shared-image scan, SBOM and all eight service smoke checks passed on Alpine 3.24; the media scan failed on the FFmpeg findings only.
- A manual run on the exception change must show the media scan and the new binary check passing. Until then the exceptions are a candidate.
