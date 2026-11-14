# KoloVibe R1 release-candidate evidence record — 14 November 2026

**Decision: NO-GO for AWS staging deployment and physical-iPhone R1 acceptance.** *(Code gaps in section 4 are addressed by the follow-up [runtime release candidate](R1_Runtime_Release_Candidate_2026-11-14.md); the operational findings here still stand except where that record corrects them: the AWS worker does carry two Swarm labels, and OPA and backup are now waived for restricted staging.)* This record authorizes nothing. No AWS, Docker, Swarm, OPA, database, secret, IAM, SSH, firewall or network operation was performed or attempted for it. Nothing was merged or deployed.

Baseline: `origin/main` `0afc0d3` (PR #73, CI run `43592285946`, all jobs green). Branch: `release/r1-candidate-2026-11-14` (main plus the per-service flag guard, one isolation hardening, one test-guard fix and this documentation). Evidence was produced on the operator's macOS workstation (Python 3.12.5, PostgreSQL 14.15 client/server tools, Flutter stable) and is repeated by CI on the pull request.

## 1. Source evidence and its limits

| Input | State |
| --- | --- |
| Current `main` | Verified: `0afc0d3`, CI green, shared-image publication succeeded. |
| PRs #69, #70, #71, #72, #73 | Verified merged (`gh pr list`): #69 `a92b8e9`, #70, #71, #72, #73. |
| Local commit `ebe3068` | Existed only in a local branch (`fix/per-service-staging-flags`). Re-applied unchanged as the first commit on this branch (it was already rebased onto #70 by the operator) and reviewed: it is valid and still needed. |
| 14 November "AWS staging evidence" and "security-readiness audit" reports | **Not in the repository or the working tree.** Their findings are treated as **user-reported** and are used only where the repository's own records (the 14 Nov remediation plans, the gate list, the flag read-back in `infra/swarm/README.md`) restate them. The original files are requested (section 7). |
| AWS facts (labels, RAM, OPA, Docker versions, live flags, GHCR pullability) | **UNVERIFIED** from this session. `ssh swarm-manager` timed out on 14 Nov from the operator workstation; this session has no AWS, Docker or SSH access. |

## 2. What this branch changes (repository side)

1. **Per-service staging flag guard** (`ebe3068`). `aws-staging` carries a reviewed flag table: Gateway and Identity `KOLOVIBE_STAGING_ACCOUNTS=1` / `PRIVILEGED=0`; the other six `0` / `0`; `oracle-staging` all `0` / `0`. `update-plan` and `update` stop on any named service whose live flags differ from its row, naming only the variable. `api_spec` sets a new service's flags from its row, not from the Gateway. A table the staging runtime would refuse, or one where Gateway and Identity disagree on `ACCOUNTS`, fails when the module loads.
2. **Isolation hardening.** `api_spec` also stops copying other Gateway-only configuration (`KOLOVIBE_ACCOUNT_APPROVAL_FILE`, `KOLOVIBE_STAGING_CREATOR_ONBOARDING`) into receivers; Identity still gets its approval file explicitly. New test `test_new_services_never_inherit_other_gateway_only_configuration`.
3. **Test file defect.** `unittest.main()` sat above `ServiceFlagTableTests` in `scripts/test_cluster_aws_profile.py`, so running that file directly skipped those tests (discovery, and so CI, was unaffected). Moved to the end of the file: 50 tests now run directly.
4. **Test guard.** `services/content/tests/test_posters.py` skipped on `shutil.which("ffmpeg")` but the encoder deliberately runs with the fixed `PATH` `os.defpath` (`/bin:/usr/bin`). On macOS with Homebrew FFmpeg the test failed instead of skipping. The guard now looks where the runtime looks. The sandbox `PATH` was **not** widened. With `PATH` overridden for one run only, the real encode and poster test passed (5/5), which is the only local evidence that FFmpeg encoding works end to end.
5. **Documentation corrections** (section 6).

No service code, migration, contract, Dockerfile, stack file or workflow changed.

## 3. Test and security evidence (local, before this PR's CI)

| Check | Result |
| --- | --- |
| `scripts/check_structure.py`, `check_mobile_design.py` | PASS (8 services; 108 entries, 150 assets) |
| Dependency locks (`verify_dependency_locks.py --python --flutter`, `--ci`) | PASS (28 packages / 373 hashes; CI toolchain 59 / 873) |
| `pip check` | PASS |
| `scripts/` unittest discovery (deployment tooling, staging runtime, image artifact, CI contract, secret-scan, ADR-013 spec) | PASS, 258 tests |
| `makemigrations --check --dry-run`, eight services | PASS, no pending model changes |
| Django suites | gateway 149 (14 skipped: "accepts no internal callers" by design), identity 85, creators 46, content 75, engagement 59, points 61, moderation 45, audit 40: **PASS**. Content with media extras installed (`requirements-media.txt`, hash-locked): 75 OK, 2 skipped (FFmpeg on sandbox `PATH`; caller-mode skip). |
| `apps/web_django` check and tests | PASS, 22 tests |
| PostgreSQL TLS migrations, isolation, ledger, events (`test_postgres_foundations.py`) | PASS on local PostgreSQL **14.15** (staging uses PostgreSQL 16 per the 10 Nov record: version gap noted) |
| Gateway, mail and web contract journeys (`verify_local_journeys.py`) | PASS, 6 tests (includes concurrent refresh: one winner, reuse revokes) |
| Restricted staging WSGI, TLS and capability journeys (`verify_staging_runtime`) | PASS |
| OpenAPI validation (health, DOC-205 draft) | PASS |
| Flutter `analyze` | PASS, no issues |
| Flutter tests | PASS, 893 |
| Secret scan (`detect-secrets` plus `check_secret_findings.py`) on a clean `git archive` of the branch | PASS (153 recognized non-secret identifiers) |
| `pip-audit` on `requirements-dev.txt` | PASS, no known vulnerabilities |
| Bandit | 126 findings, 0 medium/high (CI gate: PASS) |
| osv-scan (Flutter and Python advisories), container image build and vulnerability scan, "no SQLite" image check, eight-service smoke matrix, SBOM | **Not runnable locally** (no Docker, `osv-scanner` or Trivy). Run by CI on the pull request; the result is recorded on the PR, not here. |

Failures found and disposition: one local failure (content poster test, `PATH`), fixed as a test-guard defect without weakening the control. No test was disabled, skipped or loosened otherwise.

## 4. R1 API journey audit (source and tests; staging reachability)

"Local" means the Django suites and the PostgreSQL/HTTP journeys above. "Staging" means reachable through the restricted staging runtime that the deployed AWS stack uses.

| Journey | Backend source and tests | Flutter | Reachable on AWS staging | Verdict |
| --- | --- | --- | --- | --- |
| Registration, verification, login, logout, `/me` | Implemented and tested (identity, gateway, PG journeys) | Wired; tests for restore, rotation, logout | **Yes** (accounts flag, tester-reported 9/9 on 10 Nov) | Backend PASS; device retest UNVERIFIED |
| Verification resend, password reset, sessions list/revoke, change password, reauthenticate, preferences, privacy requests | Implemented and tested | Wired (M-007, M-009/010, M-083…) | **No.** `ACCOUNTS` middleware allows only register, verify, login, refresh, logout, `/me` | **FAIL** on staging |
| Persistent mobile session, refresh and replay | Server: rotation, replay revoke, concurrent single winner (tested). Client: restore on cold start, one shared refresh, rejection clears credentials, secure storage (`flutter_secure_storage`) | Tests pass | Refresh route yes | Local PASS; device SEC-05 retest and refresh-after-logout rejection UNVERIFIED |
| Creator onboarding | Implemented (DEC-004), tested | Wired (M-036–M-039) | Only with `KOLOVIBE_STAGING_CREATOR_ONBOARDING=1` on gateway and creators plus privileged MFA; currently off | BLOCKED |
| Creator profile management (`/creators/me`, `PATCH`) | Implemented, tested | Wired | **No** (`media` capability) | **FAIL** on staging |
| Video upload to R2 (intent, create-only PUT, completion, status) | Implemented; R2 signer tests need optional media deps (passed locally with them) | Wired (M-041–M-049) | **No**; also no R2 secrets, no bucket | **FAIL** on staging |
| FFmpeg on-demand processing | Worker `run_media_worker`, encode and poster (5/5 with sandbox `PATH` overridden) | n/a | **No worker service, no FFmpeg in the shared image** | **FAIL** on staging |
| Publish and playback | Moderated publication; publish/unpublish and signed playback (5 min) implemented | Playback wired; **no client for `/videos/{id}/publish` or `/unpublish`** and no M-053–M-056 management actions | **No** | **FAIL** (staging) and open Flutter gap |
| Server-verified views and likes | Implemented; qualified-view timing, per-account dedupe (DEC-003) | Likes, follows and watch-session progress wired | **No** (no engagement capability) | **FAIL** on staging |
| Non-cash points | Implemented, append-only audit evidence | Ledger wired (M-061–M-069) | **No**; also no consumers/schedulers | **FAIL** on staging |
| Moderation, appeals, audit events | Implemented (DEC-005); audit ingest allowed on audit service | Reports and appeals wired; reviewer UI is API-only by design | Reports/moderation **No**; audit ingest yes | **FAIL** on staging |

Mobile route check: every distinct path the Flutter app calls resolves to a gateway route (`/me/{kind}` is `reports` or `appeals`). Gateway routes with no Flutter caller are reviewer, onboarding-admin, analytics and publish/unpublish endpoints.

### Root cause of every "FAIL on staging" row

`services/gateway/service/capabilities.py` opens a staging capability only if `settings.STAGING_CAPABILITIES` lists it, but nothing in `staging_runtime.configure` ever sets that value, and `staging_runtime/middleware.py` allows only health, probe, public video/creator reads, the five account routes plus `/me`, MFA verify (privileged), creator onboarding (flag) and four internal paths. The Content, Engagement, Points and Moderation settings enable media, points and moderation only when `ENVIRONMENT == "local"`. So the deployed AWS stack **cannot** serve upload, publish, playback, likes, views, points, reports or moderation, whatever digest is deployed. `infra/swarm/staging.yml` has no media worker, Celery consumers or schedulers, and the shared image has no FFmpeg.

This is the dependency-matrix work (packages C, D, E, F). It is **not implemented in this branch**: it needs owner decisions that are not derivable from the repository (which capabilities to open first and for which services, R2 account/bucket/secrets, the AWS instance size and memory budget for a media worker, Celery and scheduler topology, a hostname-pinned AWS stack file versus labelling the nodes). Implementing it without them would mean inventing security configuration, which this task was told not to do. It should proceed as the reviewed PRs 3 to 7 of the matrix.

## 5. Release gates

PASS = proven by evidence in this record or CI. FAIL = proven not to work. BLOCKED = cannot proceed until an input or approval arrives. UNVERIFIED = no evidence either way.

### 5.1 Repository gates

| Gate | Status | Evidence / reason |
| --- | --- | --- |
| Per-service flag guard integrated and tested | **PASS** (pending PR CI) | Section 2; 50 profile tests, 158 cluster tests |
| No flag or Gateway-only config copied into other services | **PASS** | Tests in section 2 |
| Mismatched flags rejected without disclosing values | **PASS** | `test_the_refusal_never_echoes_other_environment_values` (Gateway and Identity) |
| AWS worker-label, RAM, backup and published-image documentation corrected | **PASS** | Section 6 |
| Backend and mobile suites, contracts, security tests, secret scan, advisories (Python) | **PASS** | Section 3 |
| Image scan, osv-scan (Flutter), smoke matrix, SBOM | **UNVERIFIED** here; **PASS** on `main` `0afc0d3`; to be repeated by PR CI | CI run `43592285946` |
| R1 journeys reachable on staging (all except accounts) | **FAIL** | Section 4 |
| Flutter publish/unpublish and manage-video actions (M-053–M-056) | **FAIL** (not implemented) | Section 4 |
| Media worker, RabbitMQ consumers and schedulers in a deployable stack | **FAIL** (absent) | `staging.yml`, `Dockerfile.service` |
| Cloudflare R2 delivery proven with real credentials | **UNVERIFIED** | Only mocked/signature tests exist |
| RabbitMQ delivery, retry, dead-letter, restart behaviour | **UNVERIFIED** | Local unit and PG event tests only; AWS broker queues were empty on 10 Nov |

### 5.2 Operational gates

| Gate | Status | Evidence / what is needed |
| --- | --- | --- |
| Published immutable digest for the candidate | **PASS (CI) / UNVERIFIED (registry)** | `ghcr.io/markcino/kolovibe/services@sha256:893a4d0138f761ff80416e7cf2c01381eec20344ad58ab43a3bfd0a447548ebe`, published by run `43592285946` from `0afc0d3`; read from the job log. Manifest existence and pullability from both nodes not checked (token lacks `read:packages`). It does **not** contain this branch's changes; a deploy digest must be republished from the merged release commit. |
| GHCR manifest and digest verification | **UNVERIFIED** | Procedure in the runbook, section 2 |
| PostgreSQL and RabbitMQ health, end-to-end messaging on AWS | **UNVERIFIED** | Last evidence 10 Nov: both 1/1, broker healthy, queues empty |
| OPA authorization rehearsal | **BLOCKED** | Needs the disposable environment (owner approval I-2); tool only ever ran against mocks |
| Encrypted PostgreSQL backup, restore test, RPO/RTO | **BLOCKED** | No backup exists anywhere; approvals I-3 and I-4 |
| AWS capacity, Swarm placement, permissions | **UNVERIFIED** / **BLOCKED** | Instance size unrecorded; SSH timed out; operator read-only pack (remediation plans section 3) not yet returned |
| Migration plan on restored copy (including creators 0004 handle collisions) | **BLOCKED** | Needs a restored copy |
| Rollback readiness | **PARTIAL** | Image/secret rollback implemented and mock-tested; schema changes forward-only; restore unproven |
| `main` protection (required, up-to-date checks) | **BLOCKED** | Proposal only (GH-1), not applied |
| Owner approval of exact deployment plan | **BLOCKED** | Not requested; cannot be until the gates above pass |
| Physical iPhone acceptance | **BLOCKED** | Needs a deployed, capability-enabled stack; checklist ready |

## 6. Documentation corrections

* `infra/rabbitmq/README.md`, `infra/swarm/README.md`, the dependency matrix: the "~956 MiB" RAM and the `kolovibe.workloads` label are **Oracle** facts; the AWS instance size is unrecorded and the AWS worker has no labels (hostname pin).
* `AWS_Staging_Deployment_Plan_R1_2026-11-13.md`: correction box. The image pin, the `sqlite-libs` blocker and "no published digest" are superseded (PRs #54, #60; digest above). Capability gates, worker services and FFmpeg stay open.
* Backup: the repository claims no existing encrypted PostgreSQL backup; the phrase "existing encrypted overlays" in the Oracle record means network encryption. `infra/rabbitmq/README.md` now says that no broker or database backup exists or has been restored.

## 7. Exact remaining approvals and inputs

| # | Needed from | Item |
| --- | --- | --- |
| 1 | Owner | Send the two 14 Nov reports (AWS staging evidence, security-readiness audit) so this record can cite them instead of treating them as user-reported |
| 2 | Owner | Decide the staging capability design for R1 (which capabilities and services; one worker topology; hostname-pinned AWS stack file or node labels) so packages C to F can be built and reviewed |
| 3 | Owner | R2 account, private bucket and scoped keys (names only in Git), approved memory budget once the AWS instance size is known |
| 4 | Operator (I-1) | Run the read-only AWS evidence pack and return the output |
| 5 | Owner (I-2) | Provision a disposable OPA rehearsal host; run T1 to T15 |
| 6 | Owner (I-3, I-4) | Encrypted backup, disposable restore, migration rehearsal, RPO/RTO |
| 7 | Owner (GH-1) | Apply or reject the `main` protection proposal |
| 8 | Owner | Review this PR; merge only after PR CI is green. Then a new digest is published |
| 9 | Owner | Written deployment approval per remediation plans section 4.1, naming the digest, operator, restore point, services, order, migrations and window. Valid 24 hours |

## 8. Decision

**NO-GO.** Even with every operational gate satisfied, the deployable stack cannot yet serve the R1 journeys the iPhone acceptance needs (section 4). The repository-side gates that could be closed without owner decisions are closed in this branch; the rest are listed above with the exact inputs needed.
