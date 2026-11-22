# #133 — Document register and detail-baseline decisions

**Status: In review — four methods approved by the owner on 2026-11-22; detail acceptance and research execution pending.** [Owner decision record](https://github.com/Markcino/KoloVibe/issues/133#issuecomment-7076320307). Related to [#133](https://github.com/Markcino/KoloVibe/issues/133); Stage 1 remains open in [#169](https://github.com/Markcino/KoloVibe/issues/169). Approval authority: **Mark Allen Gbalazeh (@Markcino)**. The decision record below reflects the owner's explicit “Approve all four methods” reply; CI and this document grant no additional approval.

## Owner-approved methods and remaining actions

1. **S1-133-ID: preserve the IDs already present on source files.** Keep DOC-004 RBAC, DOC-005 journeys, DOC-006 rules, DOC-007 traceability, DOC-201–209 architecture, and the SRS's NFR section under DOC-002. Use the proposed [register CSV](document_register.csv) as the inventory, with the old register entries retained as historical aliases. Recover missing DOC-201/DOC-202 sources; do not invent their content or approval dates.
2. **S1-133-RESEARCH: conduct a small, evidence-backed R1 role review.** Adopt the [DOC-003 protocol](DOC-003_Stakeholder_Research_Proposed.md), not a waiver. Cover viewer, creator, assigned moderator and supervising administrator tasks; record sanitized findings and requirement links. No interviews or research results are claimed to have occurred.
3. **S1-133-BASELINE: review and approve detail sections explicitly.** Use the [detail review manifest](detail_baseline_review.csv). Keep PRD/SRS details Draft until an actual owner decision is recorded against a source revision. Existing DEC-001 scope approval remains authoritative and separate. Recommend accepting only sections with clear R1 boundaries, measurable Must acceptance and an owner; leave unresolved sections pending their linked issue. Do not blanket-approve v0.2 filenames.
4. **S1-133-CONTROL: use Git issues and draft PRs for document control.** Adopt [DOC-023](DOC-023_Change_Control_Proposed.md): one change request, impact analysis, exact source revision, explicit owner decision, then verified status updates. This uses the existing repository; it changes no GitHub ruleset or deployment setting.

The register's owner roles describe responsibilities, not additional employees. [Stage 3's recorded staffing](../engineering/Stage3_Current_Status.md) assigns Engineering/DBA/API/DevSecOps/SRE/sponsor responsibilities to the same owner. Independent security and legal assurance still require appropriate reviewers; owner self-review is not independent certification.

## S1-133-ID — Which identifier scheme is authoritative?

**Why it matters:** conflicting IDs break requirement/control/evidence links and can make an unrelated approval appear to authorize a release. DOC-007 is already a traceability file; the historical master table used DOC-007 for NFRs. Several architectural deliverables already use DOC-20x IDs.

| Option | Security | Privacy | Cost | Operations | Open-source implications |
| --- | --- | --- | --- | --- | --- |
| **A — Preserve file IDs and use historical aliases (recommended)** | Stable control/evidence links; ambiguous approval claims explicitly corrected | No new system or copies of private evidence | Small register maintenance effort | No file renames; one inventory; old references remain resolvable | Plain Markdown/CSV and Git; portable to another host |
| B — Rename all artifacts to the old DOC-001–023 table | Requires revalidating every control and evidence link | Wider copying/renaming review increases accidental disclosure risk | Larger migration and review effort | Breaks established references; rollback needs a mapping | Still portable, with unnecessary tooling/migration work |
| C — Keep both schemes as parallel current registers | Approval/control attribution stays ambiguous | Unclear evidence ownership/retention | Lowest immediate edit cost; recurring reconciliation cost | Conflicting sources of truth continue | No vendor dependency, but weak governance |

