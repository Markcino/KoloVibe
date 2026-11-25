# Phase 11 — comprehensive UAT preparation checklist

**Status: prepared 25 November 2026; testing NOT started and NOT authorized.** Companion to the [Phase 10 report](Phase10_Platform_Integration_Report_2026-11-25.md). Production is NO-GO; passing UAT does not change that. This list does not replace the existing [iPhone checklist](../iphone_e2e_checklist.md), [iPhone run card](../iphone_run_card.md), [Android checklist](../android_e2e_checklist.md), [staging administrator and MFA record](../../operations/Staging_Administrator_Promotion_and_Web_MFA.md) or [release gates](../../operations/R1_Consolidated_Release_Gates_2026-11-14.md); it says what must be true before they are run, and what they should cover that earlier phases did not.

## A. Needed before testing starts (owner)

| # | Item | Why it blocks | Owner |
| --- | --- | --- | --- |
| A1 | **Authorize Phase 11** and state its environment (AWS staging, which build) | Nothing was deployed or tested outside this machine | Owner |
| A2 | **Read back the AWS instance size** and authorize a read-only capacity check | Never recorded or measured; every sizing statement in the repo is a planning figure | Owner |
| A3 | **Database role ownership (R-01):** decide the remediation model; the 23 November audit found 26 tables and 8 sequences owned by runtime roles | Isolation tests prove roles are separate, not that ownership is safe | Owner |
| A4 | **RabbitMQ read-back and permissions.** Read `list_permissions` on the live vhost and compare with `BROKER_PERMISSIONS` in `scripts/ops/generate_r1_secrets.py` (proved on a real broker in Phase 10); decide whether to adopt it. Confirm the Points exchange and queues exist before Engagement publishes | Live accounts were provisioned differently from the generator and were never inspected | Owner |
| A5 | **Dead-letter and poison-message handling** for `kolovibe.points`: configure or accept the risk | Currently none | Owner |
| A6 | **Cloudflare R2** bucket, credentials, lifecycle and CORS-free signed access; **FFmpeg worker** node and memory limit | Real R2 was never exercised; the worker runs untrusted media | Owner |
| A7 | **SMTP delivery** and the sender domain | Registration, verification and reset depend on mail | Owner |
| A8 | **Which capabilities are open in staging.** R1 list: `account_management`, `moderation`, `media`, `analytics`, `engagement`, `points`, `watch`, `audit_read`. **Business is not in the staging capability set** (it is dark by design): decide whether Business is in UAT; if yes, the capability table and rollout table need a reviewed code change first | Defines the UAT scope | Owner |
| A9 | **Decide M-1** (Creators and Content audit delivery) before the audit-history tests, or accept that creator and video events will be absent from the history | Otherwise the audit tests will report a known gap as a finding | Owner |
| A10 | **Decide M-3**: schedule `requeue_stalled_media`, `purge_expired_security_rows` and `purge_expired_web_sessions`, or document the manual run | Stalled media and unbounded expired rows | Owner |
| A11 | **Test devices and builds:** at least one iPhone and one Android phone; build the app with Flutter **3.47.8** against the staging Gateway URL (`KOLOVIBE_API_URL`) | Phase 10 mobile results are widget tests only; no device has run the app | Owner |
| A12 | **Backup and restore.** No backup of PostgreSQL or the broker exists and none was ever restored | A restore drill is a release gate | Owner |
| A13 | **Independent security test** scope and tester | Phase 10 was not a penetration test | Owner |

## B. Scope

**In scope for Phase 11 (Ready for comprehensive UAT):** accounts and sessions; roles and invitations; creator onboarding; upload to playback; likes and qualified views; points ledger and history; reports, moderation, appeals, copyright pipeline; privileged console security; audit read (with A9); the Engagement-to-Points event path; and, only if A8 says so, the Business module.

