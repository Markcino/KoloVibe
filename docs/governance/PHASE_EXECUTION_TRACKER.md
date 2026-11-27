# KoloVibe phase execution tracker

**Read this file first when resuming work.** It tracks execution under the [full application mandate of 27 November 2026](Full_Application_Mandate_2026-11-27.md) (referred to below as "the mandate"). Then check the repository state (`git log origin/main`, open pull requests and issues) before acting. GitHub Issues stay the authoritative work and defect tracker (mandate section 7). This file points to them and does not copy them.

Established: 27 November 2026, at `main` `37c5a44` (after #299).

## 1. Current gate

| Item | State |
| --- | --- |
| Current phase | **None. Phase 1 is NOT STARTED.** The mandate says "Do not begin Phase 1 until instructed", and no instruction has been given |
| Phase list and exit criteria | **NOT DEFINED.** The mandate requires phase gates (section 10) but does not name the phases or their exit criteria. They will be proposed at Phase 1's Plan step for the owner to approve. They are not invented here |
| Production | NO-GO. Nothing in this file authorizes deployment, live payments, live advertising, destructive data changes or production publication (mandate section 8) |
| Infrastructure access from Claude's cloud sessions | **NOT AVAILABLE.** The SSH aliases `swarm-manager` and `swarm-worker` (mandate section 4) are set up on the owner's own computer. The cloud environment Claude works in has no SSH configuration or keys for them. Runtime verification there needs the owner to run the commands, or a Remote Control session on the owner's computer that the owner approves. It is never assumed |

## 2. Phase register

Each phase follows the eleven gate steps in mandate section 10. Its completion report has the fields in section 11 and is linked here. Only PASS opens the next phase, and only after the owner authorizes it. BLOCKED, FAIL, NOT RUN, SKIPPED and PARTIAL are never PASS.

| Phase | Name | Status | Started at (commit) | Ended at (commit) | Verdict | Completion report | Next phase authorized |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | To be proposed at Phase 1's Plan step | NOT STARTED | — | — | — | — | — |

The phase statuses are NOT STARTED, IN PROGRESS, PASS, FAIL and BLOCKED. Test and evidence results are PASS, FAIL, BLOCKED, NOT RUN, SKIPPED, PARTIAL and NOT IMPLEMENTED. They are never added together across different builds. Requirement classifications keep the vocabulary in [EXECUTION_PROGRESS.md](../engineering/reverification/EXECUTION_PROGRESS.md#status-vocabulary).

### Phase completion report template (mandate section 11)

Phase name and number · starting commit · final commit · requirements completed · files changed · GitHub issues created, updated and closed · pull requests and CI results · database migrations · infrastructure changes · tests executed · PASS, FAIL, BLOCKED and NOT RUN counts · evidence locations · security findings · remaining defects · decisions required · rollback instructions · final gate verdict · whether the next phase is authorized to begin.

### Missing-decision template (mandate section 8)

Decision ID · exact blocking requirement · why the decision is necessary · available options · recommended option · security, financial and operational implications · consequences of delay · exact approval wording.

## 3. How the mandate fits with earlier work

This work continues from the existing records and does not restart them. Earlier mandates used their own phase numbers: "Phases 00 to 14" from 25 November, and the "Remediation and Completion" items 2.1 to 4.6 from 27 November. To keep them distinct from the new phases, their items are cited with a prefix (for example "remediation 3.4"). Their detailed record stays in [EXECUTION_PROGRESS.md](../engineering/reverification/EXECUTION_PROGRESS.md).

### 3.1 Decisions that stay in force (not asked again)

| Decision | Record |
| --- | --- |
| A to J (edits re-review, legal acceptance, privacy retention and deletion, backup and alerting, copyright, creator restrictions, Identity step-up, Events, Advertising, Finance with one ledger) | [Owner decisions A to J](../planning/Owner_Decisions_A-J_2026-11-25.md) |
| Public web surface: static policy pages and the account-deletion request page only | Same record, rulings of 25 and 26 November |
| SIM-02 sharing as app links only, with a store fallback | [EXECUTION_PROGRESS.md](../engineering/reverification/EXECUTION_PROGRESS.md), completed packages |
| Business R2 design (PR #218) | [Business owner approval record](../architecture/business/BIZ-Owner_Approval_Record_2026-11-24.md) |
| ADR-013 v1.0 client authentication and session security | [ADR-013](../architecture/ADR-013_Client_Authentication_and_Session_Security_v1.0_APPROVED.md) |

### 3.2 Where the mandate changes earlier instructions

| Earlier instruction | Mandate | Reconciliation |
| --- | --- | --- |
| R1 "MVP" scope ([DEC-001](../requirements/platform_documentation_register_and_DEC001.md)). Instruction files said "Do not implement deferred features" and listed business discovery, ticketing and cash payouts as deferred | The full application, including Business discovery, Events and ticketing, Advertising, Google mobile ads, Finance, payments and payouts (section 2) | The deferral no longer justifies leaving approved functionality incomplete. DEC-001 is kept as history. The instruction files now point here, and their old wording is kept as dated history |
| Events (H), Advertising (I) and Finance (J) are sandbox development only. No real payments, live payouts or live ads | Payment processing, reconciliation and payouts are in scope. Development approval does not authorize live payments or ad activation (section 8) | Unchanged in effect. Build to completion in sandbox. Live activation, provider credentials and money values each need their own owner approval |
| Public web: static policies and the deletion page only | "Necessary approved legal, account-deletion and application-link resources may remain publicly accessible" (section 3) | Application-link association resources, which SIM-02 app links need, are now explicitly allowed. Nothing else becomes public |
| Live streaming is excluded | Not approved just because this is no longer an MVP (section 2) | Still excluded. A scope recommendation is due in Phase 1 |
| Eleven or twelve services named in older documents | Twelve expected services (section 3) | To be checked against the as-built architecture in Phase 1. No new service is added without justification |

### 3.3 Continuation work carried over (state at 27 November, before Phase 1)

| Item | State |
| --- | --- |
| Remediation 2.1 Points→Audit (#271), 2.2 Content and Creators audit delivery (#272), 2.3 audit alerting (#145) | Waiting on owner decisions: the #281 rotation, the #279 ruleset, the #283 measurement, and alert thresholds and channel |
| Remediation 3.1 erasure runtime wiring | In the repository, NOT DEPLOYED. Waiting on approval of the broker plan (#294) |
| Remediation 3.2 untracked media (#295) and retention policy (#296) | Merged. Retention values are an owner decision |
| Remediation 3.3 access export, a to c (#297, #298, #299) | Merged. The retrieval window and the withheld categories are owner decisions. Device UAT NOT RUN |
| Remediation 3.4 restore-safe erasure recovery | **PR #300 open.** A PostgreSQL restore drill passed locally on 27 November. The recovery contract is PROPOSED and needs owner approval. A staging restore is NOT RUN |
| Remediation 3.5 lifecycle execution and the completion notice | NOT STARTED. The completion notice is an owner decision |
| Remediation 4.1 to 4.6 (stalled video, end-to-end staging proof, client IP and rate limits, legacy broker account, DLQs, acceptance items) | NOT STARTED |
| Time-bound: the OpenSSL scan exception expires on 5 December (#284) | It will not be renewed silently. It needs an owner decision before then |

Whether these items continue in parallel or are folded into Phase 1 is for the owner to say when Phase 1 is authorized.

## 4. Governance files located

| Subject | Canonical file today |
| --- | --- |
| Agent instructions | [`AGENTS.md`](../../AGENTS.md). [`CLAUDE.md`](../../CLAUDE.md) and [`.github/CLAUDE.md`](../../.github/CLAUDE.md) point to it. [`.github/copilot-instructions.md`](../../.github/copilot-instructions.md) has the same rules for Copilot |
| Mandate and phase rules | [Full application mandate](Full_Application_Mandate_2026-11-27.md) and this tracker |
| Documentation index | [`docs/README.md`](../README.md). A full canonical-source index per subject (mandate section 9) is Phase 1 work |
| Scope decision and document register | [DEC-001 register](../requirements/platform_documentation_register_and_DEC001.md), [`document_register.csv`](../requirements/document_register.csv), [change control (proposed)](../requirements/DOC-023_Change_Control_Proposed.md) |
| Owner decisions | [Owner decisions A to J](../planning/Owner_Decisions_A-J_2026-11-25.md), [consolidated open decisions](../architecture/DOC-209_Consolidated_Open_Decisions.csv), [ADR register](../architecture/DOC-207_ADR_Register.csv), [`docs/adr/`](../adr/) |
| Engineering standards and repository governance | [Engineering standards](../engineering-standards.md), [FND-01](../engineering/FND-01_repository_governance.md), [`CODEOWNERS`](../../.github/CODEOWNERS), [PR template](../../.github/PULL_REQUEST_TEMPLATE.md), [`branch-protection/`](../../.github/branch-protection/) |
| Continuation progress (earlier mandates) | [EXECUTION_PROGRESS.md](../engineering/reverification/EXECUTION_PROGRESS.md) |
| Release readiness | [Go-live readiness](../planning/go_live_readiness.md) |
