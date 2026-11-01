# KoloVibe Oracle VM1/VM2 Infrastructure Verification Runbook

**Baseline:** 2026-11-01 ADR-003/ADR-007 reconciliation. **State:** Evidence pending. No live VM access or configuration changes are claimed.

## Deployment layout
- Oracle **VM1**: single Docker Swarm manager and host-level Nginx (outside Swarm).
- Oracle **VM2**: Docker Swarm worker.
- Cloudflare Tunnel: configured per owner; connector location, origin policy and DNS route need verification.
- RabbitMQ: private broker for Celery; **do not deploy Redis** as a default dependency.
- PostgreSQL: authoritative data with service-level isolation, outbox/inbox and backups; hosting and restore evidence pending.
- One manager plus co-located Nginx is **not HA**. Keep ingress and manager recovery runbooks.

## Step 1 — safe, read-only manager audit
Connect using the existing SSH alias and run:

```bash
hostname
cat /etc/os-release
nproc; free -h; df -h
docker info --format 'Swarm={{.Swarm.LocalNodeState}} Manager={{.Swarm.ControlAvailable}}'
docker node ls
docker service ls
docker stack ls
docker network ls
docker volume ls
sudo nginx -t
systemctl is-active nginx || true
systemctl is-active cloudflared || true
sudo ss -tlnp | grep -E ':(80|443|5672|5671|15672|2377|7946|4789|5432)\\b' || true
```

## Step 2 — safe, read-only worker audit
Connect through the existing SSH ProxyJump alias:

```bash
hostname
nproc; free -h; df -h
docker info --format 'Swarm={{.Swarm.LocalNodeState}} Manager={{.Swarm.ControlAvailable}}'
docker ps --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}'
docker network ls
docker volume ls
```

## Step 3 — verify RabbitMQ/Celery (metadata only)
On VM1:

```bash
docker service ls --format '{{.Name}} {{.Image}} {{.Replicas}}' | grep -Ei 'rabbit|celery|worker' || true
docker ps --format '{{.Names}} {{.Image}} {{.Status}}' | grep -Ei 'rabbit|celery|worker' || true
```

Identify the exact running broker service/host before any changes. Verify private RabbitMQ ports, version/image digest, persistent volume, vhosts/users, permissions, durable queue semantics, resource alarms, Celery consumers, replay/retry and DLQ behavior.

**Do not share** raw `.env`, Cloudflare connector credentials, SSH keys, Docker secret values, RabbitMQ passwords or full service-inspection environment variables. Redact private addresses and sensitive infrastructure identifiers if necessary.

## Infrastructure acceptance checklist
1. **INF-01:** VM1/VM2 inventory, patch status, CPU, RAM and available disk.
2. **INF-02:** Swarm one-manager/one-worker health, capacity and restoration strategy (not HA).
3. **INF-03:** OCI NSG/security list, host firewall and SSH source restrictions. No public Docker, DB or RabbitMQ ports.
4. **INF-04:** Cloudflare Tunnel connector → VM1 host Nginx routing, hostname controls and no origin bypass.
5. **INF-05:** Nginx → Swarm gateway private authenticated transport, TLS/identity, correct proxy headers.
6. **INF-06:** RabbitMQ and Celery identity, persistence, monitorability and failure/retry tests.
7. **INF-07:** PostgreSQL service-owned privileges, encryption, durable storage, backup and isolated restore drill.
8. **INF-08:** Docker networks, resource limits, Swarm secrets, pinned images and rollbacks.
9. **INF-09:** logs/metrics/alerting, redaction and audit retention.
10. **INF-10:** GitHub Actions security scan success and explicit release acceptance.

**Safety:** Do not run `docker swarm init`, `docker swarm leave`, delete volumes, redeploy a second broker, restart host networking or change OCI firewall rules until evidence is reviewed and SSH recovery is confirmed.

## Current CI blocker
The 2026-11-01 API quality workflow failed in the `Secret discovery and regression checks` step, while RabbitMQ/Celery, Django service tests, dependency review and container quality checks passed. Review flagged paths in the workflow output; do not assume confirmed credential leakage, bypass the security gate or publish sensitive candidate secrets.

**Next action:** Capture VM1/VM2 metadata-only inspection output, validate against INF-01–INF-06, then configure any missing components using a reversible change plan.
