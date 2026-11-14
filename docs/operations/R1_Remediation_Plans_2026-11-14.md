# R1 AWS staging remediation plans — 14 November 2026

**Status: PLANNING ONLY. Nothing here is approved for AWS, executed on AWS or applied to GitHub settings.** Built from `main` `939f6a45bddf2831bcecfc5c78fb4c52ea5d05ad`. Owner decisions in force: read-only inspection, repository-only fixes, a branch-protection *proposal*, and OPA rehearsal on a **disposable** environment only. Not approved: any change to the AWS manager, Docker, SSH, Nginx, cloudflared, EC2, security groups, firewalls, IAM, networking, Swarm placement, containers, images, secrets, migrations or data.

## 1. Evidence state

| Item | Finding |
| --- | --- |
| Main CI | Run `43577143643` on `939f6a4` failed in "Security scans and SBOM" only. Reproduced offline with the hash-pinned `detect-secrets` 1.5.0: five *Secret Keyword* findings, all Swarm secret **names** or prose: `scripts/ops/kolovibe_cluster.py:738` and `scripts/test_cluster_secret_overrides.py:37,39,235,271`. |
| Root cause | PR #67 merged with `Security scans and SBOM` **failing**; PR #68 (based on `815f55a`, without #67) passed alone and merged 25 s later. No required checks and no up-to-date requirement existed; the ruleset only blocks deletion and non-fast-forward. |
| AWS read-only access | `ssh swarm-manager` (`ec2-…compute-1.amazonaws.com:22`) **timed out** on 14 Nov from the operator workstation; `swarm-worker` is reached through it. Nothing was retried or changed. Fresh VM evidence therefore needs the operator (section 3). |
| GHCR | The GitHub token has no `read:packages` scope, so manifest existence was not checked directly. |

## 2. Conflicting node-label and RAM reports: reconciliation

| Claim | Source | Environment | Verdict |
| --- | --- | --- | --- |
| VM2 carries `kolovibe.workloads=true`; RabbitMQ label absent | `infra/swarm/README.md`, `infra/rabbitmq/README.md` (1 Nov readback) | **Oracle** | True for Oracle. Not evidence about AWS. |
| Worker has **no labels** (`{}`), services pinned `node.hostname==ip-172-31-16-154` | Operator paste of 14 Nov in the image-update dry-run note | **AWS** | Current AWS statement; fresh read-back still outstanding. |
| "~956 MiB RAM, 322 MiB available, no swap" | `Deployment_Verification_2026-11-03.md` | **Oracle** VM2 | True for Oracle. |
| "two ~956 MiB VMs" for the AWS plan | Dependency matrix package F, plan section 3 | Copied from Oracle | **Unsupported for AWS.** The AWS instance size is not recorded anywhere in the repository. |

The reports do not contradict each other; they describe different environments. The AWS RAM and labels remain unverified until section 3 is run.

## 3. Operator read-only evidence pack (AWS)

Run as the named operator. Every command is read-only. None prints an environment value other than the two flags, a secret, or a key. Paste back the complete output.

On VM1 (manager) and VM2 (worker):

```bash
hostname; . /etc/os-release; echo "$PRETTY_NAME"; uname -mr
cat /sys/devices/virtual/dmi/id/product_name 2>/dev/null
nproc; free -m; swapon --show; echo "(swap list end)"; df -h /var/lib/docker
docker version --format 'engine={{.Server.Version}} api={{.Server.APIVersion}}'
docker info --format 'swarm={{.Swarm.LocalNodeState}} control={{.Swarm.ControlAvailable}} authz={{json .Plugins.Authorization}} liverestore={{.LiveRestoreEnabled}} cgroup={{.CgroupVersion}}'
docker plugin ls
docker stats --no-stream --format '{{.Name}} mem={{.MemUsage}}'
```

On VM1 only:

