> Source: DOC-207_Full_Architecture_Decision_Records_DRAFT_v1_0.docx (text export; formatting and embedded images are not included). Original status is retained.

<PARSED TEXT FOR PAGE: 1 / 10>
                                                  DOC-207
              ARCHITECTURE DECISION RECORDS
                              Version 1.0 • 28 October 2026 • FULL REVIEW DRAFT

Baseline: Approved DOC-201 through DOC-206. Formal approval of this document is pending. Decisions marked
“Accepted — inherited” are existing approved architecture constraints; proposed/open items remain unapproved.



1. Executive decision summary
This register documents 22 decisions or decision candidates across client architecture, service boundaries,
deployment, network edge, data, identity, messaging, media, fraud prevention, security, privacy and operations. It
distinguishes inherited approved choices from unresolved technical and business decisions. The records are
implementation guardrails, not evidence of deployed security controls.



2. Decision status taxonomy
    Accepted — inherited: already established in previously approved architecture or scope; not a fresh approval
     of DOC-207.
    Proposed — needs approval: recommendation requiring explicit decision.
    Open — decision required: alternatives and evidence are insufficient to select a final approach.
    Superseded: replaced by a later accepted ADR with documented migration.



3. Decision register
ID                                     Decision                              Status

ADR-001                                Microservices instead of modular      Accepted — inherited
                                       monolith
ADR-002                                Docker Swarm orchestration            Accepted — inherited
ADR-003                                Dedicated external Nginx VM           Accepted — inherited
ADR-004                                Flutter mobile clients                Accepted — inherited
ADR-005                                Django templates web frontend         Accepted — inherited
ADR-006                                PostgreSQL with service data          Accepted — inherited
                                       ownership
ADR-007                                Redis and Celery for asynchronous     Accepted — inherited
                                       tasks
ADR-008                                Managed video processing and          Accepted — inherited
                                       streaming
ADR-009                                Server-authoritative engagement       Accepted — inherited
                                       and non-cash points
ADR-010                                Release sequencing and financial      Accepted — inherited
                                       separation
ADR-011                                Public gateway and internal           Proposed — needs approval
                                       service access
ADR-012                                Service-to-service identity           Proposed — needs approval

                     DOC-207 | Stage 2 | Full review draft | Controlled architecture record
<PARSED TEXT FOR PAGE: 2 / 10>
ADR-013                              Client authentication and sessions    Open — decision required
ADR-014                              Nginx-to-Swarm private transport      Open — decision required
ADR-015                              Swarm control-plane sizing and        Open — decision required
                                     availability
ADR-016                              PostgreSQL hosting and DR targets     Open — decision required
ADR-017                              Observability and audit pipeline      Proposed — needs approval
ADR-018                              Secrets, images and CI/CD controls    Proposed — needs approval
ADR-019                              Qualified view and points             Open — business decision required
                                     parameters
ADR-020                              Privacy retention and data            Open — legal/product decision
                                     residency                             required
ADR-021                              Nginx high availability and TLS       Open — decision required
                                     ownership
ADR-022                              API versioning and event contracts    Proposed — needs approval




4. Full Architecture Decision Records

ADR-001 — Microservices instead of modular monolith
Status: Accepted — inherited

Domain: Service boundaries

Decision / proposal: Use independently deployable Django/DRF microservices for identity, content, engagement,
points, moderation and supporting functions.

Alternatives: Modular Django monolith; service-oriented shared deployment

Rationale: Independent scaling, ownership and blast-radius containment; fits explicit product direction.

Consequences and risks: Distributed tracing, network latency, service auth, operational complexity and
consistency overhead.

Mitigation and follow-up: Maintain service contracts, per-service CI/CD, distributed tracing and runbooks.

Linked specifications: DOC-201, DOC-202, DOC-205

Acceptance / verification evidence: Service inventory and deployment independence demonstrated

ADR-002 — Docker Swarm orchestration
Status: Accepted — inherited

Domain: Infrastructure

Decision / proposal: Deploy containerized services and workers using Docker Swarm stacks, overlay networks,
secrets and rolling updates.

Alternatives: Kubernetes; standalone Docker Compose; Nomad

