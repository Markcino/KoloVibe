> Source: platform_SRS_v0_1.docx (text export; original formatting, formulas and embedded images are not included). Original review status is retained.

<PARSED TEXT FOR PAGE: 1 / 7>
SOFTWARE REQUIREMENTS SPECIFICATION
Flutter mobile + Django templates web + Django REST Framework | Creator-content pilot R1

Version 0.1 — Working draft | 28 October 2026 | Approval status: Pending



1. Purpose, scope and conventions
This specification translates the proposed R1 PRD into testable system requirements. Each item has
an identifier, verification criterion and priority. Later-release requirements are recorded as
interfaces or exclusions, not committed R1 functionality.



2. System context and technology
Flutter mobile clients and Django-rendered HTML/CSS/JavaScript web clients communicate with
Django REST Framework or server-rendered views. Django owns authorization, engagement
qualification, points and audit events. PostgreSQL is authoritative; Redis/Celery handle background
processing. Media is delivered through a managed video service. All infrastructure and credentials
are separated by environment.



3. Actors and trust boundaries
Actor                             Trust level                         Access

Anonymous visitor                 Untrusted                           Public approved content only
Viewer                            Authenticated, untrusted            Own profile and public
                                  client                              content
Creator                           Authenticated, untrusted            Own media and read-only own
                                  client                              points
Moderator                         Privileged                          Assigned moderation
                                                                      workflows
Administrator                     Highly privileged                   Limited admin operations
                                                                      with MFA and audit
Background worker                 Service identity                    Explicit queue/task and data
                                                                      permissions
Ad/payment provider               External system                     Signed/validated integration
                                                                      only




4. Functional requirements and verification
ID                       Requirement                 Verification              Priority

FR-001                   Registration — The          Attempt valid,            Must
                         system SHALL register       duplicate and
                         a user after validated      malformed
                         required fields and         registrations.
                         enforce unique
                         account identifiers.
<PARSED TEXT FOR PAGE: 2 / 7>
FR-002   Authentication — The      Failed-login rate test;   Must
         system SHALL              revoked session
         authenticate accounts,    cannot access
         rate-limit failed         protected API.
         attempts and support
         session/token
         revocation.
FR-003   Authorization —           Cross-account             Must
         Every protected           IDOR/BOLA tests deny
         endpoint SHALL            access.
         enforce server-side
         role and object-level
         authorization.
FR-004   Creator onboarding —      State transitions         Must
         The system SHALL          require permitted
         track creator             actor and audit.
         verification states and
         reviewer decisions.
FR-005   Upload initiation —       Malicious                 Must
         The system SHALL          type/oversize/other-
         validate content          user upload rejected.
         ownership, type, size
         and authorization
         before issuing upload
         permission.
FR-006   Publishing — Only         Pending/removed           Must
         content passing           media cannot be
         required moderation       publicly listed.
         states SHALL become
         publicly discoverable.
FR-007   Playback — The            Unauthorized private      Must
         system SHALL              content cannot be
         provide authorized        streamed.
         playback URLs and
         record telemetry
         separately from
         financial records.
FR-008   Likes — The system        Repeated request does     Must
         SHALL prevent             not double count.
         duplicate active likes
         per account/content
         combination.
FR-009   View events — The         Replay event cannot       Must
         system SHALL accept       double-credit.
         playback evidence as
         untrusted input and
         process events
         idempotently.
FR-010   Qualification — The       Self-engagement/          Must
         server SHALL apply        velocity test yields
         versioned                 correct hold/rejection.
         engagement rules and
<PARSED TEXT FOR PAGE: 3 / 7>
         flag suspicious
         patterns.
FR-011   Points ledger —           Balance recomputes        Must
         Eligible points SHALL     from entries; no direct
         be recorded as            client mutation.
         auditable append-only
         entries with
         adjustment events.
FR-012   Points display —          Creator A cannot see      Must
         Creators SHALL see        creator B private
         their own eligible,       ledger.
         pending and reversed
         points without
         implied cash
         equivalence.