```bash
for n in $(docker node ls -q); do docker node inspect "$n" --format '{{.Description.Hostname}} role={{.Spec.Role}} avail={{.Spec.Availability}} state={{.Status.State}} labels={{json .Spec.Labels}} mem={{.Description.Resources.MemoryBytes}} cpus={{.Description.Resources.NanoCPUs}}'; done
docker service ls --format '{{.Name}} {{.Replicas}}'
# The two flags only, on every service (identity and gateway are the ones expected to differ):
for s in $(docker service ls --format '{{.Name}}'); do
  docker service inspect "$s" --format '{{range .Spec.TaskTemplate.ContainerSpec.Env}}{{println .}}{{end}}' \
    | grep -E '^KOLOVIBE_STAGING_(ACCOUNTS|PRIVILEGED)=' | sed "s/^/$s /"
done
sudo ls -ld /etc/docker /etc/docker/policies; sudo ls -l /etc/docker/policies
sudo python3 -c "import json;print('daemon.json keys:',sorted(json.load(open('/etc/docker/daemon.json'))))"
docker ps --format '{{.Names}}'          # containers on the manager itself
docker secret ls --format '{{.Name}}' | sort
```

Why each matters: labels and RAM settle section 2; the flags decide whether the AWS profile constants in the flags PR are right (and whether non-gateway services differ, which would require a per-service flag table); `authz`, `plugin ls`, `daemon.json` keys and `/etc/docker/policies` settle the OPA question; `docker ps` on the manager tells whether a Docker restart would stop anything.

## 4. Release image: publication is not deployment authorization

| Field | Value |
| --- | --- |
| Digest | `ghcr.io/markcino/kolovibe/services@sha256:887c9a051acd7521f9e69b9b8cf398273e88c539ac52934b6314a4311c3398e8` |
| Tag / source | `v0.124.1` / commit `92e5a55aec02a8174794f762645f3ef996cbe52e` |
| Gates (run `43516806784`) | Django, Flutter, security scans and SBOM, osv, shared-image build, vulnerability scan, "no SQLite" image and SBOM checks, eight-service smoke matrix, publish: all success. The publish step compared the pushed image ID with the verified image ID. |
| Evidence | CI artifact `published-image-92e5a55…` (expires 2027-02-11), the input for `--release-dir`. The companion `verified-image-…` artifact expires 14 Nov 22:10 UTC and is not needed afterwards. |
| Still the same code? | Between `92e5a55` and `939f6a4` only the ops tool, its tests and docs changed; no service, package, Dockerfile or requirements file. |
| Not shown | Current `main` has **no** published digest (publish is skipped while CI is red). GHCR manifest existence and pullability from both nodes are unchecked. |

**Publication** means CI built, scanned and stored an immutable image and recorded evidence. It authorizes nothing on AWS. **Deployment authorization** is a separate, written owner decision that names this exact digest, the operator, the restore point and the services in scope; it is not requested in this document.

### 4.1 Release approval plan: what a deployment approval must contain

A deployment approval is a written record from the owner; silence, a merged PR or a green CI run is never approval. It is valid only for one run and lapses after 24 hours or on any change to the items below.

| Field | Required content |
| --- | --- |
| Preconditions (all true, evidence linked) | `main` CI green; the CI-fix, gateway-flag and placement PRs merged; live gateway flags read back and equal to the AWS profile; OPA decision taken and, if adopted, rehearsed (section 5); no unresolved BLOCKED output from the tool's dry runs |
| Release | The exact digest from section 4 and the `published-image-<sha>` artifact used as `--release-dir`; any other digest is out of scope |
| Restore point | A reference to a backup that has been **restored and validated** (section 6), with the evidence package attached |
| Operator and window | A named operator on VM1 and VM2, start and end time, and who can stop the run |
| Scope and order | Services named explicitly; receivers one at a time with `verify-worker` after each, gateway last; no service outside the list |
| Secrets | Secret **names** only (never values), who created them, and the `--secret-override` pairs; per-peer keys exist before the gateway moves |
| Migrations | Explicit yes/no; if yes, order, logins, the handle-collision report and the rehearsal result on the restored copy |
| Stop conditions | Any BLOCKED message, failed `verify-worker` or `verify-edge`, Swarm `rollback_*` or `paused` state, or an unexpected service change: stop and report |
| Rollback owner | Who runs `rollback` and who decides on restoring data (schema changes are forward-only) |
| Evidence | Commands, UTC times, HTTP statuses, digest per service from `docker service inspect`, redacted logs |

