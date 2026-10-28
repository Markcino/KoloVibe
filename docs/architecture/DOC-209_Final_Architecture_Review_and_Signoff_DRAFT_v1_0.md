> Source: DOC-209_Final_Architecture_Review_and_Signoff_DRAFT_v1_0.docx (text export; original formatting, formulas and embedded images are not included). Original review status is retained.

<PARSED TEXT FOR PAGE: 1 / 6>
                                                 DOC-209
        FINAL ARCHITECTURE REVIEW & SIGN-OFF
                          Stage 2 | Version 1.0 | 28 October 2026 | FULL REVIEW DRAFT

Document status: Pending formal approval. Stage 2 closure: NOT GRANTED. Implementation and security evidence:
NOT YET AVAILABLE.



1. Executive review and recommendation
DOC-201 through DOC-208 have received user approval as design baselines. The architecture is a Django/DRF
microservice system deployed on Docker Swarm, with a dedicated Nginx server/VM outside Swarm; Flutter mobile
clients and a Django-template web frontend; private PostgreSQL data ownership; Redis/Celery; managed video
processing. This review does not assert the infrastructure is deployed, tests have passed, or the remaining
architecture decisions are resolved. Recommended disposition: CONDITIONAL DESIGN BASELINE ACCEPTANCE,
not unconditional Stage 2 closure.



2. Scope and release boundary
Release 1: account identity, creator profiles, video upload/playback, qualified engagement, non-cash points,
moderation and auditing. Release 2 business verification/reviews, Release 3 ticketing and payments, Release 4
monetary revenue sharing and payouts remain deferred. No financial ledger or real-money rewards in R1;
advertising clicks/impressions must never generate points.



3. Evidence register
DOC-201 Software Architecture v1.0 — approved; DOC-202 Architecture and Data Flows v1.0 — approved; DOC-203
STRIDE Threat Model v1.0 — approved as design, testing pending; DOC-204 Database Architecture v1.0 — approved;
DOC-205 OpenAPI Specification v1.0 — approved, open contract decisions tracked; DOC-206 Security Verification
Plan v1.0 — approved, all test evidence pending; DOC-207 ADR Register v1.0 — approved as register, proposed/open
decisions not implicitly accepted; DOC-208 Infrastructure Blueprint v1.0 — approved as design, deployment
decisions open; DOC-209 — this document, awaiting review.



4. Architecture invariants
INV-A Nginx is on a separate VM/server outside Swarm. INV-B Only Nginx or approved gateway path exposes public
ingress; Swarm control plane and DB remain private. INV-C Each service owns its data and authenticates cross-
service requests. INV-D Points writes are private, idempotent, append-only and traceable. INV-E Untrusted client
playback and ad events never directly create rewards. INV-F Service secrets are managed and rotated, not
embedded in images. INV-G Every release supports auditability, rollback and restore.



5. End-to-end consistency review
Trace frontend authentication to Identity API; creator upload intent to Content API and video provider; signed
provider callbacks to Content state; verified watch evidence to Engagement; qualified event with unique ID to
Points; reports to Moderation; security events to central audit. Review service data ownership, asynchronous
<PARSED TEXT FOR PAGE: 2 / 6>
delivery semantics, authorization at each hop and compensating controls for unavailable dependencies. Mark as
technical walkthrough pending; no live integration results exist.



6. Threat and security acceptance
DOC-203 identifies 42 design-stage threats. DOC-206 includes 42 verification controls; these have not been executed.
Before pilot, critical issues must be mitigated and verified; residual high risk requires explicit owner acceptance
and expiry. Run Nginx origin-bypass, proxy-header spoofing, Swarm network, token audience, webhook replay,
points race, media privacy, backup restoration and deployment rollback tests.



