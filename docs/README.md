# Documentation index

**This is the authoritative documentation index (Phase 1, 27 November 2026).** Each subject has exactly one canonical source. Other documents on the same subject are supporting detail or archived evidence; when they conflict, the canonical source wins. Superseded documents are listed in the [archive register](archive/ARCHIVE_REGISTER.md) and kept in place. Link to sources instead of copying requirements, decisions or status into new summaries.

## Governance (read first)

| Subject | Canonical source |
| --- | --- |
| Mandate and phase rules | [Full application mandate, 27 November](governance/Full_Application_Mandate_2026-11-27.md) |
| Where execution stands, phase plan, carry-over | [Phase execution tracker](governance/PHASE_EXECUTION_TRACKER.md) and GitHub issue [#301](https://github.com/Markcino/KoloVibe/issues/301) |
| Agent instructions | [`AGENTS.md`](../AGENTS.md) (`CLAUDE.md` and `.github/CLAUDE.md` point to it) |
| Work and defect tracking | GitHub Issues, Phase 2 to 11 milestones |
| Approval gates and open decisions | [Governance gate register](governance/phase1/PHASE-01_Governance_Gate_Register.md), pointing to the source decision registers below |

## Canonical source per subject

| Subject | Canonical source | Status | Supporting detail |
| --- | --- | --- | --- |
| Full-product scope and requirement sets (PRD and SRS index) | [FP-000](requirements/FP-000_Full_Product_Requirements_Baseline.md) | Active index | [Scope baseline](governance/phase1/PHASE-01_Full_Product_Scope_Baseline.md) |
| Detailed requirements, core platform | [PRD v0.2](requirements/platform_PRD_v0_2_scope_approved.md), [SRS v0.2](requirements/platform_SRS_v0_2_scope_approved.md) | Scope approved, detail draft (#133); R1 deferral statements archived | [DOC-006 points rules](requirements/DOC-006_Engagement_Points_Rules_DRAFT.md) |
| Detailed requirements, Business | [BIZ reconciliation](requirements/BIZ-Requirements_Reconciliation_PHASE6A.md) | Design approved (#218) | [DOC-020](requirements/DOC-020_Business_Requirements_and_Scope_PROPOSED.md), [Business package](architecture/business/README.md) |
| Detailed requirements, Events | [EVT requirements](requirements/EVT-Requirements_PRD_SRS_PROPOSED.md) | Scope approved (H); detail PROPOSED | [Events package](architecture/events/README.md) |
| Detailed requirements, Advertising | [AD requirements](requirements/AD-Requirements_PRD_SRS_PROPOSED.md) | Scope approved (I); detail PROPOSED | [Advertising package](architecture/advertising/README.md) |
| Detailed requirements, Finance | [FIN requirements](requirements/FIN-Requirements_PRD_SRS_PROPOSED.md) | Scope approved (J, sandbox); detail PROPOSED | [Finance package](architecture/finance/README.md) |
| Detailed requirements, notifications | [FP-NT](requirements/FP-NT_Notifications_Requirements_PROPOSED.md) | PROPOSED (27 Nov); placement approved (GD-03) | Identity notification module, #309 |
| Detailed requirements, payments and payouts | [FP-PAY](requirements/FP-PAY_Payments_and_Payouts_Requirements_PROPOSED.md) | PROPOSED (27 Nov); sandbox only | FIN F5, EVT E5, AD A7 |
| Detailed requirements, Google mobile ads | [FP-GA](requirements/FP-GA_Google_Mobile_Ads_Requirements_PROPOSED.md) | PROPOSED (27 Nov); test units only | AD requirements |
| Detailed requirements, store distribution | [FP-DST](requirements/FP-DST_Store_Distribution_Requirements_PROPOSED.md) | PROPOSED (27 Nov) | [Policies page](../apps/policies/README.md) |
| Detailed requirements, comments | [FP-CM](requirements/FP-CM_Comments_Requirements_PROPOSED.md) | PROPOSED (27 Nov); scope approved (GD-07) | Moderation reports |
| Feature traceability | [Feature traceability matrix](governance/phase1/PHASE-01_Feature_Traceability_Matrix.csv) | Active | [DOC-007](requirements/DOC-007_Traceability_and_Signoff_DRAFT.md) (sign-off record, #134) |
| Owner decisions | [Owner decisions A to J](planning/Owner_Decisions_A-J_2026-11-25.md) | Approved | [Gate register](governance/phase1/PHASE-01_Governance_Gate_Register.md) |
| Open decisions | [DOC-209 consolidated open decisions](architecture/DOC-209_Consolidated_Open_Decisions.csv) plus the per-area decision documents | Active | Business, Events, Advertising and Finance decision documents in `architecture/` |
| Software architecture and ADRs | [DOC-207 ADR register](architecture/DOC-207_ADR_Register.csv) | Mixed (per ADR) | [ADR files](architecture/), [`adr/`](adr/), [architecture decision summary](architecture-decisions.md), [DOC-208 diagram](architecture/DOC-208_Architecture.mmd) |
| Service boundaries and ownership | [Scope baseline, section 4](governance/phase1/PHASE-01_Full_Product_Scope_Baseline.md#4-service-boundaries) | Active; new contexts wait on GD-01 to GD-03 | [Repository layout](engineering/repository-layout.md) |
| As-built infrastructure blueprint | [AWS staging as-built](architecture/R1_AWS_Staging_As_Built_2026-11-23.md) | Historical snapshot until re-verified | [`infra/`](../infra/README.md), [network ports](architecture/DOC-208_Network_Ports.csv) |
| ERD and database schema | Django migrations in each `services/*/service/migrations/` (authoritative for built services); [DOC-204 ERD](architecture/DOC-204_ERD.mmd) | ERD is illustrative and needs reconciliation (#141) | Per-area ERDs in `architecture/business`, `events`, `advertising`, `finance` |
| API contracts | [DOC-205 OpenAPI](architecture/DOC-205_OpenAPI_3_1_DRAFT.yaml) | DRAFT; matches the Gateway path for path (Phase 1 audit); promotion tracked in #305 | Per-area API proposals |
| Event contracts | Each service's `events.py` | No catalogue yet (#305) | — |
| RBAC and authorization | [DOC-004 RBAC matrix](requirements/DOC-004_RBAC_Matrix_DRAFT.md) | Draft | Console route-security matrix test; Business authorization matrix |
| User journeys | [DOC-005](requirements/DOC-005_User_Journeys_DRAFT.md) | Draft | Per-area journey documents |
| Figma screen inventory | [Mobile design coverage register](mobile-design-coverage.md); Figma file [`ANaV0jnwjZ0LEcByTc98HP`](https://www.figma.com/design/ANaV0jnwjZ0LEcByTc98HP/KoloVibe?node-id=0-1) | 108 approved frames; new areas undesigned (#306) | [Parity](mobile-design-parity.md), [R1 adaptations](mobile-design-r1-adaptations.md), [Business screen inventory](architecture/business/BIZ-Flutter_Screen_Inventory_PROPOSED.md), [asset hashes](mobile-asset-manifest.json) |
| Security requirements and threat model | [DOC-203 STRIDE register](architecture/DOC-203_STRIDE_Risk_Register.csv) and [DOC-206 control verification matrix](architecture/DOC-206_Control_Verification_Matrix.csv) | Review open (#140) | [Security review](security/SECURITY-REVIEW.md), `security/phase*` |
| Privacy requirements | [Account erasure plan](privacy/account-erasure-plan-PROPOSED.md) under Decision C | Mechanism approved; values open (#136) | Other files in [`privacy/`](privacy/) |
| Deployment and operations | [Deployment and rollback runbook](operations/R1_Deployment_and_Rollback_Runbook_2026-11-14.md) | Active for staging | [`operations/`](operations/) dated records |
| Current staging evidence | [27 November read-only check](operations/R1_AWS_Staging_Readonly_Check_2026-11-27.md) | Current for v0.542.1 (69 commits behind `main`) | [26 November staging verification](operations/R1_AWS_Staging_Verification_2026-11-26.md), release reconciliation records |
| Testing strategy and acceptance criteria | [Phase execution tracker](governance/PHASE_EXECUTION_TRACKER.md) phase exit criteria; mandate section 10 | Active; the full test strategy is a Phase 10 deliverable | Phase 12 matrix (historical) |
| Engineering standards | [Engineering standards](engineering-standards.md) | Active | [Dependency and security checks](engineering/dependency-and-security.md), [FND-01](engineering/FND-01_repository_governance.md) |

## Document control

Draft, proposed, approved and archived states stay distinct; "scope approved" does not approve every detail. Git holds readable text editions of some Word and Excel sources without their original formatting. When a scope, architecture or security decision changes, update its canonical source and this index in the same pull request. Do not copy credentials, threat details or personal data into documentation.
