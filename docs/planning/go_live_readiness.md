# Go-live readiness by stage

**Updated 23 November 2026 using GitHub publication and owner-supplied AWS terminal/UAT evidence. Production is NO-GO.** This page indexes the open work that must close before a controlled pilot go-live. It links to source documents rather than restating them. Release 1 scope is unchanged (DEC-001); deferred: live streaming, business discovery, ticketing and cash payouts.

The [seven-stage plan](liberian_platform_seven_stage_development_plan.md) is the reference. Go-live depends on Stages 1–6; Stage 7 (operations and improvement) starts after the go/no-go. Dates in that plan are targets, not commitments.

**Tracking:** [#169 Go-live readiness tracker](https://github.com/Markcino/KoloVibe/issues/169). Each stage has a GitHub milestone and a `stage-N-…` label; release blockers carry `go-live-blocker`, owner decisions carry `needs-decision`. Update this page and the issues together from verified evidence only.

| Stage | Gate | Evidence-based state | Open issues |
| --- | --- | --- | --- |
| 1 Requirements | Approved PRD, SRS, MVP scope | Scope approved (DEC-001); #133 methods owner-approved; PRD/SRS detail acceptance, research, traceability and sign-off remain pending | #133–#137 |
| 2 Architecture | Reviewed SAD, ERD, API, threat model | Design baselines approved; critical decisions, security risk review and sign-off open (G-03, G-04, G-05, G-07, G-10) | #138–#141 |
| 3 Foundation | Secure identity and CI/CD | Owner-declared complete; main protection, scanner exceptions, restore drill, monitoring and deployed credentials still open | #142–#147 |
| 4 Development | Feature-complete pilot candidate | In progress; **v0.357.1** has eight APIs, six jobs, media worker and web deployed on AWS (16/16). Admin/moderator positive UAT passed; real R2/FFmpeg/RabbitMQ, points and 108-screen mobile parity/feature journeys remain unaccepted | #100, #148–#154 |
| 5 Verification | ASVS/MASVS evidence, release readiness | In parallel: v0.357.1 passed 6/6 public smoke probes and owner-reported 6/6 privileged dashboard UAT. **26/0/19** is a historical v0.187.2-only matrix. Negative authorization, device/security/recovery tests and the **26 runtime-owned tables/8 sequences** privilege finding remain open | #155–#162 |
| 6 Pilot | Limited release and go/no-go report | Not started; DOC-018 pilot plan not written | #163–#168 |

## Alignment notes

- **Stage 1 document control (#133).** [Decision brief](../requirements/S1-133_Document_Control_Decision_Brief.md), [source inventory](../requirements/document_register.csv), [detail review manifest](../requirements/detail_baseline_review.csv), [DOC-003 research protocol](../requirements/DOC-003_Stakeholder_Research_Proposed.md), and [DOC-023 change control](../requirements/DOC-023_Change_Control_Proposed.md). [Four methods approved by the owner](https://github.com/Markcino/KoloVibe/issues/133#issuecomment-7076320307) on 2026-11-22; actual detail decisions and research remain pending. #133 and #169 remain unchecked.
- **Document sources of truth.** Delivery status: [R1 application tracker](../engineering/R1_Application_Tracker.md). Current release and evidence boundary: [23 November AWS reconciliation](../operations/R1_AWS_Staging_Reconciliation_2026-11-23.md); topology: [AWS as-built](../architecture/R1_AWS_Staging_As_Built_2026-11-23.md). Historical gate snapshot: [14 November consolidated gates](../operations/R1_Consolidated_Release_Gates_2026-11-14.md), still awaiting a full refreshed #161 gate matrix.
- **Known inconsistencies, tracked rather than silently edited:** document register IDs versus `docs/requirements/DOC-00x` files (#133); Oracle-era / dedicated Nginx / Redis / managed-video wording in DOC-201/202/207/208/209 (#138). The as-built addendum documents **AWS two-VM host Nginx, RabbitMQ and private R2 + FFmpeg VOD** without rewriting historical approved artifacts. ADR-008 and ADR-019 record the owner's OD-07 and DEC-003 decisions.
- **Branch protection.** `main` now has an active ruleset that blocks deletion and force-push only; no required checks or reviews (#142).
- **Time-bound risk.** The OpenSSL scanner exception expires 2026-11-28 UTC (#143).
