# KoloVibe R1 AWS staging: operator runbook (deployment, verification and rollback)

> **Dated procedure — review before reuse (23 November reconciliation).** The steps below were written for the **14 November** candidate (including its two-image artifact assumption and older PostgreSQL assumptions), not the verified **v0.357.1 three-image** release. Use [current release/rollback evidence](R1_AWS_Staging_Reconciliation_2026-11-23.md) and the pinned manifest for any future authorized rollout. Do not execute these historical commands as a generic upgrade recipe. The restricted-staging no-backup/OPA waiver **does not** constitute production recovery or security acceptance; PostgreSQL ownership remediation requires a separate reviewed procedure and recoverability decision.

**Status: PROCEDURE FOR A FUTURE, SEPARATELY APPROVED RUN. Nothing here is authorized or executed.** Read it with the [release-candidate evidence record](R1_Release_Candidate_Evidence_2026-11-14.md) (current decision: **NO-GO**) and the [remediation plans](R1_Remediation_Plans_2026-11-14.md) (OPA test plan section 5, backup and restore section 6, approval record section 4.1).

Rules for every step: run as the named operator; never paste, print or store a secret, key, token, password or environment value; record the command, UTC time, exit status and redacted output; **stop at the first unexpected result and report it**. Steps marked READ-ONLY change nothing. Steps marked MUTATES need their own written owner approval naming the exact command, and are listed only so the approval can be specific.

## 0. Entry conditions (all must be true; otherwise stop)

1. The release PR is merged and `main` CI is green; the digest to deploy was published by that CI run from the merged commit. Any other digest is out of scope.
2. The staging stack can serve the R1 journeys: the capability policy, media worker, consumers and schedulers of the [runtime release candidate](R1_Runtime_Release_Candidate_2026-11-14.md) are merged and every R1 secret in its section 6 exists.
3. **Backup and restore: APPROVED — WAIVED FOR RESTRICTED R1 STAGING** (owner, 14 November 2026). Not a blocker. Use `--restore-point-ref WAIVED-R1-STAGING-20261114`. Consequence: migrations cannot be undone; the owner approves them explicitly (release candidate section 4).
4. **OPA: APPROVED — WAIVED FOR RESTRICTED R1 STAGING.** The `aws-staging` profile runs without the plugin; sections 4 and 5 below are retained for a later production request only.
5. Written deployment approval per remediation plans section 4.1 (valid 24 hours, one run).
6. Operator, stop authority and window are named.

## 1. Read-only evidence pack (AWS)

Run the commands in remediation plans section 3 on VM1 (manager) and VM2 (worker). Attach complete output. They settle: instance size and free memory, node labels (expected none), Docker and API versions, the authorization plugin state, live capability flags per service, and whether VM1 hosts containers. Compare:

| Expectation | Source |
| --- | --- |
| Worker has no labels; services pinned `node.hostname==ip-172-31-16-154` | 14 Nov operator read-back |
| Gateway and Identity `ACCOUNTS=1`/`PRIVILEGED=0`; the six others `0`/`0` | `aws-staging` flag table |
| No `kolovibe.workloads` label, instance size unknown | repository (Oracle facts must not be applied to AWS) |

Any difference: stop; changing the profile is a reviewed code change, never an edit on the VM.

## 2. Release image: manifest, digest and pull verification

READ-ONLY apart from the pull (a pull writes image layers to the node; it needs the pull approval).

```bash
# Workstation: the digest named in the approval must equal the CI record
gh run view <run-id> --json conclusion,headSha --jq '.conclusion + " " + .headSha'
# Download the published-image-<sha> artifact (approved file download) into a NEW empty directory
# and use it as --release-dir; its digest must equal the approved digest, character for character.

# Registry check with a read:packages credential entered at the hidden prompt, never on the command line:
docker login ghcr.io -u <user>                 # password prompt
docker buildx imagetools inspect ghcr.io/markcino/kolovibe/services@sha256:<approved-digest>
```

Pass: the manifest resolves for the approved digest, the platform matches the AWS architecture (from section 1), and the digest printed equals the approval. A tag, a different digest, or a manifest that cannot be read is a stop. Pullability from VM2 is proven by the tool's own `update` step (it pulls with a hidden-prompt credential); do not pre-pull on VM1.

## 2b. Read-only database preflight (separate approval; no write, no commit)

Before any migration approval run **one** of: `infra/postgres/r1_readonly_preflight.sql` through `psql -X -v ON_ERROR_STOP=1 -f` as a login that can read all schemas, or `python3 scripts/ops/r1_db_preflight.py` where a TLS path exists (`--print-expected` lists the migrations the commit carries). Stop on: a migration the database has and the commit lacks; creators 0004 pending with case-only handle collisions (resolve by hand, never by script); `stream_upload_id` holding data; PostgreSQL major not 16 (note it). Details: [image fix and readiness](R1_Image_Fix_and_Readiness_2026-11-14.md) section 8.