**Recommendation:** A. Preserve the 28 October table as history and mark its conflicting references **Superseded only after owner approval**. DOC-007's former NFR meaning resolves to DOC-002 section 5; its materialized traceability meaning stays DOC-007. DOC-008/009/010/011/012/016 are legacy register references to the existing architecture family, not duplicate new documents. Missing DOC-201/DOC-202 files are gaps, even though G-01 records historical design approval.

**Risk if wrong:** a historic approval could be attached to the wrong artifact. Mitigation: retain the original text, record aliases with source paths and revisions, and never infer an approval date from Git history.

**Owner method decision:** A approved; inventory/source-detail limitations remain explicit. **Authorized record fields:** `document_register.csv` → `mapping_state` and `owner_decision_reference`; the register's `S1-133-ID` approval record; the historical table's supersession note. Preserve each source's observed status and existing approval scope.

## S1-133-RESEARCH — Record research or waive it?

**Why it matters:** untested assumptions about rights declarations, non-cash points and moderator scope are Stage 1 risks. A test suite cannot substitute for stakeholder validation.

| Option | Security | Privacy | Cost | Operations | Open-source implications |
| --- | --- | --- | --- | --- | --- |
| **A — Lean role walkthroughs and sanitized findings (recommended)** | Tests comprehension of rights, roles and sensitive workflows | No recordings, identity documents or unnecessary contact data | Limited participant/owner time; no paid service required | Repeatable role checklist with findings assigned to issues | Markdown/CSV; self-hosted calls or in-person sessions |
| B — Explicit, bounded owner waiver | Assumptions remain unvalidated; residual risk must be accepted | Avoids research-data collection | Lowest immediate effort | Must state rationale, affected requirements, expiry/next gate and compensating checks | No tool dependency |
| C — Broad market-research exercise before any progress | More coverage but does not itself verify authorization | Larger participant-data footprint | More recruitment and analysis effort | Delays a restricted pilot; includes unnecessary R1-excluded audiences if not constrained | Can be self-hosted, with more administration |

**Recommendation:** A. One walkthrough per R1 role; a participant may cover more than one privileged role, with coverage recorded honestly. Do not recruit businesses/organizers or design their deferred features. A waiver is an explicit fallback, not an assumed approval.

**Risk if wrong:** a small sample misses usability/abuse misunderstandings. Mitigation: record sample limits, unresolved findings and pilot feedback checkpoints; do not call this representative market research or independent security testing.

**Owner method decision:** protocol A approved; actual participant coverage/results remain pending. **Authorized record fields:** DOC-003 `Protocol owner decision`, `Decision reference` and `Actual decision date` fields. Research completion remains Pending until real dated findings are entered. A waiver instead requires DOC-003's waiver record and a linked owner decision; no fabricated findings.

## S1-133-BASELINE — How should PRD/SRS details be accepted?

**Why it matters:** both v0.2 filenames retain a v0.1 working-draft body. The traceability export also attributed PRD/SRS approval to DEC-002, although the authoritative register leaves DEC-002 for product name/legal entity. DEC-001 approves R1 scope, not every detailed requirement.

| Option | Security | Privacy | Cost | Operations | Open-source implications |
| --- | --- | --- | --- | --- | --- |
| **A — Version-pinned, section-by-section owner review (recommended)** | Mandatory controls and measurable Must criteria remain visible; no inferred sign-off | Retention/residency sections stay pending #136 | Bounded review of existing documents | Clear acceptance/defer/reject/pending records and issue links | Existing Git/CSV; no external requirements platform |
| B — Approve entire documents from filenames or implementation status | Risks approving unresolved controls and obsolete wording | Can accidentally accept unreviewed retention/provider commitments | Fast now; costly remediation later | Weak basis for Stage 1 closure | No vendor cost, but unreliable evidence |
| C — Freeze all detail review until every general-release decision closes | Avoids premature acceptance | Privacy stays unresolved | Highest delay/coordination cost | Ignores valid restricted-pilot decisions already recorded | No tooling advantage |

