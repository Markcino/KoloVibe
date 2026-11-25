# Phase 11 — release-blocker list

**Date:** 25 November 2026. Production is **NO-GO** and nothing here changes that. This list separates what **must be fixed** (defects), what **must be proven** (gates not met because they could not be run here), and what **does not exist** (modules). "Blocker" means: the area it affects must not be exposed to users, or enabled in a shared environment, until it is closed or formally accepted by the owner.

## A. Defects that block

| ID | Blocks | Why | Closes when |
| --- | --- | --- | --- |
| **D11-002** (High) | Enabling any ledger or audit-bearing capability in a shared environment (Points, Audit read, and every future money module) | A service credential can switch off the append-only guards; the tamper-evidence design is void until ownership is separated (R-01) | Owner and runtime roles are separate; `T10_03` and `T10_04` pass; read-back on the staging database |
| **D11-001** (Medium) | Running the Points consumer (and, by the same pattern, the Engagement and Content consumers) outside a disposable environment | One malformed message permanently stops points awards; no dead-letter queue | `T3_35` passes; a dead-letter policy exists; the same check passes for the other two consumers |

## B. Defects to fix before production, but not blocking UAT preparation

| ID | Title | Note |
| --- | --- | --- |
| D11-003 | Registration reveals existing accounts | ADR-013 review topic; fix and update DOC-205 |
| D11-004 | No registration limit | Needs a policy value from the owner; also no edge limit in the repository's Nginx |
| D11-005 | Validation before authorization | Low |
| D11-006 | Console reflow at 320 px | Low |
| D11-007 to D11-009 | Creators and Content audit not delivered; copyright claimant intake has no client; three unscheduled maintenance commands | Carried from Phase 10; **not retested here** |

## C. Gates not met (nothing failed; they could not be run in this environment)

| # | Gate | Needs |
| --- | --- | --- |
| G-1 | **Physical iPhone and Android testing of every approved journey** (Group 8, 32 rows BLOCKED) | Devices, a build pointed at a staging Gateway, the existing checklists |
| G-2 | **Real Cloudflare R2 upload and playback** and the media worker against real storage | R2 credentials and authorization |
| G-3 | Deployed staging verification: versions and image digests, migrations on the staging database, health | Authorization to deploy or read AWS staging |
| G-4 | **Backup and restore of the real database** and broker definitions | A backup exists first (none does) |
| G-5 | Deployed broker permissions read-back, dead-letter policy | Owner broker access |
| G-6 | Container image vulnerability scans and Flutter dependency advisories | Build environment with a scanner; network access to OSV |
| G-7 | Capacity on the AWS instance (size unrecorded) and Swarm limit enforcement | Owner read-back |
| G-8 | Live edge: TLS, Cloudflare and Nginx rate limits, Gunicorn headers | Edge access |
| G-9 | Independent penetration test | Tester and scope |
| G-10 | Firefox, Safari, and screen-reader testing of the console | Browsers and assistive technology |
| G-11 | Alerting and monitoring | A monitoring stack |

## D. Modules that do not exist (scope, not defects)

Events and ticketing, Advertising, and Revenue and payouts exist only as unapproved design packages (Phases 7A, 8A, 9A). Their test groups (5, 6, 7: 32 rows) are NOT RUN. They cannot be released; each also depends on the owner decisions listed in those packages and on the shared prerequisites (Identity step-up, image pipeline, database role model, capacity, consent store, ledger ownership).

## E. Carried decisions that still gate release

Identity step-up (DR-BZ-33), image pipeline, consent and privacy records (ADR-020), notification delivery, retention, creator restriction write path, and the DOC-023 change requests, as in the Phase 10 report.