## 2c. Two images

`main` CI publishes two digests into one `published-image-<sha>` artifact: `published-digest.txt` (services: eight APIs and the six non-media processes) and `published-media-digest.txt` (media worker only, the only image with FFmpeg). Export `KOLOVIBE_IMAGE` and `KOLOVIBE_MEDIA_IMAGE` from them and run `python scripts/validate_staging_stack.py --aws-stack --release-dir <artifact dir>`; it fails if either differs from the evidence. The cluster tool moves only the services image.

## 3. PostgreSQL, RabbitMQ and messaging health

READ-ONLY, from VM1 (manager). The PostgreSQL and RabbitMQ service names on AWS are not recorded in the repository; take them from `docker service ls` (section 1) and substitute them below.

```bash
docker service ls --format '{{.Name}} {{.Replicas}}'
docker service ps <postgres-service> --no-trunc --format '{{.Name}} {{.CurrentState}} {{.Error}}' | head
docker service ps <rabbitmq-service> --no-trunc --format '{{.Name}} {{.CurrentState}} {{.Error}}' | head
```

On VM2, in the broker container (name from `docker ps`, never a secret):

```bash
docker exec <rabbitmq-container> rabbitmq-diagnostics -q check_running
docker exec <rabbitmq-container> rabbitmq-diagnostics -q alarms
docker exec <rabbitmq-container> rabbitmqctl list_queues name messages consumers
```

Pass: 1/1 replicas, no restarts or errors, no alarms, TLS listener, expected application vhost. End-to-end messaging (publish, consume, redelivery, duplicate suppression, dead-letter, restart recovery: exactly one effect per event id) needs the consumer services that do not exist in the current stack; until they do this gate stays **UNVERIFIED**. `scripts/test_rabbitmq_celery.py` and the PostgreSQL event tests prove the code path only, not the broker.

## 4. OPA authorization rehearsal: WAIVED for restricted R1 staging (kept for production)

Follow remediation plans section 5 (tests T1 to T15). The existing AWS manager is not a rehearsal target. Evidence to attach: Docker and plugin versions and architecture, plugin state with the required args, the atomic-rename reload result (T4), `allow_once` exact-body behaviour and its 403 proofs (T6), cleanup under signals including `kill -9` (T7), the lockout recovery drill and its timing (T13). Pass only if every test passes; a failed T4 means the tool's design needs a reviewed change. Production use needs a separate approval naming the commands, a second out-of-band access path, saved `daemon.json` and policy copies, and an EBS snapshot.

## 5. PostgreSQL encrypted backup and restore test: WAIVED for restricted R1 staging (kept for production)

Follow remediation plans section 6. Summary of what must be attached: PostgreSQL version and data size; `pg_dump -Fc` plus globals dump streamed to the operator workstation and encrypted on arrival (no plaintext dump on the VM); encrypted-file SHA-256; restore on a disposable host with the same major version (**PostgreSQL 16; the developer workstation tests ran on 14**); object and per-schema row counts equal; `scripts/verify_postgres_isolation.py` passes on the copy; `showmigrations` against the release digest; the forward migrations rehearsed on the copy, including the case-insensitive creator-handle collision report before `creators 0004`; measured restore duration (RTO) and the owner-set RPO/RTO. The dumps contain tester personal data: encrypt, restrict and destroy them, and record the destruction.

## 6. Placement and capacity

READ-ONLY. From section 1, compute free memory on VM2 against the sum of memory limits in the plan: PostgreSQL, RabbitMQ, eight APIs (the tool sets 256 MiB limit and 128 MiB reservation per new service), plus any media worker. An unrecorded instance size, or a plan that exceeds free memory minus an operating margin the owner sets, is a stop. The tool's `worker-preflight --profile aws-staging` (on VM2) records node state, TLS reach to the database and the exact hostname pin; it must be fresh (valid five minutes).

## 7. Deployment (MUTATES; each command needs approval)

Services move one at a time with the tool, copied unmodified to each VM, always with `--profile aws-staging`.

```bash
# VM2: fresh evidence (read-only)
sudo python3 kolovibe_cluster.py worker-preflight --profile aws-staging > worker-evidence.json

# VM1: dry run first; it must report only the approved services and no BLOCKED message
sudo python3 kolovibe_cluster.py update-plan --profile aws-staging --worker-evidence worker-evidence.json \
  --release-dir release/ --services <approved,list,in,order>

# R1 rollout: add --enable-r1-capabilities (and --set-env content:KOLOVIBE_R2_ACCOUNT_ID=... / KOLOVIBE_R2_MEDIA_BUCKET=...)
# to both update-plan and update; see infra/swarm/README.md "AWS R1 capability rollout".
# VM1: apply, one named service at a time, receivers first, gateway last
sudo python3 kolovibe_cluster.py update --profile aws-staging --worker-evidence worker-evidence.json \
  --release-dir release/ --services <one-service> --restore-point-ref <approved-ref> \
  --confirm-image ghcr.io/markcino/kolovibe/services@sha256:<approved-digest> \
  --rollback-file <new-private-file>
# After each service (VM2):
sudo python3 kolovibe_cluster.py verify-worker --profile aws-staging --image <approved-digest> --services <one-service>
```