**Recommendation:** A. The current draft needs review, not an automatic status promotion. Preserve DEC-003/004/005 and OD-07 as restricted-pilot authorities. General-release points (#137), comments/ads (#135), privacy (#136), and complete Must/FR/NFR evidence/sign-off (#134) remain separate work. Live streaming, business discovery, ticketing and cash payouts remain outside R1. The web client remains moderator/administrator-only; 108 mobile screen IDs do not expand approved scope.

**Risk if wrong:** conditional acceptance is mistaken for go-live. Mitigation: distinguish source detail approval from implementation, verification, legal acceptance and release authorization; Stage 1 stays open while its gate is unmet.

**Owner method decision:** A approved. The owner must still decide each reviewed source section, with rationale and remaining gate. **Fields for those later section decisions:** `detail_baseline_review.csv` → `owner_decision`, `decision_reference`, `actual_decision_date`, `conditions`; PRD/SRS `Detail status` and version metadata only for the approved revision/sections. Never fill a signature/date on the owner's behalf. DOC-007 formal sign-off remains #134.

## S1-133-CONTROL — What routine controls future changes?

**Why it matters:** documents, CSVs, ADRs and issue checklists must not drift or silently turn implementation evidence into an approval.

| Option | Security | Privacy | Cost | Operations | Open-source implications |
| --- | --- | --- | --- | --- | --- |
| **A — Issue + impact analysis + draft PR + explicit owner decision (recommended)** | Review links to requirements/controls; existing controls cannot be weakened silently | Sanitized evidence links; no raw sensitive material | Uses existing tooling | One change request and source revision; mechanical consistency checks | Git and text formats are self-hostable/exportable |
| B — Adopt a new commercial document-control product | May provide workflow features but adds integration/security review | Adds a processor and data-export questions | Subscription and migration cost | Duplicate sources unless integrated carefully | Creates avoidable lock-in |
| C — Edit documents without a change record | Weak provenance and approval attribution | Disclosure review can be skipped | Low immediate effort; recurring audit/remediation cost | Status drift returns | Open formats alone do not provide control |

**Recommendation:** A. Keep the current host while retaining portable source files; a host migration is not needed for this issue. The routine does not create a new deployment or branch-protection approval flow.

**Risk if wrong:** a lightweight process is applied inconsistently. Mitigation: require the DOC-023 fields in each proposed change, name the owner and link an explicit decision before a lifecycle transition.

**Owner method decision:** DOC-023 routine A approved. **Authorized record fields:** DOC-023 `Routine owner decision`, `Decision reference`, `Actual decision date`; register row DOC-023 `owner_decision_reference`. Operational execution and independent assurance remain distinct.

## Owner decision record — methods only

| Decision ID | Recommended option | Owner decision | Actual decision date | Owner evidence link |
| --- | --- | --- | --- | --- |
| S1-133-ID | A | Approved by Mark Allen Gbalazeh — method only | 2026-11-22 | [Owner record](https://github.com/Markcino/KoloVibe/issues/133#issuecomment-7076320307) |
| S1-133-RESEARCH | A | Approved by Mark Allen Gbalazeh — method only | 2026-11-22 | [Owner record](https://github.com/Markcino/KoloVibe/issues/133#issuecomment-7076320307) |
| S1-133-BASELINE | A (review method; no blanket detail approval) | Approved by Mark Allen Gbalazeh — method only | 2026-11-22 | [Owner record](https://github.com/Markcino/KoloVibe/issues/133#issuecomment-7076320307) |
| S1-133-CONTROL | A | Approved by Mark Allen Gbalazeh — method only | 2026-11-22 | [Owner record](https://github.com/Markcino/KoloVibe/issues/133#issuecomment-7076320307) |

Issue #133 remains open. The owner has approved the four methods; actual PRD/SRS section decisions, completed research, and source-recovery/gap handling still need action. No waiver was approved. No #169 checkbox is eligible to be ticked from this proposal alone.
