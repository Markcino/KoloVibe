> Source: platform_documentation_register_and_DEC001.docx (text export; original formatting, formulas and embedded images are not included). Original review status is retained.

<PARSED TEXT FOR PAGE: 1 / 3>
Project Documentation Register &
Decision Log
Liberian creator-content platform | Baseline v1.0 | 28 October 2026


## Current inventory and approval interpretation — #133

**Four document-control methods approved by Mark Allen Gbalazeh on 2026-11-22; detailed baselines and research execution remain pending.** [Owner decision](https://github.com/Markcino/KoloVibe/issues/133#issuecomment-7076320307). Use the [23-row source inventory](document_register.csv), [owner decision brief](S1-133_Document_Control_Decision_Brief.md), [detail review manifest](detail_baseline_review.csv), proposed [DOC-003 protocol](DOC-003_Stakeholder_Research_Proposed.md) and [DOC-023 change routine](DOC-023_Change_Control_Proposed.md). This records the owner-approved methods; it neither approves details nor closes Stage 1.

### Approval interpretation

DEC-001 approves R1 scope only. The PRD/SRS detailed bodies remain working drafts; filenames and implementation evidence are not approval records. DEC-003/004/005 and OD-07 retain their recorded restricted-pilot authority. DEC-002 remains the open product-name/legal-entity decision; it is not a PRD/SRS approval. DEC-006/007 and other open decisions stay open. Existing architecture approval claims are reported at their recorded design scope; missing files and execution evidence remain gaps.

The inventory records real paths, observed status, historical owner responsibilities, the recorded sole accountable owner, declared source dates and separately labelled Git dates. `Not recorded` means missing metadata, not a new date or approval. Git dates show a source change only. Its `inventory_base_commit` pins the inspection baseline. Architecture CSVs and BE/FL records retain their own scoped status; no local result or design approval is promoted to independent assurance.

### Owner-approved ID method and aliases

Keep materialized DOC-004/005/006/007 and DOC-201–209 identifiers. NFRs remain in DOC-002 section 5; the historical DOC-007 NFR reference is an alias to that section, not a second DOC-007. Legacy DOC-008/009/010/011/012/016 entries resolve to the architecture references named in the CSV. The 28 October table below is retained as history; its conflicting legacy references are **Superseded as register references** under the [owner-approved mapping method](https://github.com/Markcino/KoloVibe/issues/133#issuecomment-7076320307). Source artifacts keep their existing detail/design/verification status. No source file is renamed or deleted. Standalone DOC-201/DOC-202 sources were not found; related files do not substitute for those missing artifacts.

### Owner decisions — method approval only

| Decision | State | Owner evidence reference | Actual decision date |
| --- | --- | --- | --- |
| S1-133-ID | Approved by owner — method only | [Decision](https://github.com/Markcino/KoloVibe/issues/133#issuecomment-7076320307) | 2026-11-22 |
| S1-133-RESEARCH | Approved by owner — method only | [Decision](https://github.com/Markcino/KoloVibe/issues/133#issuecomment-7076320307) | 2026-11-22 |
| S1-133-BASELINE | Approved by owner — method only | [Decision](https://github.com/Markcino/KoloVibe/issues/133#issuecomment-7076320307) | 2026-11-22 |
| S1-133-CONTROL | Approved by owner — method only | [Decision](https://github.com/Markcino/KoloVibe/issues/133#issuecomment-7076320307) | 2026-11-22 |


Decision DEC-001 — Initial MVP scope approved
Date: 28 October 2026 | Authority: Product owner | Decision: Approved | Evidence: explicit
approval in project conversation

Release 1 IN: secure accounts; creator profiles; original video uploads and playback; server-
verified views and likes; non-cash points dashboard; moderation and reporting. Release 1 OUT:
business discovery, ticketing, and monetary payouts. All deferred modules remain in product
roadmap documentation.

Scope approval is not technical, legal, budget or production-release approval. No
implementation or independent testing is claimed complete.


Documentation governance
   Every document has an ID, version, owner, status, date, reviewer, and change history.
   Draft → In review → Approved → Superseded is the controlled lifecycle.
   Approved baseline is versioned; changes require a Change Request (CR) and impact
    analysis.
   Every Must requirement maps to design, issue/ticket, test, security control and evidence.
   Keep all documents in Git under docs/ and review changes through pull requests.
   Do not publish sensitive threat details, secrets, personal data or internal operational
    runbooks publicly.


Historical master register — 28 October 2026 (retained; conflicting aliases Superseded by owner-approved mapping)
ID                 Document            Owner              Status              Target stage
DOC-001            Product             Product owner      Scope approved;     1
                   Requirements                           details draft
                   Document
DOC-002            Software            Technical lead     Scope approved;     1
                   Requirements                           details draft
                   Specification
DOC-003            Stakeholder and     Product owner      Not started         1
                   user research
DOC-004            Role and            Security +         Not started         1–2
                   permissions         backend
                   matrix
DOC-005            User journeys       UX/product         Not started         1–2
                   and UX flows
DOC-006            Business rules      Product + fraud    Not started         1–2
<PARSED TEXT FOR PAGE: 2 / 3>
                   and points         lead
                   qualification
DOC-007            Nonfunctional      Technical lead     Draft in SRS        1
                   requirements
                   and KPIs
DOC-008            Software           Technical lead     Not started         2
                   architecture and
                   ADRs
DOC-009            Trust-boundary     Security lead      Not started         2
                   DFD and
                   STRIDE model
DOC-010            ERD and data       Backend lead       Preliminary in      2
                   dictionary                            SRS
DOC-011            OpenAPI            Backend lead       Preliminary in      2–3
                   contract                              SRS
DOC-012            ASVS/MASVS         Security + QA      Not started         2–5
                   traceability
DOC-013            Privacy,           Product + legal    Not started         1–5
                   retention and
                   copyright policy
DOC-014            Engineering        Technical lead     Not started         3
                   standards and
                   CI/CD
DOC-015            Test plan and      QA lead            Not started         3–5
                   evidence
DOC-016            Threat             Security lead      Not started         2–6
                   remediation and
                   risk register
DOC-017            Deployment and     Operations         Not started         3–6
                   rollback
                   runbook
DOC-018            Pilot plan and     Product +          Not started         6
                   go/no-go           operations
                   checklist
DOC-019            Monitoring and     Operations +       Not started         3–7
                   incident           security
                   response
DOC-020            Business module    Product +          Deferred            Post-pilot
                   R2 specification   technical
DOC-021            Ticketing R3       Product +          Deferred            Post-pilot
                   specification      technical
DOC-022            Revenue/payout     Finance +          Deferred            Post-pilot
                   R4 specification   security
DOC-023            Change requests    Product owner      Active              All
                   and decision log


DEC-003 — Restricted pilot qualified views and non-cash points

Approved by the product owner on 10 November 2026. A signed-in viewer may qualify after watching the lesser of 30 seconds or 80 percent of the processed video. Count at most one qualified view per viewer account and video in a rolling 24-hour window. Self-views, ad views, duplicates and suspicious progress are ineligible. Each qualified view earns the creator one non-cash point, capped at 100 per creator per UTC day. Likes award zero points.

Engagement owns watch sessions and qualification. Content supplies the encoded duration and current publication revision. Points applies the approved formula once per durable event and serves the creator's own balance and history. The pilot rejects impossible or stale playback progress using server elapsed time and forward samples. A signed R2 URL and paced client telemetry cannot prove that a person watched the video. Edge throttling, abuse monitoring and session retention need staging acceptance and DEC-008 review before activation.

Local acceptance requires `KOLOVIBE_LOCAL_POINTS_ENABLED=1` for Gateway, Engagement and Points, `KOLOVIBE_LOCAL_MEDIA_ENABLED=1` for tracked playback, and the existing PostgreSQL schema bootstrap and migrations. Run the Points Celery worker on `kolovibe.points` and periodically run the Engagement `dispatch_engagement_events` command. Verify RabbitMQ permissions and retry behavior with the staging broker. Legacy renditions without a measured millisecond duration keep ordinary playback and require reprocessing to qualify.

DEC-004 — Restricted pilot creator eligibility

Approved by the product owner on 10 November 2026. Invited accounts with verified email may apply. Applicants attest that they are at least 18 and will upload only content they own or have permission to use. The pilot collects neither government IDs nor dates of birth. An authorized reviewer approves the application before upload eligibility is granted. Publication requires separate content review.

The Creators service owns pilot eligibility. It records the invitation, policy attestation and review with account IDs and timestamps. The future upload API must verify eligibility server-side on every new upload authorization. Creator approval does not elevate the Identity account role. General privacy retention, copyright/takedown/appeals rules and the video provider remain separate decisions.

OD-07 — Restricted pilot video provider

Approved by the product owner on 10 November 2026. R1 uses private Cloudflare R2 for uploaded originals and playback renditions, with FFmpeg encoding managed by a Content Celery worker over RabbitMQ. This supersedes the earlier Cloudflare Stream selection. Live streaming is outside R1. The worker moves a valid encoded video to private review. Publication requires a separate content decision under DEC-005. Live R2, RabbitMQ and worker deployment acceptance remain open.

DEC-005 — Restricted pilot moderation

Approved by the product owner on 10 November 2026. A reviewer approves a processed video before publication. Signed-in users can report a published video. Authorized moderators can unpublish it and must record a reason. The creator can appeal the removal and a different reviewer must approve restoration.

Moderation owns reports, appeals and attributed decisions. Content applies signed decisions against the current video revision. Removal closes public discovery and stops new playback URLs. Previously issued playback URLs can remain usable until their short expiry. This decision covers the application workflow. Legal notices and data retention require separate review.

Open decisions
   DEC-002: Final product name and legal entity.
<PARSED TEXT FOR PAGE: 3 / 3>
   DEC-006: Pilot cohort size and Android/iOS release requirement.
   DEC-007: Monthly cloud cap, moderation capacity and security assessment budget.
   DEC-008: Data retention, privacy notices and jurisdictional review.


Next execution steps
1. Validate PRD/SRS requirements individually with product owner.

2. Complete the role-permission matrix and creator/viewer user journeys.

3. Specify qualified engagement as a versioned business rule with abuse tests.

4. Complete privacy/copyright rules and acceptance criteria.

5. Conduct Stage 1 sign-off on detailed requirements before Stage 2 architecture sign-off.