# Phase 12 — defect remediation, regression testing and release readiness

**Date:** 25 November 2026. **Source:** branch `claude/blissful-albattani-81b81r` on top of Phase 11 source `384f4b5` (the commits listed in section 13). **Scope:** fix the Phase 11 defects, prove the fixes, rerun the applicable Phase 11 suite on the fixed build, and state whether the application can be released. **No deployment, no AWS or staging action, no production access, no real money moved.** A separate owner approval is required for any release deployment, and none is requested here.

## 0. Conclusion

> ## NOT READY — BLOCKERS REMAIN
>
> Seven gates are open (section 3). The most serious: **the staging database still has the old ownership** (D11-002 is fixed and verified in the repository, but not on the real database), **no phone has ever run the application**, **no backup of the real database exists or has ever been restored**, and **the per-origin abuse limits are switched off as deployed** (D12-001). This is a statement about evidence, not about the quality of the code: on the environment available here, the code passes everything that can be run.

**What would change it.** Closing blockers B1 to B5 and B7 (owner actions O-2, O-3, O-4, O-6, O-7, O-8, O-9) with evidence, and an owner decision on D11-003 (O-1), would support **READY ONLY FOR A RESTRICTED PILOT** (staging users on named devices). A general release additionally needs the items in section 3 table C. Neither state is approved by this document; both need the owner's written approval.

## 1. What was done

| Phase 12 step | Outcome |
| --- | --- |
| 1 Triage | All nine Phase 11 defects classified and root-caused: [defect register](Phase12_Defect_Register.md). One new finding, D12-001 |
| 2 and 3 Backend fixes | D11-001, D11-002 (repository side), D11-004, D11-005 fixed, each with a test that **failed before the fix** |
| 4 Mobile | No mobile defect was found in Phase 11; no mobile code changed. Flutter was still re-run (analyze clean, 1,823 tests) |
| 5 Web dashboard | D11-006 fixed; the console stays restricted to administrators and moderators (route-security matrix unchanged, 179 tests) |
| 6 Security regression | Every previously failed security case re-run; see section 5 |
| 7 Full regression | All applicable Phase 11 groups and baselines re-run on the fixed build; **no earlier PASS reused**: [matrix](Phase12_Test_Matrix.md), 244 rows |
| 8 Package | This report and the documents it links |

**Not fixed, on purpose.** D11-003 (registration `409`) is an approved design (ADR-013, screen M-012); changing it is the owner's decision. D11-007 and D11-008 are carried owner decisions. D11-009's scheduling needs an owner approval. No test was disabled, skipped or weakened to obtain a pass (defect register, section 3, lists every test change).

## 2. Test summary (all run on the fixed build)

| Suite | Result |
| --- | --- |
| **Phase 11 black-box groups** (real stack: TLS PostgreSQL, nine services, console, RabbitMQ, FFmpeg, Chromium) | **Groups 1, 2, 3, 4, 9, 10: 130 results, 129 PASS, 1 FAIL (T1_03, D11-003)**; plus 8 static rows: 6 PASS, 2 FAIL (T10_81, T10_87); plus 24 baseline rows, all PASS |
| Complete matrix | **244 rows: 159 PASS, 3 FAIL, 39 BLOCKED, 43 NOT RUN.** Phase 11 was 242 rows: 149 PASS, 11 FAIL |
| Nine service suites | 1,098 tests pass (Phase 11: 1,089), no migration drift |
| Console | 179 pass |
| Scripts | 468 pass (Phase 11: 459); includes the poison-message, runtime-role and R-01 conversion tests |
| TLS PostgreSQL | foundations 59 checks over nine services, Business and Audit 15, preflight and ownership report 17, R-01 conversion 1, all pass |
| Event pipeline | 8 pass; **real TLS RabbitMQ 7 pass** (adds the malformed-envelope regression) |
| Local journeys, staging runtime | 11 of 11 pass; staging runtime PASS |
| Flutter 3.47.8 | analyze clean; 1,823 tests pass (widget and unit; **not** a device) |
| Gates | Bandit 0 medium or high (229 low); secret scan passes; `pip-audit` 0 vulnerable in all four locks; OpenAPI valid; structure check passes |

