> Source: DOC-208_Full_Infrastructure_Blueprint_DRAFT_v1_0.docx (text export; formatting and embedded images are not included). Original status is retained.

<PARSED TEXT FOR PAGE: 1 / 5>
                                                DOC-208
            INFRASTRUCTURE & DOCKER SWARM
                           DEPLOYMENT BLUEPRINT
                              Version 1.0 • FULL DESIGN DRAFT • 28 October 2026

Baseline: approved DOC-201–DOC-207. Nginx runs on a dedicated VM outside Docker Swarm. No deployment or
verification is claimed.



1. Purpose, scope and architecture baseline
Release 1 production design for a Liberian creator video platform. Approved: Flutter clients; Django templates
web; Django REST Framework microservices; dedicated Nginx VM outside Docker Swarm; PostgreSQL service-
owned data; Redis/Celery; managed video platform; Cloudflare edge; server-qualified engagement and non-cash
points. DOC-208 is a full design draft, not a deployment acceptance certificate. R2 business, R3 ticketing and R4
payouts are explicitly excluded from the deployed R1 stacks.



2. Design principles and non-negotiable constraints
No direct public access to Swarm managers, workers, PostgreSQL or Redis. Dedicated Nginx VM terminates or re-
encrypts approved TLS traffic and forwards only to a private Swarm gateway. Zero-trust service identity; no
implicit trust from overlay network membership. Deploy images by immutable digest, run non-root, use read-only
filesystems where feasible, store secrets in a secrets manager/Swarm secrets rather than environment variables.
No public points mutation API. All deployment values in examples are placeholders.



3. Topology options and availability
Option A—pilot/minimum: 1 Nginx VM, 1 Swarm manager+worker, 1 isolated PostgreSQL host/managed DB,
managed video, backup destination. This has single points of failure and is not HA. Option B—recommended
production HA: 2 Nginx VMs behind provider L4 load balancer or equivalent; 3 Swarm managers (quorum 2), 2+
workers across failure domains; HA PostgreSQL service or primary/standby with tested failover; replicated
monitoring and durable backup storage. Cluster sizes and costs are proposals pending provider, budget and SLO
approval. Do not claim a 2-manager Swarm cluster is HA.



4. Logical service placement
Public-facing: edge Cloudflare; dedicated Nginx VMs; Swarm gateway/BFF exposed only on private interface or
VPN. Internal services: identity, content, engagement, points, moderation, web frontend, background worker(s),
observability agents. Database: separate logical DBs/roles for service ownership, not shared tables. Redis: private
queue/cache, scoped credentials. Video: managed streaming provider with server-signed callbacks and access
tokens. R1 points ledger is non-cash and append-only.
<PARSED TEXT FOR PAGE: 2 / 5>
5. Networking and trust zones
Z0 Internet/Cloudflare; Z1 Nginx DMZ VM; Z2 private tunnel or routed application ingress; Z3 Swarm frontend
overlay; Z4 Swarm internal service overlays; Z5 private data tier; Z6 management/backup/monitoring; Z7 external
video provider. Public firewall allows 443 to Nginx only from approved Cloudflare addresses where origin
protection is deployed. Dedicated Nginx-to-gateway uses private routed connectivity plus TLS/mTLS or
WireGuard. Do not route private RFC1918 networks over public Internet without an authenticated tunnel. Docker
overlay encryption can add protection but does not replace application identity.



6. Port and firewall matrix
Internet→Cloudflare 443/TCP; Cloudflare→Nginx 443/TCP; Nginx→Swarm gateway 8443/TCP example private-only;
management VPN/bastion→Nginx SSH 22/TCP restricted; Swarm managers 2377/TCP between cluster nodes;
Swarm node discovery 7946/TCP+UDP; overlay VXLAN 4789/UDP between trusted Swarm nodes only;
gateway/services→PostgreSQL 5432/TCP private; service/workers→Redis 6379/TCP private; outbound provider
APIs 443/TCP allowlisted where practical. Ports are illustrative and must be matched to actual stack, host firewall
and provider policies. Never expose 2377, 7946, 4789, 5432 or 6379 to the public Internet.



7. DNS, TLS and reverse-proxy security
Public hostname resolves to Cloudflare proxied record, then dedicated Nginx origin. Cloudflare Full (strict) to
Nginx with valid origin certificate, preferably Authenticated Origin Pulls or equivalent origin authentication.
Restrict origin to Cloudflare published ranges plus authenticated tunnel as appropriate. Nginx overwrites X-
Forwarded-For, X-Forwarded-Proto, Host and request IDs; Django trusts only the known proxy chain. Separate
upstream TLS/mTLS to private gateway; reject plain HTTP and invalid upstream certificates.
CSRF_TRUSTED_ORIGINS, SECURE_PROXY_SSL_HEADER, HSTS, ALLOWED_HOSTS and cookies require
configuration and test.



