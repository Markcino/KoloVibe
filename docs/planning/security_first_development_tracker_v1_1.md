> Source: security_first_development_tracker_v1_1.xlsx (text export; original formatting, formulas and embedded images are not included). Original review status is retained.

index,SECURE PLATFORM — DELIVERY DASHBOARD,Unnamed: 1,Unnamed: 2,Unnamed: 3,Unnamed: 4,Unnamed: 5
0,,,,,,
1,Project start,2026-11-02 00:00:00,,Work status,Count,
2,Pilot target,2027-02-19 00:00:00,,Not Started,30,
3,Planned weeks,16,,In Progress,0,
4,Total tasks,30,,Blocked,0,
5,Completed tasks,0,,Done,0,
6,Completion rate,0,,,,
7,,,,,,
8,,,,,,
9,STAGE,TASKS,DONE,COMPLETION,START WEEK,END WEEK
10,1,4,0,0,1,2
11,2,4,0,0,2,3
12,3,5,0,0,3,5
13,4,7,0,0,5,12
14,5,5,0,0,4,15
15,6,3,0,0,15,16
16,7,2,0,0,16,16
17,,,,,,
18,,,,,,
19,TRACKING RULES,,,,,
20,Update Task Tracker status and percent complete at least twice weekly,,,,,
21,"Blocked tasks require an owner, reason and mitigation in Notes",,,,,
22,Do not mark a security gate Done without test evidence,,,,,
23,Rebaseline dates explicitly if dependencies or scope change,,,,,
<PARSED TEXT FOR SHEET: 2 / 6 TABS
TAB NAME: Task Tracker>
index,ID,Stage,Task,Start,Due,Owner,Priority,Status,% Complete,Dependency,Deliverable / Evidence,Notes,Days Remaining,Schedule Health
0,T001,1,Approve product vision and stakeholders,2026-11-02,2026-11-06,Product owner,Critical,Not Started,0,—,Vision + stakeholder register,,9,Upcoming
1,T002,1,"Interview creators, viewers, businesses and organizers",2026-11-02,2026-11-13,Product owner,High,Not Started,0,Stakeholders,Interview notes,,16,Upcoming
2,T003,1,"Define roles, journeys, business rules and MVP scope",2026-11-02,2026-11-13,Product owner,Critical,Not Started,0,Interviews,Role matrix and scope,,16,Upcoming
3,T004,1,"Write PRD, SRS and acceptance criteria",2026-11-09,2026-11-13,Product owner,Critical,Not Started,0,Scope,PRD / SRS approved,,16,Upcoming
4,T005,2,Map sensitive data and trust boundaries,2026-11-09,2026-11-20,Tech lead,Critical,Not Started,0,PRD,Data flow diagrams,,23,Upcoming
5,T006,2,STRIDE threat model and abuse cases,2026-11-09,2026-11-20,Security lead,Critical,Not Started,0,Data flows,Threat register,,23,Upcoming
6,T007,2,Design database ERD and financial/points boundaries,2026-11-16,2026-11-20,Backend lead,Critical,Not Started,0,Threat model,ERD + ledger design,,23,Upcoming
7,T008,2,Define MASVS/ASVS matrix and API contracts,2026-11-16,2026-11-20,Security lead,Critical,Not Started,0,Architecture,Controls + OpenAPI,,23,Upcoming
8,T009,3,"Create repositories, branch protections and CI checks",2026-11-16,2026-11-20,Tech lead,Critical,Not Started,0,Architecture,Secure Git + CI,,23,Upcoming
9,T010,3,"Bootstrap Django, DRF, PostgreSQL and migrations",2026-11-16,2026-11-27,Backend lead,Critical,Not Started,0,Repository,Running backend,,30,Upcoming
10,T011,3,"Implement identity, roles, MFA and audit logging",2026-11-23,2026-12-04,Backend lead,Critical,Not Started,0,Backend,Identity + audit tests,,37,Upcoming
11,T012,3,"Bootstrap Flutter, Django templates and staging",2026-11-23,2026-12-04,Mobile/Web lead,High,Not Started,0,API,Running clients + staging,,37,Upcoming
12,T013,3,"Secrets, backups, monitoring and deploy pipeline",2026-11-30,2026-12-04,DevOps,Critical,Not Started,0,Staging,Repeatable deployment,,37,Upcoming
13,T014,4,Creator registration and profile management,2026-11-30,2026-12-11,Full-stack team,High,Not Started,0,Identity,Creator onboarding,,44,Upcoming
14,T015,4,Secure media uploads and moderation,2026-12-07,2026-12-25,Full-stack team,Critical,Not Started,0,Profiles,Upload + moderation flow,,58,Upcoming
15,T016,4,Video playback and content discovery,2026-12-14,2027-01-01,Mobile/Web lead,High,Not Started,0,Uploads,Feed and playback,,65,Upcoming
16,T017,4,Qualified views and likes verification,2026-12-21,2027-01-08,Backend lead,Critical,Not Started,0,Playback,Fraud-aware engagement,,72,Upcoming
17,T018,4,Points ledger and read-only rewards dashboard,2027-01-04,2027-01-15,Backend lead,Critical,Not Started,0,Verification,Auditable points,,79,Upcoming
18,T019,4,AdMob/AdSense test integration and privacy controls,2027-01-11,2027-01-22,Mobile/Web lead,High,Not Started,0,Consent design,Ad test build,,86,Upcoming
19,T020,4,Admin moderation and fraud-review workflows,2027-01-11,2027-01-22,Full-stack team,Critical,Not Started,0,Engagement,Review console,,86,Upcoming
20,T021,5,Continuous unit/integration/API security tests,2026-11-23,2027-02-12,QA/Security,Critical,Not Started,0,Implementation,Test evidence,,107,Upcoming
21,T022,5,MASVS Flutter mobile security assessment,2027-01-18,2027-02-05,Security lead,Critical,Not Started,0,Flutter features,MASTG results,,100,Upcoming
22,T023,5,ASVS Django/API verification and abuse tests,2027-01-18,2027-02-05,Security lead,Critical,Not Started,0,Backend features,ASVS results,,100,Upcoming
23,T024,5,"Load, backup restore, incident and fraud exercises",2027-01-25,2027-02-12,QA/DevOps,Critical,Not Started,0,Staging,Recovery + fraud reports,,107,Upcoming
24,T025,5,Remediate findings and approve pilot readiness,2027-02-08,2027-02-12,Tech/Security leads,Critical,Not Started,0,All tests,Signed release gate,,107,Upcoming
25,T026,6,Deploy restricted pilot and onboard participants,2027-02-08,2027-02-19,Product/DevOps,High,Not Started,0,Release gate,Pilot deployed,,114,Upcoming
26,T027,6,"Monitor costs, incidents and engagement quality",2027-02-08,2027-02-19,Operations,Critical,Not Started,0,Pilot,Pilot metrics,,114,Upcoming
27,T028,6,Pilot go/no-go review and retrospective,2027-02-15,2027-02-19,Product owner,Critical,Not Started,0,Pilot metrics,Decision + action list,,114,Upcoming
28,T029,7,"Patch cadence, fraud operations and support",2027-02-15,2027-02-19,Operations,Critical,Not Started,0,Pilot,Operations runbook,,114,Upcoming
29,T030,7,"Prioritize business, ticketing and payout phases",2027-02-15,2027-02-19,Product owner,High,Not Started,0,Pilot findings,Next release backlog,,114,Upcoming
<PARSED TEXT FOR SHEET: 3 / 6 TABS
TAB NAME: Weekly Schedule>
index,Week,Start,End,Focus,Milestone / Exit Evidence,Stage,Owner,Status
0,1,2026-11-02,2026-11-06,Discovery kickoff; stakeholder map,Product vision and interview plan,1,Product owner,Not Started
1,2,2026-11-09,2026-11-13,Requirements and initial threats,Approved PRD/SRS and user roles,1,Product owner,Not Started
2,3,2026-11-16,2026-11-20,"Threat model, ERD and API design",Architecture/security review,2,Tech lead,Not Started
3,4,2026-11-23,2026-11-27,Django/Flutter foundation,Identity + API skeleton,3,Tech lead,Not Started
4,5,2026-11-30,2026-12-04,"MFA, staging, CI/CD and backups",Secure foundation gate,3,Tech lead,Not Started
5,6,2026-12-07,2026-12-11,Creator profiles and upload design,Creator onboarding demo,4,Full-stack team,Not Started
6,7,2026-12-14,2026-12-18,Secure uploads and moderation,Upload pipeline demo,4,Full-stack team,Not Started
7,8,2026-12-21,2026-12-25,Playback and feed,Video journey demo,4,Mobile/Web lead,Not Started
8,9,2026-12-28,2027-01-01,Engagement verification,Fraud scenarios tested,4,Backend lead,Not Started
9,10,2027-01-04,2027-01-08,Engagement and points,Qualified events demo,4,Backend lead,Not Started
10,11,2027-01-11,2027-01-15,"Points dashboard, ad test setup",Ledger integrity demo,4,Backend lead,Not Started
11,12,2027-01-18,2027-01-22,Moderation and ad integration,Feature-complete MVP candidate,4,Full-stack team,Not Started
12,13,2027-01-25,2027-01-29,MASVS/ASVS assessments,Initial security reports,5,Security lead,Not Started
13,14,2027-02-01,2027-02-05,Security fixes and resilience tests,Risk remediation evidence,5,Security lead,Not Started
14,15,2027-02-08,2027-02-12,Pilot readiness and deployment,Go/no-go security gate,6,Tech lead,Not Started
15,16,2027-02-15,2027-02-19,Pilot observation and retrospective,Pilot report and next roadmap,7,Product owner,Not Started
<PARSED TEXT FOR SHEET: 4 / 6 TABS
TAB NAME: Release Gates>
index,Gate,When,Required evidence,Decision owner,Decision
0,G1 — Scope approved,End W2,PRD/SRS; prioritized backlog; acceptance criteria,Product owner,Pending
1,G2 — Architecture approved,End W3,Threat model; ERD; API contracts; MASVS/ASVS mapping,Tech + Security,Pending
2,G3 — Foundation ready,End W5,Auth tests; CI; secrets; staging; backups,Tech lead,Pending
3,G4 — MVP feature complete,End W12,Creator journey; moderation; points tests,Product + Tech,Pending
4,G5 — Security approved,End W15,MASVS/ASVS evidence; fraud tests; restored backups; findings review,Security lead,Pending
5,G6 — Pilot evaluated,End W16,Pilot metrics; incident log; cost measurements; go/no-go,Product owner,Pending
6,G7 — Cash payout launch,Later release,Provider contracts; compliance review; reconciled ledger; independent test,Finance + Security,Not in MVP
<PARSED TEXT FOR SHEET: 5 / 6 TABS
TAB NAME: Instructions>
index,HOW TO USE THIS TRACKER,DETAILS
0,1. Set ownership,Replace generic roles with assigned individuals in Task Tracker.
1,2. Review dependencies,Confirm prerequisite tasks and adjust dates if necessary.
2,3. Update execution,"Edit Status, % Complete, and Notes on the Task Tracker."
3,4. Weekly check-in,Use Weekly Schedule for sprint planning and Friday reviews.
4,5. Review gates,Record evidence and formal decision on Release Gates.
5,6. Read dashboard,Dashboard automatically calculates task completion.
6,7. Rebaseline,"If scope changes, revise schedule and record reason in Notes."
7,Security reference,https://mas.owasp.org/MASVS/
8,Backend security reference,https://owasp.org/www-project-application-security-verification-standard/
9,Planning assumption,16 weeks; two developers + product owner + part-time QA/security; no cash payouts in pilot.
<PARSED TEXT FOR SHEET: 6 / 6 TABS
TAB NAME: Decisions & Documents>
index,Type,ID,Item / decision,Status,Owner,Recorded / due,Evidence / next action
0,Decision,DEC-001,"R1 scope: accounts, creators, media, verified engagement, non-cash points, moderation; defer business, tickets, cash payouts",Approved,Product owner,2026-10-28,Explicit user approval; see PRD/SRS v0.2
1,Document,DOC-001,PRD v0.2,Scope approved; details draft,Product owner,2026-11-13,Review detailed business rules
2,Document,DOC-002,SRS v0.2,Scope approved; details draft,Technical lead,2026-11-13,Review acceptance criteria
3,Document,DOC-023,Documentation register and decision log,Active,Product owner,2026-10-28,Maintain versioned decision trail
4,Decision,DEC-002,Final product name / entity,Open,Product owner,2026-11-06,Confirm naming
5,Decision,DEC-003,"Qualified views, likes and points formula",Open,Product + security,2026-11-13,Specify fraud-resistant rule
6,Decision,DEC-004,Creator eligibility / age verification,Open,Product owner,2026-11-13,Document eligibility
7,Decision,DEC-005,Copyright / appeals / privacy,Open,Product + legal,2026-11-20,Legal review
8,Decision,DEC-006,Pilot cohort and Android/iOS,Open,Product owner,2026-11-13,Confirm test scope