FR-013   Content reporting —       Report enters             Must
         Authenticated users       moderation queue
         SHALL report content      and is audited.
         with category and
         reason subject to
         abuse limits.
FR-014   Moderation —              Decision and appeal       Must
         Moderators SHALL          history are
         record decision,          immutable/audited.
         rationale, time and
         actor; appeals SHALL
         be traceable.
FR-015   Audit — Privileged        Audit includes            Must
         actions and reward        actor/action/object/tim
         adjustments SHALL         e/outcome.
         generate structured
         audit events.
FR-016   Advertising               Ad event produces         Must
         separation — Ad           zero reward entries.
         impression/click
         events SHALL NOT
         trigger creator points
         or cash credits.
FR-017   Privacy requests —        Request and               Must
         Users SHALL have a        resolution tracked.
         documented workflow
         to request data
         access/deletion subject
         to retention
         obligations.
FR-018   Admin MFA —               MFA absent blocks         Must
         Privileged operators      privileged action.
         SHALL complete MFA
         before sensitive
         operations.
FR-019   Observability — The       Alerts and dashboard      Must
         system SHALL emit
<PARSED TEXT FOR PAGE: 4 / 7>
                 health, error, security   smoke tests.
                 and cost-relevant
                 telemetry.
FR-020           Ads integration —         Test ads only before    Should
                 Production ads SHALL      release approval.
                 be gated behind
                 policy, privacy and
                 publisher approval
                 checks.




5. Quality and security requirements
ID                       Category                          Acceptance condition

NFR-001                  OWASP MASVS                       Applicable mobile controls
                                                           verified using documented
                                                           MASTG tests.
NFR-002                  OWASP ASVS                        Applicable ASVS 5.0 Level 2
                                                           controls traced to Django
                                                           implementation/tests.
NFR-003                  Transport                         Public and sensitive internal
                                                           traffic protected by validated
                                                           TLS.
NFR-004                  Secrets                           No secrets in source control,
                                                           client bundles or logs; rotation
                                                           documented.
NFR-005                  Storage                           Tokens stored via platform
                                                           secure storage; sensitive
                                                           database access restricted.
NFR-006                  CSRF/XSS                          Django CSRF protection and
                                                           contextual output escaping;
                                                           restrictive CSP.
NFR-007                  API abuse                         Rate limits, payload validation,
                                                           pagination bounds and
                                                           authorization checks.
NFR-008                  Backups                           Encrypted backups and
                                                           documented restore exercise
                                                           before pilot.
NFR-009                  CI/CD                             Protected branches, review,
                                                           automated tests and
                                                           dependency/secret scanning.
NFR-010                  Performance                       Measure response time,
                                                           playback startup and error
                                                           rates; set targets after
                                                           baseline.
NFR-011                  Accessibility                     Responsive and accessible
                                                           controls; test with keyboard
                                                           and screen reader.
NFR-012                  Data privacy                      Minimize collection, log
                                                           consent, publish retention and
<PARSED TEXT FOR PAGE: 5 / 7>
                                                                    incident processes.
NFR-013                         Resilience                          Idempotent engagement
                                                                    processing; retry and dead-
                                                                    letter strategies.
NFR-014                         Audit integrity                     Restrict audit edits and retain
                                                                    protected copies outside
                                                                    primary application access.




6. Data model — preliminary
Entity                                            Important fields / constraints

User                                              id, status, contact identifier unique, created_at
RoleAssignment                                    user_id, role, scope, active; no implicit
                                                  superuser
CreatorProfile                                    user_id unique, verification_state, reviewed_by
MediaAsset                                        owner_id, rights_status, moderation_status,
                                                  storage_ref
EngagementEvent                                   event_id unique, viewer_id, media_id,
                                                  event_type, risk_flags
QualificationDecision                             event_id unique, ruleset_version, outcome,
                                                  rationale
