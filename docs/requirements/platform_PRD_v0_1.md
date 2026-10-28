> Source: platform_PRD_v0_1.docx (text export; original formatting, formulas and embedded images are not included). Original review status is retained.

<PARSED TEXT FOR PAGE: 1 / 5>
PRODUCT REQUIREMENTS DOCUMENT
Liberian-owned content, verified services, events and advertising-funded rewards platform

Version 0.1 — Working draft | 28 October 2026 | Approval status: Pending



1. Product vision and business model
Build a free-to-use platform that helps Liberian creators distribute original entertainment, helps
customers find trustworthy businesses and events, and gives eligible participants a transparent
share of collected company revenue. The company earns revenue from AdMob/AdSense and direct
advertising or sponsorships. The platform does not pay viewers to click or watch Google
advertisements.



2. Problem and opportunity
   Original creators need distribution, discoverability and transparent engagement reporting.
   Customers need reliable business information and authentic service feedback.
   Organizers need trustworthy ticket purchase and entry verification.
   The company must control video delivery costs, fraud, moderation and advertising-policy risk.



3. Product goals and success measures
Goal                              Proposed measure                  Baseline / target

Creator activation                Verified creators publishing an   Baseline to be measured in
                                  original item                     pilot
Viewer experience                 Successful playback / failed      Baseline and SLO to be
                                  playback                          approved
Integrity                         Qualified vs rejected             Measure by fraud category
                                  engagement events
Moderation                        Time from report to               Policy and target pending
                                  disposition
Financial readiness               Reconciled revenue and ledger     No payouts in initial pilot
                                  discrepancy rate
Cost discipline                   Cost per active viewer and        Measure real pilot usage
                                  delivered minute




4. Stakeholders and user roles
Role                                               Core needs

Viewer                                             Register, browse, play, like, report, manage
                                                   privacy
Creator                                            Verify profile, upload original media, view
                                                   eligible points, appeal moderation
Business owner                                     Claim/verify listing and respond to genuine
<PARSED TEXT FOR PAGE: 2 / 5>
                                                  reviews (later)
Event organizer                                   Create events, track paid tickets, validate
                                                  entries (later)
Moderator                                         Review reports, remove or restore content with
                                                  reasons
Finance officer                                   Reconcile receipts, approve settlement and
                                                  payouts (later)
Administrator                                     Manage platform configuration under least
                                                  privilege
Advertiser                                        Buy approved direct placements (later)




5. Release strategy
Release                          Included                           Excluded or gated

R1 limited creator pilot         Accounts, profiles, media,         Cash payouts, live streaming,
                                 playback, likes, qualified         paid tickets
                                 engagement, non-cash points,
                                 moderation, admin, test ads
R2 verified businesses           Business ownership                 Automatic cash settlement
                                 verification, services,            unless separately approved
                                 customer evidence and
                                 feedback
R3 events and tickets            Organizer verification,            Payout automation until
                                 payments, refunds, QR ticket       control validation
                                 issuance/redemption
R4 revenue share and             Reconciled eligible revenue,       No guarantee of fixed dollars
payouts                          reward pool, approvals,            per view
                                 provider payouts




6. Pilot user journeys
Viewer
Register → verify contact → browse approved content → play video → like/report → manage sessions.

Creator
Register → apply for creator status → submit identity/rights evidence as applicable → upload →
moderation → publish → see eligible points and holds.

Moderator
Receive flagged content → inspect evidence → decide with reason → notify creator → preserve appeal
record.

Administrator
Authenticate with MFA → perform permitted change → generate audit event → review suspicious
activity.
<PARSED TEXT FOR PAGE: 3 / 5>
7. Core functional requirements
ID                                Capability                       Priority

PRD-F01                           Accounts and secure sign-in      Must
PRD-F02                           Role and permission              Must
                                  management
PRD-F03                           Creator profile and              Must
                                  verification status
PRD-F04                           Original media upload and        Must
                                  playback
PRD-F05                           Like, view and engagement        Must
                                  event collection
PRD-F06                           Server-side qualified-           Must
                                  engagement evaluation
