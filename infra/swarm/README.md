# Restricted staging candidate — activation pending

## Minimal deployment configuration on VM1

Do **not** clone the whole Django/Flutter project onto Oracle VM1 or VM2.
The pinned GHCR shared image already packages the application runtime. VM1
(Swarm manager) needs only the reviewed
[`infra/swarm/staging.yml`](staging.yml) and
[`infra/rabbitmq/rabbitmq.conf`](../rabbitmq/rabbitmq.conf)
at their original relative paths, along with protected Swarm secrets and
the explicitly approved non-secret deployment inputs. The host-Nginx operator
separately needs
[`infra/nginx/staging.conf.template`](../nginx/staging.conf.template)
when updating the verified TLS edge configuration; the DBA separately uses
[`infra/postgres/schema_isolation.sql`](../postgres/schema_isolation.sql).
VM2 receives service tasks and pulls images through Swarm; no application
source, Flutter files or Git checkout is needed on the worker. GHCR access
for workers needs a reviewed credential/provisioning lifecycle: do not store
registry credentials in Git or commit an `.env` file.

**Placement profiles:** the label constraints described next, and in `staging.yml`, are the
`oracle-staging` profile. The AWS staging nodes carry **no Swarm labels** (operator read-back of
14 November 2026), so on AWS placement is the exact `node.hostname==<worker>` pin of the
`aws-staging` profile of `scripts/ops/kolovibe_cluster.py`, and `staging.yml` must not be deployed
there. `scripts/validate_staging_stack.py --profile aws-staging` refuses explicitly. Giving the
worker, Celery and media services (matrix packages D, E) a stack file for AWS needs an owner decision
between a hostname-pinned AWS stack file and applying the labels, which changes Swarm node metadata.

**Worker-only scheduling:** All eight API services require
`node.labels.kolovibe.workloads == true`. RabbitMQ requires both that label
and `node.labels.kolovibe.rabbitmq == true` on the same worker, following
durable-volume and capacity approval. The November 1 worker readback confirms
only VM2 carries the workload label; neither node has the separate RabbitMQ
label. Do not add the latter until the broker's storage/capacity review passes.
These placement constraints do not establish memory sufficiency or authorize
activation. All nine services continue to default to `replicas: 0`.

[staging.yml](staging.yml) is the **single deployment YAML** defining all eight API
services and RabbitMQ, with Gunicorn for APIs,
verified TLS, external owner-only secrets, a private overlay, read-only non-root
filesystems, readiness checks, resource bounds and rollback-on-update-failure.
There are no published ports, database containers or enabled account/points APIs.
This is a candidate, not a deployed/accepted stack. All nine services default to
**zero replicas**: definition does not authorize activation. The two ~956 MiB VMs
cannot be assumed to fit eight Django processes plus RabbitMQ and existing
workloads. `API_MEMORY_LIMIT`, `API_MEMORY_RESERVATION` and `RABBITMQ_MEMORY_LIMIT`
are required reviewed inputs, not invented defaults. The validator rejects
nonzero candidate replicas; enabling a reviewed subset requires an explicit
owner-approved manifest/rollout change after capacity/identity/transport checks.
Single replicas and stop-first updates can interrupt the pilot; VM1 is not HA.

Set only the non-secret inputs named by `${...:?}` in the candidate.
`KOLOVIBE_IMAGE` must be `ghcr.io/markcino/kolovibe/services@sha256:<64-hex-digest>`
from the exact successful CI run, not a tag. All service containers use this same
digest and select their own application with `KOLOVIBE_SERVICE_NAME`.
RabbitMQ uses its own independently reviewed `dhi.io/rabbitmq@sha256:...` image;
the application image does not embed a broker. Database logins, secret mounts
and capabilities remain service-specific. With approved inputs:

```bash
.venv/bin/python scripts/validate_staging_stack.py
docker stack config -c infra/swarm/staging.yml
```

The first command validates static boundaries without contacting infrastructure.
The second requires Docker and is still pending in the current environment.
Neither deploys the stack. The previous separate RabbitMQ stack was removed;
its config remains [rabbitmq.conf](../rabbitmq/rabbitmq.conf), referenced relative
to this file. Input syntax checks do not verify image provenance or
the actual network's encryption, firewall, capacity or secret lifecycle.