7. Infrastructure and resilience gate
Choose provider/region, pilot versus HA target, Swarm manager/worker sizing, private connectivity from Nginx to
Swarm, origin protection, certificate ownership, DNS, PostgreSQL/Redis topology, RPO/RTO, backup retention,
monitoring and video provider. A one-VM Nginx deployment is a single point of failure unless an HA plan is
implemented or explicitly accepted for pilot. Do not label a minimal topology highly available.



8. Product, privacy and abuse gate
Approve qualified-view thresholds, deduplication windows, creator self-engagement rules, points formula, fraud
hold/reversal policy, creator verification, privacy notice, IP/device fraud-signal retention, deletion and audit
retention. These affect API behavior, schema constraints and security acceptance tests; no invented defaults are
accepted by this document.



9. Decision treatment and deferral rules
Each unresolved decision must have a unique ID, accountable owner, deadline/gate, alternatives, risk, dependency,
chosen disposition and written approval. A deferral is valid only if the affected feature is blocked from
implementation or the sponsor accepts a documented bounded pilot exception. Blanket approval of DOC-209 must
not be interpreted as approving every ADR or INF entry.



10. Stage 3 entry options
Option A — Full Stage 2 closure: all Stage-2-blocking decisions resolved, technical walkthrough passed and required
signatories approve. Option B — Conditional Stage 3 entry: permit repository setup, CI baseline, service skeletons,
container hardening and test scaffolding, but block authentication, engagement points, private transport and
production deployment until corresponding decisions are approved. Option C — Hold Stage 3 until decisions close.
Recommended option B if the sponsor authorizes it explicitly.



11. Verification and evidence plan
Maintain test IDs linked to TM-### threat IDs, DOC-206 controls, API operation IDs and service components. Record
test date, environment, version/digest, test operator, observed result, evidence link and remediation owner.
Failures create tracked issues. Before pilot, demonstrate restoration to an isolated environment, ingress bypass
prevention, Swarm control-plane isolation and ledger idempotency.
<PARSED TEXT FOR PAGE: 3 / 6>
12. Change control and baselines
Baseline versions DOC-201–208 v1.0 remain immutable references. Future changes require ADR amendment,
impact analysis on ERD/OpenAPI/security controls, version bump, reviewer approval and release notes. Changes to
Nginx placement, database ownership, financial boundaries or points eligibility are material changes requiring
sponsor/security review.



13. Final review disposition
Current assessment: 8 of 9 document baselines approved; DOC-209 ready for review. Stage 2 NOT YET CLOSED.
Recommended sign-off: approve DOC-209 as a review register with outstanding decisions tracked; separately decide
whether to grant conditional Stage 3 entry. Formal signatories and dates are intentionally blank.



14. Stage 2 gate criteria

G-01 — Architecture baselines
Criterion: DOC-201 through DOC-208 individually approved as design baselines

Assessment: PASS — user approval recorded

Gate: Stage 2 design

G-02 — Complete review package
Criterion: DOC-209 contains decision log, traceability, risks, responsibilities and sign-off

Assessment: READY FOR REVIEW

Gate: Stage 2 design

G-03 — Critical architecture decisions
Criterion: Authentication, private Nginx-to-Swarm transport, manager sizing, DB/DR, points rules, privacy, TLS HA
resolved or formally deferred

Assessment: BLOCKED — ADR open

Gate: Before unconditional Stage 2 closure

G-04 — Infrastructure commitments
Criterion: Provider, region, budget, topology, ports, backup retention and video provider chosen

Assessment: BLOCKED — INF open

Gate: Before affected implementation

G-05 — Security risk acceptance
Criterion: Security owner reviews all DOC-203 threats, controls and residual risks; no unowned critical risk

Assessment: PENDING SECURITY REVIEW

Gate: Before pilot
<PARSED TEXT FOR PAGE: 4 / 6>
G-06 — Security verification mapping
Criterion: DOC-206 controls assigned, tests/evidence planned, no controls represented as tested

Assessment: DESIGN BASELINE APPROVED; EXECUTION PENDING