## 5. OPA test plan (disposable environment only)

### 5.1 What the tool needs, and what has never been proven

`kolovibe_cluster.py` requires, for **every** manager-side mode including dry runs: Docker authorization plugin `openpolicyagent/opa-docker-authz-v2:0.9` enabled with args exactly `["-policy-file","/opa/policies/authz.rego","-quiet"]`, a root-owned `/etc/docker/policies/authz.rego` equal to a GET/HEAD-only baseline, and `info.Plugins.Authorization` equal to that one plugin. `update` and `rollback` open a policy window (`allow_once`): a systemd-run 3-minute watchdog, an atomic `os.replace` of the policy with one exact method/path/body rule, restoration, and a mandatory 403 on an unrelated `POST /secrets/create`.

**All of this has only ever run against mocks.** The 3 Nov record states that real OPA authorization was pending, and the 1 Nov Oracle preflight recorded the plugin pointing at a missing policy file with fail-open warnings. The key unproven assumption is that the plugin picks up a policy replaced by atomic rename.

### 5.2 Environment

Preferred: a throwaway single-node Swarm VM in the owner's AWS account, same architecture, OS image and Docker Engine version as the manager (taken from section 3), in an isolated VPC/security group with no route to staging, no staging secrets and no staging data, terminated afterwards. Provisioning it needs its own owner approval (cost, IAM, who creates it). A hosted CI runner is a lower-fidelity fallback (different kernel, Docker and architecture). The existing AWS manager is **not** an option.

### 5.3 Tests (record command, UTC time, output; no secrets)

| # | Test | Pass criterion |
| --- | --- | --- |
| T1 | Compatibility: `uname -m`, Docker and API version, plugin pull, plugin architecture | Plugin installs disabled; manifest matches host architecture |
| T2 | Plugin with **missing** policy file | Expected fail-open per 1 Nov record: tool's `policy_baseline` stops; record whether an unrelated write succeeds (documents the hazard) |
| T3 | Baseline policy, plugin enabled with the required args | `info.Plugins.Authorization` and `plugin inspect` equal the tool's expected values; GET succeeds; POST to `/secrets/create` returns 403 |
| T4 | **Reload semantics**: atomic rename of the policy while the plugin runs | New rule effective without restart; restoration effective. If not, the tool's design does not work and needs a reviewed change |
| T5 | Syntax error in the policy | Record behaviour (expected deny-all); recovery by file restore only |
| T6 | `allow_once` against real Docker: exact service create/update with body | Exact body passes; a body differing by one field, and any other path, return 403 |
| T7 | Window cleanup under SIGINT, SIGTERM, SIGHUP and `kill -9` | Policy restored (watchdog restores within 3 min after `kill -9`); the 403 proof passes afterwards |
| T8 | Quiet mode: request bodies and registry auth in daemon and plugin logs | Nothing credential-like is logged; test with a canary value that is not a real secret |
| T9 | Normal operator work under the baseline: `docker service ls`, `docker pull`, `docker secret create`, `docker exec` | Record which are denied. This defines the secret-creation procedure the tool lacks today |
| T10 | Daemon reload and restart: `kill -HUP` versus `systemctl restart docker` after adding the plugin to `daemon.json` | Record whether a reload suffices (no container disruption) or a restart is needed |
| T11 | Reboot | Plugin and policy come back enabled before the API serves requests; no fail-open window |
| T12 | Plugin crashed or disabled while `daemon.json` still lists it | Record the exact API behaviour (expected fail-closed) |
| T13 | Lockout recovery drill | See 5.4; time it; operator gets Docker API access back using only host root access |
| T14 | Full tool rehearsal on the disposable Swarm: fixture services named for the AWS profile, `update-plan`, `update`, `rollback` | Dry run changes nothing; update moves exactly the named service; rollback restores image and secret references |
| T15 | Swarm control plane unaffected: node join, scheduling, overlay traffic during T3–T11 | No task flapping; internal Swarm traffic is not subject to the Docker API policy |

### 5.4 Failure modes, lockout recovery and rollback (for the later production request)