8. Docker Swarm manager and worker hardening
Three manager nodes in production HA, manager-only placement for control plane where capacity permits;
workers run app tasks. Join tokens rotated after use; nodes joined over trusted private network. Enable Swarm
autolock with a documented unlock-key escrow process; restrict manager SSH and Docker socket; avoid mounting
Docker socket into application containers. Use placement constraints, resource reservations/limits, health checks,
update_config and rollback_config. Document manager quorum failure and recovery. Prefer encrypted overlays
for sensitive east-west traffic; use per-service networks and service-authentication.



9. Microservice deployment and runtime configuration
Build one immutable container image per service/release, with SBOM and vulnerability scan; image tags may be
human-readable but deployment should pin digest. Each service receives only its own DB credential and service
identity. Configure Django SECURE_SSL_REDIRECT as appropriate to proxy chain, CSRF protections for cookie
sessions, CORS restricted to approved origins, request size and timeout limits, Gunicorn/Uvicorn worker tuning,
graceful shutdown, /healthz and /readyz. Web and API may have distinct routes but must not be coupled to Nginx
process/container.
<PARSED TEXT FOR PAGE: 3 / 5>
10. PostgreSQL data tier and lifecycle
Database is outside the public ingress and reachable only from approved service networks or private application
hosts. Separate databases/roles or schemas with explicit ownership; cross-service joins/writes prohibited. Use TLS,
SCRAM-SHA-256 where supported, credential rotation, schema migration owner, indexes and connection pooling.
Backup: full/base backup plus WAL archiving for PITR; encryption and offsite immutable retention. Establish
target RPO/RTO before choosing replication, provider or backup schedule. Rehearse isolated restore and integrity
checks.



11. Redis, Celery and event reliability
Redis only on private network with authentication/TLS as supported; separate cache and broker logical isolation
or instances based on criticality. Celery queues per responsibility, retry with bounded exponential backoff,
poison-message dead-letter handling, payload schema validation and job idempotency. Transactional outbox in
each producing database and deduplicating inbox in consumer prevent inconsistent side effects. Redis is not the
system of record for points, audit or business events.



12. Managed video, storage and callbacks
Client requests a short-lived upload authorization from content service, uploads directly to managed provider;
provider signs webhook to dedicated handler; content service verifies signature, timestamp, replay protection
and provider status before publication. Playback tokens/URLs should be short-lived when provider supports. No
raw video streaming through Django/Nginx by default. Storage and retention, region, copyright moderation and
provider pricing require sign-off.



13. Identity, service authentication and secrets
Users authenticate via selected identity implementation (decision pending); admin/moderator MFA required.
Between services use short-lived audience-scoped workload credentials and optionally mTLS, not reusable shared
API keys. Secrets provided via Swarm secrets or dedicated vault; no secrets in git, stack YAML, environment
dumps, container image or CI logs. Rotate credentials and webhook signing keys; test revocation. Swarm secrets
do not automatically provide external KMS lifecycle, so ownership and rotation remain operational requirements.



14. Security enforcement and points fraud controls
Points service has no externally routable write endpoint. Only authenticated engagement service can request an
award using evidence ID, rule version and idempotency key. Atomic unique constraints enforce single effective
award; append-only reversal entries preserve history. Do not issue points from Google ad impressions/clicks,
callbacks or user-provided playback counters. Rate limits, anti-automation, collusion detection, moderation holds
and evidence retention are separate controls. No cash payouts in R1.



15. CI/CD and supply-chain gates
Protected main branch, reviewed pull requests, reproducible builds, dependency and secret scans, container
vulnerability scans, SBOM, signed artifact provenance, integration tests, infrastructure policy validation and
approval before production deploy. Use short-lived CI credentials and dedicated deploy role with no unrestricted
host root. Stage to staging Swarm first, run smoke/security tests, promote digest to production, record deploy ID
and maintain rollback path. Database schema changes use expand-migrate-contract with backward compatibility.
<PARSED TEXT FOR PAGE: 4 / 5>
16. Monitoring, logging and alerting
Centralize Nginx access/error logs, Swarm events, service JSON logs, PostgreSQL metrics, Redis queue depth, video
provider webhook failures, and points fraud alerts. Propagate correlation/request IDs. Collect metrics and traces
via OpenTelemetry-compatible agents; choose actual stack later. Monitor p95 latency, 5xx, upload/playback
success, queue age, DB connections, disk, backup freshness, Swarm quorum and Nginx health. Redact tokens,
secrets and raw personal data; define retention and access controls.



