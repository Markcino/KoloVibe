> Source: DOC-005_User_Journeys_DRAFT.docx (text export; original formatting, formulas and embedded images are not included). Original review status is retained.

<PARSED TEXT FOR PAGE: 1 / 3>
End-to-End User Journeys
DOC-005 | Role-based workflows, failure paths and acceptance checkpoints

Version 0.1 | 28 October 2026 | Status: Draft for stakeholder review. PRD and SRS v0.2 remain
approved baselines.



Viewer onboarding and viewing
1. Open Flutter app or Django website

2. Review terms and privacy notice; create account and verify contact

3. Authenticate; configure privacy/preferences

4. Browse approved feed; request playback

5. Server issues appropriate media access and records untrusted engagement telemetry

6. Like/report content; receive confirmation

7. Manage sessions, profile, privacy requests

Alternative and abuse paths
Invalid contact; login throttling; unavailable media; slow network; blocked content; rate-limited
likes

Traceability
FR-001, FR-002, FR-007, FR-008, FR-013



Creator application and publishing
1. Authenticate and request creator role

2. Submit creator details and rights declarations

3. Reviewer or approved process verifies eligibility

4. Upload original video with server-authorized upload token

5. Media scan/transcode and moderation state checks

6. Approved media becomes discoverable

7. Creator sees playback/engagement metrics and non-cash points

Alternative and abuse paths
Creator rejected; upload too large; copyright claim; unsafe content; failed processing; private media
access attempt
<PARSED TEXT FOR PAGE: 2 / 3>
Traceability
FR-004, FR-005, FR-006, FR-012



Qualified engagement and points
1. Viewer watches eligible content; client submits telemetry

2. Backend checks authentication, device/session risk, deduplication and rule version

3. Decision engine accepts, rejects or holds event

4. Accepted event produces exactly one idempotent points ledger entry

5. Creator dashboard shows eligible/pending/reversed points with no cash promise

6. Fraud review can create compensating adjustment with audit reason

Alternative and abuse paths
Self-engagement; event replay; bot velocity; disconnected playback; deleted media; disputed points

Traceability
FR-009, FR-010, FR-011, FR-016



Content report and moderation
1. Viewer reports approved media with category

2. Report queue groups duplicates and abuse signals

3. Moderator opens assigned case and evidence

4. Moderator decides allow, restrict, remove or escalate

5. Decision is logged; affected creator notified

6. Creator can appeal; separate reviewer assesses appeal

Alternative and abuse paths
Abusive mass reporting; conflict of interest; reviewer unauthorized; false copyright complaint

Traceability
FR-013, FR-014, FR-015



Privileged admin and incident handling
1. Admin authenticates with MFA

2. System validates specific permission and context

3. Admin views authorized queues/configuration

4. Sensitive change is audited and alerted if necessary
<PARSED TEXT FOR PAGE: 3 / 3>
5. Incident triggers containment, preservation, escalation and recovery runbook

Alternative and abuse paths
MFA unavailable; privilege escalation; compromised admin; audit storage outage

Traceability
FR-003, FR-015, FR-018



Deferred future journeys — documented, not authorized for MVP
   Business owner claims listing → identity verification → service completion evidence → customer
    review → fraud checks.
   Organizer creates event → approval → ticket inventory → payment provider checkout → signed
    webhook → issued QR → single redemption → refunds/reconciliation.
   Finance officer reconciles finalized ad revenue → approved reward pool → monetary journal →
    dual approval → payout provider → settlement and exception handling.
   All future journeys require separate threat modeling, legal/provider validation and release
    approval.