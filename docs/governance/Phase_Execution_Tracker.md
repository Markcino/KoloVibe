# KoloVibe phase execution tracker

**Read this file first when resuming work.** Then check `git log origin/main` and the open pull requests before acting. This tracker governs the [full application mandate](Full_Application_Mandate_2026-11-27.md) of 27 November 2026 and is mirrored by GitHub issue [#301](https://github.com/Markcino/KoloVibe/issues/301).

Updated: 27 November 2026, `main` at `37c5a44` (after #299). Staging last recorded at **v0.542.1** on 16 application services ([record](../operations/R1_AWS_Staging_Verification_2026-11-26.md)); not re-verified under this mandate. **Production is NO-GO.**

It continues, and does not restart, the earlier [execution progress tracker](../engineering/reverification/EXECUTION_PROGRESS.md). That file stays as the historical record of the 25 to 27 November reverification and remediation work. Its unfinished items are carried into the phases below (section 4).

## 1. Current authorization

| Item | State |
| --- | --- |
| Mandate acknowledged, governance stored, tracker established | This change (Phase 0) |
| Phase 1 authorized to begin | **No.** The owner said: "Do not begin Phase 1 until instructed." |
| Staging access in this environment | None. `ssh swarm-manager` and `ssh swarm-worker` exist only on the owner's computer |
| Deployment, AWS, secrets, staging database or RabbitMQ changes | Not authorized without an approved operations plan |
| Live payments, payouts, advertiser charging, live ads, production publication | Not authorized |

## 2. Status vocabulary

**Phase status:** NOT STARTED, AUTHORIZED, IN PROGRESS, then one gate verdict: PASS, FAIL or BLOCKED. BLOCKED, NOT RUN, SKIPPED and PARTIAL never count as PASS.

**Requirement classification** (the standing directive's terms; the earlier tracker's terms map onto them):

| Classification | Meaning | Earlier term |
| --- | --- | --- |
| Accepted with evidence | Acceptance criteria passed in the target environment, evidence linked | VERIFIED COMPLETE (in its stated scope) |
| Ready for comprehensive testing | Full chain implemented with development tests; awaits staging or device acceptance | IMPLEMENTED BUT UNVERIFIED |
| Development complete | Code, contracts and development tests done; integration not yet proven | IMPLEMENTED BUT UNVERIFIED |
| Partial | Some links of the chain are missing | PARTIALLY IMPLEMENTED |
| Missing | Not built | NOT IMPLEMENTED |
| Blocked by approval | Waits on a named owner decision | NOT IMPLEMENTED, waiting on a decision |
| Blocked by dependency | Waits on access, a provider or another item | EXTERNAL DEPENDENCY BLOCKER |
| Defective | Built, but fails its criteria | DEFECTIVE, SECURITY BLOCKER |
| Explicitly excluded | Out of scope by owner decision (for example live streaming) | NOT APPLICABLE, APPROVED DEFERRED |

A feature is classified by its weakest link in the chain: Requirement → Architecture → Database → Backend → API → Gateway → Authorization → Flutter/Web → Integration → Tests → Deployment → Acceptance evidence.

## 3. Phase plan (proposed)

The mandate defines the gate rules but not the phase list. The list below is **proposed** for the owner to confirm or amend when authorizing Phase 1. It is ordered by dependency: evidence and decisions first, then shared foundations, then the new bounded contexts, then the clients, then the gate and comprehensive testing.

| # | Phase | Lead roles | Main exit criteria | Status |
| --- | --- | --- | --- | --- |
| 0 | Governance and tracker | Documentation, principal architect | Mandate stored; agent instruction files point to it; tracker and tracking issue in place | IN PROGRESS (this change) |
| 1 | Evidence-first reverification and single source of truth | Principal architect, QA, documentation | Documentation index naming one canonical source per subject; superseded documents archived; full-product traceability matrix for the 18 areas traced through the whole chain; GitHub issues reconciled (each unresolved item has the section 1.7 fields); staging runtime verified on the owner's computer or recorded BLOCKED | NOT STARTED |
| 2 | Scope and decision closure | Principal architect, product, finance, security | Every open owner decision presented in the section 1.8 format with a recommendation; approved requirements recorded for each area before policy-dependent work | NOT STARTED |
| 3 | Architecture and contracts | Principal architect, PostgreSQL, RabbitMQ | 12-service boundaries validated (including where Notifications lives); OpenAPI, event contracts, ERDs and RBAC matrix reconciled for every area; ADRs for any reviewed change | NOT STARTED |
| 4 | Core platform completion | Backend, PostgreSQL, Flutter, security | Identity, Creators, Content, Engagement, Points, Moderation, Audit, Privacy and Notifications reach Ready for comprehensive testing | NOT STARTED |
| 5 | Business completion | Backend, Flutter | Business discovery and management, including the DR-BZ extensions once decided | NOT STARTED |
| 6 | Finance, payments, reconciliation and payouts (sandbox) | Financial systems, backend, security | Finance service with the single ledger; sandbox payment provider integration; reconciliation; payout workflow; creator pool allocation (Decision J); no live money | NOT STARTED |
| 7 | Events and ticketing | Backend, Flutter | Events service posting to Finance only; organizer and attendee journeys in Flutter | NOT STARTED |
| 8 | Advertising, sponsorship and Google mobile ads | Backend, Flutter, release | Advertising service; direct campaigns posting to Finance; Google Mobile Ads in test mode after checking current Google policy; no live ads | NOT STARTED |
| 9 | Flutter applications and Figma parity | Flutter, UI/UX | Role-aware navigation for every non-privileged role; Figma parity (#100); Android and iOS release builds | NOT STARTED |
| 10 | Administrator and moderator console | Backend, UI/UX, security | Every privileged workflow for all areas, with MFA and audit | NOT STARTED |
| 11 | Security and privacy hardening | Application security | ASVS 5.0 L2 and MASVS evidence (#159); STRIDE review (#140); findings closed (#151) | NOT STARTED |
| 12 | Infrastructure, DevSecOps, observability and DR | DevSecOps, AWS/Swarm | Least-privilege roles and keys (#146); signed images and digests (#147); logging and alerting (#145); backup and restore drill (#144); branch protection (#142) | NOT STARTED |
| 13 | Development completeness gate | Principal architect, QA | Every in-scope requirement is Ready for comprehensive testing or has an owner-accepted exception | NOT STARTED |
| 14 | Comprehensive testing | QA, all | Staging acceptance (#155–#157), devices (#158), load (#160), penetration test (#161), rollback and incident drill (#162) | NOT STARTED |
| 15 | Defect fixing and retest | All | Every defect fixed with a test that failed first, then a full regression | NOT STARTED |
| 16 | Release readiness and store submission | Release, principal architect | Readiness report; legal sign-off (#165); Play and App Store submission package (#166); go/no-go (#168) | NOT STARTED |

Phases 4 to 10 may run tasks in parallel once their dependencies (phases 2 and 3 for the area concerned) are met, but each phase still closes through its own gate.

## 4. Carry-over from the earlier tracker

Nothing here is redone. Each item moves into the phase that now owns it, with its existing evidence.

| Earlier item | State at handover | Moves to |
| --- | --- | --- |
| Earlier phases 00 to 02 (baseline, requirements, gap analysis) | COMPLETED for the R1 boundary | Phase 1 re-baselines them for the full product; their findings are inputs, not re-derived |
| Packages A, B, E, F, G, SIM-01 to SIM-10, static policies page, Business R1 (#234 to #259) | Implemented, not accepted (earlier "IMPLEMENTED BUT UNVERIFIED") | Phase 1 reclassifies them; acceptance in Phase 14 |
| Decision C privacy: review, holds, erasure (#260 to #268), untracked media (#295), retention policy file (#296), access export 3.3a to 3.3c (#297 to #299) | Merged; not deployed | Phase 4 |
| 3.4 restore-safe erasure recovery, 3.5 | Not started (3.4 was next) | Phase 4 |
| D backups and observability (repository side), RV2-03 dead letters | Not started | Phases 4 and 12 |
| J Finance, H Events, I Advertising | Design packages proposed (`docs/architecture/finance`, `events`, `advertising`); not built | Phases 6, 7 and 8 |
| Remediation 1.1 #143 scan exceptions | OpenSSL exception renewed to 5 December; FFmpeg rules retired | Phase 12, with a hard date of 5 December |
| Remediation 1.2 #274 CPU budget (#283) | Package ready; measurement NOT RUN | Phase 12 |
| Remediation 1.3 / 2.1 #271 Points to Audit key (#281) | Plan ready; NOT APPLIED | Phase 12 |
| Remediation 1.4 #142 ruleset (#279) | Plan ready; NOT APPLIED | Phase 12 |
| Remediation 1.5 D13-005 release reconciliation (#287, #288) | Tool merged; read-back NOT RUN | Phase 1 (runtime verification) |
| 2.2 #272 Content and Creators audit delivery | Repository side ready; NOT DEPLOYED | Phase 12 |
| 2.3 #145 audit alerting | Signals built; notification channel NOT IMPLEMENTED | Phase 12 |
| 3.1 #273 erasure runtime wiring | Repository side ready; NOT DEPLOYED | Phase 12 |
| Earlier phases 07 to 14 | NOT STARTED | Phases 11 to 16 |

## 5. Open owner decisions carried over

These are already on record. They are listed so they are not asked again; Phase 2 presents any that are still open in the mandate's decision format.

| Decision | What is needed | Where it is recorded |
| --- | --- | --- |
| Points to Audit key correction | Approve the plan and step-0 code PR | #281, #271 |
| Staging CPU measurement | Go for the 24-hour read-only measurement, then the budget | #283, #274 |
| Alert thresholds and monitoring channel | OD-08 | `docs/operations/R1_Audit_Alert_Signals_2026-11-27.md`, #145 |
| Access export availability period | Retrieval window (no default) | #297, `docs/privacy/account-erasure-plan-PROPOSED.md` |
| Withheld export categories | Which may be shown to the person | #298 |
| Retention values | ADR-020, RV2-04, DR-BZ-08, DR-BZ-25 | #136, `docs/architecture/business/BIZ-Owner_Decision_Register_PROPOSED.md` |
| Deletion-completion email | Whether and what to send | Earlier tracker, item 3 |
| Branch protection ruleset | Approve and apply | #279, #142 |
| mTLS versus per-caller keys | Service identity model (ADR-012, INF-07) | #138 |
| Legal texts | Qualified legal review | #165 |
| Finance, Events and Advertising values | Revenue shares, thresholds, provider, refund rules, Google products | `FIN-`, `EVT-`, `AD-Owner_Decisions_Required_*.md` |
| General-release points rules | ADR-019 / DEC-003 | #137 |

## 6. Scope questions to resolve in Phase 2

Raised by the mandate; not decided here.

- **Notifications:** the mandate lists it as a capability but not as a service. Phase 3 recommends whether it belongs inside an existing service or justifies a thirteenth.
- **Payment processing and payouts:** provider, sandbox account and regulatory position.
- **Google mobile advertising:** which products, after checking current Google policy (Decision I).
- **Comments and ad test-mode placements** (#135).
- **Live streaming:** stays excluded unless the owner decides otherwise.

## 7. Phase reports

| Phase | Report | Verdict |
| --- | --- | --- |
| 0 | This tracker and the PR that adds it | Pending owner review |
