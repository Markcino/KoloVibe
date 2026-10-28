> Source: DOC-201_Full_Software_Architecture_DRAFT_v1_0.docx (text export; formatting and embedded images are not included). Original status is retained.

<PARSED TEXT FOR PAGE: 1 / 8>
LIBERIAN CREATOR PLATFORM | STAGE 2 | CONTROLLED DRAFT




DOC-201 | Full Software Architecture
Specification
Liberian Digital Creator Platform • Stage 2 • Microservices on Docker Swarm • Dedicated external
Nginx VM

 Document control                                    Value
 Version                                             1.0 — full review draft
 Date                                                28 October 2026
 State                                               Complete draft for technical review; not
                                                     formally approved
 Source baseline                                     Approved Stage 1 PRD/SRS; Stage 2 v0.3
                                                     architecture direction
 Decisions carried forward                           Microservices; Docker Swarm; Nginx on
                                                     independent VM (DEC-004)
 Scope                                               R1 creator-content MVP; future R2–R4 as
                                                     extension boundaries



1. Executive architecture statement
Release 1 delivers secure identity, creator profiles, original video upload/playback, qualified
engagement, non-cash points, and moderation. The architecture uses domain-owned Django/DRF
services deployed as independently versioned containers in Docker Swarm. The public Django-
template web application is a separate web service; Flutter clients use versioned APIs. Nginx runs on
a dedicated server/VM outside Swarm and is the sole approved ingress to private application
endpoints.

This specification defines design intent, enforceable invariants, operating behavior, and review
questions. It is not evidence that the deployment, performance, security tests, or commercial
provider integrations have been completed.



2. Scope and release boundaries
 Release                            Enabled                           Explicitly excluded
 R1                                 Identity; creator profile;        Cash rewards; ticket
                                    media; engagement                 payments; business reviews;
                                    qualification; non-cash points;   revenue allocation
                                    moderation; audit
 R2                                 Verified business and service     No R1 dependencies on R2
                                    evidence (future)                 availability
 R3                                 Events, ticketing, QR             No ticket payment endpoints
                                    redemption (future)               in R1
 R4                                 Collected revenue                 No R1 cash balances, payouts,
                                    reconciliation and cash           or earnings promises
                                    payouts (future)




DOC-201 • Version 1.0 full draft • Not approved for implementation
<PARSED TEXT FOR PAGE: 2 / 8>
LIBERIAN CREATOR PLATFORM | STAGE 2 | CONTROLLED DRAFT



3. Quality attributes and design targets
     Security: OWASP ASVS Level 2 as the Django web/API verification target, MASVS/MASTG for
      Flutter; explicit object-level authorization and strong audit trails.
     Availability: tolerate failure of one application task through replicated stateless services where
      capacity permits; no false claim of HA when Nginx, DB, or a single Swarm manager is a
      singleton.
     Consistency: strong transactions within one service database; eventual consistency across
      services with outbox/inbox, deduplication, and reconciliation.
     Performance: define measurable p95 API and upload/playback targets during pilot sizing; do not
      invent an SLA before workload testing.
     Privacy: data minimization, access limitation, documented retention, deletion/appeal workflow
      and media moderation controls.
     Operability: reproducible images, CI quality gates, centralized logs/metrics/traces, restore drills
      and rollback procedures.



4. Component and service inventory
    Service                       Data ownership /                 Public exposure
                                  responsibilities
 web-frontend                     Django templates, BFF,           Via Nginx only
                                  browser sessions, CSRF, safe
                                  presentation
 identity-service                 Accounts, password/MFA           Versioned API via Nginx
                                  policy, sessions/tokens, roles,
                                  creator eligibility
 content-service                  Videos, upload grants, media     Versioned API via Nginx
                                  lifecycle, publication and
                                  playback grants
 engagement-service               View candidates, likes,          Versioned API via Nginx
                                  deduplication, fraud signals,
                                  qualification decisions
 points-service                   Append-only non-cash points      Read API via Nginx; award
                                  transactions, holds, reversals,  command internal only
                                  balances
 moderation-service               Reports, cases, review actions,  Restricted API via Nginx
                                  appeals, takedown
 audit-service                    Immutable-ish append audit       Internal only
                                  ingestion, event integrity and
                                  retention
 worker processes                 Celery tasks, outbox delivery,   Internal only
                                  media reconciliation,
                                  scheduled checks
 future services                  Business, events, revenue and    Not deployed R1
                                  payout as isolated domains