## External provisioning prerequisites

- Provision/review encrypted service, data (`kolovibe_data`) and messaging
  (`kolovibe_messaging`) overlays and a private **host Nginx to gateway**
  route. Swarm DNS is available to containers, not automatically to host Nginx.
  No host-reachable address is invented here; do not add public published ports
  as a shortcut. Until this route is approved/tested, activation is blocked.
- APIs join the service/data networks only; RabbitMQ joins messaging only.
  No Celery worker or broker-dependent feature is enabled by this change.
  Scoped producers/consumers need a separately approved messaging connection,
  TLS broker credentials, queue policy and worker/retry/recovery acceptance;
  do not join all APIs to messaging as a shortcut.
- Issue distinct server cert/key pairs with the actual service DNS SANs. Services
  use their own names internally. Put the gateway's private TLS name
  first in `GATEWAY_HOSTS` and include every approved ingress Host explicitly.
  The first host is also used by the verified-TLS image readiness probe.
- Supply a trusted-peers JSON object containing exactly `content` and `creators`,
  each a canonical `https://<service>:8000` origin. The gateway's `outbound_key`
  secret is a JSON object mapping each peer audience to its own signing key, for
  example `{"content": "<key>", "creators": "<key>"}`; every value is distinct and
  at least 32 characters. A peer's `caller_keys` secret holds only that peer's entry,
  `{"gateway": "<key>"}`. A key must never appear in two receivers' secrets, and a
  receiver refuses a caller map in which two callers share a key. The gateway has no
  signed internal routes, so its caller map is empty. A receiver also accepts only
  its fixed caller set and paths (`CALLER_PATHS` in `service_auth.py`), so a key
  held by one service cannot sign as another service. A sender with a single peer
  (identity to audit) may keep one plain key. Keys, DB credentials, Django keys and
  probe tokens are distinct per service; signing/Django/probe secrets require at
  least 32 characters.
