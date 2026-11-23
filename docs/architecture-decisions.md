# Architecture decisions

This file is an index, not a second decision register.

- Current Stage 3 blockers: [OD-01–OD-09](engineering/Stage3_Open_Decisions.csv).
- Formal ADR status, rationale and acceptance evidence: [DOC-207 ADR register](architecture/DOC-207_ADR_Register.csv) and [open decision log](architecture/DOC-207_Open_Decision_Log.csv).
- Infrastructure-specific open items: [DOC-208 architecture and network registers](architecture/).

ADR-001–ADR-010 were originally accepted inherited baselines; ADR-003 and ADR-007 now have user-confirmed implementation amendments dated 2026-11-01. Do not treat those identifiers as the current open-decision list. Do not enable a dependent feature or deployment until its applicable decision and acceptance evidence are approved.

## 2026-11-01 implementation reconciliation

- [ADR-003 / ADR-007 — RabbitMQ broker and VM1 host-level Nginx](architecture/ADR-003_007_Implementation_Reconciliation_2026-11-01.md) records the architecture changes, risks and verification gates.
- [ADR-013 — Django-native identity authority selection](architecture/ADR-013_Django_Native_Identity_Selection_2026-11-01.md) records the owner-confirmed provider choice.
- [ADR-013 v1.0 session and MFA design](architecture/ADR-013_Client_Authentication_and_Session_Security_v1.0_APPROVED.md), the [DOC-205 design addendum](architecture/ADR-013_DOC-205_Contract_Design_Addendum_v1.0_APPROVED.md) and [DOC-206 verification plan](architecture/ADR-013_DOC-206_Verification_Plan_v1.0_APPROVED.csv) were owner-approved on 1 November. The remaining executable contract, implementation and verification are open.
- These implementation amendments supersede the corresponding Redis and dedicated-third-VM wording in historical DOC-201/202/208/209 drafts; historical source files are preserved for traceability.
- Infrastructure acceptance is tracked separately for [AWS staging](operations/AWS_Staging_Deployment_Verification_2026-11-10.md) and [Oracle Cloud](operations/Deployment_Verification_2026-11-03.md).

## AWS staging as-built — 23 November 2026

- [Current AWS implementation and architecture drift](architecture/R1_AWS_Staging_As_Built_2026-11-23.md) describes **AWS VM1 (Swarm manager and host Nginx), VM2 (worker), Cloudflare Tunnel, eight backend services, six jobs, web and FFmpeg media worker**. RabbitMQ replaces the old Redis broker assumption; **private R2 + FFmpeg VOD** replaces the former managed-video proposal for R1. Public production ingress/security acceptance remains open.
- [v0.357.1 release and verified scope](operations/R1_AWS_Staging_Reconciliation_2026-11-23.md) records operator-reported **16/16 image updates**, **6/6 public smoke probes** and owner-reported **6/6 authenticated administrator/reviewer tests**. Neither design nor deployment certification extends to all mobile/R1 features.
- The historical **Oracle VM1** phrasing in ADR-003 is a dated accepted implementation amendment, **not** the current cloud provider. Original DOC-208 diagrams describing dedicated Nginx, multi-manager HA, Redis and managed video are historical design snapshots; formal revisions to DOC-201/202/207/208/209 and any unresolved decision require documented owner review rather than unapproved retroactive edits.
- A 23 November read-only PostgreSQL catalog report found **26 runtime-role-owned tables and eight sequences**. Privilege remediation, backup/restore, operator controls and negative authorization evidence remain **open**; see the release reconciliation.
