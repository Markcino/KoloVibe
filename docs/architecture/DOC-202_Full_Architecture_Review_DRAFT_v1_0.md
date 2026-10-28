> Source: DOC-202_Full_Architecture_Review_DRAFT_v1_0.docx (text export; formatting and embedded images are not included). Original status is retained.

<PARSED TEXT FOR PAGE: 1 / 4>
STAGE 2 / ARCHITECTURE GOVERNANCE / DOC-202




DOC-202 | Architecture & Data-Flow
Diagrams
Full review draft v1.0 • 28 October 2026 • Based on approved DOC-201


Architecture baseline
Dedicated Nginx VM outside Docker Swarm; independent Django/DRF microservices in Swarm;
Flutter clients and Django-template web frontend; private database and queue layers; Cloudflare
video service. R1 excludes real-money payouts, ticketing and verified-business modules.



Diagram catalog and implementation review notes

DFD-01 — System context and external trust boundaries
External requests enter via Cloudflare, then the dedicated Nginx VM. Only approved public routes
are forwarded into the Swarm cluster. Provider webhooks require signature validation and replay
protection.

Editable source: 01_context.mmd; Mermaid source is also embedded in
DOC-202_Full_Architecture_Diagrams_v1_0.md.

Verification: review trust boundary, route authorization, failure modes, secrets and observability for
this flow.

DFD-02 — Physical deployment and network zones
Node counts are deployment options, not confirmed inventory. Three managers are recommended
for manager quorum in production HA. Never expose PostgreSQL, Redis, or Docker daemon
publicly.

Editable source: 02_physical.mmd; Mermaid source is also embedded in
DOC-202_Full_Architecture_Diagrams_v1_0.md.

Verification: review trust boundary, route authorization, failure modes, secrets and observability for
this flow.

DFD-03 — Service ownership and communications
Logical ownership is per service. A shared physical PostgreSQL instance may be used initially with
separate databases or schemas, separate credentials and no cross-service write access.

Editable source: 03_microservices.mmd; Mermaid source is also embedded in
DOC-202_Full_Architecture_Diagrams_v1_0.md.




FULL REVIEW DRAFT v1.0 • Not approved for production
<PARSED TEXT FOR PAGE: 2 / 4>
STAGE 2 / ARCHITECTURE GOVERNANCE / DOC-202



Verification: review trust boundary, route authorization, failure modes, secrets and observability for
this flow.

DFD-04 — Identity, authorization and service trust
Browser sessions should use secure HttpOnly cookies and CSRF protection; mobile access may use
short-lived tokens and secure refresh-token rotation. Final identity protocol and key management
require DOC-205/207 decisions.

Editable source: 04_auth.mmd; Mermaid source is also embedded in
DOC-202_Full_Architecture_Diagrams_v1_0.md.

Verification: review trust boundary, route authorization, failure modes, secrets and observability for
this flow.

DFD-05 — Video upload, processing and publication
Untrusted uploads never become publicly discoverable until processing, ownership verification, and
moderation checks pass. Avoid sending raw video through Nginx/Django unless a fallback is
explicitly designed.

Editable source: 05_upload.mmd; Mermaid source is also embedded in
DOC-202_Full_Architecture_Diagrams_v1_0.md.

Verification: review trust boundary, route authorization, failure modes, secrets and observability for
this flow.

DFD-06 — Playback authorization and telemetry
Client telemetry is untrusted. Playback authorization, eligibility windows, device/session abuse
signals, and independent server checks are required; exact qualified-view thresholds remain an
open business decision.

Editable source: 06_playback.mmd; Mermaid source is also embedded in
DOC-202_Full_Architecture_Diagrams_v1_0.md.

Verification: review trust boundary, route authorization, failure modes, secrets and observability for
this flow.

DFD-07 — Qualified engagement and non-cash points ledger
Ledger rules must remain server-owned, auditable and replay-safe. Pending points formulas and
qualification criteria must be resolved before enabling awards. No payout functionality in Release 1.

Editable source: 07_engagement.mmd; Mermaid source is also embedded in
DOC-202_Full_Architecture_Diagrams_v1_0.md.

