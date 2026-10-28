> Source: Stage2_Architecture_Change_Record_v0_2.docx (text export; original formatting, formulas and embedded images are not included). Original review status is retained.

<PARSED TEXT FOR PAGE: 1 / 1>
Stage 2 — Architecture Change Record
CR-ARCH-001 | Version 0.2 | 28 October 2026 | Status: Revised draft for review



Approved direction
   Replace Django modular monolith with independently deployable Django/DRF microservices.
   Use Docker Swarm for application deployment.
   Keep Nginx as a separate reverse proxy, not inside Django application containers.
   Retain Flutter mobile, Django Templates web, PostgreSQL, Redis/Celery, managed video delivery and
    Stage 1 MVP scope.



Proposed service boundaries
Web frontend, identity, content, engagement, points, moderation and audit. Future business, events,
revenue and payouts remain disabled until separately approved.



Additional risks
   Inter-service authentication, authorization and token propagation.
   Partial failure, event duplication, outbox delivery and cross-service consistency.
   Docker Swarm manager quorum and overlay network exposure.
   Separate Nginx high availability, private upstream connectivity and TLS ownership.
   Increased operational cost and integration/testing workload.



Unresolved questions
Confirm whether Nginx is on its own server/VM or an independent Swarm service; Swarm node count;
PostgreSQL hosting; internal workload identity; budget.



Impact on Stage 2 artifacts
DOC-201/202/207/208 revised. Original ERD, OpenAPI, threat register and security matrix require
service-boundary refactoring before Stage 2 approval. No implementation or deployment has occurred.