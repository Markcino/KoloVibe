# R1 media worker: `celery.pidbox` ACCESS_REFUSED fix (2026-11-17)

Status: code fix and regression tests done locally. Image publish, RabbitMQ permission audit, staging deployment and the
R2 → RabbitMQ → FFmpeg → R2 acceptance run are **not done** (see "Pending").

## Root cause

`staging_runtime.roles.run_celery` started `service.media_tasks:app` with `--without-gossip --without-mingle` only.
Celery's remote-control (`Control`/`Pidbox`) bootstep is chosen from `worker_enable_remote_control` (default `True`) and
is not switched off by those flags. At start-up it declares the `celery.pidbox` fanout exchange and a per-node
`<node>.celery.pidbox` queue. The broker account `kolovibe_content_r1` has no configure permission on that exchange, so the
broker answers `Exchange.declare: (403) ACCESS_REFUSED` and the worker exits. Nothing in the application overrode the setting.
Proved with real Celery 5.6.3 on Kombu's in-memory transport: with the default the worker declares
`celery.pidbox` plus `<node>.celery.pidbox`; with `worker_enable_remote_control=False` it declares only
`kolovibe.content.media` (exchange, queue, and their one binding).

## Fix

- `services/staging_runtime/roles.py`: `run_celery` sets `app.conf.worker_enable_remote_control = False` before
  `worker_main` (shared by the engagement/points consumers, which would fail the same way); the worker options are now the
  pinned `CELERY_WORKER_OPTIONS` constant, unchanged in value.
- `services/content/service/media_tasks.py`: `worker_enable_remote_control=False` in the app configuration, so the app is
  safe however it is started (including `manage.py run_media_worker`).
- Unchanged: queue `kolovibe.content.media`, concurrency 1, prefetch 1, `--max-tasks-per-child=20`,
  `--max-memory-per-child=262144`, `--without-gossip`, `--without-mingle`, heartbeats, `CERT_REQUIRED` TLS with the explicit
  CA, `task_acks_late`, `task_reject_on_worker_lost`, `confirm_publish`, `task_time_limit=240`, the `media` capability check.
- Consequence: `celery inspect/control` (ping, stats, shutdown) no longer works against this worker. Use the RabbitMQ
  consumer list and `docker service` commands below.

## Other start-up declarations (what the worker still needs)

| Behaviour | Broker resource | Operation |
|---|---|---|
| Auto-created queue (`task_create_missing_queues`) | queue `kolovibe.content.media` | configure |
| Its exchange (same name, direct) | exchange `kolovibe.content.media` | configure |
| Binding exchange → queue | queue (write) and exchange (read) | write, read |
| Consume | queue `kolovibe.content.media` | read |
| Publish (Content API, retries) | exchange `kolovibe.content.media` | write |

Gossip, mingle, task events (`celeryev`) are off or not enabled by default; heartbeats are AMQP-level only. Whether the
broker permits these has **not** been demonstrated; only the `celery.pidbox` refusal is observed.

## RabbitMQ permission findings

- The live permissions of `kolovibe_content_r1` were **not inspected** (no broker access from this environment).
- Repository drift: `scripts/ops/generate_r1_secrets.py` names the account `kolovibe_content` and its generated script
  grants `'.*' '.*' '.*'` on `/kolovibe`. The live account is `kolovibe_content_r1` and was refused configure on
  `celery.pidbox`, so it was provisioned differently; the generator no longer describes live state and its wildcard grant
  contradicts least privilege. Not changed here (no approval to alter provisioning).
- Proposed minimum (NOT applied; needs approval) for the content account in vhost `/kolovibe`:

  ```
  rabbitmqctl set_permissions -p /kolovibe kolovibe_content_r1 '^kolovibe\.content\.media$' '^kolovibe\.content\.media$' '^kolovibe\.content\.media$'
  ```

  configure/write/read all `^kolovibe\.content\.media$`. No change is needed for this fix if the account already has that
  (or a superset of it); do not grant `.*`. Verify with `rabbitmqctl list_permissions -p /kolovibe`.

## Tests

`scripts/test_media_worker_startup.py` (19 tests; part of `python -m unittest discover -s scripts -p 'test_*.py'`):
role resolution, capability enforcement and init failure, remote control off before the worker is built (mock and real
Celery argument parsing), a real worker on the in-memory broker declaring only the media exchange/queue and consuming a
task, TLS/`CERT_REQUIRED`, concurrency/prefetch/recycling, ack/confirm settings, broker URI/CA secret validation without
leaking the password, non-root/read-only/no-ports stack settings. Without the fix, 6 of them fail.
No test connects to a live broker.

## Pending (not verified)

- Image build, security scan, publish: runs through `.github/workflows/ci_cd.yml` on push to `main` as
  `ghcr.io/markcino/kolovibe/media-worker:v0.<run>.<attempt>` with a recorded digest. `v0.176.1` is not overwritten.
- Live RabbitMQ permission audit, staging start at 1/1, and the full pipeline (upload intent → R2 → validation → publish
  → Celery → FFmpeg → poster → R2 → PostgreSQL state → playback rules) with a real MP4.
- The repository stack file sets the worker to 512M limit / 256M reservation (budget test pins 1536M total); the brief
  states 768 MiB / 128 MiB. Reconcile with the live service before deploying.

## Deployment (after the CI digest is recorded; run on VM1, manager)

```
NEW=ghcr.io/markcino/kolovibe/media-worker@sha256:<verified digest>
OLD=ghcr.io/markcino/kolovibe/media-worker:v0.176.1
docker service update --image "$NEW" --with-registry-auth kolovibe-media-worker
docker service scale kolovibe-media-worker=1
```

Rollback (restores previous image, then stops it if it must not run):

```
docker service update --image "$OLD" --with-registry-auth kolovibe-media-worker
docker service scale kolovibe-media-worker=0
```

Inspect:

```
docker service ps kolovibe-media-worker --no-trunc
docker service logs --since 10m kolovibe-media-worker
docker service ls --filter name=kolovibe-media-worker
docker exec <rabbitmq-container> rabbitmqctl list_queues -p /kolovibe name consumers messages_ready messages_unacknowledged
docker exec <rabbitmq-container> rabbitmqctl list_consumers -p /kolovibe
docker stats --no-stream $(docker ps -q --filter label=com.docker.swarm.service.name=kolovibe-media-worker)   # on VM2
```

The `<rabbitmq-container>` runs on the node hosting `kolovibe-rabbitmq`.