**Honest notes on the run.** The first attempt of group 1 did not start because my broker helper generated a password beginning with `-`; fixed and re-run. `T10_31` and a few script checks encoded the old ownership model and were updated (not weakened). A group 10 run on its own fails `T10_90`, which needs the other groups' secrets in the same stack; the combined run passes. Raw results, including the superseded attempts, are in [`results/`](results/).

## 3. Open gates and remaining risks

### A. Blockers (a required security, data-integrity or functional gate is open)

| # | Blocker | Why it blocks | Closes when | Owner |
| --- | --- | --- | --- | --- |
| **B1** | **Staging database ownership not converted** (D11-002 on the real database) | A stolen service credential on staging can still switch off the ledger and audit guards. `T10_94` BLOCKED | O-3 then O-2 done, read-back shows no login-owned object, and `T10_03` and `T10_04` repeated on staging | Infrastructure owner, DBA |
| **B2** | **No device acceptance** (Group 8: 32 rows BLOCKED) | The mobile app has only run as widget tests. Real storage (Keychain, Keystore), session restore, playback, uploads and accessibility are unproven | iPhone and Android checklists passed with evidence (O-7) | Product owner with QA |
| **B3** | **No backup of the real database was ever taken or restored**; ADR-016 open; no RPO or RTO | A failed migration or the B1 conversion has no proven way back. The restore drill passes only on the disposable fixture (`T10_30`) | A restore of a real backup into a scratch database with row counts compared (O-6) | Infrastructure owner |
| **B4** | **Per-origin limits are inert as deployed** (D12-001) and the repository's Nginx has no rate limiting (`T10_81`, `T10_87`) | Sign-in, code and registration abuse controls count only when the Gateway knows the client address | O-4 done and tested through the real edge | Infrastructure owner |
| **B5** | **Real R2 and the media worker were never exercised** (G-2) | Upload, processing and playback against real storage is unproven | O-8 done and the upload-to-playback journey run on staging | Product owner (credentials) |
| **B6** | **D11-003 open** | Account enumeration through registration remains (bounded only by B4's budget, which is inert today) | Owner decision (O-1), then the prepared change is applied, or the risk is accepted in writing | Product owner |
| **B7** | **Broker permissions and dead-letter policy unread on the live broker** (G-5) | D11-001 now stops the crash loop, but a rejected message is discarded with no record | O-9 | Infrastructure owner |

### B. Fixed code that needs a deployment change (do not deploy without these)

1. **A migration login per service must exist before this build is deployed.** The runtime login can no longer alter tables (by design). Deploying without O-3 makes the next migration fail; the services themselves keep running. Order: `schema_isolation.sql`, create migration logins, switch the migration job (`KOLOVIBE_DB_MIGRATION_ROLE`), then convert ownership (runbook).
2. The registration budget (20 per hour per origin, shared with code emails) is a policy figure reused from an approved value; the owner should confirm it for shared mobile networks (O-5).

### C. Required before a general release (not before a restricted pilot)

D11-007 audit events for Creators and Content (O-10); D11-008 copyright claimant intake decision (O-11); scheduling of the three maintenance commands (O-12); AWS capacity read-back and a load and soak test (O-13); independent penetration test, container image scans and the OSV check in CI (O-14); Firefox, Safari and screen-reader checks of the console; alerting and monitoring.

### D. Not part of R1 (scope, not defects)

Events and ticketing, Advertising, and Revenue and payouts exist only as unapproved design packages: 32 matrix rows NOT RUN. No real payment, payout or ad network is enabled or implied.

### Remaining risks (summary)

| Risk | Rating | Note |
| --- | --- | --- |
| Tamper-evidence of ledger and audit on staging | High until B1 | Fixed in code, unverified live |
| Mobile behaviour on real devices | High until B2 | Widget tests are not a substitute |
| Unrecoverable data loss on migration | High until B3 | No restore ever proven on the real system |
| Abuse of sign-in, codes and registration | Medium until B4 | Budgets exist but are inert |
| Registration enumeration | Medium | D11-003 |
| Missing creator and content audit trail | Medium | D11-007 |
| Same engineers wrote the code and the tests | Medium | No independent test (O-14) |
| Single-host fixture scale | Unknown | No load or soak run; capacity unmeasured |

## 4. Final feature-completion matrix

Development status is carried from the [Phase 10 matrix](../phase10/Phase10_Platform_Integration_Report_2026-11-25.md) (no feature code changed in Phase 12 other than the fixes above). The right-hand column is the Phase 12 acceptance on **the evidence available**.

| # | Capability | Development | Phase 12 regression evidence | Acceptance |
| --- | --- | --- | --- | --- |
| 1 | Accounts, sessions, password, privileged MFA | Complete | Group 1: 42 of 43 pass (T1_03 open) | **Accepted in code**; B4, B6 open |
| 2 | Roles and permissions | Complete | Groups 1, 9; role matrix; console route matrix | **Accepted in code** |
| 3 | Creator profile and eligibility | Complete | Creators 84; group 2 | **Accepted in code** |
| 4 | Creator restriction write path | Not implemented (D-8) | — | Out of scope until approved |
| 5 | Upload, encoding, review, playback | Complete | Group 2 (real FFmpeg): 18 pass; R2 BLOCKED | **Not accepted**: B5 |
| 6 | Likes, views, qualification | Complete | Group 3 | **Accepted in code** |
| 7 | Non-cash points | Complete | Group 3 (cap, replay, outage, kill, broker restart, **poison message**) 20 pass | **Accepted in code**; B7 |
| 8 | Points adjustment and reversal | Excluded by SRS | — | Out of scope |
| 9 | Reports, moderation, appeals | Complete | Moderation 71; console; journeys | **Accepted in code** |
| 10 | Copyright pipeline | Partial (no claimant client) | Content, Gateway, journeys | **Partial** (D11-008) |
| 11 | Privacy intake, export, deletion | Partial, blocked by approval | Intake tests | **Partial** |
| 12 | Audit trail | Partial (M-1) | Audit 51 | **Partial** (D11-007) |
| 13 | Console security | Complete | Group 9: 19 pass incl. reflow | **Accepted in code**; browsers and screen reader NOT RUN |
| 14 | Service identity, default-deny | Complete | Group 10 perimeter; scripts | **Accepted in code** |
| 15 | Engagement-to-Points pipeline | Complete | Event pipeline 8, real broker 7 | **Accepted in code**; B7 |
| 16 | Scheduled and maintenance jobs | Partial | Runbook written | **Partial** (O-12) |
| 17 | Business module | Complete (dark by design) | Group 4: 13 pass; Business 232; journeys | **Accepted in code**; not in the staging capability set |
| 18 | Business sensitive actions | Not implemented | — | Out of scope |
| 19 | Images and evidence files | Not implemented | — | Out of scope |
| 20 to 23 | Events, ticketing, advertising, revenue and payouts | **Not implemented** (design only) | 32 rows NOT RUN | Out of scope |

"Accepted in code" means the automated and black-box evidence passes on a local disposable stack. It is **not** device, staging or production acceptance.

## 5. Security verification evidence

| Area | Evidence | Result |
| --- | --- | --- |
| Previously failed security cases | `T1_31` (order), `T1_94` (registration limit, with a trusted origin), `T3_35` (poison message), `T4_23` (Business order), `T10_03`, `T10_04` (guards, ownership) | **All PASS**; `T1_03` still FAIL (D11-003) |
| Authorization boundaries | Group 4: for every one of the 26 business-scoped operations a stranger gets the same answer as for a missing business; a refused actor now gets that answer for any body; console: 17 pages redirect anonymous visitors, moderator refused administrator pages | PASS |
| MFA and refresh | Group 1: challenge only, wrong code, TOTP replay, recovery code single use, exhausted challenge, forged challenge, refresh rotation and family revocation on replay | PASS |
| Object-level permissions | Creator A cannot reach creator B's video, points or analytics; customer cannot read another's inquiry | PASS |
| Audit logging | Audit 51 tests; Identity, Moderation, Points, Business deliver; Creators and Content do not (D11-007) | Partial |
| Media restrictions | Real FFmpeg: HLS and concat files that point at local files refused, appended bytes do not survive, metadata stripped, size and duration limits | PASS |
| Financial idempotency and integrity | Points ledger: append-only (now with the guard out of the service's reach), idempotent awards, daily cap, replayed events applied once. **No monetary module exists** | PASS for Points; nothing to test for money |
| Cross-business and cross-organizer isolation | Business as above; **no organizer module exists** | PASS for Business; organizer NOT RUN |
| Secrets | Over 40 harness secrets absent from every service log (`T10_90`); no database password in any process line | PASS |
| Static gates | Bandit, secret scan, `pip-audit` (0 vulnerable), OpenAPI | PASS |
| Edge | No Nginx rate limiting; trusted-header not configured | **FAIL** (B4) |
| Independent penetration test | Not performed | **NOT RUN** (O-14) |

## 6. Device acceptance summary

**BLOCKED, unchanged from Phase 11.** No iPhone, no Android device, no Xcode or Android SDK, no attached computer. All 32 Group 8 rows (16 areas, two platforms) stay BLOCKED with disposition *required before release* and owner *Product owner with QA*. The [iPhone checklist](../iphone_e2e_checklist.md), [run card](../iphone_run_card.md) and [Android checklist](../android_e2e_checklist.md) are ready. Flutter results are widget and unit tests only.

## 7. Migration and backup readiness

| Item | State |
| --- | --- |
| Migrations | 60, unchanged by Phase 12; `makemigrations --check` clean for all nine services and the console; apply, reverse and re-apply proven on a fresh TLS PostgreSQL (`T10_31`) as the new migration login; second `migrate` is a no-op |
| New prerequisite | One migration login per service in the owner role, and `KOLOVIBE_DB_MIGRATION_ROLE` on the migration job ([runbook](../../operations/R1_Database_Ownership_Remediation_Runbook.md)) |
| Conversion of an existing database | Script tested on a recreated legacy schema; **not run on staging** |
| Backup and restore | Fixture drill passes: dump, restore into a new database, row counts equal for every table, triggers present and the append-only guard still fires (`T10_30`). **No backup of the real database exists; none has been restored** (B3). RPO and RTO unset |

## 8. Release image provenance

**Not available.** No Docker daemon and no images were built or scanned here, so there are no image digests, no SBOM and no signature to report. What is pinned: source commit (section 13), dependency locks by hash: `requirements-dev.txt` `3ed1b2af…`, `requirements-ci.txt` `92de7ce8…`, `requirements-web.txt` `1c46a49e…`, `requirements-media.txt` `f9578448…`, `pubspec.lock` `38e9cc46…` (unchanged from Phase 11). Building, scanning and publishing the release image is CI's job and an owner step (O-14); the digest must be recorded before any deployment.

## 9. Operational runbooks

| Runbook | Status |
| --- | --- |
| [Deployment and rollback](../../operations/R1_Deployment_and_Rollback_Runbook_2026-11-14.md) | Existing; unchanged |
| [R-01 ownership remediation](../../operations/R1_Database_Ownership_Remediation_Runbook.md) | **New**, written, not executed |
| [Maintenance commands](../../operations/R1_Maintenance_Commands_Runbook.md) | **New**; manual procedure; scheduling not approved |
| [Staging administrator and MFA](../../operations/Staging_Administrator_Promotion_and_Web_MFA.md) | Existing |
| [Consolidated release gates](../../operations/R1_Consolidated_Release_Gates_2026-11-14.md) | Existing; this report is evidence against it, not a replacement |

## 10. Rollback plan

1. **Application:** re-pin the previous image digest (`docker service rollback` or the cluster tool's `rollback`); image rollback never reverses migrations. This build adds **no** migration, so rolling the images back is safe for the schema.
2. **Database ownership (B1):** restore from the pre-change restore point; never hand ownership back to a login. This is why B3 must close first.
3. **Migration job:** if the migration login is missing, keep the previous migration procedure until O-3 is done; the running services are unaffected.
4. **Poison-message guard:** reverting the commit restores the old crash behaviour; the guard does not change valid-message handling.
5. **Registration budget:** removing the `origin` forwarding in the Gateway disables it.
Evidence of a working rollback on staging does not exist yet: the documented rollback has not been exercised there.

## 11. Owner actions

| # | Action | Owner |
| --- | --- | --- |
| O-1 | Decide D11-003: keep the `409` (accept the risk in writing) or change registration and the M-012 flow | Product owner |
| O-2 | Run the R-01 conversion on staging with a verified backup; read back; repeat T10_03, T10_04, T10_94 | Infrastructure owner, DBA |
| O-3 | Create migration logins and switch the migration job (prerequisite of O-2) | Infrastructure owner, DBA |
| O-4 | Configure the trusted client-address header end to end (edge, Nginx pass-through, Gateway) and rate limits at the edge; test through the real edge | Infrastructure owner |
| O-5 | Confirm the registration budget (20 per hour per origin) | Product owner |
| O-6 | Back up the real database, restore into a scratch database, compare, set RPO and RTO (ADR-016) | Infrastructure owner |
| O-7 | Run the iPhone and Android acceptance checklists on devices against a staging build | Product owner with QA |
| O-8 | Provide R2 credentials, bucket and lifecycle; run upload-to-playback against real storage | Product owner |
| O-9 | Read back broker permissions against the generator; adopt a dead-letter policy | Infrastructure owner |
| O-10 | Decide and provision Creators and Content audit delivery (M-1, D11-007) | Product owner |
| O-11 | Decide copyright claimant intake (D11-008) | Product owner |
| O-12 | Approve scheduling of the three maintenance commands | Infrastructure owner |
| O-13 | Read back AWS instance size; approve a load and soak test | Infrastructure owner |
| O-14 | Commission an independent penetration test; run image scans and the OSV check in CI; record the release image digest | Product owner, Engineering (CI) |

## 12. Release approval checklist

Nothing below is approved. Each line needs a named approver, a date and evidence; an unticked line means the gate is open.

- [ ] B1 database ownership converted on staging, read-back attached
- [ ] B2 device acceptance passed on iPhone and Android
- [ ] B3 backup restored from the real database, RPO and RTO recorded
- [ ] B4 trusted client address and edge rate limits configured and tested
- [ ] B5 real R2 upload-to-playback passed
- [ ] B6 D11-003 decided
- [ ] B7 broker permissions read back, dead-letter policy decided
- [ ] Release image built, scanned and its digest recorded
- [ ] Rollback exercised on staging
- [ ] Owner written approval for **restricted pilot** or **controlled release**
- [ ] Separate owner authorization for deployment (not given)

## 13. Commits in this phase

`384f4b5` Phase 11 source. Phase 12 changes: poison-message guard and Business, Identity, Gateway authorization ordering; ownership split, registration budget, console CSS and runbook; harness adjustments; defect register and results; matrix generator; this report. `git log 384f4b5..HEAD` lists them; they are on `claude/blissful-albattani-81b81r`.

## 14. Stop point

**STOP AFTER PHASE 12.** No deployment was started or requested. A separate owner approval is required for release deployment.