Verification: review trust boundary, route authorization, failure modes, secrets and observability for
this flow.




FULL REVIEW DRAFT v1.0 • Not approved for production
<PARSED TEXT FOR PAGE: 3 / 4>
STAGE 2 / ARCHITECTURE GOVERNANCE / DOC-202



DFD-08 — Moderation and appeal lifecycle
Moderation decisions require role checks, reason codes, timestamps and audit trails. Content
availability and engagement eligibility must react consistently to takedowns and reversals.

Editable source: 08_moderation.mmd; Mermaid source is also embedded in
DOC-202_Full_Architecture_Diagrams_v1_0.md.

Verification: review trust boundary, route authorization, failure modes, secrets and observability for
this flow.

DFD-09 — Asynchronous reliability and recovery
This is an at-least-once delivery model with idempotent consumers, not exactly-once delivery.
Retries and dead-letter processing require monitoring and access control.

Editable source: 09_failure.mmd; Mermaid source is also embedded in
DOC-202_Full_Architecture_Diagrams_v1_0.md.

Verification: review trust boundary, route authorization, failure modes, secrets and observability for
this flow.

DFD-10 — Swarm rollout and rollback
Schema changes must be backward-compatible across rolling updates. Database rollback is not
assumed; use expand/migrate/contract and tested recovery procedures.

Editable source: 10_deploy.mmd; Mermaid source is also embedded in
DOC-202_Full_Architecture_Diagrams_v1_0.md.

Verification: review trust boundary, route authorization, failure modes, secrets and observability for
this flow.

DFD-11 — Security trust zones and permitted flows
Port numbers are reference defaults and must be validated against actual Swarm overlay
encryption, private networking and chosen reverse-proxy implementation. Docker published ports
may bypass host firewall assumptions; test actual rules.

Editable source: 11_security.mmd; Mermaid source is also embedded in
DOC-202_Full_Architecture_Diagrams_v1_0.md.

Verification: review trust boundary, route authorization, failure modes, secrets and observability for
this flow.

DFD-12 — Audit, metrics and operational telemetry
Correlate requests across services using non-sensitive trace IDs. Mask tokens and personal
information. Audit trails require retention, tamper resistance and access policies to be decided.

Editable source: 12_observability.mmd; Mermaid source is also embedded in
DOC-202_Full_Architecture_Diagrams_v1_0.md.




FULL REVIEW DRAFT v1.0 • Not approved for production
<PARSED TEXT FOR PAGE: 4 / 4>
STAGE 2 / ARCHITECTURE GOVERNANCE / DOC-202



Verification: review trust boundary, route authorization, failure modes, secrets and observability for
this flow.



Open decisions and sign-off gate
   **INF-01:** Confirm single-node pilot versus three-manager production quorum and worker
    count; diagrams show options rather than purchased infrastructure.
   **INF-02:** Confirm Nginx-to-Swarm private connectivity (VPN, private VLAN or dedicated
    private network), routing endpoint and upstream mTLS feasibility.
   **INF-03:** Confirm Cloudflare TLS mode, origin authentication, proxy header allowlist and
    client-IP trust chain.
   **INF-04:** Confirm PostgreSQL topology, backup location, replication, encryption, RPO/RTO
    and service credential isolation.
   **INF-05:** Confirm broker technology and durable queue/outbox operational policy; Redis
    alone is not a guarantee of durable event delivery.
   **SEC-01:** Complete threat model (DOC-203) for each crossing; approve secrets management,
    identity issuer, service-to-service authentication and logging retention.
   **BIZ-01:** Finalize qualified-view rules and non-cash points calculation before awarding
    points.
   **OPS-01:** Validate firewall rules from the actual Nginx VM and all Swarm hosts, including
    published port exposure, node failover and rollback.
   **OPS-02:** Test restore, service degradation, queue replay, moderation takedown and ledger
    reversals.



Release scope and approval
Only R1 creator-content capabilities are in scope. DOC-202 is a full review draft and does not
supersede approved DOC-201 or authorize production deployment. Reviewer signature:
___________________ Date: __________




FULL REVIEW DRAFT v1.0 • Not approved for production