Rationale: Chosen deployment platform and comparatively simple operating model.

Consequences and risks: Manager quorum, limited native policy features, overlay troubleshooting and
ecosystem constraints.


                     DOC-207 | Stage 2 | Full review draft | Controlled architecture record
<PARSED TEXT FOR PAGE: 3 / 10>
Mitigation and follow-up: Restrict manager control plane; pinned images; secrets; backup manager state; test
upgrades.

Linked specifications: DOC-201, DOC-202, DOC-203, DOC-208

Acceptance / verification evidence: Swarm recovery and rollout drills

ADR-003 — Dedicated external Nginx VM
Status: Accepted — inherited

Domain: Network edge

Decision / proposal: Run Nginx on a dedicated VM/server outside Docker Swarm; proxy only to designated
Swarm ingress endpoints.

Alternatives: Nginx in Swarm; ingress controller inside cluster

Rationale: Separates edge patching, routing and blast radius from application services.

Consequences and risks: Additional host to patch; external-to-cluster secure channel; possible single point of
failure.

Mitigation and follow-up: Harden VM; private tunnel or TLS upstream; restrict Swarm ports; plan HA and
recovery.

Linked specifications: DOC-201, DOC-202, DOC-203, DOC-208

Acceptance / verification evidence: Origin bypass and gateway failover tests

ADR-004 — Flutter mobile clients
Status: Accepted — inherited

Domain: Clients

Decision / proposal: Build Android and iOS applications using Flutter/Dart.

Alternatives: Separate native apps; React Native

Rationale: One shared mobile codebase and consistent UX.

Consequences and risks: Platform-specific secure storage, lifecycle and plugin vulnerabilities require testing.

Mitigation and follow-up: MASVS checks, secure token storage, release signing and dependency review.

Linked specifications: DOC-201, DOC-206

Acceptance / verification evidence: Mobile security test matrix

ADR-005 — Django templates web frontend
Status: Accepted — inherited

Domain: Clients

Decision / proposal: Use Django templates with HTML/CSS/vanilla JavaScript for web; do not introduce Next.js.

Alternatives: Next.js SPA; React SPA

Rationale: Matches approved stack and reduces client complexity.

Consequences and risks: CSRF, session security and BFF design need care.

Mitigation and follow-up: Strict CSRF/CSP, session cookie settings, no secret in browser, web service deployment
separation.


                    DOC-207 | Stage 2 | Full review draft | Controlled architecture record
<PARSED TEXT FOR PAGE: 4 / 10>
Linked specifications: DOC-201, DOC-205, DOC-206

Acceptance / verification evidence: CSRF and browser security tests

ADR-006 — PostgreSQL with service data ownership
Status: Accepted — inherited

Domain: Data

Decision / proposal: Use PostgreSQL; each microservice owns its logical data store and credentials, with no direct
cross-service writes.

Alternatives: Shared schema; separate physical database server per service; NoSQL

Rationale: Transactional guarantees and strong isolation semantics while allowing initial shared hardware.

Consequences and risks: Distributed consistency, outbox delivery and cross-service reporting complexity.

Mitigation and follow-up: Per-service roles/databases, migration ownership, outbox/inbox, reconciliation.

Linked specifications: DOC-204, DOC-203

Acceptance / verification evidence: Cross-service privilege negative tests

ADR-007 — Redis and Celery for asynchronous tasks
Status: Accepted — inherited

Domain: Messaging

Decision / proposal: Use Redis/Celery for non-authoritative background tasks; persist authoritative business
events transactionally.

Alternatives: RabbitMQ; Kafka; database polling alone

Rationale: Compatible with Django ecosystem and approved stack.

Consequences and risks: Queue loss, duplicates and at-least-once semantics.

Mitigation and follow-up: Idempotent consumers, retry policies, DLQ, outbox, bounded queues and monitoring.

Linked specifications: DOC-201, DOC-204

Acceptance / verification evidence: Crash/replay/poison-message tests

ADR-008 — Managed video processing and streaming
Status: Accepted — inherited

Domain: Media