PointsEntry                                       id, creator_id, source_event_id, delta, state,
                                                  timestamp; append-only
ModerationCase                                    reporter, media_id, category, status, reviewer,
                                                  decision
AuditEvent                                        actor, action, resource, outcome, timestamp,
                                                  correlation_id
AdRevenueRecord                                   provider, statement_period, collected_amount,
                                                  reconciliation_status; later
MonetaryJournal                                   double-entry journal, idempotency key; later,
                                                  separate from points




7. API interface — preliminary contracts
Method / path                   Purpose                             Authorization

POST /api/v1/auth/login         Authenticate                        Anonymous with throttling
POST /api/v1/auth/logout        Revoke session                      Authenticated
GET /api/v1/me                  Own account                         Authenticated
POST /api/v1/creator/apply      Apply for creator status            Authenticated
POST /api/v1/media/uploads      Request authorized upload           Verified creator
GET /api/v1/feed                Approved content feed               Public / policy
POST /api/v1/media/{id}/likes   Like approved content               Authenticated
POST                            Submit untrusted playback           Authenticated / abuse controls
/api/v1/media/{id}/engageme     event
<PARSED TEXT FOR PAGE: 6 / 7>
nt
GET /api/v1/creator/points         Own points statement                Creator, own records
POST                               Report content                      Authenticated
/api/v1/media/{id}/reports
POST                               Moderation decision                 Moderator with MFA policy
/api/v1/moderation/{id}/deci
de

Endpoint names are design candidates, not a finalized OpenAPI contract. API semantics, rate limits,
schemas, versioning and CSRF/session strategy must be reviewed in Stage 2.



8. High-risk abuse test scenarios
    Alter creator_id in a points request: server must ignore or reject any client-defined beneficiary.
    Replay identical engagement event: one qualification outcome and at most one points entry.
    Create many accounts/devices and rapidly replay a video: rate/risk controls flag or hold activity.
    Attempt to upload content to another creator’s account: access denied and audited.
    Access another creator’s points endpoint: no cross-account disclosure.
    Forge an administrator role in a request: server rejects.
    Send ad click/impression callbacks: no reward credit generated.
    Repeat a moderator action: consistent state transition, attributable audit record.
    Restore from backup and verify audit/ledger integrity in staging.



9. Requirement traceability template
Requirement          Threat / control     Implementation         Test evidence     Status

FR-003               ASVS                 Pending                SEC-API-003       Not started
                     authorization /
                     BOLA
FR-009/010           Fraud and replay     Pending                ENG-REPLAY-001    Not started
FR-011               Ledger integrity     Pending                LEDGER-001        Not started
FR-016               Ad policy            Pending                ADS-001           Not started
                     boundary
NFR-001              MASVS                Pending                MOB-SEC-*         Not started
NFR-002              ASVS 5.0             Pending                WEB-SEC-*         Not started




10. Release criteria and exclusions
    Every Must requirement is tested and accepted by the product owner.
    Applicable security controls have evidence; no unresolved release-blocking issues.
    Backup restore, deployment rollback, moderation response and alert escalation are
     demonstrated.
    Pilot cohort, cost limits, support ownership and incident stop conditions are approved.
    No live cash payout, ticket checkout or business-reward settlement is enabled in R1.
<PARSED TEXT FOR PAGE: 7 / 7>
11. Open specification questions
   Define qualified view: watch-time, repeat limits, viewer eligibility, handling offline playback.
   Decide whether likes influence points and how gaming is limited.
   Choose session model for Flutter and Django web; specify token lifetimes and revocation.
   Choose media upload/streaming provider and signed URL expiration.
   Specify age restrictions, data retention, moderation SLAs and rights evidence.
   Determine pilot scale, Android/iOS scope and actual operating budgets.



12. Approval
Role                              Status                             Date

Product owner                     Pending                            —
Technical lead                    Pending                            —
Security reviewer                 Pending                            —