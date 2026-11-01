# Architecture reconciliation — RabbitMQ and VM1 Nginx

**Change record:** AR-2026-11-01-01  
**Date:** 2026-11-01  
**Status:** User-confirmed implementation baseline; infrastructure acceptance pending  
**Related decisions:** ADR-003, ADR-007, ADR-014, ADR-015, ADR-021  
**Sources:** DOC-201 architecture; DOC-202 diagrams; DOC-207 ADR register; DOC-208 infrastructure blueprint; DOC-209 review.

## Context and change control

The October 28 architecture documents described (a) a dedicated Nginx server outside Swarm and (b) Redis/Celery background processing. The owner subsequently confirmed that the actual target platform has **two Oracle Cloud VMs**, that **Nginx is installed on VM1**, and that **RabbitMQ**, not Redis, is the message broker. The earlier documents are historical baseline artifacts; this amendment supersedes only the conflicting implementation requirements. It does not assert that any host, service, backup, or security check has passed.

## ADR-003: Nginx placement amendment

- **Oracle VM1:** Docker Swarm **manager** and **host-installed Nginx** (a systemd process, *not* a Swarm service, subject to verification).
- **Oracle VM2:** Docker Swarm **worker**.
- **Edge flow:** mobile/web client → Cloudflare edge → Cloudflare Tunnel → host-level Nginx on VM1 → designated private Swarm API gateway → internal Django/DRF microservices.
- **Tunnel connector placement:** verify on the hosts before documenting an exact connector location. If Tunnel runs on VM1, its origin should target a locally protected Nginx listener; if remote, require authenticated private transport and origin ACLs.
- **Ingress controls:** do not publish Docker API, Swarm control-plane ports, PostgreSQL, RabbitMQ or backend microservice listeners on public interfaces. Confirm tunnel-to-Nginx origin policy, trusted proxy headers, hostname restrictions, TLS assumptions, upstream authentication and Nginx-to-gateway routing.
- **Availability:** VM1 co-locates the Swarm manager, edge ingress and possibly tunnel connector. A VM1 loss interrupts ingress and manager operations. A **single-manager two-node Swarm cluster is not HA**. Maintain restore/rebuild procedures and assess future dedicated edge separation.
- This is an explicit *co-location deviation* from the old dedicated-third-VM invariant in DOC-201/DOC-208/DOC-209, not a claim that a host process on VM1 satisfies the old dedicated-VM constraint.

## ADR-007: RabbitMQ as asynchronous broker

- **RabbitMQ** is the private broker for **Celery** workers. Do **not** provision Redis as a required broker or silently reuse old Redis service definitions.
- **PostgreSQL** remains the authoritative store for service-owned transactions, event outboxes/inboxes, qualification decisions and non-cash points ledger entries.
- Proposed delivery: producer commits business state and outbox atomically; publisher forwards outbox entries to RabbitMQ; consumers deduplicate by stable event ID and commit before acknowledging. Use durable exchanges/queues, persistent messages, publisher confirms and appropriately configured acknowledgments.
- Use scoped RabbitMQ users and virtual hosts, least privilege, private network listeners, TLS where warranted, restricted management UI, memory/disk alarms, bounded queue sizes, retry/backoff, dead-letter handling, monitoring and validated backups/recreation procedures.
- RabbitMQ is **not** the persistent Celery results database and must not substitute for PostgreSQL business state. Configure result backend only if a specific task requires it, with documented retention.
- Verify actual RabbitMQ image/version, image digest, Swarm service/standalone placement, volume durability, persistence configuration, private networking, credentials, broker/workers connectivity and failure behavior before deploying API integration.

## Updated pilot topology

| Tier | Placement | Readiness |
| --- | --- | --- |
| Cloudflare DNS / edge / Tunnel | Cloudflare and connector placement to verify | Configured per owner, verification pending |
| Nginx | VM1, host service | Installed per owner, configuration/security verification pending |
| Swarm control plane | VM1 manager | Installed per owner, health/backup verification pending |
| Swarm workloads | VM2 worker; VM1 only if explicitly permitted by capacity policy | Placement verification pending |
| Django/DRF API gateway and microservices | Swarm private application networks | Not authorized for deployment yet |
| RabbitMQ + Celery | Private service network; node/volume policy to verify | Design aligned, deployment verification pending |
| PostgreSQL | Approved provider/topology still to verify | No claim of running |
| Video/object storage | Provider integrations per approved architecture and subsequent decisions | Verify separately |

## Impact on other documents

- **DOC-201:** Replace Redis/Celery descriptions with RabbitMQ/Celery. Replace references to a dedicated third Nginx VM with the VM1 host-process edge model; note increased single point of failure.
- **DOC-202:** Update diagrams to show Cloudflare Tunnel → VM1 Nginx → private Swarm ingress; RabbitMQ between publisher and Celery workers.
- **DOC-203 / DOC-206:** Add VM1 co-location blast-radius and RabbitMQ credential/durability/replay/poison-message checks to threat and verification evidence.
- **DOC-204:** Retain PostgreSQL ownership, outbox/inbox, idempotency. No RabbitMQ replacement of transactional data.
- **DOC-205:** Align asynchronous event/worker and error-handling contracts without introducing public broker APIs.
- **DOC-207:** ADR-003 and ADR-007 implementation details amended in the tracked CSV.
- **DOC-208:** Change topology, firewall zones, Nginx placement and broker operational runbook to this design; leave HA/storage decisions open.
- **DOC-209:** Record approved design deviation and require implementation/security verification before Stage 2 closure or pilot acceptance.

## Remaining evidence gates

1. SSH/host inventory, `nginx -t`, host service status, ports, Cloudflare Tunnel connector mapping.
2. `docker node ls`, node roles, manager quorum, service inventory, overlay networks, volume mounts, capacity, OCI/host firewall inspection.
3. RabbitMQ broker role, private listener, durability, health and workers; negative access tests, retry/DLQ and replay tests.
4. TLS/authenticated transport between Nginx, gateway and internal services; no public origin bypass.
5. Database placement, least-privilege access, encrypted backups and tested restore.
6. Resource reservations, image provenance, secrets, monitoring and rollout/rollback verification.

**Governance:** This is an implementation architecture reconciliation, **not** a deployment acceptance certificate or claim that Stage 2 is closed. Any differences discovered in the live environment must be recorded before proceeding.