Decision / proposal: Use managed Cloudflare video processing/streaming rather than running self-managed
transcoders; exact product/plan subject to commercial validation.

Alternatives: Self-hosted FFmpeg pipeline; alternative managed provider

Rationale: Reduces operational risk and media-processing attack surface.

Consequences and risks: Vendor dependence, pricing, egress, playback access control and webhook behavior.

Mitigation and follow-up: Provider proof-of-concept, signed callbacks, direct upload intents and data-processing
review.

Linked specifications: DOC-201, DOC-202, DOC-205

Acceptance / verification evidence: Provider integration and cost acceptance


                        DOC-207 | Stage 2 | Full review draft | Controlled architecture record
<PARSED TEXT FOR PAGE: 5 / 10>
ADR-009 — Server-authoritative engagement and non-cash points
Status: Accepted — inherited

Domain: Business integrity

Decision / proposal: Award non-cash points only after backend-qualified genuine engagement; append-only
auditable postings; never award for ad clicks/views.

Alternatives: Client-calculated points; ad-event rewards; mutable balances

Rationale: Fraud resistance and ad-policy separation; respects approved R1 scope.

Consequences and risks: Higher implementation cost; fraud false positives and disputes.

Mitigation and follow-up: Versioned rules, evidence references, dedupe, reversals, review workflow.

Linked specifications: DOC-203, DOC-204, DOC-205, DOC-206

Acceptance / verification evidence: Replay, concurrency, fraud and ad-event zero-award tests

ADR-010 — Release sequencing and financial separation
Status: Accepted — inherited

Domain: Product scope

Decision / proposal: R1 creator-content with non-cash points; defer business verification R2, ticketing R3 and
financial settlement/payouts R4.

Alternatives: Build all verticals in R1

Rationale: Limits launch risk and separates financial regulatory scope.

Consequences and risks: Future schema and integration changes require forward compatibility.

Mitigation and follow-up: Feature gates, isolated future contexts and separate monetary ledger design.

Linked specifications: PRD/SRS, DOC-201, DOC-203

Acceptance / verification evidence: R1 endpoints cannot issue cash payouts

ADR-011 — Public gateway and internal service access
Status: Proposed — needs approval

Domain: API security

Decision / proposal: Expose only a dedicated public API gateway/BFF through Nginx; internal service APIs are
private and workload-authenticated.

Alternatives: Expose every service behind Nginx; API gateway vendor

Rationale: Reduces public attack surface and centralizes routing.

Consequences and risks: Gateway may become a bottleneck and failure point; gateway auth cannot replace
object authorization.

Mitigation and follow-up: Horizontal scaling, per-service auth, audience scopes, rate limits and health checks.

Linked specifications: DOC-202, DOC-205, DOC-206

Acceptance / verification evidence: Gateway failover and unauthorized route probes

ADR-012 — Service-to-service identity
Status: Proposed — needs approval


                     DOC-207 | Stage 2 | Full review draft | Controlled architecture record
<PARSED TEXT FOR PAGE: 6 / 10>
Domain: Identity

Decision / proposal: Use mutually authenticated transport and short-lived scoped service credentials, with
explicit audience restrictions.

Alternatives: Shared static API keys; trust overlay network

Rationale: Reduces lateral movement and credential replay.

Consequences and risks: Certificate issuance/rotation complexity and clock synchronization.

Mitigation and follow-up: Select certificate/identity issuer; automate rotation and revocation.

Linked specifications: DOC-203, DOC-205, DOC-206

Acceptance / verification evidence: Expired, wrong-audience and forged identity tests

ADR-013 — Client authentication and sessions
Status: Open — decision required

Domain: Identity

Decision / proposal: Select identity authority and token/session strategy after evaluating Django-native auth and
managed identity; enforce MFA for privileged users.

Alternatives: Django-native; managed OIDC; custom auth

Rationale: Decision pending due to cost, portability, operational burden and secure mobile/web session
requirements.

Consequences and risks: Unresolved decision blocks detailed auth endpoints and revocation design.

Mitigation and follow-up: Document session lifetimes, refresh rotation, logout semantics, MFA and recovery.

Linked specifications: DOC-205, DOC-206

