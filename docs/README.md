# Documentation

Use the controlled source documents below. Link to them instead of copying requirements, decisions or delivery status into new summaries.

## Product and architecture

- [DEC-001 and document register](requirements/platform_documentation_register_and_DEC001.md) — canonical Release 1 scope decision.
- [PRD](requirements/platform_PRD_v0_2_scope_approved.md) and [SRS](requirements/platform_SRS_v0_2_scope_approved.md) — detailed requirements remain drafts; only the Release 1 scope is approved.
- [Architecture references](architecture/) — data model, draft API, architecture, risks, controls and open decisions.
- [Architecture decision summary](architecture-decisions.md) — index to decisions; the registers in `architecture/` remain authoritative. ADR-013 selects Django-native client identity, with session/MFA details still pending.

## Delivery and engineering

- [Current Stage 3 status](engineering/Stage3_Current_Status.md) and [implementation tracker](engineering/Stage3_Implementation_Tracker.csv) — update together from verified evidence.
- [R1 application tracker](engineering/R1_Application_Tracker.md) and [API test deployment roadmap](engineering/API_Test_Deployment_Roadmap.md) — feature status and staging sequence.
- [Open Stage 3 decisions](engineering/Stage3_Open_Decisions.csv) — blockers requiring owner approval or environment evidence.
- [Engineering standards](engineering-standards.md), [repository layout](engineering/repository-layout.md), and [dependency/security checks](engineering/dependency-and-security.md).
- [FND-01 governance provenance](engineering/FND-01_repository_governance.md) — owner-declared complete; historical observations and verification procedure retained.

## Mobile reference

The [Figma design](https://www.figma.com/design/ANaV0jnwjZ0LEcByTc98HP/KoloVibe?node-id=0-1) is canonical. Supporting references cover [implementation and verification](mobile-ui-implementation.md), [screen coverage](mobile-design-coverage.md), [integration gaps](mobile-live-integration-gaps.md), [design principles](mobile-design.md), and [asset hashes](mobile-asset-manifest.json). These are implementation references, not separate product requirements.

## Document control

“Scope approved” does not mean every PRD/SRS detail, architecture decision, security control or deployment gate is approved. Draft, proposed, pending and approved states remain distinct. Git contains readable text editions of some Word/Excel sources; original formatting, formulas and embedded images are not preserved. Historical plans and reviews are retained as records, not current execution instructions.

Update the relevant source document when a material scope, architecture or security decision changes. Do not copy sensitive threat details, credentials or personal data into documentation.
