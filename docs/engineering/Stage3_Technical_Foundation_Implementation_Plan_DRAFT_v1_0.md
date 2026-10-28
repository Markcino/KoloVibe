> Source: Stage3_Technical_Foundation_Implementation_Plan_DRAFT_v1_0.docx (text export; original formatting, formulas and embedded images are not included). Original review status is retained.

<PARSED TEXT FOR PAGE: 1 / 6>
                                         STAGE 3
                TECHNICAL FOUNDATION
                             Implementation Plan v1.0 | 28 October 2026

Gate status: CONDITIONAL AUTHORIZATION. DOC-201 through DOC-209 are approved design
baselines. Unresolved decisions block dependent implementation and production release.



Executive delivery calendar

Week 3 / Nov 16–20
Work: Repository, toolchains, service scaffolds, Flutter/web shells, CI checks, initial risk/decision
owners

Evidence: Reproducible builds; unit tests; OpenAPI lint; CI green

Owner: Engineering lead | Dependencies: Token provider, hosting, CI choice

Week 4 / Nov 23–27
Work: PostgreSQL roles/migrations, Redis/Celery, outbox/inbox, service auth adapters, image
hardening

Evidence: DB privilege negative tests; idempotency tests; SBOM/scan artifacts

Owner: Backend + Security | Dependencies: Auth scheme, DB topology, event rules

Week 5 / Nov 30–Dec 4
Work: Swarm staging, dedicated Nginx VM, private routing, monitoring, restore/rollback and
security gate

Evidence: Staging smoke tests, network isolation evidence, rollback/restore drill, review sign-off

Owner: SRE + Security | Dependencies: Private link/TLS, cluster count, RTO/RPO



Governance and scope
Stage 3 is conditionally authorized by the DOC-209 gate. Approved DOC-201 through DOC-209 are
design baselines. This plan authorizes foundation work only; no production deployment, cash
rewards, ticketing, business verification or unapproved fraud rules. Date baseline: November 16–
December 4, 2026; actual start depends on staffing and infrastructure availability.



Objectives and acceptance
Deliver independently buildable Django/DRF service skeletons, Django-template web app, Flutter
mobile scaffold, shared contracts without shared business models, private database boundaries,
async worker scaffold, CI quality/security gates, reproducible local development, Swarm staging
<PARSED TEXT FOR PAGE: 2 / 6>
stack, and dedicated Nginx VM configuration. Evidence must include runnable commands, test
output, logs, screenshots, and signed review.



Approved topology
Internet clients -> Cloudflare -> dedicated hardened Nginx VM outside Swarm -> authenticated, TLS-
protected private ingress -> Swarm API gateway -> identity, creator, content, engagement, points,
moderation and audit services. Each service owns its PostgreSQL database or schema with separate
credentials; Redis/Celery is private. Video provider is managed. No service has direct cross-service
database writes.



Repository and service structure
Recommended initial monorepo for governance, with independent image build/deploy per service:
apps/mobile_flutter; apps/web_django; services/gateway, identity, creators, content, engagement,
points, moderation, audit; packages/contracts (OpenAPI, JSON schemas); infra/swarm, infra/nginx,
infra/postgres, infra/observability; scripts; docs/adr; tests/security. A monorepo does not change
microservice deployment independence. Shared libraries may contain observability and auth
helpers, not shared mutable business models.



Technology and baseline
Python/Django/DRF versions must be selected and pinned to supported releases at implementation;
Flutter/Dart versions pinned via toolchain. PostgreSQL, Redis, Celery, Docker Engine/Swarm, Nginx
and CI runner versions pinned to maintained releases. Reproducible builds, lockfiles, SBOM,
signed/pinned container digests, non-root runtime, multi-stage images and vulnerability scans
required. Do not invent versions before dependency compatibility review.



Identity and service authentication
Build identity service interfaces, session/token contract adapters, RBAC policy tests, privileged MFA
placeholders, service-to-service auth middleware and audit hooks. Final provider, token issuance,
refresh rotation, workload identity and credential rotation are BLOCKED until ADR selection.
Temporary staging-only identity mocks must be isolated and must not permit production
deployment.



