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
  each a canonical `https://<service>:8000` origin. Supply a gateway signing key
  matching each peer's caller-key JSON. The gateway can have an empty caller map.
  Keys, DB credentials, Django keys and probe tokens are distinct per service;
  signing/Django/probe secrets require at least 32 characters.
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
