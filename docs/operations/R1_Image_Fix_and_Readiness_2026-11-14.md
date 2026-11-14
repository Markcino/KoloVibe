# KoloVibe R1: FFmpeg image blocker, secret dependencies, database preflight and readiness — 14 November 2026

**Decision: NO-GO to deploy.** This record authorizes no deployment, merge, AWS mutation, secret creation or database change. Owner decisions in force: OPA **APPROVED — WAIVED FOR RESTRICTED R1 STAGING**; backup and restore testing **APPROVED — WAIVED FOR RESTRICTED R1 STAGING**; no destructive or irreversible database change without separate approval. It updates the [runtime release candidate](R1_Runtime_Release_Candidate_2026-11-14.md), whose image decision it replaces.

## 1. The failure, from the logs

GitHub Actions run `43596907169` (main at the merge of PR #75), job "Build and scan shared service image", step "Scan local image vulnerabilities" (Anchore Grype 0.97.1, `fail-build: true`, `severity-cutoff: high`): the scan failed with "discovered vulnerabilities at or above the severity threshold", so the publish job was skipped. Every other job passed, including Django, Flutter, Security and SBOM, osv-scan, and the Dockerfile's own FFmpeg, SQLite and `pip check` assertions.

What the table contained (420 rows, 75 distinct CVEs in all; none had a fixed version for FFmpeg):

| Package set (all from the FFmpeg install) | Installed | Findings |
| --- | --- | --- |
| `ffmpeg`, `ffmpeg-libavcodec`, `-libavdevice`, `-libavfilter`, `-libavformat`, `-libavutil`, `-libswresample`, `-libswscale` | 8.0.1-r1 (Alpine 3.23) | 49 distinct CVEs on the same eight packages: **1 Critical (CVE-2026-40962), 26 High, 22 Medium**; the High set includes the named CVE-2026-52297, CVE-2026-8461, CVE-2026-64831, CVE-2026-66040 and CVE-2026-64834. "Fixed in" is empty for all |
| `libssh` 0.11.4-r0, `cjson` 1.7.19-r1, `alsa-lib` 1.2.14-r2 | pulled in by FFmpeg | Several High (libssh four, cjson three, alsa-lib one) |
| `busybox`, `ssl_client`, `python` binary | already in the base | Medium only |

The task's single-CVE description understated it: the blocker is the whole FFmpeg 8.0.1-r1 package set and three of its dependencies, not CVE-2026-52297 alone. None of it was in the shared image before PR #75 (main run `43593703173` was green).

## 2. Is a patched FFmpeg available?

Read-only checks of Alpine's package indexes and security database (metadata only):

| Alpine branch | ffmpeg | libssh | CVE-2026-52297 | CVE-2026-8461 |
| --- | --- | --- | --- | --- |
| 3.22 | 6.1.2-r2 | 0.11.2 | not listed | not listed |
| **3.23** (the shared image's base) | **8.0.1-r1** | 0.11.4 | **no fix listed**; no 2026 FFmpeg fix at all | no fix listed |
| **3.24** (released, Docker `python:3.12.16-alpine3.24` exists) | **8.1.3-r0** | 0.12.2 | **fixed in 8.1.1-r0** | **fixed in 8.1.2-r0** |
| edge | 9.0.2-r3 | 0.12.2 | | fixed 8.1.2-r0 |

So a supported, patched FFmpeg exists on Alpine 3.24, not on 3.23. For CVE-2026-40962 (the Critical) and several others the security database lists no fix on any branch. Whether Grype still reports them against 8.1.3-r0 can be decided only by the CI scan, which is why the fix is built so that the scan decides and is never bypassed.

## 3. Options evaluated

| Option | Verdict |
| --- | --- |
| **A. Keep FFmpeg in the shared image** | Rejected. Unpatched on 3.23; puts 113 packages, including network-facing libraries, into all eight API and consumer containers that never run FFmpeg; and a single scanner failure blocks every service's publication |
| **B. Move the whole shared image to Alpine 3.24** | Rejected for now. Changes the base of eight services, unrelated to the video worker, to fix one component |
| **C. Separate media-worker image on Alpine 3.24 with Alpine's `ffmpeg` package (tried; failed the scan)** | FFmpeg and its dependency closure exist only in the one image whose only job is to run it. The shared image returns to its previously green state. The scan gate is identical for both images and not weakened. If FFmpeg on 3.24 still fails the scan, only the media image fails, nothing is excepted, and the next step is below |
| **D. Minimal FFmpeg 9.0.2 built from pinned upstream source (chosen by the owner after C failed)** | MP4/H.264/HEVC/AAC/MP3/ALAC/PCM in, libx264 + AAC + JPEG out, scale/format filters, `file` and `pipe` protocols only; no network protocols, no devices, no optional libraries. Removes cjson, alsa-lib, glib, libssh and the rest of the dependency closure, and fixes the three FFmpeg CVEs fixed in 9.0 |
| E. Static third-party FFmpeg binary | Rejected: unverifiable provenance |

## 4. The fix

| Area | Change |
| --- | --- |
| `Dockerfile.service` | Build arguments `PYTHON_BASE` (default: the unchanged Alpine 3.23 digest), `WITH_FFMPEG` (default `0`) and `FFMPEG_SOURCE` (default `ffmpeg-empty`). The same `release` target builds both images. The default build copies an empty directory, never builds FFmpeg, and **refuses to contain it**. The media build (`WITH_FFMPEG=1`, `FFMPEG_SOURCE=ffmpeg-minimal`, base `python:3.12.16-alpine3.24@sha256:c5ba3dee…dd89`) builds **FFmpeg 9.0.2 from the upstream tarball pinned by SHA-512** (the value Alpine's APKBUILD records) in a throwaway `alpine:3.24.1` stage, copies two static binaries, adds only `x264-libs`, fails if any network protocol is compiled in, and re-asserts that no SQLite package or module exists |
| CI | New job "Build and scan media worker image": build with the two arguments; inspect (non-root, working directory, no secret-like env, Alpine 3.24, invalid service refused); FFmpeg and ffprobe on the encoder's fixed `PATH`; no SQLite; **the same scan step and thresholds**; SBOM must list `ffmpeg` and no SQLite; artifact `verified-media-image-<sha>`. The shared job now proves FFmpeg is absent |
| Publication | The publish job needs both images, verifies each artifact, pushes `…/services:vN` and `…/media-worker:vN`, resolves each remote digest, pulls it and compares image IDs. Both digests land in the one `published-image-<sha>` artifact (`published-digest.txt`, `published-media-digest.txt`) |
| Deployment tooling | `staging-aws.yml`: only `media-worker` uses `KOLOVIBE_MEDIA_IMAGE`; the validator enforces the media repository and the shared digest on the other six, and `--release-dir` checks both digests against the published evidence. The cluster tool's `--release-dir` still resolves the shared image; the media image is deployed by `docker stack deploy` from the stack |
| Contract tests | Updated for two images (two builds, two pushes, both required by publish), plus new tests for the media publication script (mocked registry cases), the artifact handoff, both scan steps being unweakened, FFmpeg only under `WITH_FFMPEG=1`, and the pinned bases |

Nothing was weakened: the scan step text, `fail-build: true`, `severity-cutoff: high` and the absence of ignore files are asserted by tests for **both** images.

## 5. CI results

Pull request run `43598874335` on commit `c4abb61` (all jobs finished):

| Job | Result |
| --- | --- |
| Django services and reproducibility (includes the new read-only database preflight verifier, 11 cases) | **PASS** |
| Flutter static and widget tests | **PASS** |
| Security scans and SBOM (secret scan, pip-audit, Bandit, SBOM) | **PASS** (after allowlisting three secret-name false positives found by an earlier run of this PR) |
| Python and Flutter dependency advisories / osv-scan | **PASS** |
| **Build and scan shared service image** (no FFmpeg, Alpine 3.23, unchanged gate) | **PASS** |
| Image build and security, eight-service PostgreSQL smoke matrix | **PASS** (8 of 8) |
| **Build and scan media worker image** (Alpine 3.24, FFmpeg 8.1.3-r0) | **FAIL at the scan step**: build, inspection, FFmpeg-on-sandbox-PATH and no-SQLite steps passed; the Grype scan ("severity-cutoff: high") found High and Critical findings. SBOM, artifact and publication steps were skipped |
| Publish | Not run (pull request) |

**The shared image blocker is resolved**: the corrected source's shared image passes the unweakened scan and all eight service smoke checks. **The media image is not yet publishable.** Distinct High or Critical findings in its scan (164 package/CVE rows in all):

| Package | Version | Severity | Fix available | Reachable in this pipeline |
| --- | --- | --- | --- | --- |
| ffmpeg (CLI and eight libraries) | 8.1.3-r0 | CVE-2026-70628, CVE-2026-70632, CVE-2026-96611 High; CVE-2026-107696 High | 70628, 70632 and 96611 are fixed in FFmpeg 9.0 (NVD ranges end at 9.0; Alpine 3.24 does not ship 9.x). **CVE-2026-107696 (RTSP redirect loop) affects every release through 9.0.2, the newest upstream** | RTSP and the other network protocols are refused by the encoder's `-protocol_whitelist file,pipe` |
| cjson | 1.7.19-r1 | CVE-2026-16554, CVE-2026-67215, CVE-2026-67216 High | none on any Alpine branch | not used; pulled in by FFmpeg's optional libraries |
| alsa-lib | 1.2.15.3-r0 | CVE-2026-56109 High | none listed | audio devices; not used |
| glib | 2.88.1-r1 | CVE-2026-58016 **Critical** | fixed in glib 2.89.0 (Alpine edge has 2.90.0, 3.24 does not) | D-Bus XML parsing; not used |

Progress from the first design (FFmpeg 8.0.1-r1 on Alpine 3.23: 49 distinct CVEs on the FFmpeg packages, 1 Critical, 26 High, 22 Medium): on Alpine 3.24 the named CVE-2026-52297 and CVE-2026-8461 and the earlier Critical CVE-2026-40962 are no longer reported; FFmpeg's own findings fell to 4 High and 14 Medium.

**Conclusion: no released FFmpeg passes a "High, regardless of fix state" gate today.** Alpine 3.24's package is the newest packaged build and still reports four High; the newest upstream release, 9.0.2, is itself affected by CVE-2026-107696. The remaining High and Critical findings in cjson, alsa-lib and glib come only from FFmpeg's full dependency closure, which this pipeline does not need.

**Decision needed from the owner (not made here):**

1. *Recommended path.* Build a **minimal FFmpeg 9.0.2** from upstream source in the media image: only the MP4/H.264/HEVC/AAC decoders, libx264 and AAC encoders, the JPEG poster path, the scale and format filters, and the `file` and `pipe` protocols; RTSP and every other network protocol, devices and optional libraries compiled out. That removes cjson, alsa-lib, glib, libssh and the rest of the closure, and fixes the three CVEs fixed in 9.0. The one CVE no release fixes, CVE-2026-107696, concerns code that would not be compiled in. If the scan still reports it, the media image can pass only with a **narrow, named-CVE exception for the media image** (Grype ignore for exactly that ID, with this rationale and an expiry), which is a deliberate relaxation of the gate and so the owner's decision.
2. *No exception.* Keep the gate as is. Then the media image stays unpublished until upstream fixes CVE-2026-107696, and R1 is deployed without the media worker (no upload, processing or playback; every other capability can still be exercised). The CI would be split so the shared image can publish on its own.
3. *Change the architecture* (not recommended: the R2 plus FFmpeg pipeline is approved).

## 6. Corrections found by replaying the cluster tool against the live specs

Method: read-only export of the eight live `docker service inspect` specs, networks, secret names and nodes; the tool's `update-plan` was then run **offline** against that export (the replay refuses any non-GET call). It exposed three places where the AWS profile did not match AWS, so the tool would have refused to plan at all:

| Profile assumption | Live AWS | Fix |
| --- | --- | --- |
| Database CA secret named `db_ca` | `kolovibe_pg_ca_v1` mounted at target `db_ca` | Profile records the environment's CA secret name; ownership check accepts exactly that name at that target. Oracle unchanged |
| Runtime logins `kv_<service>_run` | `kolovibe_<service>_app` | Profile `db_user_format` |
| Database host an address in `172.31.0.0/16` | the Swarm service name `kolovibe-postgres` | Accepted exactly; a service-name database is guarded by a running task (host-level probes cannot resolve overlay names); the earlier address form stays accepted |
| `verify-worker` expects `/api/v1/auth/login` gated | open on Gateway and Identity (accounts on): 405 for GET | Expects 405 when accounts are on, 403 otherwise |

After the fixes the replay result is: **a plain image update plans for all eight services**; the R1 plan stops at the first missing secret, naming it (`identity_mfa_encryption`), changing nothing. The stack file's database CA secret name was corrected to match.

Also observed (read-only, names only): the AWS Identity service additionally attaches the `kolovibe_identity_smtp_egress` network; the worker carries two Swarm labels (the profile ignores them); the manager has no OPA plugin and no policy directory, consistent with the waiver.

## 7. Remaining secret dependencies (names only; no value read)

State from the live secret list and service specs on 14 November 2026. "Present" means the Swarm object exists; whether its *contents* are correct is not inspected.

### 7.1 Already present and mounted (unchanged by R1)

Per service: `<svc>_django`, `<svc>_db`, `<svc>_tls_cert`, `<svc>_tls_key`, `<svc>_callers`, `<svc>_probe`, `internal_ca`, `kolovibe_pg_ca_v1` (at `db_ca`). Gateway also `gateway_outbound` (target `outbound_key`), `kolovibe_gateway_trusted_peers_accounts_20261110_v1` (`trusted_peers`), `kolovibe_account_uat_approval_20261110_v1` (`account_approvals`). Identity also `kolovibe_identity_smtp_user_20261110_v1`, `kolovibe_identity_smtp_password_20261110_v1`, the same approval secret. Broker: `kolovibe_rmq_ca`, `kolovibe_rmq_cert`, `kolovibe_rmq_key`, `kolovibe_rmq_definitions`, `kolovibe_rmq_app_password_v1`. PostgreSQL: `kolovibe_pg_admin_password_v1`, `kolovibe_pg_ca_v1`, `kolovibe_pg_hba_v1`, `kolovibe_pg_server_cert_v1`, `kolovibe_pg_server_key_v1`.

### 7.2 Absent: must exist before the rollout can plan (12 new objects)

| Capability | Object (all absent) | Mounted by | Content (not a value) |
| --- | --- | --- | --- |
| R2 | `kolovibe_content_r2_access_key_r1_v1`, `kolovibe_content_r2_secret_key_r1_v1` | content API, media worker | Cloudflare R2 token scoped to **one private bucket**, object read/write only |
| R2 (non-secret) | account id (32 hex) and bucket name | `--set-env` / stack inputs | identifiers, not secrets. **STOP: not provided** |
| RabbitMQ | `kolovibe_content_rabbitmq_url_r1_v1`, `kolovibe_engagement_rabbitmq_url_r1_v1`, `kolovibe_points_rabbitmq_url_r1_v1` | content, engagement, points (API and their workers) | `amqps://` URI, port 5671, one account per service. CA is the existing `kolovibe_rmq_ca` |
| Points to audit | `kolovibe_points_outbound_key_r1_v1`, `kolovibe_points_audit_peers_r1_v1` | points | signing key (32+ chars) and JSON `{"audit": "https://audit:8000"}` |
| Moderation to audit and content | `kolovibe_moderation_outbound_key_r1_v1`, `kolovibe_moderation_peers_r1_v1` | moderation | per-audience key map and JSON peers for `audit` and `content` |
| MFA and audit (Identity) | `identity_mfa_encryption`, `identity_audit_signing`, `identity_audit_peers` | identity API and its audit worker | a Fernet key, a signing key, JSON `{"audit": "https://audit:8000"}` |

### 7.3 Existing mounts that need a new version

These replace what is already mounted, through `--secret-override` (each new name must be the service's own `<service>_…` name or one the AWS profile lists):

| Object | Change |
| --- | --- |
| `kolovibe_gateway_trusted_peers_r1_v1` (listed) | peers file must equal exactly `{content, creators, identity, engagement, points, moderation}` as HTTPS origins |
| `kolovibe_gateway_outbound_r1_v1` (listed) | JSON map, one distinct key per audience (content, creators, identity, engagement, points, moderation) |
| `kolovibe_account_approval_r1_v1` (listed), for Gateway **and** Identity | adds the `mfa` and `audit` approval references to the existing four |
| `engagement_callers_2`, `points_callers_2`, `moderation_callers_2` | `{"gateway": <the key the new outbound map holds for that audience>}`; staging refuses a receiver with capabilities and no gateway credential |
| `audit_callers_2` | distinct keys for identity, points and moderation (the staging runtime refuses duplicates) |

### 7.4 Dependencies that cannot be seen from Swarm

* **RabbitMQ accounts, vhost, permissions and queues.** Only one application password secret exists. The definitions secret is not readable here. Needed: an account per service with write on its own queue and read only for its consumer, queues `kolovibe.content.media`, `kolovibe.engagement`, `kolovibe.points`, durable, TLS only. Check with `rabbitmqctl list_users` and `list_permissions` (names only) before creating the URIs.
* **MFA enrollment.** A reviewer (moderator) account must have enrolled TOTP through `enroll_privileged_mfa`; without it reviewer decisions, and therefore publication, cannot happen.
* **Audit receiving side.** Audit validates its callers file for distinct credentials; its allowed producers already include points, moderation and identity.
* **R2 bucket lifecycle** expiring originals and abandoned renditions (the code does not clean up).
* **Database logins**: each service's login needs privileges on the new tables of engagement and moderation (their schemas do not exist yet; the migration login creates them).

## 8. Read-only PostgreSQL migration and creator-handle checks

Two equivalent, non-destructive procedures, both ending in `ROLLBACK`/no commit, both over TLS, both printing counts and names only:

| Form | Use |
| --- | --- |
| `infra/postgres/r1_readonly_preflight.sql`, run with `psql -X -v ON_ERROR_STOP=1 -f` as a login that can read all schemas (for example the DBA login, from inside the PostgreSQL task) | When the only path to the database is the container. Output lists applied migrations per schema, schema and table counts for the new apps, handle-collision counts, `stream_upload_id` presence and login role names |
| `scripts/ops/r1_db_preflight.py` | Where a TLS path from a workstation or a throwaway read-only task exists. Compares applied migrations with the release commit (`--print-expected` shows the expected list), **stops** on a database ahead of the code, on case-only handle collisions while creators 0004 is pending, and on `stream_upload_id` data; handles are shown only with `--show-handles` on the operator's own terminal |

Proven by `scripts/verify_r1_db_preflight.py` (11 cases, in CI on a disposable migrated PostgreSQL): clean database passes; pending, ahead-of-code, collisions and `stream_upload_id` data are detected; the connection is read-only even if a bug tried to write; no handle or password appears in default output; the SQL file contains no write statement and selects no handle. Running either against AWS needs its own approval (it is a read, but of staging data).

Migration effects, restated (details in the release candidate record): content `stream_upload_id` is added by 0003 and dropped by 0005, net schema-neutral against the deployed image; creators 0004 fails on case-only collisions, which the preflight finds first; **with the backup waived no migration can be undone**, so no migration is approved here.

## 9. Updated GO/NO-GO

| Gate | Status |
| --- | --- |
| FFmpeg blocker: root cause, patched package, design, implementation | Done (sections 1 to 4) |
| Shared image passes the unweakened scan and the 8-service smoke matrix | **PASS** (section 5) |
| Media image passes the unweakened scan | **FAIL**: no released FFmpeg passes; owner decision needed (section 5) |
| Immutable published digests from the corrected source | Produced only by `main` CI after merge, and only when both image jobs pass; **UNVERIFIED** (nothing is published from a pull request) |
| AWS profile consistent with live services (replay) | **PASS** (section 6); live apply still unverified |
| R2 credentials, bucket, lifecycle | **BLOCKED** |
| 12 R1 secrets and the new versions | **BLOCKED** (none exist) |
| RabbitMQ accounts and queues; reviewer MFA enrollment | **UNVERIFIED / BLOCKED** |
| Read-only migration and handle checks | Prepared and proven on a disposable database; **not run on AWS** (needs approval) |
| OPA, backup and restore | Waived (approved) |
| Irreversible migrations, deployment, each AWS mutation | **BLOCKED**: no approval requested |

**NO-GO.** The shared image blocker is fixed and verified by CI. The media image still fails the scan and needs the owner's decision in section 5; the deployment also has none of its secrets, no R2 account, and no approval.

## 10. Exact next steps

1. Decide the media image path (section 5, options 1 to 3). Review and merge the pull request when both image jobs are green; main CI then publishes both digests.
2. Verify both manifests (a `read:packages` credential, or the pull inside `update`).
3. Supply R2 (identifiers, scoped keys, lifecycle); create the 12 objects and the new versions of section 7 (names there; values by the owner).
4. Verify RabbitMQ accounts and enroll a reviewer's MFA.
5. Approve and run the read-only database preflight; resolve any handle collisions by hand.
6. Written approval of the deployment plan (release candidate record, section 4), of the irreversible migrations, and of each mutating command.