PRD-F07                           Auditable non-cash points        Must
                                  balance and adjustments
PRD-F08                           Report, moderation and           Must
                                  appeal workflow
PRD-F09                           Privacy controls, consent and    Must
                                  account deletion workflow
PRD-F10                           Admin review, audit trail and    Must
                                  fraud holds
PRD-F11                           AdMob/AdSense test               Should; conditional approval
                                  integration, independent ad
                                  accounting
PRD-F12                           Verified business services and   R2
                                  reviews
PRD-F13                           Ticket payments, refunds and     R3
                                  QR redemption
PRD-F14                           Revenue pool settlement and      R4
                                  verified payouts




8. Reward and advertising rules
    A content view/like is a candidate event, not an automatic payment entitlement.
    The backend defines and verifies qualified engagement; self-views, duplicates and suspicious
     patterns may be excluded or held.
    Points are non-cash records until an approved settlement policy creates a monetary obligation.
    Eligible revenue must be collected and reconciled before funding any reward pool.
    No user or creator is compensated for Google ad clicks or ad impressions.
    Rewards are variable; no fixed cash-per-view promise without an approved funded model.
    Appeals, reversals, disputes and sanctions must be recorded and reviewable.



9. Security and privacy principles
    OWASP MASVS/MASTG for Flutter; OWASP ASVS 5.0 Level 2 baseline for Django web/API with
     risk-based extensions.
<PARSED TEXT FOR PAGE: 4 / 5>
   Server-side authorization for every protected object and financial action.
   Privileged MFA, session revocation, secure credential storage, least privilege and audit logs.
   Secure media upload, content-rights verification, reporting and takedown procedures.
   Data minimization, retention schedule, consent records and local legal review before launch.
   Payout release requires separate provider, regulatory, fraud and financial-control approvals.



10. Non-functional expectations
Area                                               Requirement / acceptance approach

Security                                           Documented threat model and MASVS/ASVS
                                                   evidence; no unresolved release-blocking issues
Availability                                       Set measurable SLO after pilot load testing
Performance                                        Measure API latency and video startup across
                                                   Liberian networks
Accessibility                                      Keyboard access, screen-reader semantics,
                                                   contrast, captions where applicable
Reliability                                        Idempotent event processing, backup restore
                                                   and rollback exercises
Maintainability                                    Modular Django, documented APIs, CI/CD,
                                                   reviewed code
Observability                                      Audit, metrics, error tracking, abuse alerts and
                                                   cost dashboards




11. External dependencies and constraints
   Cloudflare Stream and object storage: verify actual costs and terms before production.
   Google AdMob/AdSense: publisher and app approval are not guaranteed; review policy before
    production.
   Payment providers: verify Liberia coverage, business onboarding, webhooks, bulk
    disbursements and fees.
   Mobile store accounts, testing devices, moderation capacity, legal advice and security
    assessment require funding.



12. Product acceptance criteria for R1
   A viewer can securely register and consume approved content on supported pilot devices.
   A creator can upload authorized content and view a server-computed points statement.
   Unauthorized users cannot modify another creator’s media or balances.
   Suspicious events are rejected or held and leave an audit trail.
   Moderators can process reports and appeals with attributable decisions.
   The platform can restore from backup and roll back a release.
   Pilot cost, playback and fraud metrics are collected for go/no-go review.



13. Open decisions requiring approval
   Product name, brand, legal entity and intended countries of operation.
<PARSED TEXT FOR PAGE: 5 / 5>
   Precise qualified-view threshold, points formula and anti-abuse rules.
   Creator eligibility, age limits, identity evidence and content licensing policy.
   Pilot cohort size and whether iOS is mandatory for the first pilot.
   Privacy retention schedule, moderation policy and dispute process.
   Advertising placement strategy and launch budget cap.
   Revenue-sharing allocation, reserves, payout threshold and provider (later).



14. Stage 1 approval record
Approver                           Decision                           Date

Product owner                      Pending                            —
Technical lead                     Pending                            —
Security reviewer                  Pending                            —