Gate: Stage 3 onward

G-07 — Data and API consistency
Criterion: DOC-204 service ownership and DOC-205 operations mapped to DOC-201 service boundaries

Assessment: REQUIRES TECHNICAL WALKTHROUGH

Gate: Before service build

G-08 — Business-rule consistency
Criterion: Points are non-cash; no ad-event rewards; qualification thresholds and points formula approved

Assessment: PARTIAL — invariant accepted, parameters open

Gate: Before engagement implementation

G-09 — Deployment readiness
Criterion: Nginx separate VM; Swarm network restrictions; rollback and restore plans reviewed

Assessment: DESIGN ACCEPTED; PROVISIONING NOT DONE

Gate: Before staging/pilot

G-10 — Governance sign-off
Criterion: Sponsor, architecture lead and security lead explicitly sign with conditions and dates

Assessment: NOT SIGNED

Gate: Stage 2 gate



15. Open decisions — DOC-207
ADR-011 | Public gateway and internal service access | Proposed — needs approval | Due: Before implementation
of affected component

ADR-012 | Service-to-service identity | Proposed — needs approval | Due: Before implementation of affected
component

ADR-013 | Client authentication and sessions | Open — decision required | Due: Before Stage 2 final sign-off

ADR-014 | Nginx-to-Swarm private transport | Open — decision required | Due: Before Stage 2 final sign-off

ADR-015 | Swarm control-plane sizing and availability | Open — decision required | Due: Before Stage 2 final sign-
off

ADR-016 | PostgreSQL hosting and DR targets | Open — decision required | Due: Before Stage 2 final sign-off
<PARSED TEXT FOR PAGE: 5 / 6>
ADR-017 | Observability and audit pipeline | Proposed — needs approval | Due: Before implementation of affected
component

ADR-018 | Secrets, images and CI/CD controls | Proposed — needs approval | Due: Before implementation of
affected component

ADR-019 | Qualified view and points parameters | Open — business decision required | Due: Before Stage 2 final
sign-off

ADR-020 | Privacy retention and data residency | Open — legal/product decision required | Due: Before Stage 2
final sign-off

ADR-021 | Nginx high availability and TLS ownership | Open — decision required | Due: Before Stage 2 final sign-
off

ADR-022 | API versioning and event contracts | Proposed — needs approval | Due: Before implementation of
affected component



16. Open decisions — DOC-208
INF-01 | Pilot versus HA target and budget | OPEN

INF-02 | Hosting provider and region | OPEN

INF-03 | Nginx origin protection and private upstream | OPEN

INF-04 | Manager and worker count | OPEN

INF-05 | PostgreSQL topology and RPO RTO | OPEN

INF-06 | Redis hosting | OPEN

INF-07 | Workload identity and mTLS | OPEN

INF-08 | DNS ownership | OPEN

INF-09 | Observability stack | OPEN

INF-10 | Backup retention | OPEN

INF-11 | Video provider and egress | OPEN

INF-12 | CI/CD registry and deploy credentials | OPEN

INF-13 | Capacity and SLO | OPEN

INF-14 | Nginx high availability | OPEN
<PARSED TEXT FOR PAGE: 6 / 6>
17. Formal review and sign-off
Sponsor disposition (select): [ ] Approve DOC-209 review register only [ ] Authorize conditional Stage 3 entry [ ]
Grant full Stage 2 closure after blockers resolved [ ] Return for revision

Project sponsor: __________________________ Signature: ____________________ Date: __________

Architecture lead: __________________________ Signature: ____________________ Date: __________

Security lead: __________________________ Signature: ____________________ Date: __________

Platform/SRE lead: __________________________ Signature: ____________________ Date: __________

Product/privacy owner: __________________________ Signature: ____________________ Date: __________

Conditions, accepted risks and due dates: _______________________________________________________

Important: No signature is represented as completed. User approval of this review document does not imply
operational controls have passed.