**Out of scope (not implemented or not approved):** events, ticketing, advertising, revenue accounting, sandbox payouts and their console pages and screens; Business sensitive actions (step-up); any image upload; notifications; privacy export, deletion and retention; creator restriction write path; copyright claimant intake in the app; live streaming; any public website. A UAT report must list these as *not tested because not built*, not as passed.

## C. Environment preparation

1. Seed accounts per role: viewer, creator (invited and approved), moderator with and without assignment, administrator with MFA, a second creator and a second viewer for cross-account tests; and, if Business is in scope, owner, staff, customer and a reviewer with and without grants.
2. Seed content: published, in-review, rejected and removed videos across two creators; reports and appeals in each state.
3. Mail capture or a mailbox for verification codes and invitations.
4. Provision the broker topology before the first publish: exchange and queue `kolovibe.points`, `kolovibe.engagement`, `kolovibe.content.media`.
5. Read back, record and do not print: service identity keys per audience (each distinct), database roles, TLS CA, broker URIs.
6. Time source: all services on synchronized time (the service identity window is ±60 s).
7. Evidence folder per run: build id, commit, image digests, date, tester, device, OS version.

## D. What each journey must cover (beyond the earlier checklists)

| Journey | Required checks |
| --- | --- |
| Viewer | Register, verify, sign in, force-close and restore session (SEC-05), browse, search, play, like, report, sign out everywhere; airplane mode and slow network states; text size 2x; screen reader on the main flow |
| Creator | Apply, onboarding, upload at the size limit and over it, interrupted upload, processing success and failure, moderation outcome, publication, unpublish, analytics, points balance after a qualified view, replayed view gives no second award, daily cap |
| Moderator | Queue visibility only for assigned scope, decision with reason, second reviewer on appeal, MFA required, session expiry (15 and 30 minutes), CSRF |
| Administrator | Invitation of a moderator with QR enrolment, creator approval, assignment, audit read with redaction, points review read-only |
| Business (if in scope) | The 11 journey steps in `scripts/business_journey.py` on devices, plus staff removal showing the fail-closed message |
| Cross-account | A creator cannot read or change another creator's video, points or analytics; a customer cannot read another customer's inquiry; every attempt is refused with no existence leak |
| Replay and abuse | Replayed refresh token revokes the family; replayed qualified-view event changes nothing; duplicate delivery changes nothing; rate limits trigger |

## E. Operational checks (staging only)

1. **Broker:** consumer count 1 on `kolovibe.points`; publish one qualified view and watch the ledger; stop the broker, publish, restart, confirm one entry; confirm Engagement cannot consume `kolovibe.points` with its own credentials.
2. **Jobs:** the seven roles running and restarting after forced failure; the three unscheduled commands run by hand once, each logged.
3. **Rollback:** the documented rollback of one image; the data survives.
4. **Observability:** a forced error appears in logs without any token, code or email; health probes; alarms for broker memory and disk.
5. **Secrets:** rotation of one service identity key without downtime.

## F. Known issues the tester should expect (do not report as new)

M-1 (no Creators or Content audit events), M-2 (no app route for copyright claimants), M-3 (three unscheduled commands), 99 designed screens that are functional with a recorded deviation from the Figma export (8 are visually matched), M-045 not verified, profile photos absent, privacy export and deletion absent, Business sensitive actions refused, no notifications, no dead-letter queue.

## G. Exit criteria for Phase 11 (proposed)

1. Every in-scope journey passes on both device families, with evidence.
2. No open Critical or High finding; every Medium has an owner and a decision.
3. Cross-account and replay checks pass on staging, not only locally.
4. Backup and restore demonstrated once.
5. Items in section B "out of scope" are listed as untested.
6. The report states, in terms, that production remains NO-GO unless the owner separately decides otherwise.

## H. Not part of UAT

Real payments, payouts, ad networks, tax or legal sign-off, and any activation of the modules that exist only as design packages. Those need their own approvals.