Database and event foundation
Create per-service DB roles and migrations; enforce no cross-service write privileges. Implement
transactional outbox/inbox scaffolds, idempotency key persistence, retry/backoff and dead-letter
policy. Points ledger supports append-only non-cash entries, deduplication and reversal tests only;
point-award calculation is blocked until qualified-view thresholds and rules are approved. Redis
queues use authenticated private connections.



Dedicated Nginx VM and networking
Provision or stage a separately managed Nginx VM, not a Swarm service. Inbound only from
approved edge paths and admin jump host. Nginx must sanitize Host and forwarding headers,
<PARSED TEXT FOR PAGE: 3 / 6>
restrict body size, rate-limit routes and proxy over private TLS/mTLS or approved encrypted tunnel
to Swarm gateway. Expose only intended gateway listener; Swarm managers, DB, Redis and internal
service ports are never public. Actual network ranges, cert ownership and HA plan remain open.



Swarm staging and deployment
Create overlay networks separated by trust zone, secrets/config objects, placement constraints,
health/readiness checks, rolling update and rollback policy, per-service resource limits, log shipping
and image digest pinning. Three-manager quorum is preferred for HA production, but staging
cluster count is a separate budget decision. Do not claim HA for a single manager, single Nginx VM
or single DB host.



Flutter and Django web foundation
Flutter: application flavors dev/stage/prod, routing, typed API client, secure token storage
abstraction, error handling, crash-safe telemetry and test harness. Django templates: accessible
responsive shell, CSRF protection, session boundary, CSP and secure cookies. Both clients consume
documented public APIs and never directly mutate points.



CI/CD and software supply chain
Pull requests require formatting, lint, type checks, unit tests, schema lint, migration checks,
dependency/secret scans, container image scan and SBOM. Build once, promote immutable digest.
Staging deploy requires protected credentials and approval. Production pipeline exists as disabled
skeleton until security sign-off. Secrets must not appear in code, CI logs or image layers.



Observability and resilience
Generate correlation IDs at Nginx and propagate across gateway, services and workers. Collect
structured redacted logs, service health, latency, error rates, queue depth, failed logins, points
posting anomalies and backup status. Define alerts and ownership. Perform restore and rollback
drills in staging; RTO/RPO targets must be approved before acceptance.



Security verification at Stage 3
Threats from DOC-203 and controls from DOC-206 map to evidence. Mandatory negative tests: origin
bypass, untrusted forwarding headers, unauthorized service calls, cross-service DB access, duplicate
events, direct points writes, forged webhook, secrets in image/log, Swarm manager exposure and
staging rollback. No testing is claimed passed until executed.



Open decisions and hold points
Blocking decisions: OD-01 workload identity and token provider; OD-02 private Nginx-to-Swarm
transport and TLS ownership; OD-03 Swarm cluster size/hosting; OD-04 PostgreSQL topology and
backup RTO/RPO; OD-05 creator verification and privacy retention; OD-06 qualified-view criteria
and points formula; OD-07 video provider upload/webhook specifics; OD-08 monitoring and audit
retention; OD-09 CI platform and deployment credentials. Nondependent scaffolding may proceed.
Each blocker requires named owner, due date, ADR and acceptance evidence.
<PARSED TEXT FOR PAGE: 4 / 6>
Change control and risk management
Any change to approved service boundaries, separate Nginx placement, ledger rules or data
ownership requires new ADR and DOC-201/202 impact review. Maintain weekly risk register and
decision log. Do not merge insecure temporary bypasses into production branches.



Stage 3 exit gate
Required: independently buildable services; isolated database credentials; documented API contract
tests; staging Swarm deployment; Nginx VM staging routing over protected transport; tested rollback
and restore; CI scans; security negative tests; secrets rotation procedure; architecture traceability;
unresolved blocker disposition; sponsor and security reviewer sign-off. No production release
implied.



