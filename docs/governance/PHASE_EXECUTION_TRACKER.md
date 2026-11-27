# KoloVibe phase execution tracker

**Read this file first when resuming work.** It tracks execution under the [full application mandate of 27 November 2026](Full_Application_Mandate_2026-11-27.md) ("the mandate"). Then check the repository state (`git log origin/main`, open pull requests and issues) before acting. GitHub Issues are the authoritative work and defect tracker (mandate section 7); each phase has a milestone, and [#301](https://github.com/Markcino/KoloVibe/issues/301) tracks the phases. This file points to them and does not copy them.

Established 27 November 2026 at `37c5a44` (after #299). Updated 27 November 2026 in Phase 1, from `1c706ce` (after #303). This file merges the two trackers that #302 and #303 created (they differed only in letter case); the removed copy is in Git history at `79d69eb`.

## 1. Current gate

| Item | State |
| --- | --- |
| Current phase | **Phase 1, full-product reconciliation: verdict BLOCKED on owner approval of the five requirement sets** (see [report](phases/PHASE-01_Full_Product_Reconciliation_Report.md)). Authorized 27 November 2026, 11:12 UTC. Closure instruction 12:13 UTC: the sets FP-NT, FP-PAY, FP-GA, FP-DST and FP-CM are written (PROPOSED); Phase 1 passes when the owner approves them |
| Phase 2 | **NOT STARTED.** Formal Phase 2 is architecture, contracts and decisions (section 2, milestone 7). It starts only after Phase 1 is PASS, and then only with read-only and repository-side work; every staging write needs its own approval (owner, 12:13 UTC). The owner's 11:40 UTC message produced a **read-only staging inspection** ([record](phases/PHASE-02-ENTRY_Staging_Infrastructure_Inspection_2026-11-27.md), PR #327), first titled a "Phase 2 report"; it was reclassified at 12:13 UTC as input to the Phase 2 entry staging sequence and to Phase 9. Its plans A to G stay unexecuted |
| Next phase | Phase 2 entry is authorized by the owner's 12:13 UTC message **conditional on Phase 1 PASS**, read-only and repository-side only. Phase 3 is not authorized |
| Production | NO-GO. Nothing here authorizes deployment, live payments, live advertising, destructive data changes or production publication (mandate section 8) |
| Infrastructure access | Claude's **cloud** sessions have no SSH to staging. Sessions on the owner's Mac (Remote Control) can reach `ssh swarm-manager` and `ssh swarm-worker`; the read-only check ran that way on 27 November 11:42–11:55 UTC ([read-only check](../operations/R1_AWS_Staging_Readonly_Check_2026-11-27.md)). Any staging write still needs a concrete plan and the owner's explicit yes |

## 2. Status vocabulary

**Phase status:** NOT STARTED, IN PROGRESS, then one verdict: PASS, FAIL or BLOCKED. **Test and evidence results:** PASS, FAIL, BLOCKED, NOT RUN, SKIPPED, PARTIAL, NOT IMPLEMENTED. Results from different builds are never added together. BLOCKED, NOT RUN, SKIPPED and PARTIAL never count as PASS.

**Requirement classification** (the standing directive's terms; earlier terms in brackets):

| Classification | Meaning |
| --- | --- |
| Accepted with evidence | Acceptance criteria passed in the target environment, with linked evidence [VERIFIED COMPLETE] |
| Ready for comprehensive testing | Whole chain built with development tests; waits for staging or device acceptance [IMPLEMENTED BUT UNVERIFIED] |
| Development complete | Code, contracts and development tests done; integration or deployment not yet proven [IMPLEMENTED BUT UNVERIFIED] |
| Partial | Some links of the chain are missing [PARTIALLY IMPLEMENTED] |
| Missing | Not built [NOT IMPLEMENTED] |
| Blocked by approval | Waits on a named owner decision |
| Defective | Built, but fails its criteria [DEFECTIVE, SECURITY BLOCKER] |
| Explicitly excluded | Out of scope by owner decision [NOT APPLICABLE] |

A feature takes the classification of its weakest link: Requirement → Architecture → Database → Backend → API → Gateway → Authorization → Flutter/Web → Integration → Tests → Deployment → Acceptance evidence.

## 3. Phase plan

The owner's Phase 1 instruction refers to Phases 2 to 11, so the plan has eleven phases. The sixteen phases proposed in #302 are folded into these eleven (the right-hand column) rather than kept as a second list. The plan is decision GD-08, **approved** by the owner on 27 November at 11:31 UTC with GD-01 to GD-07 ([gate register](phase1/PHASE-01_Governance_Gate_Register.md)).

| # | Phase | Milestone | Main exit criteria | Earlier proposal folded in | Status |
| --- | --- | --- | --- | --- | --- |
| 1 | Full-product reconciliation | — (#301) | Owner's nine Phase 1 exit criteria | 0 governance, 1 reverification | **BLOCKED**: requirement sets written, owner approval pending (#307) |
| 2 | Architecture, contracts and decisions | [Phase 2](https://github.com/Markcino/KoloVibe/milestone/7) | Approved ADRs for Finance, Events, Advertising and Notifications; one canonical API and event contract; requirement sets FP-NT, FP-PAY, FP-GA, FP-DST approved; Figma frames for new areas; Stage 1 and 2 sign-offs (#133, #134, #140, #141) | 2 decisions, 3 architecture | NOT STARTED |
| 3 | Core platform completion | [Phase 3](https://github.com/Markcino/KoloVibe/milestone/8) | Identity, Creators, Content, Engagement, Points, Moderation, Audit, Privacy and Notifications reach Ready for comprehensive testing; D13-001 to D13-003 resolved | 4 core | NOT STARTED |
| 4 | Business completion | [Phase 4](https://github.com/Markcino/KoloVibe/milestone/9) | Business sensitive actions per decisions; staging plan | 5 Business | NOT STARTED |
| 5 | Finance, payments and payouts (sandbox) | [Phase 5](https://github.com/Markcino/KoloVibe/milestone/10) | Finance service and ledger; revenue records; creator pool; provider in sandbox; payouts; Finance console | 6 Finance | NOT STARTED |
| 6 | Events and ticketing | [Phase 6](https://github.com/Markcino/KoloVibe/milestone/11) | Events service; sandbox ticketing posting to Finance; QR check-in; console | 7 Events | NOT STARTED |
| 7 | Advertising, sponsorship and Google mobile ads | [Phase 7](https://github.com/Markcino/KoloVibe/milestone/12) | Advertising service; direct campaigns; billing facts to Finance; Google Mobile Ads in test mode | 8 Advertising | NOT STARTED |
| 8 | Flutter, console and distribution readiness | [Phase 8](https://github.com/Markcino/KoloVibe/milestone/13) | Screens for every role and area; Figma parity (#100); console acceptance (#153); Android and iOS release builds and store packages (#166) | 9 Flutter, 10 console | NOT STARTED |
| 9 | Security, privacy and infrastructure hardening | [Phase 9](https://github.com/Markcino/KoloVibe/milestone/14) | ASVS and MASVS evidence (#159); least privilege (#146); provenance (#147); observability (#145); backups (#144); branch protection (#142); scan exceptions (#143); capacity (#274) | 11 security, 12 infrastructure | NOT STARTED |
| 10 | Completeness gate and comprehensive testing | [Phase 10](https://github.com/Markcino/KoloVibe/milestone/15) | Every in-scope row Ready for comprehensive testing; staging acceptance (#155 to #157); devices (#158); load (#160); penetration test (#161); rollback drill (#162) | 13 gate, 14 testing | NOT STARTED |
| 11 | Defect closure, release readiness and store submission | [Phase 11](https://github.com/Markcino/KoloVibe/milestone/16) | Defects fixed with failing-first tests and full regression; legal sign-off (#165); readiness review (#164); rollout plan (#163, #167); go/no-go (#168) | 15 defects, 16 release | NOT STARTED |

Phases 3 to 8 may run tasks in parallel once their Phase 2 dependencies are approved, but each phase closes only through its own gate and the owner's authorization.

### Phase register

| Phase | Started at | Ended at | Verdict | Completion report | Next phase authorized |
| --- | --- | --- | --- | --- | --- |
| 1 | `1c706ce` | this PR's merge commit | **BLOCKED** | [PHASE-01 report](phases/PHASE-01_Full_Product_Reconciliation_Report.md) | No |

### Templates

**Phase completion report (mandate section 11):** phase name and number · starting commit · final commit · requirements completed · files changed · GitHub issues created, updated and closed · pull requests and CI results · database migrations · infrastructure changes · tests executed · PASS, FAIL, BLOCKED and NOT RUN counts · evidence locations · security findings · remaining defects · decisions required · rollback instructions · final gate verdict · whether the next phase is authorized. Reports live in [`phases/`](phases/).

**Missing decision (mandate section 8):** decision ID · exact blocking requirement · why it is necessary · options · recommended option · security, financial and operational implications · consequences of delay · exact approval wording.

## 4. How the mandate fits with earlier work

Earlier mandates used their own numbering ("Phases 00 to 14" of 25 November; "Remediation" items 1.1 to 4.6 of 27 November). They are cited with a prefix, for example "remediation 3.4". Their detail stays in [EXECUTION_PROGRESS.md](../engineering/reverification/EXECUTION_PROGRESS.md), now archived in place.

### 4.1 Decisions that stay in force

See the [gate register, section 1](phase1/PHASE-01_Governance_Gate_Register.md#1-already-approved-for-development-not-asked-again). They are not asked again.

### 4.2 Where the mandate changes earlier instructions

See the [scope baseline, section 2](phase1/PHASE-01_Full_Product_Scope_Baseline.md#2-mvp-only-restrictions-removed-from-active-planning).

### 4.3 Carried-over work and where it now sits

| Earlier item | State at `1c706ce` | Phase and issue |
| --- | --- | --- |
| Packages A, B, E, F, G, SIM fixes, static policies page (#234 to #259) | Merged; mostly in v0.542.1; not accepted | Matrix rows; acceptance in Phase 10 (#155) |
| Remediation 1.1 OpenSSL scan exception | Renewed to **5 December**; not renewed silently | Phase 9, #143 |
| Remediation 1.2 CPU budget (#283) | Package ready; measurement NOT RUN | Phase 9, #274 |
| Remediation 1.3 / 2.1 Points to Audit key (#281) | Plan ready; NOT APPLIED | Phase 3, #271 |
| Remediation 1.4 ruleset (#279) | Plan ready; NOT APPLIED | Phase 9, #142 |
| Remediation 1.5 release read-back (#287, #288) | NOT RUN on VM1 at `1c706ce`; **RUN read-only on 27 November 11:42–11:55 UTC**: every running service is v0.542.1 ([read-only check](../operations/R1_AWS_Staging_Readonly_Check_2026-11-27.md), PR #327) | Done for Phase 1; release of `main` is Phase 2 entry plan D, needs approval |
| Remediation 2.2 Content and Creators audit delivery (#292) | NOT DEPLOYED | Phase 3, #272 |
| Remediation 2.3 audit alerting (#293) | Signals built; channel NOT IMPLEMENTED | Phase 9, #145 |
| Remediation 3.1 erasure wiring (#294) | NOT DEPLOYED | Phase 3, #273 |
| Remediation 3.2 untracked media and retention policy (#295, #296) | Merged; values open | Phase 3, #136 |
| Remediation 3.3 access export (#297 to #299) | Merged; window and withheld categories open | Phase 3, #152 |
| Remediation 3.4 restore-safe recovery (#300) | **Merged** at 11:04 UTC; recovery contract PROPOSED; staging restore NOT RUN | Phase 3, #152; Phase 9, #144 |
| Remediation 3.5 lifecycle and completion notice | NOT STARTED | Phase 3, #310 |
| Remediation 4.1 stalled video, 4.2 end-to-end staging proof, 4.3 client address and rate limits, 4.4 legacy broker account, 4.5 dead letters, 4.6 acceptance items | NOT STARTED | #149; #156; #325; #146; #311; #155 |
| Staging inspection plans A to G (capacity, stale jobs, broker account, release from `main`, VM1 ingress with rate limits, rollback drill, Points audit key) | Prepared, NOT APPLIED ([inspection](phases/PHASE-02-ENTRY_Staging_Infrastructure_Inspection_2026-11-27.md) section 8); 24-hour capacity measurement ends about 11:58 UTC on 28 November | Phase 2 entry sequence (each needs its own approval); Phase 9 |
| Events (H), Advertising (I), Finance (J) | Design packages PROPOSED; no code | Phases 5 to 7, #313 to #323 |

## 5. Governance files

The [documentation index](../README.md) names the canonical source for every subject. The governance files are [`AGENTS.md`](../../AGENTS.md) (with [`CLAUDE.md`](../../CLAUDE.md) and [`.github/CLAUDE.md`](../../.github/CLAUDE.md) pointing to it), the [mandate](Full_Application_Mandate_2026-11-27.md), this tracker, the [Phase 1 records](phase1/) and the [phase reports](phases/).
