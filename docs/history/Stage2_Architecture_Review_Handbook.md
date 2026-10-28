> Source: Stage2_Architecture_Review_Handbook.docx (text export; original formatting, formulas and embedded images are not included). Original review status is retained.

<PARSED TEXT FOR PAGE: 1 / 2>
STAGE 2 — ARCHITECTURE & THREAT
MODEL
Review handbook • Draft v0.1 • 28 October 2026 • Target window: 9–20 November 2026

Project: Liberian creator-content platform | Approved Stage 1 MVP baseline | Architecture approval
pending



Purpose
Turn approved requirements into a buildable security-first design: modular Django, Flutter mobile,
Django templates web, private PostgreSQL, Redis/Celery and managed media delivery.



MVP boundary
R1: accounts, creators, original content, playback, server-qualified engagement, non-cash points,
moderation and audit. R2 business verification; R3 ticketing; R4 revenue settlement and payouts are
deferred.



Core security invariants
All authorization and points calculations are server-side. Engagement events are idempotent and
untrusted. Points entries are append-only. Ad interactions never award points. Financial ledger is
separate and disabled in R1.



Documentation set
DOC-201 architecture; DOC-202 editable Mermaid diagrams; DOC-203 STRIDE register; DOC-204 ERD
and SQL; DOC-205 OpenAPI; DOC-206 security verification; DOC-207 ADRs; DOC-208 deployment;
DOC-209 stage gate.



Review responsibilities
Product owner validates business scope and assumptions; technical lead validates implementability
and data/API consistency; security reviewer validates threats and evidence plans.



Critical open questions
Qualified-view thresholds and points formula; creator verification; data retention; video vendor;
web/mobile authentication design; hosting budget; legal and publisher policy review.
<PARSED TEXT FOR PAGE: 2 / 2>
Approval criteria
All critical threats mitigated by design, no client-controlled points, documented auth decision,
complete interface schemas, control mappings, and approved ADRs. Stage 2 is not complete until
sign-off.



Next action
Review the files in order and resolve architecture-blocking decisions. After Stage 2 approval, create
Django/Flutter repos, CI/CD, staging and secure identity under Stage 3.



Stage 2 approval
Product owner: __________________ Technical lead: __________________ Security reviewer:
__________________

Decision: PENDING     Date: ____________   Version approved: ____________