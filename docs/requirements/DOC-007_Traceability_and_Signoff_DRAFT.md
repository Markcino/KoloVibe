> Source: DOC-007_Traceability_and_Signoff_DRAFT.docx (text export; original formatting, formulas and embedded images are not included). Original review status is retained.

> Approval interpretation: the export's “approved baselines” wording covers [DEC-001 scope only](platform_documentation_register_and_DEC001.md#approval-interpretation). Detailed approval is pending; the source remains Draft.

<PARSED TEXT FOR PAGE: 1 / 2>
Requirements Traceability and Stage 1 Sign-
Off
DOC-007 | Links approved SRS requirements to journeys, roles, risks, and planned verification

Version 0.1 | 28 October 2026 | Status: Draft for stakeholder review. PRD and SRS v0.2 remain
approved baselines.

SRS ID          Journey /        Actor           Verification     Owner            State
                feature
FR-001          Viewer           Viewer          Registration     QA               Pending
                onboarding                       validation,
                                                 duplicates
FR-002          Viewer           Viewer          Rate limit,      QA/Security      Pending
                onboarding                       revocation
FR-003          All protected    All             BOLA/IDOR        Security         Pending
                journeys                         and role
                                                 checks
FR-004          Creator          Creator         Verification     QA               Pending
                onboarding                       transitions
FR-005          Creator          Creator         Upload           QA/Security      Pending
                upload                           ownership,
                                                 type and size
FR-006          Creator          Creator         Moderation       QA               Pending
                publishing                       state gate
FR-007          Viewer           Viewer          Private          QA               Pending
                playback                         content
                                                 denial
FR-008          Viewer           Viewer          Duplicate like   QA               Pending
                engagement
FR-009          Engagement       Viewer          Replay and       Security         Pending
                qualification                    idempotency
FR-010          Engagement       Worker          Self-view,       Security         Pending
                qualification                    fraud velocity
FR-011          Points ledger    Worker          Append-only      Backend/QA       Pending
                                                 balance and
                                                 reversal
FR-012          Creator          Creator         Own-account      QA/Security      Pending
                points                           isolation
                dashboard
FR-013          Content          Viewer          Report           QA               Pending
                reporting                        abuse/rate
                                                 limit
FR-014          Moderation       Moderator       Permission,      QA               Pending
                                                 decision,
                                                 appeal
FR-015          Privileged       Admin           Audit event      Security         Pending
                actions                          integrity
FR-016          Ads              Worker          No points        Security         Pending
                separation                       from ad
                                                 events
FR-017          Privacy          Viewer          Request          QA               Pending
<PARSED TEXT FOR PAGE: 2 / 2>
                 requests                          tracking
FR-018           Admin MFA        Admin            MFA bypass        Security         Pending
                                                   rejection
FR-019           Operations       Ops              Monitoring        Ops              Pending
                                                   and alert
                                                   smoke test
FR-020           Ads              Product          Test mode         Product          Pending
                 integration                       and policy
                                                   review



Non-functional traceability
   NFR-001: MASVS applicable controls → mobile test evidence; security owner.
   NFR-002: ASVS 5.0 Level 2 applicable controls → backend/web test evidence; security owner.
   NFR-003 to NFR-014: TLS, secrets, storage, XSS/CSRF, API abuse, backup, CI, performance,
    accessibility, privacy, resilience and audit controls → CI checks and staged operational tests.
   Detailed MASVS/ASVS per-control mapping is a Stage 2 deliverable and is not falsely represented
    as complete here.



Stage 1 exit checklist
☐ Approved PRD v0.2

☐ Approved SRS v0.2

☐ Approved MVP boundary

☐ Stakeholder/user role validation

☐ RBAC matrix reviewed and approved

☐ User journeys reviewed and approved

☐ Engagement/points rule parameters resolved or explicitly deferred

☐ Requirement-to-test traceability reviewed

☐ Open decisions assigned with owners/dates

☐ Product owner and technical/security leads authorize Stage 2



Approval record
Item                              Decision                           Date / owner
DEC-001 MVP scope                 Approved by user                   Previously confirmed
PRD/SRS detailed baselines        Pending owner decision (#133)      —
DOC-004 RBAC                      Pending                            —
DOC-005 Journeys                  Pending                            —
DOC-006 Business rules            Pending                            —
DOC-007 Traceability              Pending                            —
Stage 1 formal closure            Pending                            —

Document-control correction (#133): the original export row said “DEC-002 PRD and SRS v0.2 / Approved by user / Previously confirmed.” That historical assertion is retained here, but it is not usable detail-approval evidence. The authoritative register leaves DEC-002 open for product name/legal entity and limits DEC-001 to scope. FR/NFR verification states and formal Stage 1 sign-off remain unchanged for #134.

## Phase 2 review addendum (27 November 2026)

The feature traceability authority is the [full-product matrix](../governance/phase1/PHASE-01_Feature_Traceability_Matrix.csv), now including exact detailed IDs for every actual row in the five approved sets. The tables above remain historical Stage 1 evidence; “Pending” is not silently changed to acceptance. FR-021..030 and NFR-015 are covered by the full matrix's console/account rows and SRS verification requirements, with staged/device/security acceptance still open. [The review packet](../governance/phases/PHASE-02_Review_and_Decision_Packet.md) records the exact research, section decisions and signatures needed. No Stage 1 signature or research waiver was supplied in this task. Scope approval, automated checks and a merged PR do not close #134.