Order: audit, identity, creators, content, engagement, points, moderation, gateway (the tool enforces it). The Gateway needs `--accept-ungated` while it has no readiness check, and `--secret-override` pairs only as approved. After the Gateway, run `verify-edge` from the workstation.

Migrations are **not** run by the tool. They are applied separately by the service-owned migration logins in the approved order (identity, creators, content, audit, engagement, points, moderation) only after the validated restore point, with `showmigrations` showing nothing pending afterwards.

Stop conditions: any `BLOCKED:` message, a failed `verify-worker` or `verify-edge`, a Swarm `rollback_started`, `rollback_*` or `paused` state, drift stop, or any unexpected service change. Report; do not retry or edit.

Expected impact: stop-first single-replica updates mean each service is briefly unavailable during its own update (about its start period of up to 60 s plus the 30 s monitor window); VM1 is not highly available. Users: UAT testers only. Window length is set in the approval.

## 8. Rollback

| Situation | Action | Notes |
| --- | --- | --- |
| Update fails or pauses | Swarm rolls back automatically (`failure_action: rollback`); confirm with `docker service ps` | Report before any further step |
| Verified problem after update | `sudo python3 kolovibe_cluster.py rollback --profile aws-staging --services <list>` (dry run), then repeat with `--confirm-rollback <planned list>` | Restores the previous spec, image, revision label and secret references; **keep old secret versions until the soak ends** |
| Schema or data problem | Restore from the validated restore point; the owner decides | Migrations are forward-only. Export Points 0005, Moderation 0003 and Audit 0004 evidence rows before a restore |
| OPA lockout (if OPA was adopted) | Host root: restore saved `daemon.json` or the policy file, reload/restart Docker | Drilled in T13 |

After any restore of a service database, re-apply approved account deletions (Decision C) so the restore cannot bring an erased account's data back: run Identity's `python manage.py reapply_erasures --all`, then its `dispatch_identity_events`, and let each service's worker and dispatcher answer. The command is idempotent and prints counts only. It needs the erasure broker plan to be approved and applied first; until then, it only records the requests in Identity's outbox.

**Restoring Identity's own database** (mandate 3.4; the Audit recovery contract is PROPOSED and needs the owner's approval before first use). A backup older than a deletion would otherwise bring the account back. In this order, with the Gateway kept closed to sign-ins until step 3 passes:
1. Restore Identity, run its migrations, and start it. Do not restore Audit: it has its own database and append-only storage, and it is the record of what happened after the backup.
2. `python manage.py recover_erasures_from_audit --dry-run`. It reads, through Identity's signed call to Audit's `/internal/audit/erasure-recovery`, every `account.deactivated` and `account.privacy_erasure_completed` fact Audit holds, and prints counts only. The Audit service must carry the `audit_read` capability for the route to be open.
3. `python manage.py recover_erasures_from_audit`. Each restored account that a deletion approval deactivated is deactivated again and its sessions revoked; each account whose erasure completed is de-identified again; a deletion request the backup still shows as waiting for review returns to `processing` with its jobs reopened. Nothing is marked completed by hand. Run it again: it must report 0 re-applied.
4. `python manage.py reapply_erasures --all`, then `dispatch_identity_events`, so every service is asked again; completion follows each service's confirmation.
5. Record the counts (never ids) in the dated operations record.
*Superseded, 27 November 2026:* "Restoring Identity's own database to a point before a deletion was approved also needs the Audit-held confirmations to be read back, and no Audit read contract for that exists yet."

Rollback owner and data-restore decision-maker are named in the approval. After a rollback, run `verify-worker` and `verify-edge` and attach the output.

## 9. Post-deployment tests

1. `verify-worker` (every deployed service) and `verify-edge`: all PASS.
2. Authentication: unauthenticated 401; authorized 200; cross-account `/me` isolation; logout then 401 on the old access token; refresh after logout rejected; refresh replay detected.
3. For each capability the approval enables, the matching UAT section of the [iPhone checklist](R1_iPhone_UAT_Checklist_2026-11-14.md). A journey whose capability is not enabled is recorded as not tested, never as passed.
4. Audit rows delivered once; no secret, token or playback URL in any log excerpt.
5. Record per service the image digest from `docker service inspect`.