- Rotate a peer key without an outage (Swarm secrets are immutable, so each step
  creates a new secret and updates the service; never print or commit values):
  1. Generate a fresh random key for that one gateway-to-peer pair and create
     `<peer>_callers_<n+1>` containing `{"gateway": ["<new>", "<old>"]}`
     (at most two keys per caller) and roll the peer.
  2. Create `gateway_outbound_<n+1>` with the new key for that peer only and roll the gateway.
  3. Confirm readiness and the cluster `signed_tests` (run them only once the gateway holds the per-peer map; they fail against a single shared key by design; the cluster tool no longer assumes a fixed number of Swarm secrets and follows the secret names an existing service already mounts) (including "other peer credential
     rejected"), then roll the peer to a secret holding only the new key and retire the old secrets.
  A suspected leak is rotated the same way and the old key is destroyed, never reused.
  Moving from the previous single shared gateway key: roll every receiver to a
  secret holding `["<new>", "<previous shared>"]` first, then the gateway to the map,
  then drop the shared key everywhere. Treat the shared key as compromised afterwards.
- Provision external secrets named by the manifest from protected Actions
  environment secrets. Target files are `/run/secrets/*`, owner UID/GID 10001,
  mode 0400. Never commit credentials or include root `.env` in artifacts/images.
  Configure rotation, staged replacement and revocation before activation.
- DBA provisioning uses [schema isolation SQL](../postgres/schema_isolation.sql).
  Migrate via a separate service-owned migration login before rollout, not in
  application startup. Runtime logins receive only owning-schema USAGE, needed
  table DML and sequence privileges, not the schema-owner role, schema CREATE,
  database CREATE or cross-service grants. Reconcile DBA-provisioned nonce tables
  with existing `CREATE TABLE IF NOT EXISTS` migrations; do not create duplicates.
  Recheck/grant only newly required object permissions after reviewed migrations.
  Runtime access to migration history should be SELECT-only.
- Readiness checks DB privilege/migration/nonce state and gateway dependencies;
  public liveness only checks the process. `/ops/verify` requires the distinct
  probe bearer token and the existing protected verification workflow.

The account wave needs approved identity/session, SMTP, credential revocation and
transport references, activation of the defined private identity service, updated
peer configuration and a separately reviewed ingress/stack change.
This gated candidate cannot enable
it merely by setting a flag. Account runtime checks are tested only with disposable
approval references and captured mail; they do not approve actual infrastructure.

See [RabbitMQ prerequisites](../rabbitmq/README.md) for DHI entitlements, durable
node-bound volume, TLS definitions and sizing/recovery gates, and the
[API roadmap](../../docs/engineering/API_Test_Deployment_Roadmap.md) for
runtime configuration, evidence and remaining backup/restore/acceptance gates.
Production remains rejected. No stack, network, secret or database was deployed
or changed on either VM.

## Identity and privileged account activation

Identity secret mounts for SMTP, MFA encryption, audit signing/peers and approval
references are defined in the same YAML. They are external secrets, not embedded
values. See [protected secret validation](../../docs/security/staging-verification.md#identity-secrets-offline-validation-only)
for the Actions inputs. Actual provisioning is not performed by offline validation.
SMTP uses certificate-verified STARTTLS, authentication and a five-second timeout;
the sender/host/port still require an approved manifest change. The optional
`KOLOVIBE_SMTP_CA_FILE` permits a reviewed private CA, never disables verification.

`KOLOVIBE_STAGING_PRIVILEGED=0` remains the default at gateway and identity.
Activation requires both account and privileged gates, six owner approval references,
verified private identity/audit routing, audit trust for caller `identity`, migrations
and reviewed least-privilege grants. The candidate validator rejects activation
flags and nonzero replicas; Nginx still blocks account/MFA endpoints.

Enroll only an **existing active moderator/administrator**, on the identity runtime
with owner-controlled access. This command never creates/promotes privileged users:

```bash
python manage.py enroll_privileged_mfa \
  --account-id <existing-account-uuid> \
  --recovery-file <new-private-output-path> \
  --approval-reference <recorded-owner-approval>
```

Supply owner-only `KOLOVIBE_ENROLLMENT_SECRET_FILE` (authenticator Base32 secret)
and `KOLOVIBE_ENROLLMENT_CODE_FILE` (current TOTP), through private provisioning,
not command arguments. The separate MFA encryption key must be retained securely.
The command consumes the setup timestep, revokes sessions/challenges, writes ten
hashed-at-rest one-use recovery credentials exclusively to a new mode-0600 file,
and never prints them. Securely deliver them to the owner and remove temporary
enrollment/output files after handoff. Enrollment approval is an external owner
record, not independently verified by parsing its reference. No factor overwrite,
public promotion or password-only recovery backdoor is provided.

Password login returns a five-minute 202 challenge, not a session. TOTP allows
one timestep of clock skew and rejects replay; challenges allow five failed
attempts. Privileged sessions expire after fifteen minutes of MFA authentication;
refresh cannot extend that deadline. Role changes, removed factors and disabled
privileged capability invalidate them. Pre-migration sessions default to viewer;
existing creator/privileged sessions must log in again. Privileged client UI and
approved key replacement/rotation/recovery procedures remain activation gates.

Identity appends credential-free security events transactionally with its session
changes. Audit ingestion accepts only HMAC-authenticated identity calls over verified
HTTPS and is idempotent; conflicting event IDs fail. Owning PostgreSQL triggers
reject UPDATE, DELETE and TRUNCATE, while delivery acknowledgments are separate.
DB/schema owners can still change triggers: operator privilege and retention policy
remain required controls, not cryptographic tamper-proofing.

Before activation, provision an owner-approved periodic runner for
`python manage.py deliver_security_audit --limit 100`, using the identity runtime
and its least-privilege credentials. Failed batches exit nonzero, log a redacted
error and retain events for retry; subsequent successful batches acknowledge them.
Monitor command failures, pending delivery count and oldest pending timestamp in
`service_auditdelivery` joined to `service_securityevent`. Approve retry cadence,
delivery-lag alerts, retention and storage capacity; no live scheduler is installed
or silently implied here.

## Moving running services to a new approved image

Every mode except `verify-edge` needs an explicit `--profile <oracle-staging|aws-staging>`; see
[Choosing the environment profile](#choosing-the-environment-profile). The commands below show
`<profile>` for that reason.

`scripts/ops/kolovibe_cluster.py deploy` only creates missing services; it never touches a
running one. Moving services is a separate, explicit step run on VM1 after a fresh VM2
`worker-preflight`. No image is defaulted anywhere: every command that needs one takes the
published `published-image-<sha>` CI artifact (`--release-dir`, preferred) or an explicit
`--image` plus `--revision`. The tool rejects a tag, another repository, the 1 November
baseline, and a release whose evidence lists SQLite or a different service set.

```bash
python3 kolovibe_cluster.py update-plan --profile <profile> --worker-evidence worker.json --release-dir published-image \
  --services audit,identity --restore-point-ref <approved-restore-point>
```

`update-plan` is read-only. `update` is the same command, and is a dry run until
`--confirm-image <the approved digest>` repeats the digest exactly. When confirmed it:

1. requires `--restore-point-ref` (an operator attestation; the tool cannot verify a restore);
2. writes a new mode-0600 rollback record (current and target pin, service spec hash, rollback
   commands) before changing anything, and never overwrites an existing one;
3. updates the named services one at a time in a fixed order (audit, identity, creators,
   content, engagement, points, moderation, gateway last), changing only the image pin, the
   revision label and the stop-first rolling guards (monitor 30 s, roll back on failure);
4. re-reads each service first and stops if it drifted since planning, and stops at the first
   service Swarm pauses or rolls back, naming those not yet updated.

The Gateway changes only when named, and only with `--accept-ungated` while its spec has no
readiness healthcheck; run `verify-worker --image <digest> --services <name>` after each service.

Image rollback restores each service's previous spec, Gateway first, without a registry
credential (the previous image is cached on the worker). Dry run unless confirmed:

```bash
python3 kolovibe_cluster.py rollback --profile <profile> --services audit,identity --confirm-rollback identity,audit
```

**Rollback never reverses migrations.** Treat schema changes as forward-only and restore from
the approved restore point; export Points 0005, Moderation 0003 and Audit 0004 evidence rows
first. The tool does not run migrations, create or delete secrets, or touch PostgreSQL, Nginx or DNS;
it only re-points a named mount to a secret you already created (next section).

### Moving the image and chosen secrets in one step (`--secret-override`)

Used for the per-peer key rollout: the Gateway needs the new image **and** the per-peer outbound map
at the same time, and receivers mount `<peer>_callers_2`. `update-plan` and `update` take a
repeatable, never-defaulted flag, one per service and mount target:

```bash
sudo python3 kolovibe_cluster.py update-plan --profile <profile> --worker-evidence worker-evidence.json \
  --release-dir release/ --services gateway \
  --secret-override gateway:outbound_key=gateway_outbound_2
sudo python3 kolovibe_cluster.py update-plan --profile <profile> --worker-evidence worker-evidence.json \
  --release-dir release/ --services identity,content \
  --secret-override identity:caller_keys=identity_callers_2 \
  --secret-override content:caller_keys=content_callers_2
```

Format: `<service>:<mount target>=<Swarm secret name>`. The target is the file name under
`/run/secrets/` the service already mounts (`caller_keys` for a receiver's peer-key file,
`outbound_key` for the Gateway's outbound key). The service must also be in `--services`.
Nothing is inferred: without the flag no secret ever changes. Before anything is planned the tool
refuses (`BLOCKED:`, nothing changed) unless:

1. the service already mounts a secret at exactly that target (no new mounts, no removals);
2. the new secret **already exists in Swarm** (create it yourself first; the tool never creates one);
3. it is not already mounted at a different target of the same service;
4. the service passes the active profile's ownership check **with the new name in place**
   (`require_secrets_belong`): the service's own `<service>_...` secrets or, under `aws-staging`, the
   exact names listed for that service. A foreign secret, another service's name, or a replaced
   cluster CA mount (`internal_ca`, `db_ca`) is refused under both profiles;
5. the resulting spec differs from the live one only by the image pin, the revision label, the
   rolling-update guards and the named secret references. The mount target, mode (0400), UID and
   GID of the secret are carried over unchanged; any other difference stops the plan.

The plan and the rollback record list each swap as `{target, from, to}` (names only; no values, IDs or
specs). `update` stays a dry run until `--confirm-image <digest>` repeats the digest exactly, still
needs `--restore-point-ref`, still re-reads the service and stops on drift, and after Swarm reports the
update finished it re-reads the service and stops if its secret references are not the planned ones.
The Gateway with `--accept-ungated` moves image and secret in **one** service update, so there is no
interval with the new image on the old secret.

Suggested order for the per-peer rollout (owner creates the secrets; names only are recorded):
receivers image-only first (the old shared key still works); then receivers with
`--secret-override <peer>:caller_keys=<peer>_callers_2`; then the Gateway with the new image and
`--secret-override gateway:outbound_key=gateway_outbound_2`; run `verify-worker` and `verify-edge`
after each service.

**Rollback restores the secrets as well.** `rollback` asks Swarm for the service's previous spec, so
the image, the revision label and the secret references all go back together. The dry run prints each
changed mount (`secret caller_keys: identity_callers_2 -> identity_callers`), `rollback` refuses
(changing nothing) if a previous secret has been deleted from Swarm, and after it finishes the tool
re-reads the service and stops if its secrets differ from the previous spec. **Therefore keep the old
secret versions in Swarm until the soak is over** (do not retire `gateway_outbound` or the old
`_callers` secrets before then). Rollback restores the *previous* spec only, one step: to move back
further, re-pin with `update` and the prior approved release.

### Choosing the environment profile

`kolovibe_cluster.py` was written for the 3 November Oracle staging. The hostnames, service
prefix, placement pin, database address and the secret names a service may mount are now a
reviewed table of two profiles in the tool. The operator names one with `--profile`; it is
never inferred from the hostname, and no guard is relaxed by either profile (an unknown or
missing `--profile` stops the tool, and worker evidence is bound to the profile that wrote it).

| | `oracle-staging` | `aws-staging` |
| --- | --- | --- |
| Manager / worker hostname (`root()`, node lookup) | `vm-swarm-manager` / `vm-swarm-worker` | `ip-172-31-30-236` / `ip-172-31-16-154` |
| Service names | `kvtest-<name>` | `kolovibe-<name>` |
| Worker pin every service must carry | `node.hostname == vm-swarm-worker` | `node.hostname==ip-172-31-16-154` (no spaces; no node labels needed) |
| Database host in the Gateway | `vm-swarm-worker` | an IPv4 address inside `172.31.0.0/16` |
| Database guard in `worker-preflight` | `/usr/local/sbin/kolovibe_db_route_fix.py` | none needed: TCP reach plus a PostgreSQL TLS handshake from the worker, to the address the Gateway itself uses |
| Extra secret names allowed | gateway `trusted_peers` | identity: `kolovibe_account_uat_approval_20261110_v1`, `kolovibe_identity_smtp_user_20261110_v1`, `kolovibe_identity_smtp_password_20261110_v1`; gateway: `kolovibe_gateway_trusted_peers_accounts_20261110_v1`, `kolovibe_account_uat_approval_20261110_v1` |

Secret names are matched exactly and only for the service listed; a listed name on another
service, a rotated version of it, or any other foreign secret still stops the plan.

Running the AWS profile, as root on each VM, copying the tool unmodified (do not rename hosts or
edit it on the VM). Nothing below changes anything; `update` stays a dry run without
`--confirm-image`.

```bash
# VM2 (worker): a fresh preflight; it prints the evidence JSON and records the profile in it
sudo python3 kolovibe_cluster.py worker-preflight --profile aws-staging > worker-evidence.json

# VM1 (manager): copy worker-evidence.json over (valid for five minutes), then read-only plans
sudo python3 kolovibe_cluster.py plan --profile aws-staging --worker-evidence worker-evidence.json \
  --release-dir release/
sudo python3 kolovibe_cluster.py update-plan --profile aws-staging --worker-evidence worker-evidence.json \
  --release-dir release/ --services audit,identity,creators,content,engagement,points,moderation
```

`verify-worker` (VM2) and `rollback` (VM1) take the same `--profile aws-staging`. `cloud-run`
is Oracle-only (its SSH aliases are Oracle's) and refuses the AWS profile.

What the AWS profile could not take from evidence, so it fails closed until the first dry run
confirms it: the Gateway's networks must be `kolovibe_services` and `kolovibe_data` (plus,
optionally, `kolovibe_db_host_access`), its database name `kolovibe_staging`, and the database
logins `kv_<service>_run`. A `BLOCKED:` message names only the failed guard; report it rather than
editing the profile on the VM. The certificate identity of the database is not judged by
`worker-preflight` (no CA is readable from the host); `verify-worker` checks each service's own
`verify-full` connection.