* **Fail-open**: plugin enabled but policy file missing or unreadable. Prevention: create and verify the policy file first; the tool's file check; T2/T3 evidence.
* **Fail-closed lockout** (bad policy, crashed plugin): the Docker API denies operator commands, but **SSH and root on the host are independent of the Docker API**. Recovery uses only host root: restore the saved `/etc/docker/daemon.json` (remove the `authorization-plugins` entry) and reload or restart Docker; or restore the policy file from the pre-change copy. Both are timed in T13. Prerequisite for any production attempt: a second out-of-band path (cloud serial console or SSM), a saved copy of `daemon.json` and the policy, and the node's EBS snapshot, all owner-provided.
* **Blast radius of a Docker restart on the manager** (only if T10 shows a restart is needed): manager control plane briefly unavailable; VM2 tasks keep running; any container on VM1 stops unless live-restore is on (check `docker ps` on VM1).
* **Rollback of the OPA change**: remove the daemon entry and reload/restart; `docker plugin disable` then `docker plugin rm`; delete the policy directory only after the plugin is gone. Rollback leaves the Docker API unauthenticated as it is today.
* **Production gate**: only after T1–T15 pass on a disposable environment matching the manager, evidence reviewed by the owner, a maintenance window set and a separate explicit approval naming the exact commands. Not requested here.

## 6. PostgreSQL backup and restore validation plan

### 6.1 Known facts and gaps

PostgreSQL runs as a single Swarm service (`dhi.io/postgres@sha256:1ff21f77…`) pinned to VM2 with RabbitMQ and the eight APIs; the database is `kolovibe_staging`, one schema per service (`gateway, identity, creators, content, engagement, points, moderation, audit`) with `kolovibe_<service>` NOLOGIN roles and separate login roles (`infra/postgres/schema_isolation.sql`). No backup exists or has been restored (FND-16, ADR-016 open, SEC-032/SEC-038); no RPO/RTO is recorded; the volume location, PostgreSQL major version and free disk are unrecorded. The 10 Nov record notes the data includes UAT tester accounts, so treat dumps as personal data.

### 6.2 Procedure (needs separate approvals; nothing is run now)

1. **Read-only facts** (operator): PostgreSQL version, data volume and size, WAL settings, free space, roles list (names only), per-schema row counts.
2. **Backup**, in a maintenance window: `pg_dump -Fc` of `kolovibe_staging` and a separate globals dump, executed by the DBA login inside the database service, streamed over SSH to the operator workstation and encrypted on arrival with a public key whose private key never touches the VM. No plaintext dump is stored on the VM. Record start/end time, dump size, SHA-256 of the encrypted file, and the dump's snapshot time. Expected impact: read load on a memory-constrained VM, with no writes and no lock beyond `ACCESS SHARE`.
3. **Restore test location**: **not** on the AWS staging VMs (capacity, and a restore must never touch production volumes). Use a disposable host in the owner's account or a local Docker environment on the owner's machine, with disk encryption, the same PostgreSQL major version as production, and no network path to staging. Do **not** use a hosted CI runner for real data.
4. **Restore**: create roles first from the globals dump, then `pg_restore --exit-on-error --no-owner --single-transaction` where permitted; record duration (this is the measured RTO).
5. **Validation** (all outputs attached):
   * `pg_restore --list` counts equal the source object counts; per-schema row counts equal the counts taken in the same dump snapshot.
   * `scripts/verify_postgres_isolation.py` privilege audit passes on the restored copy; no service role gained cross-schema access.
   * Migration state: `manage.py showmigrations` for each service against the restored copy using the exact release digest in section 4 lists the expected applied set.
   * **Migration rehearsal on the copy**: apply the forward migrations there (never on staging), including the case-insensitive creator-handle check before `creators 0004`; record timings and any failure.
   * One service starts and passes its readiness probe against the restored copy.
6. **Evidence package**: commands, UTC times, file hashes, versions, counts, durations, pass/fail per check, destruction record of the disposable environment and of the decrypted dump. Owner sets the RPO/RTO from the measured numbers (ADR-016).
7. **Gate**: restore point attested and restore proven **before** any migration or image move (`update --restore-point-ref` takes a reference only; it cannot verify a restore).

