> Source: DOC-007_Traceability_and_Signoff_DRAFT.docx (text export; original formatting, formulas and embedded images are not included). Original review status is retained.

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
DEC-002 PRD and SRS v0.2          Approved by user                   Previously confirmed
DOC-004 RBAC                      Pending                            —
DOC-005 Journeys                  Pending                            —
DOC-006 Business rules            Pending                            —
DOC-007 Traceability              Pending                            —
Stage 1 formal closure            Pending                            —