Acceptance / verification evidence: Auth architecture approval and tests

ADR-014 — Nginx-to-Swarm private transport
Status: Open — decision required

Domain: Network

Decision / proposal: Choose a private routed connection or WireGuard tunnel with verified upstream TLS/mTLS
and restricted ports.

Alternatives: Public Swarm ingress with TLS; VPN only; private LAN

Rationale: Avoids direct public exposure of application nodes.

Consequences and risks: Depends on VM/network placement and certificate lifecycle.

Mitigation and follow-up: Choose topology, document CIDRs and firewall ACLs, test interception.

Linked specifications: DOC-202, DOC-203, DOC-208

Acceptance / verification evidence: Network diagram, firewall audit and MITM test

ADR-015 — Swarm control-plane sizing and availability
Status: Open — decision required

Domain: Infrastructure




                        DOC-207 | Stage 2 | Full review draft | Controlled architecture record
<PARSED TEXT FOR PAGE: 7 / 10>
Decision / proposal: Select manager count and worker capacity based on budget and availability target; 3
managers for quorum HA where feasible.

Alternatives: Single manager; 3 managers; 5 managers

Rationale: Availability requirements must be balanced against budget.

Consequences and risks: Single manager is SPOF; 2 managers do not provide robust fault tolerance.

Mitigation and follow-up: Capacity plan, node placement, manager backups, failure simulations.

Linked specifications: DOC-202, DOC-208

Acceptance / verification evidence: Quorum and node-loss drill

ADR-016 — PostgreSQL hosting and DR targets
Status: Open — decision required

Domain: Data/operations

Decision / proposal: Choose managed vs self-hosted PostgreSQL, primary/replica model, PITR, encrypted backups
and approved RPO/RTO.

Alternatives: Single DB VM; managed DB; HA self-hosted cluster

Rationale: Data durability and recovery goals must be quantified before pilot.

Consequences and risks: Cost, ops burden, data residency and replication complexity.

Mitigation and follow-up: Restore test, monitoring, retention and key management.

Linked specifications: DOC-204, DOC-208

Acceptance / verification evidence: Timed isolated restore and failover test

ADR-017 — Observability and audit pipeline
Status: Proposed — needs approval

Domain: Operations

Decision / proposal: Centralize structured logs, metrics, traces and append-only security audit records with trace
IDs.

Alternatives: Per-container logs only; vendor APM; open-source stack

Rationale: Necessary to investigate cross-service incidents and fraud.

Consequences and risks: Sensitive data exposure and storage cost.

Mitigation and follow-up: Redaction, retention, role restrictions, alert thresholds and audit integrity.

Linked specifications: DOC-203, DOC-206, DOC-208

Acceptance / verification evidence: End-to-end trace and redaction tests

ADR-018 — Secrets, images and CI/CD controls
Status: Proposed — needs approval

Domain: DevSecOps

Decision / proposal: Use Swarm secrets or external secret store, pinned images, vulnerability scans, SBOMs and
gated production deployments.

Alternatives: Environment variables; mutable latest tags; manual SSH deploy


                     DOC-207 | Stage 2 | Full review draft | Controlled architecture record
<PARSED TEXT FOR PAGE: 8 / 10>
Rationale: Protects production and improves release provenance.

Consequences and risks: Maintenance and operational overhead; Swarm secrets lifecycle needs design.

Mitigation and follow-up: Rotation runbooks, image provenance, rollback, two-person production approval.

Linked specifications: DOC-203, DOC-206, DOC-208

Acceptance / verification evidence: Secret scan and unsigned-image rejection

ADR-019 — Qualified view and points parameters
Status: Open — business decision required

Domain: Engagement

Decision / proposal: Define genuine-view thresholds, dedupe windows, exclusions, points conversion and dispute
windows before implementing award logic.

Alternatives: Fixed per-view points; weighted quality; periodic scoring

Rationale: Rules must be explicit, fair, auditable and resistant to gaming.

Consequences and risks: Prematurely freezing a formula creates fraud or product-policy risk.

Mitigation and follow-up: Approve rule table, thresholds, versioning, privacy impact and test fixtures.

