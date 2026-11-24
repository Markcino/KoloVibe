# Business module (R2) — Phase 6A design package

**Status: see the approval record.** The owner approved all 26 original recommendations as written on 24 November 2026 and decided DR-BZ-21 (mobile only; no public website, no business web portal) formally in Phase 6A reconciliation; the policy values and copy the approval cannot supply are listed in the [approval record](BIZ-Owner_Approval_Record_2026-11-24.md). The backend was built behind closed flags in Phase 6B (merged in PR #219); nothing is deployed and production is NO-GO. File names still say PROPOSED because their wording has not been rewritten. Business discovery is **outside Release 1** (DEC-001); this package is R2 design only. No feature code, migrations, AWS or staging changes are part of it.

## Approved versus proposed

| Approved today | Proposed by this package |
| --- | --- |
| DEC-001: business discovery, ticketing and payouts are out of R1 (scope only). ADR-001 microservices. ADR-010 sequencing. ADR-013 identity design. | Everything in the table below, including the Business service boundary, the authorization model and all requirement wording |

## Deliverables

| # | Deliverable | File |
| --- | --- | --- |
| 1 | Requirements and scope (proposed content for DOC-020) | [DOC-020_Business_Requirements_and_Scope_PROPOSED.md](../../requirements/DOC-020_Business_Requirements_and_Scope_PROPOSED.md) |
| 2 | Architecture decision record | [ADR-BIZ-001](../../adr/ADR-BIZ-001_Business_Bounded_Context_PROPOSED.md) |
| 3 | Service architecture | [BIZ-ARCH_Service_Architecture_PROPOSED.md](BIZ-ARCH_Service_Architecture_PROPOSED.md) |
| 4 | Database ERD | [BIZ-ERD_PROPOSED.md](BIZ-ERD_PROPOSED.md) |
| 5 | OpenAPI contract proposal (50 operations) | [BIZ-OpenAPI_3_1_PROPOSAL.yaml](BIZ-OpenAPI_3_1_PROPOSAL.yaml) |
| 6 | RBAC and object-level authorization matrix | [BIZ-RBAC_and_Object_Authorization_Matrix_PROPOSED.md](../../security/phase6/BIZ-RBAC_and_Object_Authorization_Matrix_PROPOSED.md) |
| 7 | STRIDE threat model | [BIZ-STRIDE_Threat_Model_PROPOSED.md](../../security/phase6/BIZ-STRIDE_Threat_Model_PROPOSED.md) |
| 8 | Data privacy and retention requirements | [business-data-privacy-and-retention-PROPOSED.md](../../privacy/business-data-privacy-and-retention-PROPOSED.md) |
| 9 | Dependency diagrams | [BIZ-Dependencies_PROPOSED.md](BIZ-Dependencies_PROPOSED.md) |
| 10 | Implementation backlog and Phase 6B prerequisites | [BIZ-Implementation_Backlog_PROPOSED.md](../../engineering/phase6/BIZ-Implementation_Backlog_PROPOSED.md) |
| 11 | Acceptance criteria | [BIZ-Acceptance_Criteria_PROPOSED.md](../../engineering/phase6/BIZ-Acceptance_Criteria_PROPOSED.md) |
| 12 | Owner decision register (26 original decisions approved as written; DR-BZ-21 decided formally; DR-BZ-27 and 28 open) | [BIZ-Owner_Decision_Register_PROPOSED.md](BIZ-Owner_Decision_Register_PROPOSED.md) |
| 13 | **Client architecture (DR-BZ-21): Flutter for owners, staff and customers; console for administrators and moderators only** | [BIZ-Client_Architecture_DR-BZ-21.md](BIZ-Client_Architecture_DR-BZ-21.md) |
| 14 | Architecture validation against the code, contracts and infrastructure (Phase 6A) | [BIZ-Architecture_Validation_PHASE6A.md](BIZ-Architecture_Validation_PHASE6A.md) |
| 15 | Requirements reconciliation: approval state, as-built state, what the owner owes | [BIZ-Requirements_Reconciliation_PHASE6A.md](../../requirements/BIZ-Requirements_Reconciliation_PHASE6A.md) |
| 16 | Security design completion: staff model, verification transitions, fraud controls, evidence, retention | [BIZ-Security_Design_Completion_PHASE6A.md](../../security/phase6/BIZ-Security_Design_Completion_PHASE6A.md) |
| 17 | API security matrix by client surface (57 operations, from DOC-205) | [BIZ-API_Security_Matrix_PHASE6A.md](../../security/phase6/BIZ-API_Security_Matrix_PHASE6A.md) |
| 18 | **Exact owner decisions required (gates A, B, C)** | [BIZ-Owner_Decisions_Required_PHASE6A.md](BIZ-Owner_Decisions_Required_PHASE6A.md) |

## Reading order for the approver

0. [Owner decisions required](BIZ-Owner_Decisions_Required_PHASE6A.md) — the short list.
1. Decision register — what only the owner can decide.
2. ADR-BIZ-001 — the three structural decisions (service boundary, membership-based authorization, moderation placement).
3. Requirements — scope, exclusions, what is reused.
4. Authorization matrix and STRIDE — the security argument.
5. The rest as needed.

## Conventions

IDs: `BZ-R-nnn` requirements, `BZ-AZ-nn` authorization rows (one per OpenAPI operation), `BZ-NT-nn` negative tests, `BZ-T-nnn` threats, `AC-xxx-nnn` acceptance criteria, `DR-BZ-nn` open decisions, `BZ-B-nnn` backlog items, `P6B-nn` prerequisites. Policy-pending requirements name the decision that gates them; none of those policies is decided or implied.
