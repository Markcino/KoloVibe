# R1 Stage 4A: security and CI acceptance — 13 November 2026

Verified `main`: `7ad0dae36aea34a5d4380f0515c464f78b13313b` (merge of PR #50). **Release recommendation: NO-GO.** One release gate fails and has no compatible fix available today (below). Nothing was deployed or merged by this work.

## Workflow runs on main

| Run | Commit | Result | Note |
| --- | --- | --- | --- |
| [43430293496](https://github.com/Markcino/KoloVibe/actions/runs/43430293496) | `7ad0dae36` (current main) | failure | Only the image scan fails. |
| [43428643794](https://github.com/Markcino/KoloVibe/actions/runs/43428643794) | `9e9561039` (PR #49 merge) | failure | Same single failure. |
| [43424938028](https://github.com/Markcino/KoloVibe/actions/runs/43424938028) | `4c77c077a` (PR #48 merge) | failure | Image scan. |
| [43422391927](https://github.com/Markcino/KoloVibe/actions/runs/43422391927) | `06f941d00` (PR #47 merge) | failure | Image scan. |

Job results for run 43430293496:

| Job | Result |
| --- | --- |
| Django services and reproducibility | success |
| Flutter static and widget tests | success |
| Security scans and SBOM (secret gate, bandit, pip-audit, SBOM) | success |
| Python and Flutter dependency advisories / osv-scan | success |
| Build and scan shared service image | **failure** at "Scan local image vulnerabilities" |
| Image build and security / each of 8 services | skipped (depends on the image job) |
| Publish verified shared image | skipped |

Stage 1A is confirmed in CI: the secret scan and the zlib and krb5-libs findings no longer fail.

## Local re-verification on main `7ad0dae`

| Check | Result |
| --- | --- |
| Eight Django suites and `makemigrations --check` | all pass (gateway 120, identity 58, creators 19, content 48 (1 skipped), engagement 32, points 34, moderation 18, audit 13); no migration drift |
| Django web `manage.py check` and tests | pass (21 tests) |
| OpenAPI validation (health and DOC-205) | pass |
| Script tests, structure, mobile design registry | 97 pass, OK, OK |
| detect-secrets gate, bandit gate | pass; 0 medium/high |
| pip-audit on `requirements-dev.txt` | 0 of 28 vulnerable |
| Not run locally | image build and scan (no Docker daemon, vulnerability DB host blocked), TLS PostgreSQL integration (run in CI, passing), osv-scan (blocked; passing in CI) |

## Findings and resolutions

| # | Finding | Severity | Resolution |
| --- | --- | --- | --- |
| 1 | `sqlite-libs 3.53.4-r0`: CVE-2026-119586, -119379, -119374, -119373 | High (gate) | **Open, no compatible fix.** See below. |
| 2 | CI lock pinned `lxml 5.4.0` (GHSA-vfmq-68hx-4jfw, PYSEC-2026-87, fixed 6.1.0); Dependabot alert #1 | High | Fixed in this PR: `pip-audit 2.10.1`, `cyclonedx-bom 6.1.3` (lib 10.5.0, lxml 6.1.3). |
| 3 | CI audited only `requirements-dev.txt`, so finding 2 was invisible to CI | Process gap | Fixed in this PR: CI also audits `requirements-ci.txt`, with a contract test. |
| 4 | No image signature or provenance attestation anywhere | Gap | Not implemented; recommendation below. |
| 5 | Swarm stack sets `user`, `read_only`, tmpfs and secret files, but no `cap_drop` or `no-new-privileges` | Hardening | Not changed: Swarm support cannot be verified here and deployment config is out of scope. |
| 6 | pip 25.0.1 (seven Medium or Low advisories), Python 3.12.16 and busybox findings | Medium or lower | Below the gate; no 3.12 fix exists for the Python items. Not changed. |

### Finding 1: why no fix was applied

- The scan ran after `apk upgrade --no-cache` and still reports `sqlite-libs 3.53.4-r0` with no fixed version.
- The latest published `python:3.12-alpine3.23` and `python:3.12-alpine3.24` both ship `sqlite-libs 3.53.4-r0`. Bumping the base image does not help.
- Removing `sqlite-libs` is not compatible: with `sqlite3` made unimportable, seven of eight services fail to start under the `KOLOVIBE_ENV=local` profile used by the CI smoke test (the gateway starts). Staging uses PostgreSQL, but the shared image and its smoke test also exercise the local SQLite profile.
- Remaining options, which need an owner decision: wait for an Alpine package fix (the weekly scheduled run will re-test); move the smoke test to a PostgreSQL profile and ship a PostgreSQL-only image without `sqlite-libs`; or record an owner-approved, time-boxed risk acceptance. No scanner setting, severity cutoff or exception was changed.

## Fix verification (finding 2 and 3)

```bash
python3.12 -m venv v && v/bin/pip install --require-hashes -r requirements-dev.txt -r requirements-ci.txt
pip check                                               # no broken requirements
python scripts/verify_dependency_locks.py --ci          # 59 packages, 873 hashes
pip-audit -r requirements-ci.txt --no-deps --disable-pip   # new lock: 0 of 59; old lock: lxml 5.4.0 flagged
pip-audit -r requirements-dev.txt --no-deps --disable-pip  # 0 of 28
cyclonedx-py requirements requirements-dev.txt --output-format JSON --output-file sbom.json  # CycloneDX 1.6, 28 components
python -m unittest discover -s scripts -p 'test_*.py'   # 97 pass
```

The lock was regenerated with the project's pinned `uv 0.9.15` and documented command. The application lock `requirements-dev.txt` is unchanged. Removing the new audit line makes the new contract test fail.

## Publication and image evidence

- Gating: `publish` needs all six quality jobs, runs only on a push to main with no status override, and publishes the exact artifact tested in the same run. It is covered by `scripts/test_ci_cd.py` and was observed `skipped` on every failing main run above. PRs, schedules and manual runs cannot publish. Only that job has `packages: write`.
- Last successful publication: [run 41341123921](https://github.com/Markcino/KoloVibe/actions/runs/41341123921), commit `be03dbcc`, recorded digest `ghcr.io/markcino/kolovibe/services@sha256:8d6a16e450e6a7825c7d501069cd54fa3a75776afc2819e5664499bcef85ea14` (from the operations records). It predates the zlib and krb5 fix, and no image has been published since. I could not re-read GHCR or the run artifact: package and artifact storage hosts are blocked in this environment.
- No signatures or attestations exist to verify. Recommendation: add keyless signing and build provenance to the publish job, and verify them before deployment.
- One shared image serves all eight services; the per-service matrix is a smoke test of that image, not eight builds.

## Container configuration inspected

Good: non-root `10001:10001`, no secrets in image environment (checked in CI), digest-pinned base, hash-locked dependencies, `read_only` root, tmpfs `/tmp`, secrets as 0400 files, replicas at zero, image required as a verified GHCR digest, resource limits required, staging profile refuses SQLite. Open: finding 5.

## Remaining blockers

1. Image scan (finding 1): release gate fails until an owner decision above is carried out.
2. Eight-service smoke matrix and publication have not run on any commit since PR #47; they run only after the image scan passes.
3. No signing or provenance; staging still runs the 1 November image.
4. Backend and Flutter device, TLS and live-R2 acceptance remain open per the R1 tracker.