Design caveat: “audit-service” may be implemented as a dedicated collector with immutable object
storage or a tightly controlled append-only datastore. Exact product, topology and retention require
a security design decision; ordinary application logs are not sufficient as the authoritative audit trail.




DOC-201 • Version 1.0 full draft • Not approved for implementation
<PARSED TEXT FOR PAGE: 3 / 8>
LIBERIAN CREATOR PLATFORM | STAGE 2 | CONTROLLED DRAFT



5. Runtime request topology
Internet clients → optional Cloudflare edge/WAF → dedicated Nginx VM (public HTTPS) → private
network or authenticated tunnel → restricted Swarm ingress/gateway → web-frontend or public-
facing DRF APIs → service-to-service calls and owned datastores. Managed video streaming and
object storage are external trust domains accessed via narrowly scoped credentials and time-limited
grants.

     Nginx VM is NOT a Docker Swarm node; its lifecycle, patching, TLS secrets and monitoring are
      independent.
     Expose only 443 publicly at Nginx; optionally 80 for redirect/ACME if required. Swarm
      application entrypoints are reachable only from Nginx private IP or tunnel identity.
     No public access to PostgreSQL, Redis, Celery, Docker API, Swarm ports, audit storage, or
      internal management interfaces.
     Nginx strips untrusted Forwarded/X-Forwarded-* headers and sets trusted headers; Django
      trusts only configured proxy addresses.
     If Cloudflare is enabled, prevent bypass of the intended Cloudflare-to-origin security policy;
      configure authenticated origin TLS and appropriate firewall restrictions.
     Use TLS from Nginx to Swarm gateway or an authenticated encrypted tunnel; do not treat a
      private VLAN alone as transport encryption.



6. Docker Swarm topology and deployment model
Recommended production baseline: three manager nodes for Raft quorum, plus at least two worker
nodes when capacity and budget permit. This is a design recommendation, not a confirmed
hardware purchase. A single-node pilot is acceptable only if explicitly labeled non-HA and risk
accepted. Do not place an externally exposed Swarm management endpoint on Nginx.

    Zone                             Placement                          Rules
    Public edge                      Dedicated Nginx VM                 Only public ingress; SSH via
                                                                        management VPN/bastion;
                                                                        host firewall
    Swarm managers                   Private control plane              2377/TCP manager
                                                                        join/control; 7946/TCP+UDP
                                                                        and 4789/UDP only between
                                                                        trusted nodes; encrypted
                                                                        overlay when supported and
                                                                        validated
    Swarm workers                    Private app hosts                  Stateless web/API replicas;
                                                                        resource limits; placement
                                                                        constraints
    Stateful data                    Dedicated private PostgreSQL       Backups, WAL, encryption, no
                                     host/managed DB preferred          internet route
    Broker/cache                     Private Redis or dedicated         Authentication, ACL, isolated
                                     broker                             queues; no public port
    Media provider                   Managed Cloudflare                 Signed upload/playback flows,
                                     Stream/storage                     webhook verification,
                                                                        provider quotas




DOC-201 • Version 1.0 full draft • Not approved for implementation
<PARSED TEXT FOR PAGE: 4 / 8>
LIBERIAN CREATOR PLATFORM | STAGE 2 | CONTROLLED DRAFT



Swarm ingress routing mesh can expose a published port on multiple nodes; firewall every node
and prefer a controlled gateway / host-mode published port with explicit placement to avoid
unintended exposure. Validate actual Swarm routing behavior in staging.



