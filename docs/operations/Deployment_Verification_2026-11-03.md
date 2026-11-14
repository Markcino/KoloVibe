# Deployment and API verification — 3 November 2026

This record covers the Oracle Cloud deployment on 3 November 2026. See the [AWS staging record](AWS_Staging_Deployment_Verification_2026-11-10.md) for the separate 10 November rollout.

Owner: Mark Allen Gbalazeh. Status on 3 November: **deployment in progress; full API acceptance pending**.

## Verified source and image

The 3 November GitHub API readback identified the candidate as commit
`be03dbcced01f1a4f71c643dbc179da2810ffa61`.
[Actions run 41341123921](https://github.com/Markcino/KoloVibe/actions/runs/41341123921)
completed successfully. Its jobs include all eight shared-image service smoke
checks, the Django/PostgreSQL/TLS contract journeys, security scanning, Flutter
checks and image publication. Publication logs identify the exact candidate as:

```text
ghcr.io/markcino/kolovibe/services@sha256:8d6a16e450e6a7825c7d501069cd54fa3a75776afc2819e5664499bcef85ea14
```

This matches the digest in the owner's Gateway service output. CI evidence
describes its disposable fixtures; it is not evidence of a complete Oracle deployment.

## Live evidence and limits

| Area | Evidence | Current conclusion |
| --- | --- | --- |
| Gateway on VM2 | Owner-supplied `kvtest-gateway` output: HTTPS liveness 200, certificate hostname `gateway`, PostgreSQL `verify-full`, least-privilege schema and nonce-table checks pass; about 63.57 MiB used | Gateway startup and its database connection passed |
| Database route | Owner-supplied diagnostic: container default route exists, TCP to configured DB endpoint succeeds; HBA patch applied and reloaded | Preserve the working route, firewall and HBA configuration |
| Private DNS | Owner-supplied Gateway lookup resolves `vm-swarm-worker.privatesubnet.cabetechvnc.oraclevcn.com` to `10.0.2.103` | DNS works, but the existing fixed hosts mapping remains by owner instruction |
| Public API | [Recorded endpoint results](api-edge-2026-11-03.json): 19 checks, all HTTP 503 | External API acceptance fails; a 503 is not a successful protected-route check |
| Other seven Django services | No current live acceptance report available | Deployment and private API verification pending |
| RabbitMQ | Repo contains a separately pinned DHI candidate contract; no current live broker acceptance report | Broker startup, TLS, AMQP and Celery acceptance pending |
| Main branch governance | GitHub branch readback reports `protected: false` | Historical owner declaration does not establish current enforcement; no protection settings changed |

The public 503 responses alone do not identify which ingress component produced
the response. Nginx currently has no verified route from the public hostname to
this private Gateway. Changing database DNS is unnecessary for the next step.

## Observed capacity refusal and preserved architecture

The owner's first live runner execution stopped at the capacity gate before any
service mutation: `deployment_exit_code=1`, `private_checks_exit_code=2`,
`public_failed_checks=19`, `full_acceptance=false`. The reports were written to
`kolovibe-evidence-20261103T131440Z`.

Subsequent owner-supplied VM2 output reports 956 MiB total RAM, 322 MiB available,
no swap, and only the existing Gateway container (101.8 MiB of its 256 MiB limit).
Falco/falcoctl, Docker/containerd, PostgreSQL and Oracle agent processes are
present. RSS figures are not additive accounting because processes can share
pages; `MemAvailable` is the input used by the startup gate.

The failed plan required 2,176 MiB available: seven new API limits of 256 MiB
plus 384 MiB headroom. This is a conservative limit-based policy, not a measured
minimum application footprint. That reported number contains no additional broker
allocation; a new broker would require its own approved budget.

The deployment preserves the existing layout: Cloudflare edge/Tunnel →
host-installed Nginx on VM1 (the Swarm manager) → private Gateway and API services
on VM2. Cloudflared/Nginx usage on VM1 is not charged again against VM2's memory;
VM2's current OS, security, database and Gateway usage is already reflected in
its available-memory reading. This preservation does not establish that every
security control or ingress hop has passed end-to-end acceptance.

Existing OPA policy, encrypted overlays, file-backed Swarm secrets, verified
service/database TLS, runtime database identities, bridge guard and HBA rules
remain part of the deployment boundary. Account and privileged capabilities stay
disabled. Running Falco processes confirm presence only, not rule coverage or
alert delivery. The current public 503 responses do not verify Cloudflare access
policy, Nginx-to-Gateway TLS/routing or application authorization behavior.

Do not mark the full stack deployed, lower security controls, move workloads to
VM1 or treat swap as additional physical RAM on the basis of these results.
Full concurrent deployment needs a revised, measured memory budget and sufficient
worker capacity. Sequential component checks are a separate possible test mode;
they would not establish simultaneous full-stack readiness.

## Cloud Shell execution

The assistant workspace has repository access, but no SSH connection or keys for
the Oracle nodes. The deployment must therefore run using the owner's existing
Cloud Shell aliases `swarm-manager` and `swarm-worker`. Do not paste SSH keys,
registry tokens or database passwords into chat.

Download [kolovibe_cluster.py](../../scripts/ops/kolovibe_cluster.py), upload it to
Cloud Shell, and run from the directory containing that file:

```bash
python3 kolovibe_cluster.py cloud-run --registry-user markcino
```

The script copies itself to both VMs, checks VM2's existing bridge guard and
Gateway TLS liveness, and sends a fresh capacity report to VM1. It securely asks
for a GHCR token with `read:packages` only if new API services need creating.
Type the token at the hidden terminal prompt; it is not printed, put in command
arguments, persisted to Docker login files or copied into reports.

### Deployment boundaries

- Preserve `kvtest-gateway` byte-for-byte at the service-spec level. Do not
  change PostgreSQL/HBA, its credentials, the fixed DB hosts mapping, the bridge
  guard, internal overlays, the zero-replica manifest, Nginx or cloudflared.
- Create the seven missing `kvtest-*` Django services using the already-tested
  image, service-specific existing Swarm secrets and database roles. Use service
  DNS aliases, the existing encrypted overlays and VM2 placement. New APIs use
  readiness healthchecks; existing Gateway healthcheck settings stay unchanged.
- Require available RAM for each new API's 256 MiB limit, any new broker's
  configured limit, and 384 MiB headroom. This is a conservative startup gate,
  not a load-test result. A capacity refusal requires a sizing decision.
- Activate RabbitMQ only when exactly one existing candidate has a DHI digest,
  the four expected secret references, a configuration mount, a persistent
  volume, an internal encrypted messaging overlay, no published ports and
  satisfied VM2 placement labels. Reuse its existing image/configuration/auth
  references. If it is missing or differs, report it pending; do not guess an
  image, replace credentials, create broker storage or change node labels.
- Temporarily authorize only the exact Docker POST path and complete reviewed
  body. Require the OPA plugin's existing quiet mode before sending registry
  credentials. Arm an independent recovery timer, restore GET/HEAD-only policy
  after each mutation, and verify an unrelated secret write is denied with 403.
- Stop on an unexpected existing service rather than overwrite it. A partial
  run leaves already-created services for inspection; it does not delete a
  healthy service or automatically undo the working Gateway.

On successful SSH/preflight execution, the Cloud Shell runner collects
`private-api.json`, `public-api.json` and `summary.json` in a timestamped
`kolovibe-evidence-*` directory. A blocked deployment still attempts both
verification reports. Exit 2 means failures or pending deployment work; read the
report instead of treating Running as readiness. A failed preflight stops before
deployment. An SSH/transport failure can prevent report collection.

To inspect without deployment, run these steps from Cloud Shell:

```bash
scp kolovibe_cluster.py swarm-manager:/home/ubuntu/
scp kolovibe_cluster.py swarm-worker:/home/ubuntu/
ssh swarm-worker 'sudo python3 /home/ubuntu/kolovibe_cluster.py worker-preflight --profile oracle-staging' > worker-preflight.json &&
scp worker-preflight.json swarm-manager:/home/ubuntu/kolovibe-cluster-evidence.json &&
ssh swarm-manager 'sudo python3 /home/ubuntu/kolovibe_cluster.py plan --profile oracle-staging --worker-evidence /home/ubuntu/kolovibe-cluster-evidence.json'
```

The worker evidence expires after five minutes. Generate fresh evidence before
retrying a deployment. No long-lived credential is contained in that JSON.

## Endpoint acceptance matrix

| Scope | Checks | Required result |
| --- | --- | --- |
| Each of eight APIs | HTTPS `/health/live`, `/health/ready` | 200 and exact health JSON |
| Each API | `/ops/verify` with its file-backed token; absent/invalid token | 200; 403 for negative cases |
| Each API | Wrong Host; POST to liveness; unsigned internal probe | 400; 405; 403 |
| Each API | Own runtime role/schema/database, `verify-full`, TLS session; other service schema usage | Correct service identity, TLS, nonprivileged role; cross-schema usage denied |
| Gateway | `/api/v1/videos`, invalid cursor, unsupported query | List envelope; invalid queries 400 |
| Gateway | Unknown video/creator UUID | 404 JSON; no synthetic business records inserted |
| Gateway | Signed HTTPS calls to content/creators, nonce replay and forged signature | Successful dependent readiness; replay/forgery 403 |
| Account/business gates | Auth endpoints, `/me`, points/admin and unapproved routes | Remain disabled; 403 is evidence of gating, not feature completion |
| RabbitMQ | Running container, ping, running state, local alarms, virtual hosts | Diagnostics pass; AMQP/TLS integration remains separately pending |
| Public API | Health, metadata, invalid requests and negative routes | Intended API contract through the real public hostname |

The private tests only read business records. Signed requests necessarily create
anti-replay nonce records. The suite does not seed content, create user accounts,
send mail, run migrations or change database grants. Account success flows,
positive audit event ingestion, real RabbitMQ publish/consume and Celery retry/DLQ,
load/capacity acceptance, recovery/failover and unfinished business APIs are
explicitly outside these live checks. `full_acceptance` remains false while
those items are open.

## Ingress follow-up and status updates

After the private report passes, inspect VM1's active KoloVibe Nginx virtual host,
the actual private Gateway access path and the matching internal CA before
preparing a route change. Do not expose Docker, PostgreSQL or RabbitMQ, turn off
TLS verification, or publish a new port merely to make the tests green. The
runner intentionally makes no speculative ingress changes. Re-run the public
checks after the reviewed ingress change:

```bash
python3 kolovibe_cluster.py verify-edge > public-api.json
```

Attach the resulting private/public reports and task state to this record before
marking FND-07, FND-08, FND-12, FND-13, FND-14 or FND-17 accepted. Stage 3 remains
in progress and production remains NO-GO.

## Validation of this runner

Local syntax compilation and 11 offline regression tests passed. Tests cover
service credential separation, Gateway/DB route preservation, capacity blocking,
missing secrets, refusing unexpected existing services, credential serialization
rejection, stale evidence, exact-body OPA restoration on failure, response
contracts, redirect refusal and treating every 503 as a failed check.
The changed Python files also passed Bandit enforcement with no medium/high
findings, and the changed files passed `detect-secrets` scanning. Narrow inline
annotations identify public commit/object names and fixture paths that entropy
detectors otherwise mistake for credentials; no credential values are included.

```bash
python -m unittest discover -s scripts -p test_cluster_operations.py -v
```

These tests simulate Docker and policy operations. Live execution of the runner,
real OPA authorization and deployment convergence remain pending; they are not
claimed by the offline tests or by this document.