17. Backups, disaster recovery and incident response
Document owner, RTO/RPO, dependencies, escalation and restoration order: network/VPN, Nginx, Swarm control
plane, data tier, service secrets, gateway, identity/content/engagement/points, workers and observability. Back up
Swarm manager state only with correct unlock/restore procedures and protect key material. Periodically run full
offsite restore drills, reconcile points ledger, verify media metadata and rehearse Nginx VM replacement. Failover
is not assumed until tested.



18. Capacity, costs and scaling assumptions
Pilot sizing is workload-dependent; measure concurrent users, video starts, watch events/s, upload volume,
storage/egress, DB TPS, Redis queue age and average payload sizes. Scale stateless API replicas horizontally;
workers by queue depth; data tier separately. Reserve headroom for one-node failure in HA. Cloudflare, managed
video, egress, Nginx VM, Swarm nodes, DB and backup costs must be quoted and approved; no unsupported fixed
monthly cost claim.



19. Staging, production and environment separation
Use separate DNS, identity credentials, webhook secrets, DBs, video accounts/buckets and Swarm stacks;
production secrets must never enter staging. Staging should reproduce private routing and security controls,
though size may differ. Test deployment rollback, webhook replay, manager failover, DB restore, rate limits,
proxy header spoofing and Nginx origin bypass before pilot.



20. Deployment runbook and rollback
Preflight: inventory nodes and approved IP ranges; provision VPN/private routing; harden Nginx VM and hosts;
verify DNS/cert chain; initialize Swarm; create networks/secrets; deploy DB and backup; deploy internal services;
deploy gateway; configure Nginx upstream; smoke test; enable monitoring; switch Cloudflare route; verify.
Rollback: restore prior immutable service digest via Swarm rollback, roll back Nginx config after validation, avoid
irreversible DB down migrations, and confirm points ledger reconciliation. Every command in companion
examples requires environment substitution and review.



21. Acceptance tests and evidence
Required: no public Swarm/DB/Redis ports; origin bypass blocked; valid TLS and upstream identity; admin MFA;
secret scan clear; signed webhooks reject replay; only engagement service can post points; ad event cannot create
points; backup/PITR restore successful; manager and worker failure scenarios tested; Nginx outage/rebuild
measured; image digest and CI approval traceable; logs redacted; incident escalation exercised. Evidence includes
screenshots/config exports, test output, issue IDs, reviewers and timestamps.
<PARSED TEXT FOR PAGE: 5 / 5>
22. Open infrastructure decisions
INF-01 pilot vs HA target and budget; INF-02 provider and geography; INF-03 Nginx origin protection and
upstream connectivity; INF-04 number and placement of managers/workers; INF-05 PostgreSQL managed vs self-
hosted and RPO/RTO; INF-06 Redis hosting; INF-07 TLS/mTLS and workload identity; INF-08 DNS and domain
ownership; INF-09 monitoring stack; INF-10 backup retention; INF-11 video provider and egress; INF-12 CI/CD
registry and deployment credentials; INF-13 capacity and SLOs; INF-14 failover strategy for dedicated Nginx. Each
needs accountable owner, date and formal decision before production.



23. Formal sign-off and constraints
DOC-208 design approval confirms a reference architecture, not that infrastructure has been provisioned,
penetration-tested, load-tested or certified. Stage 2 closure additionally depends on DOC-209 and
resolution/accepted deferral of applicable open decisions. No production go-live with unresolved Critical security
risks or untested backups. Sponsor, platform owner and security reviewer must approve final topology and
evidence gates.



Appendix A — Network and port controls
Source                       Destination                  Port                          Restriction
Cloudflare                   Nginx VM                     443/TCP                       Cloudflare source
                                                                                        allowlist + origin
                                                                                        authentication
Nginx VM                     Swarm private gateway        8443/TCP (example)            Private route/VPN +
                                                                                        upstream TLS/mTLS
Management VPN               Nginx/Swarm hosts            22/TCP                        Bastion and admin MFA
Swarm nodes                  Managers                     2377/TCP                      Private cluster only
Swarm nodes                  Swarm nodes                  7946/TCP+UDP                  Private cluster only
Swarm nodes                  Swarm nodes                  4789/UDP                      Private cluster only
App services                 PostgreSQL                   5432/TCP                      Private data tier and
                                                                                        service DB roles
Workers/services             Redis                        6379/TCP                      Private queue/cache
Content service              Video provider               443/TCP                       Outbound TLS; signed
                                                                                        webhooks



Appendix B — Formal review
Sponsor: __________________ Platform lead: __________________ Security lead: __________________

Decision: Approve design / Request revisions    Date: __________