7. Inter-service communication
External APIs use HTTPS/JSON with OpenAPI contracts. Internal synchronous calls are limited to
workflows requiring immediate authorization or read responses. Events and commands use a
broker with explicit schema versions, event IDs, producer identity, correlation IDs, and bounded
retries.

    Pattern                          Example                      Failure rule
    Synchronous read                 content → identity entitlement
                                                                  Timeout, bounded retries only
                                     check                        for idempotent requests; fail
                                                                  closed on protected operations
 Transactional outbox           engagement qualifies event →      Commit qualification and
                                outbox row                        outbox in one local transaction
 Asynchronous command           points consumes qualified         Verify producer identity and
                                engagement                        qualification evidence; dedupe
                                                                  award ID
 Inbox / deduplication          points processed_commands         At-least-once delivery
                                table                             accepted; exactly-once
                                                                  business effect via unique
                                                                  constraints
 Compensating event             fraud confirmed → reverse         Append compensating ledger
                                points                            entry; never overwrite prior
                                                                  award
Avoid a synchronous chain from every client view through multiple services. Client responses may
show pending verification; final points are calculated asynchronously.



8. Identity, sessions, authorization and workload identity
     Identity-service owns authentication and role grants. Access tokens are short-lived, audience-
      bound and signed; rotate signing keys and publish a trusted verification mechanism.
     Web-frontend uses secure HttpOnly SameSite cookies, CSRF protection, server-side session
      controls and a separate BFF boundary where appropriate. Flutter uses secure platform storage
      and approved token refresh flows.
     Every service validates issuer, audience, expiration and subject; perform object-level
      authorization against owned resources. A role alone never authorizes another creator’s private
      data.
     Internal service credentials must be distinct from end-user credentials; use mTLS or signed
      short-lived workload tokens with service-specific scopes and rotation.
     Moderation, support and administrator functions require elevated roles, MFA, explicit audit
      events and separation of duties.
     No cross-service sharing of user password hashes or unrestricted database credentials.




DOC-201 • Version 1.0 full draft • Not approved for implementation
<PARSED TEXT FOR PAGE: 5 / 8>
LIBERIAN CREATOR PLATFORM | STAGE 2 | CONTROLLED DRAFT



9. Data ownership and consistency
Each service owns a separate PostgreSQL database or logically isolated schema and dedicated DB
role. Cross-service SQL joins and foreign keys are prohibited; references use opaque identifiers and
contract-based lookups. A shared PostgreSQL server may host isolated databases for pilot cost
efficiency but remains a common failure domain.

 Owner                             Core entities                      Integrity requirements
 identity                          users, identities, role_grants,    Unique account identifiers;
                                   sessions, creator_status           auditable role changes
 content                           videos, media_assets,              Owner checks; state machine;
                                   upload_sessions,                   idempotent provider
                                   publication_events                 webhooks
 engagement                        view_candidates, like_events,      Uniqueness/deduplication;
                                   qualification_decisions,           evidence version; fraud holds
                                   risk_flags
 points                            point_entries, point_accounts,     Append-only entries; unique
                                   award_commands, reversals          award IDs; nonnegative
                                                                      available balance policy
 moderation                        reports, cases, actions, appeals   Case audit history and
                                                                      reviewer attribution
 audit                             audit_events,                      Tamper evidence, restricted
                                   integrity_metadata                 retention and access



10. Critical workflow A — Video upload and publication
1) Creator authenticates; content-service checks creator entitlement and rate limits. 2) Content-
service creates pending upload record and issues a short-lived, constrained provider upload grant.
3) Client uploads directly to managed video provider, not through Django or Nginx. 4) Provider
webhook is verified, timestamp/replay checked, and recorded idempotently. 5) Worker verifies
media readiness and moderation prerequisites. 6) Content-service publishes only after policy
checks; player receives time-limited playback authorization. 7) Failed or abandoned uploads are
expired and cleaned up.



