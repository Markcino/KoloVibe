# Architecture decisions

This file is an index, not a second decision register.

- Current Stage 3 blockers: [OD-01–OD-09](engineering/Stage3_Open_Decisions.csv).
- Formal ADR status, rationale and acceptance evidence: [DOC-207 ADR register](architecture/DOC-207_ADR_Register.csv) and [open decision log](architecture/DOC-207_Open_Decision_Log.csv).
- Infrastructure-specific open items: [DOC-208 architecture and network registers](architecture/).

ADR-001–ADR-010 were originally accepted inherited baselines; ADR-003 and ADR-007 now have user-confirmed implementation amendments dated 2026-11-01. Do not treat those identifiers as the current open-decision list. Do not enable a dependent feature or deployment until its applicable decision and acceptance evidence are approved.

## 2026-11-01 implementation reconciliation

- [ADR-003 / ADR-007 — RabbitMQ broker and VM1 host-level Nginx](architecture/ADR-003_007_Implementation_Reconciliation_2026-11-01.md) records the architecture changes, risks and verification gates.
- These implementation amendments supersede the corresponding Redis and dedicated-third-VM wording in historical DOC-201/202/208/209 drafts; historical source files are preserved for traceability.
- Cloudflare Tunnel, Nginx origin, private upstream transport, Swarm quorum, RabbitMQ durability, database disaster recovery and security controls must be verified. No deployment readiness or HA is claimed.