Work breakdown and acceptance evidence

FND-01 — Repo governance, branch protection, CODEOWNERS
Timing: W3 | Owner: Engineering | Dependency: None

Acceptance evidence: PR approval + branch protection screenshot | Status: Not started

FND-02 — Pin toolchains and dependency lockfiles
Timing: W3 | Owner: Engineering | Dependency: Version compatibility

Acceptance evidence: Rebuild on clean runner | Status: Not started

FND-03 — Django microservice skeletons and health checks
Timing: W3 | Owner: Backend | Dependency: DOC-201

Acceptance evidence: Independent image build + smoke tests | Status: Not started

FND-04 — Flutter and Django web shells
Timing: W3 | Owner: Frontend | Dependency: DOC-205

Acceptance evidence: CI builds + navigation smoke | Status: Not started

FND-05 — OpenAPI lint and consumer contract tests
Timing: W3 | Owner: API | Dependency: DOC-205

Acceptance evidence: Contract validation report | Status: Not started

FND-06 — Security scanning and SBOM
Timing: W3 | Owner: DevSecOps | Dependency: CI selection

Acceptance evidence: Scan reports + pinned digest | Status: Not started

FND-07 — Per-service PostgreSQL roles and migrations
Timing: W4 | Owner: DBA | Dependency: DB topology

Acceptance evidence: Cross-service SQL denied | Status: Not started
<PARSED TEXT FOR PAGE: 5 / 6>
FND-08 — Redis/Celery private queues and retries
Timing: W4 | Owner: Backend | Dependency: Queue design

Acceptance evidence: Crash/retry tests | Status: Not started

FND-09 — Outbox/inbox and idempotency scaffold
Timing: W4 | Owner: Backend | Dependency: DOC-204

Acceptance evidence: Duplicate delivery test | Status: Not started

FND-10 — Service identity enforcement
Timing: W4 | Owner: Security | Dependency: BLOCK: identity ADR

Acceptance evidence: Unauthorized service call rejected | Status: Not started

FND-11 — Append-only noncash ledger scaffold
Timing: W4 | Owner: Backend | Dependency: DOC-204; no points formula

Acceptance evidence: Reversal and uniqueness tests | Status: Not started

FND-12 — Hardened image and Swarm secret handling
Timing: W4 | Owner: DevSecOps | Dependency: Swarm staging

Acceptance evidence: Secret scan + non-root check | Status: Not started

FND-13 — Dedicated Nginx VM configuration
Timing: W5 | Owner: SRE | Dependency: BLOCK: private TLS/transport

Acceptance evidence: Origin bypass and header tests | Status: Not started

FND-14 — Swarm staging stack and network zones
Timing: W5 | Owner: SRE | Dependency: BLOCK: host sizing

Acceptance evidence: Network isolation and rollout test | Status: Not started

FND-15 — Central logs, metrics and alerts
Timing: W5 | Owner: SRE | Dependency: Observability choice

Acceptance evidence: Trace ID + redaction tests | Status: Not started

FND-16 — Backup/restore and rollback drill
Timing: W5 | Owner: DBA/SRE | Dependency: BLOCK: RTO/RPO

Acceptance evidence: Timestamped drill evidence | Status: Not started

FND-17 — Stage 3 threat-control verification
Timing: W5 | Owner: Security | Dependency: DOC-203/206

Acceptance evidence: Signed verification matrix | Status: Not started
<PARSED TEXT FOR PAGE: 6 / 6>
FND-18 — Stage 3 gate and handoff
Timing: W5 | Owner: Sponsor | Dependency: All blockers dispositioned

Acceptance evidence: Signed acceptance checklist | Status: Not started



Approval and Stage 3 exit sign-off
Engineering lead: ___________________ Date: __________

Security reviewer: _________________ Date: __________

Project sponsor: ___________________ Date: __________

Gate disposition: [ ] Approved [ ] Conditional [ ] Rejected