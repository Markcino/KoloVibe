# Restricted staging candidate — activation pending

[staging.yml](staging.yml) prepares gateway/content/creators only, with Gunicorn,
verified TLS, external owner-only secrets, a private overlay, read-only non-root
filesystems, readiness checks, resource bounds and rollback-on-update-failure.
There are no published ports, database containers, account routes or points APIs.
This is a candidate, not a deployed/accepted stack. Single replicas and stop-first
updates can interrupt the pilot; the VM1 manager/host-ingress topology is not HA.

Set only the non-secret inputs named by `${...:?}` in the candidate. Images must be
`ghcr.io/markcino/kolovibe/<service>@sha256:<64-hex-digest>` from the exact successful
CI run, not tags. With those approved inputs:

```bash
.venv/bin/python scripts/validate_staging_stack.py
docker stack config -c infra/swarm/staging.yml
```

The first command validates static boundaries without contacting infrastructure.
The second requires Docker and is still pending in the current environment.
Neither deploys the stack. Input syntax checks do not verify image provenance or
the actual network's encryption, firewall, capacity or secret lifecycle.

## External provisioning prerequisites

- Provision/review the encrypted overlay and a private **host Nginx to gateway**
  route. Swarm DNS is available to containers, not automatically to host Nginx.
  No host-reachable address is invented here; do not add public published ports
  as a shortcut. Until this route is approved/tested, activation is blocked.
- Issue distinct server cert/key pairs with the actual service DNS SANs. Content
  and creators use those names internally. Put the gateway's private TLS name
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
transport references, a private identity service, updated peer configuration and
a separately reviewed ingress/stack change. This read-only candidate cannot enable
it merely by setting a flag. Account runtime checks are tested only with disposable
approval references and captured mail; they do not approve actual infrastructure.

See the [API roadmap](../../docs/engineering/API_Test_Deployment_Roadmap.md) for
runtime configuration, evidence and remaining backup/restore/acceptance gates.
Production remains rejected. No stack, network, secret or database was deployed
or changed on either VM.
