# Documentation

Use the controlled source documents below. Link to them instead of copying requirements, decisions or delivery status into new summaries.

## Product and architecture

- [DEC-001 and document register](requirements/platform_documentation_register_and_DEC001.md) — canonical Release 1 scope decision.
- [PRD](requirements/platform_PRD_v0_2_scope_approved.md) and [SRS](requirements/platform_SRS_v0_2_scope_approved.md) — detailed requirements remain drafts; only the Release 1 scope is approved.
- [Architecture references](architecture/) — data model, draft API, architecture, risks, controls and open decisions.
- [AWS as-built architecture reconciliation · 23 November](architecture/R1_AWS_Staging_As_Built_2026-11-23.md) — current staging topology (AWS two VMs, host Nginx, RabbitMQ, R2/FFmpeg), architecture drift and security holds; historical Oracle/DOC-208 snapshots remain preserved.
- [Business module (R2) Phase 6A design package](architecture/business/README.md) — **design approved by the owner (PR #218 merged); Phase 6B backend implemented locally behind closed flags in a separate pull request, not deployed.** Requirements, ADR, architecture, ERD, API proposal, authorization matrix, STRIDE, privacy, backlog, acceptance criteria and 26 open owner decisions. Business discovery remains outside R1 (DEC-001).
- [Architecture decision summary](architecture-decisions.md) — index to decisions; the registers in `architecture/` remain authoritative. The owner approved the [ADR-013 v1.0 security design](architecture/ADR-013_Client_Authentication_and_Session_Security_v1.0_APPROVED.md), covering Django-native client identity, sessions and privileged MFA. Implementation and verification remain open.

## Delivery and engineering

- [Go-live readiness by stage](planning/go_live_readiness.md) — Stages 1–6 open work, linked to the GitHub tracker, milestones and labels. Production remains NO-GO.
- [Current Stage 3 status](engineering/Stage3_Current_Status.md) and [implementation tracker](engineering/Stage3_Implementation_Tracker.csv) — update together from verified evidence.
- [Current AWS staging reconciliation · 23 November](operations/R1_AWS_Staging_Reconciliation_2026-11-23.md) — **v0.357.1**, operator-verified 16/16 service rollout, 6/6 HTTPS probes, owner-reported 6/6 privileged dashboard UAT, and open PostgreSQL least-privilege/remaining acceptance gates. **Production NO-GO.**
- [17 November staging reconciliation (historical)](operations/R1_AWS_Staging_Reconciliation_2026-11-17.md) — v0.187.2 release-specific evidence and its 26/0/19 matrix; not current release status.
- [R1 application tracker](engineering/R1_Application_Tracker.md) and [API test deployment roadmap](engineering/API_Test_Deployment_Roadmap.md) — Stage 4 implementation, Stage 5 verification and environment-specific evidence.
- [Phase 0 implementation baseline](engineering/Phase0_Implementation_Baseline_2026-11-23.md) — HEAD-versus-staging boundary, local test evidence, dependency-ordered backlog, DRY analysis, security risk register and the Phase 1 backlog.
- [AWS staging deployment verification](operations/AWS_Staging_Deployment_Verification_2026-11-10.md) and [Oracle Cloud deployment record](operations/Deployment_Verification_2026-11-03.md) — separate environment evidence.
- [Open Stage 3 decisions](engineering/Stage3_Open_Decisions.csv) — blockers requiring owner approval or environment evidence.
- [Engineering standards](engineering-standards.md), [repository layout](engineering/repository-layout.md), and [dependency/security checks](engineering/dependency-and-security.md).
- [FND-01 governance provenance](engineering/FND-01_repository_governance.md) — owner-declared complete; historical observations and verification procedure retained.

## Mobile reference

The [Figma design](https://www.figma.com/design/ANaV0jnwjZ0LEcByTc98HP/KoloVibe?node-id=0-1) is canonical. Supporting references cover [implementation and verification](mobile-ui-implementation.md), [screen coverage](mobile-design-coverage.md), [integration gaps](mobile-live-integration-gaps.md), [design principles](mobile-design.md), and [asset hashes](mobile-asset-manifest.json). These are implementation references, not separate product requirements.

## Document control

“Scope approved” does not mean every PRD/SRS detail, architecture decision, security control or deployment gate is approved. Draft, proposed, pending and approved states remain distinct. Git contains readable text editions of some Word/Excel sources; original formatting, formulas and embedded images are not preserved. Historical plans and reviews are retained as records, not current execution instructions.

Update the relevant source document when a material scope, architecture or security decision changes. Do not copy sensitive threat details, credentials or personal data into documentation.
