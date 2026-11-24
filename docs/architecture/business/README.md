# Business module (R2) — Phase 6A design package

**Status: PROPOSED — for architectural approval. Nothing here is approved or implemented.** Phase 6A, 24 November 2026. Business discovery is **outside Release 1** (DEC-001); this package is R2 design only. No feature code, migrations, AWS or staging changes are part of it.

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
| 12 | Owner decision register (26 open decisions) | [BIZ-Owner_Decision_Register_PROPOSED.md](BIZ-Owner_Decision_Register_PROPOSED.md) |

## Reading order for the approver

1. Decision register — what only the owner can decide.
2. ADR-BIZ-001 — the three structural decisions (service boundary, membership-based authorization, moderation placement).
3. Requirements — scope, exclusions, what is reused.
4. Authorization matrix and STRIDE — the security argument.
5. The rest as needed.

## Conventions

IDs: `BZ-R-nnn` requirements, `BZ-AZ-nn` authorization rows (one per OpenAPI operation), `BZ-NT-nn` negative tests, `BZ-T-nnn` threats, `AC-xxx-nnn` acceptance criteria, `DR-BZ-nn` open decisions, `BZ-B-nnn` backlog items, `P6B-nn` prerequisites. Policy-pending requirements name the decision that gates them; none of those policies is decided or implied.