## 7. GitHub main protection proposal (not applied)

Current state: ruleset `26202507` "KoloVibe Rules" is active on the default branch with only `deletion` and `non_fast_forward`; no bypass actors; classic branch protection absent. Proposal: **add** rules to that ruleset (do not replace it):

```json
{
  "rules": [
    {"type": "deletion"},
    {"type": "non_fast_forward"},
    {"type": "pull_request", "parameters": {
      "required_approving_review_count": 0,
      "dismiss_stale_reviews_on_push": true,
      "require_code_owner_review": false,
      "require_last_push_approval": false,
      "required_review_thread_resolution": true}},
    {"type": "required_status_checks", "parameters": {
      "strict_required_status_checks_policy": true,
      "required_status_checks": [
        {"context": "Django services and reproducibility"},
        {"context": "Security scans and SBOM"},
        {"context": "Flutter static and widget tests"},
        {"context": "Python and Flutter dependency advisories / osv-scan"},
        {"context": "Build and scan shared service image"},
        {"context": "Image build and security / gateway"},
        {"context": "Image build and security / identity"},
        {"context": "Image build and security / creators"},
        {"context": "Image build and security / content"},
        {"context": "Image build and security / engagement"},
        {"context": "Image build and security / points"},
        {"context": "Image build and security / moderation"},
        {"context": "Image build and security / audit"}]}}
  ]
}
```

Decisions inside the proposal:

* **Approvals = 0** because there is a single maintainer; a self-approval requirement would block every merge. The value is the required, up-to-date checks. Raise to 1 when a second reviewer exists.
* **Strict (up-to-date) policy on**: this is the control that would have stopped the #67/#68 race.
* **Not required**: `Publish verified shared image` (runs on push to `main` only), and the jobs that are skipped on pull requests. GitGuardian is optional; add it only if the owner wants it enforced.
* **Bypass**: none proposed; an emergency path is temporarily setting the ruleset to disabled by the owner. Adding a repository-admin bypass limited to pull requests is an alternative the owner may choose.
* **Risks**: renamed matrix jobs leave a PR waiting on a check that never reports; the strict policy forces a re-run after every other merge. Both are visible and recoverable.
* **Apply order**: only after the CI-fix PR is merged and `main` is green; then apply, then confirm with a throwaway pull request that a red check blocks the merge.
* **Rollback**: `PUT` the saved original rule list (`deletion`, `non_fast_forward`) back to ruleset `26202507`, or set its enforcement to `disabled`.

## 8. Approval requests

Each is separate; approving one approves nothing else.

| ID | Request | Risk | Depends on |
| --- | --- | --- | --- |
| PR-A | Push `fix/ci-secret-scan-cluster-tool` (`fa1edd2`) and open a PR | None to AWS; five name-only allowlist markers | none |
| PR-B | Push `fix/aws-gateway-staging-flags` (`8086933`) and open a PR | Tool-only; AWS flag values still need the section 3 read-back before merge | PR-A merged |
| PR-C | Push `fix/aws-placement-profile-consistency` (`10b548c`) and open a PR | Validator and docs only; no behaviour change by default | PR-A merged |
| PR-D | Push this document as a docs-only PR | None | PR-A merged |
| GH-1 | Apply the section 7 ruleset change | Can block merges until checks are green | PR-A merged; owner reviews the JSON |
| I-1 | Named operator runs section 3 (read-only) | None | operator |
| I-2 | Provision the disposable OPA rehearsal host (5.2) and run T1–T15 | Cost only | I-1 facts |
| I-3 | Take an encrypted logical backup of staging PostgreSQL (6.2 step 2) | Read load on VM2; handles personal data | I-1 facts, window |
| I-4 | Provision the disposable restore-test environment and run 6.2 steps 3–6 | Cost; personal data on a disposable host | I-3 |
| I-5 | OPA on the AWS manager | **Not requested** | I-2 passes; separate approval |
| I-6 | Deployment of the section 4 digest, secret swap, migrations | **Not requested** | all of the above |