11. Critical workflow B — Qualified engagement and points
1) Viewer requests authorized playback. 2) Client submits telemetry as untrusted candidates;
provider telemetry may supplement evidence. 3) Engagement-service validates eligibility,
deduplicates, applies fraud signals and records a versioned qualification decision. 4) A local outbox
emits QualifiedEngagement with immutable evidence reference and award ID. 5) Points-service
authenticates the producer, validates command schema and award uniqueness, appends a non-cash
ledger credit, and acknowledges. 6) Disputes or fraud create append-only reversals. 7) Reconciliation
detects missing or duplicate commands.

Qualified-view duration/threshold, anti-abuse weighting, points formula, creator eligibility and
privacy retention are OPEN Stage 1 business parameters. Until approved, qualification and awards
must run in a test/simulation mode or remain disabled in production. Likes never translate directly
into money. Ad views/clicks never trigger point awards.




DOC-201 • Version 1.0 full draft • Not approved for implementation
<PARSED TEXT FOR PAGE: 6 / 8>
LIBERIAN CREATOR PLATFORM | STAGE 2 | CONTROLLED DRAFT



12. Moderation, abuse and privacy
     Support user reports, creator takedown, appeals and admin enforcement with least-privilege
      review queues.
     Separate safety actions from financial or points operations; moderation can request
      hold/review, but cannot silently edit the ledger.
     Use media scanning, rate limits, abuse scoring, duplicate-upload detection and quarantine
      where feasible.
     Collect minimum necessary telemetry; restrict raw device/IP data and define retention/deletion
      schedules before launch.
     Document legal basis, privacy notice, data subject request procedures and data-transfer
      considerations for Liberia and external cloud vendors.



13. Security boundaries and threat controls
    Threat                           Primary controls                  Verification
    Forged proxy headers /           Nginx header sanitation,          Direct-bypass and spoof tests
    direct ingress                   trusted proxies, private
                                     ingress ACL
    Stolen tokens / privilege        Short TTL, audience binding,      ASVS access control and
    escalation                       MFA for privileged roles,         negative API tests
                                     object authorization
    Fraudulent views / points        Server qualification,             Replay/concurrency/fraud
    replay                           idempotency, outbox/inbox,        scenario tests
                                     risk holds
    Compromised worker /             Scoped workload identity,         Credential scope and lateral
    service                          network segmentation, per-        movement tests
                                     service DB roles
    Malicious media / webhook        Signed provider webhooks,         Webhook signature/replay and
    spoofing                         MIME/media checks,                upload fuzz tests
                                     moderation, replay protection
    Swarm host compromise            Hardened hosts, minimal           Host benchmark, image scan,
                                     images, rootless/non-root         break-glass review
                                     where possible, secret controls
    Lost database / outage           PITR backups, restore drills,     Timed restoration exercise
                                     monitored replication where
                                     budget allows



14. Availability, resilience and failure handling
Nginx VM is a single point of failure until an HA pair and failover mechanism are funded and tested.
PostgreSQL and Redis may also be singletons in pilot. Document real RPO/RTO only after
backup/restore exercises; do not label the system highly available by deploying multiple Django
replicas alone.

     Health checks distinguish liveness from readiness; stop routing to unhealthy tasks.
     Set CPU/memory reservations and limits; cap worker concurrency and queue depth to prevent
      resource exhaustion.




DOC-201 • Version 1.0 full draft • Not approved for implementation
<PARSED TEXT FOR PAGE: 7 / 8>
LIBERIAN CREATOR PLATFORM | STAGE 2 | CONTROLLED DRAFT



     Use circuit breakers/timeouts and exponential backoff with jitter; never retry non-idempotent
      writes without idempotency keys.
     Deploy rolling updates with health gates and rollback to known image digest; use expand-
      contract database migrations.
     Monitor failed outbox delivery, DLQ growth, ledger reconciliation gaps, Nginx 5xx rates, disk
      capacity and certificate expiry.