Linked specifications: DOC-204, DOC-205, DOC-206

Acceptance / verification evidence: Approved rule examples and boundary tests

ADR-020 — Privacy retention and data residency
Status: Open — legal/product decision required

Domain: Privacy

Decision / proposal: Approve purpose-based retention, deletion/appeal workflows and provider data-processing
terms before pilot.

Alternatives: Indefinite retention; minimum necessary retention

Rationale: Privacy-by-design and incident response evidence balance.

Consequences and risks: Legal review and provider commitments outstanding.

Mitigation and follow-up: Retention matrix, legal review, data subject procedures and deletion tests.

Linked specifications: DOC-203, DOC-204, DOC-206

Acceptance / verification evidence: Privacy review and deletion/hold tests

ADR-021 — Nginx high availability and TLS ownership
Status: Open — decision required

Domain: Edge

Decision / proposal: Choose Cloudflare-to-Nginx TLS and origin authentication, upstream encryption, and
whether a second Nginx VM is needed for pilot.

Alternatives: Single proxy; dual proxy behind LB

Rationale: Ensures trustworthy proxy headers and continuity.

Consequences and risks: HA increases cost; single proxy outage impacts all clients.

Mitigation and follow-up: Document certificate ownership, renewals, failover, edge allowlist.

                      DOC-207 | Stage 2 | Full review draft | Controlled architecture record
<PARSED TEXT FOR PAGE: 9 / 10>
Linked specifications: DOC-202, DOC-203, DOC-208

Acceptance / verification evidence: Origin-bypass, expiry and failover tests

ADR-022 — API versioning and event contracts
Status: Proposed — needs approval

Domain: Integration

Decision / proposal: Use /api/v1 versioning, OpenAPI 3.1 for HTTP, schema-versioned internal events, consumer
compatibility checks.

Alternatives: Unversioned endpoints; protobuf-only; ad hoc events

Rationale: Supports independently deployed microservices.

Consequences and risks: Version drift and duplicated schema management.

Mitigation and follow-up: Contract tests, deprecation policy and idempotent event handling.

Linked specifications: DOC-205, DOC-206

Acceptance / verification evidence: Backward-compatibility CI test



5. Cross-cutting decisions and implementation constraints
   Every microservice owns its schema and credentials; interservice changes occur through authenticated
    APIs/events, not shared table writes.
   Public clients never post points directly; advertising impressions and clicks cannot generate points.
   No R1 monetary payouts or tickets. Future R3/R4 financial systems require separate security gates.
   Nginx remains on a dedicated VM outside Docker Swarm. Swarm manager ports must never be published
    through the public reverse proxy.
   Zero-trust service authentication applies even on private Swarm overlay networks.
   Security controls remain unverified until DOC-206 evidence is collected during implementation and testing.
   All open decisions must have a named owner, deadline, alternative analysis and approval trail.



6. Decision dependencies and critical path
Network transport (ADR-014) and TLS/HA (ADR-021) precede final firewall and Nginx deployment configuration.
Swarm sizing (ADR-015) and database topology (ADR-016) precede infrastructure provisioning. Authentication
(ADR-013) and service identity (ADR-012) precede final API auth implementation. Qualified-view parameters
(ADR-019) precede points-award code and tests. Privacy retention (ADR-020) precedes pilot data collection. These
dependencies must be tracked in DOC-209 and the project tracker.



7. Approval and change-control gate
Approving DOC-207 confirms the accuracy of the register and inherited decisions, not automatic approval of
entries marked Proposed or Open. Proposed entries may be approved individually, and Open entries require
explicit decisions or documented deferrals. Changes to accepted architecture require a new superseding ADR,
migration plan, security impact review and updated DOC-201–DOC-208 cross-references.

Sponsor approval: __________________________ Date: __________

Architecture reviewer: ______________________ Date: __________

Security reviewer: _________________________ Date: __________

                     DOC-207 | Stage 2 | Full review draft | Controlled architecture record
<PARSED TEXT FOR PAGE: 10 / 10>
Exceptions / conditional approvals: ______________________________________________




                     DOC-207 | Stage 2 | Full review draft | Controlled architecture record