15. CI/CD and software supply chain
Each service has a versioned repository or clear monorepo ownership, locked dependencies, tests,
linting, SAST, secret scanning, dependency/SBOM generation, image scanning, and provenance
records. Build once, promote immutable image digests through staging and production. Protect
Swarm manager credentials and deploy through least-privilege automation with human approval
for production changes.



16. Secrets, configuration and certificates
No credentials in images, Git, compose files or application logs. Use Docker Swarm secrets for
supported workloads with strict access and rotation; review limitations of at-rest protection and
operator access. Separate production and staging secrets. Store Nginx private keys on the dedicated
VM under restricted permissions or an appropriate secret manager. Rotate service credentials and
webhook secrets, and test revocation.



17. Observability and operational response
Adopt correlation/request IDs propagated across Nginx, Django and worker events; structured logs
without raw tokens or sensitive payloads; metrics for latency, errors, queue lag, DB health, media
processing, qualification anomalies and point reconciliation. Centralize logs with retention controls,
alerts, runbooks, incident severity, owner and escalation. Audit records must preserve actor, action,
object, decision, timestamp and trace ID.



18. Deployment, recovery and acceptance gates
    Gate                                             Minimum evidence
    Topology                                         Verified diagram, node inventory, ports and
                                                     firewall test results
    Security                                         ASVS/MASVS mapping, STRIDE risk treatment,
                                                     service auth negative tests
    Data                                             Schema ownership, migrations, backups and
                                                     completed restore drill
    API                                              OpenAPI spec, compatibility and error-contract
                                                     tests
    Points                                           Qualification rules approved,
                                                     replay/duplication tests and reconciliation
    Operations                                       Monitoring dashboards, alert routes, rolling
                                                     update/rollback drill
    Pilot                                            Privacy/moderation review, load test, abuse



DOC-201 • Version 1.0 full draft • Not approved for implementation
<PARSED TEXT FOR PAGE: 8 / 8>
LIBERIAN CREATOR PLATFORM | STAGE 2 | CONTROLLED DRAFT



                                                      simulation, launch sign-off



19. Open decisions and required reviewers
    ID                               Decision / owner                   Gate
    OD-01                            Swarm manager/worker count         Before DOC-208 approval
                                     and hosting capacity —
                                     infrastructure lead
    OD-02                            Nginx TLS termination,             Before production ingress
                                     private link and HA strategy —
                                     security/operations
    OD-03                            PostgreSQL hosting, backup         Before production data
                                     retention, RPO/RTO —
                                     data/operations
    OD-04                            Redis vs dedicated message         Before points integration
                                     broker and durability
                                     semantics — backend lead
    OD-05                            Qualified view threshold and       Before production awards
                                     points formula —
                                     product/anti-fraud
    OD-06                            Creator verification and           Before launch
                                     retention/privacy schedule —
                                     product/legal
    OD-07                            Workload identity mechanism        Before internal API
                                     and secret rotation — security     deployment
                                     lead
    OD-08                            Media provider commercial          Before upload launch
                                     plan and signed grant support
                                     — product/engineering
    OD-09                            Nginx failover budget and          Before availability claim
                                     recovery strategy —
                                     operations



20. Architecture approval checklist
     [ ] All open decisions are resolved or explicitly risk-accepted with owner and date.
     [ ] DOC-202 physical and data-flow diagrams match DOC-201.
     [ ] DOC-203 threat model maps to actual network and service boundaries.
     [ ] DOC-204 schemas and DOC-205 OpenAPI contracts implement the ownership rules.
     [ ] DOC-206 contains executable test procedures and evidence requirements.
     [ ] DOC-208 deployment topology and Nginx firewall rules are validated in staging.
     [ ] Product, engineering, security and operations reviewers sign the final baseline.

Approval requested: technical review of this complete DOC-201 draft. Stage 2 is NOT closed by this
document alone.




DOC-201 • Version 1.0 full draft • Not approved for implementation