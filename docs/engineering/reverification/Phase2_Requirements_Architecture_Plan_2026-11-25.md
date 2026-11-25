# Reverification Phase 2 — requirements reconciliation, architecture approval and development plan

**Date:** 25 November 2026. **Base:** `main` at `8a6e7a0` (Phase 1 merged in PR #232). **Nature:** planning and design only. No application code, migration, flag, deployment, staging, secret or broker change. **Nothing in this document is approved:** every recommendation waits for the owner's written answer, and no decision below was invented; each one is quoted from an existing register or, where none existed, raised here with a new `RV2-` identifier and marked new.

Companion design package for the unbuilt Release 1 work: [R1 completion design (PROPOSED)](../../architecture/R1_Completion_Design_PROPOSED.md).

## 0. Exit summary

1. **Release 1 can be finished without any new scope approval.** Five slices need no policy at all: Creators/Content audit delivery (S1), maintenance roles (S3), the poster re-render defect found in this phase (S4, D-P2-01), upload result screens M-050 to M-052 (S5), and dead-letter wiring once three values are given (S2).
2. **Seven R1 slices are policy-blocked** and listed with exact decision ids in section 5A: privacy processing (ADR-020), consent record (RV2-02, #165), observability (ADR-017), backup (ADR-016), published-video re-review (RV2-01), copyright claimant intake (D11-008), creator restriction (D-8).
3. **Events, Advertising and Finance need a scope amendment before any code:** DR-EV-01, DR-AD-01 and DR-FIN-01 (each a DOC-023 change request against DEC-001). They also need one cross-module ruling on ledger ownership (X-01) and the shared Identity step-up (DR-BZ-33 / DR-EV-05 / DR-FIN-06).
4. **Development approval is not activation approval.** Section 1 separates the two for every module.
5. **The architecture conforms** to the directive on every rule, with two recorded dependencies: the ledger-ownership conflict between the Phase 7/8 and Phase 9 packages, and unmeasured capacity for a tenth service.

## 1. Scope reconciliation

| Module | Release | Current approval | Code on `main` | Needs **development** approval? | Needs **activation** approval (separate) |
| --- | --- | --- | --- | --- | --- |
| Identity, Creators, VOD (R2+FFmpeg), Engagement, Points, Moderation, Audit | R1 | **Approved** (DEC-001; DEC-003, 004, 005; OD-07; ADR-013) | Yes; partial items in §5A | No. Remaining R1 work is inside approved scope | Yes: pilot go/no-go (#168) after the Phase 12 blockers B1–B7 close |
| Business | R2 | **Development approved** (DR-BZ-01…26 approved as recommended 24 Nov, ADR-BIZ-001 approved as written; built dark in PRs #219 onward) | Yes, flags closed | No for the built scope; **yes** for sensitive operations and extensions (DR-BZ-25…33) | Yes: capability flags, DR-BZ-24 capacity, R-01 on its schema (DR-BZ-32), visual approval (DR-BZ-27) |
| Events and ticketing | R3 | **Deferred** in DEC-001, ADR-010, DOC-021 | None (design package only) | **Yes: DR-EV-01** scope amendment via DOC-023, plus Gate G (DR-EV-02…07) | Yes, and real payments additionally need DR-EV-22 (provider) and legal |
| Advertising and sponsorship | "Should; conditional" (PRD-F11, FR-020) | **Pending / blocked** (ADS-001 not started, tracker B-19) | None | **Yes: DR-AD-01** scope amendment, Gate G | Yes; network SDKs (AdMob/AdSense) are unverified for Liberia and imply a website that DR-BZ-21 forbids |
| Revenue sharing and payouts | R4 | **Deferred** (PRD-F14, DOC-022, BR-010…012) | None | **Yes: DR-FIN-01** scope amendment, Gate G, and an **independent accounting approver (DR-FIN-04)** | Yes; a `live` book needs a named approval constant (DR-FIN-07); real money stays off |
| Live streaming | — | **Excluded** | None | Not to be developed | — |

**Rule applied throughout:** a DOC-023 change request that moves a module to "approved for development, not for release" authorizes code behind closed flags and sandbox adapters only. Turning a flag on in staging, connecting a real provider, or moving money each needs its own written approval.

## 2. Architecture review

Checked against source on `8a6e7a0`; detail in the [design package §1](../../architecture/R1_Completion_Design_PROPOSED.md#1-architecture-conformance-checked-against-code-on-8a6e7a0).

| Directive rule | Result |
| --- | --- |
| Flutter for every ordinary user | Conforms |
| Django web for administrators and moderators only | Conforms (privileged decorator and route-security matrix) |
| Server-side authorization | Conforms |
| Microservice database ownership | Conforms (per-service schema and login, no cross-service model, isolation test) |
| Secure Gateway reused | Conforms; every proposed module routes through it |
| RabbitMQ for async | Conforms; dead-letter path missing (S2) |
| R2 + FFmpeg for VOD | Conforms; live R2 unproven (B5) |
| Safe migrations | Conforms in the repository; staging not converted (B1, O-3) |
| No duplicate monetary ledger | **Open conflict:** DR-EV-03 puts a ledger in Events, DR-AD-03 leaves Ads billing open, DR-FIN-02 puts the only ledger in Finance. Ruling X-01 below |
| Fits the infrastructure | **Dependency:** a tenth service is unmeasured on the two-VM AWS stack (DR-BZ-24, DR-EV-07, O-13) |
| No public website, no live streaming | Conforms |

## 3. Decision review by topic (Task 2)

Each topic shows what is decided, what is open and where it is recorded. "None recorded" means no register held it; a new `RV2-` id is raised in section 5A.

| Topic | Decided | Open | Ids |
| --- | --- | --- | --- |
| Privacy retention, export, deletion | Request intake (receipt only) is built | Retention per category, deletion vs anonymisation, residency, legal holds, who processes | ADR-020, OD-05, #136; DR-BZ-18, 23; A10 (Business register) |
| Consent management | Notification preferences stored (default off) | **No record of terms or privacy-notice acceptance**; text not written | **RV2-02 (new)**; #165 |
| Profile images and moderation | Rules written, upload disabled (`KOLOVIBE_CREATOR_PHOTOS=0`) | Approval of the rules; one image pipeline for creators, Business and Events | D-10 (`docs/privacy/creator-profile-photos.md`); DR-BZ-19; DR-EV-17 |
| Video editing and re-review | Draft and rejected edits are free; publication needs moderation | **Edits to a published video's title, description, category and tags go live without review** (`media_api.py:177`) | **RV2-01 (new)** |
| Media retention | Pipeline chosen (R2 + FFmpeg) | Deleting originals, abandoned uploads, superseded renditions and posters; bucket lifecycle | OD-07 (partial), #149; **RV2-04 (new)** for the values |
| Copyright claimant intake | Draft policy, Content screening and moderation path exist | Claimant channel; legal review of notice and counter-notice | D11-008, O-11, #165 |
| Audit delivery and retention | Audit accepts Creators and Content events; Identity, Moderation, Points, Business deliver | Creators/Content credentials; retention period; external anchoring | D11-007, O-10, OD-08, ADR-017; DR-FIN-08 |
| Business sensitive operations | Fail closed today | Step-up proof; suspension grounds; disputes; files; links; notifications | DR-BZ-33 (P6B-04), 25, 26, 28, 19, 14 |
| Event and ticketing policies | none | 35 decisions in Gates G, A, B, C, D | DR-EV-01…52 |
| Advertising policy and consent | none | 38 decisions (Gates G, A–F), including ad consent and network SDKs | DR-AD-01… |
| Financial ledger ownership | none | One ledger in Finance vs ledger in Events | DR-FIN-02 vs DR-EV-03 vs DR-AD-03 → **X-01** |
| Sandbox payout controls | none | Environment guard, maker-checker-releaser, independent approver | DR-FIN-04, 05, 07 |
| Service capacity | DR-BZ-24 approved as "local and CI first, then rollout after R-01 and pilot acceptance" | AWS instance read-back, load and soak test, tenth service | O-13, DR-EV-07, INF-01, INF-04, INF-13 |
| Migration role separation | Repository fixed (D11-002); Business and module designs choose owner/runtime split | Staging conversion; migration logins; per-module confirmation | O-2, O-3, DR-BZ-32, DR-EV-06 |
| Dead letters (raised by Phase 1) | none | Retry ceiling, DLQ retention, replay authority | O-9; **RV2-03 (new)** |
| Maintenance scheduling | Manual runbook | Approval to schedule | O-12, D11-009 |
| Registration budget | 20 per hour per origin as configured | Confirmation | O-5 |
| Creator restriction | Read and enforcement exist; nothing writes status | Grounds, authority, appeal | D-8 |

## 4. Formal design package (Task 4)

| Item | Release 1 completion | Business | Events | Advertising | Finance |
| --- | --- | --- | --- | --- | --- |
| 1 Requirements and scope | PRD/SRS v0.2 (approved scope); this document §1 | BIZ reconciliation | EVT PRD/SRS (proposed) | AD PRD/SRS (proposed) | FIN PRD/SRS (proposed) |
| 2 ADRs | DOC-207 ADR-011…022 (§5A) | ADR-BIZ-001 (approved as written) | ADR-EVT-001 | ADR-AD-001 | ADR-FIN-001 |
| 3 Service diagrams | [R1 completion design](../../architecture/R1_Completion_Design_PROPOSED.md) §2; DOC-208 | BIZ-ARCH | EVT README | AD README | FIN accounting design |
| 4 ERDs | design §2 (audit tables); DOC-204 | BIZ-ERD | EVT-ERD | AD-ERD | FIN-ERD |
| 5 API contracts | no public API change for S1–S5; DOC-205 | DOC-205 (reconciled) | EVT-API | AD-API | FIN-API |
| 6 RBAC/BOLA | design §11 | BIZ RBAC matrix | EVT authorization matrix | AD authorization matrix | FIN control model |
| 7 STRIDE | design §2–§4 per slice; DOC-203 (41 threats, review open #140) | BIZ STRIDE | EVT STRIDE | AD STRIDE | FIN STRIDE |
| 8 Data retention | blocked by ADR-020 (S7); audit OD-08; media RV2-04 | BIZ privacy (DR-BZ-18 open) | DR-EV-30 open | AD policies | DR-FIN-08 open |
| 9 Dependencies | §6 below | Phase 6E | EVT delivery plan | AD delivery plan | FIN delivery plan |
| 10 Acceptance criteria | design §2–§6 | Phase 6E | EVT acceptance | AD acceptance | FIN acceptance and correctness |

Full paths for the later-release documents are in [design §10](../../architecture/R1_Completion_Design_PROPOSED.md#10-later-release-design-packages-already-complete-all-proposed). They were reviewed for conformance in §2 and are **not** re-authored here, to avoid duplicate sources of truth.

## 5. Approval register (Task 5)

**Approver roles** used below, as the existing registers name them: **Product owner** and **Infrastructure owner** (both Mark Allen Gbalazeh today), **Legal reviewer** (not yet named; DR-BZ-23), **Independent accounting approver** (not yet named; DR-FIN-04), **Security owner** (DOC-203 review, #140). None of these recommendations is approved by this document.

### 5A. Release 1 and cross-cutting decisions

| Id | Decision | Existing options | Recommended | Security implications | Blocks | Approver |
| --- | --- | --- | --- | --- | --- | --- |
| ADR-020 / OD-05 / #136 | Privacy retention, deletion and residency | (a) delete on request except legal holds; (b) anonymise in place; (c) per-category mix | (c): erase personal data, anonymise records that other parties rely on (reports, reviews), keep audit and financial records under hold; residency recorded, not changed | Erasure must not break audit integrity or let a banned person reset history | S7, FR-017, BZ-R-039/040, DR-EV-30, DR-FIN-08 | Product owner + Legal reviewer |
| **RV2-02 (new)** | Consent and policy-acceptance record | (a) record at registration only; (b) record and re-prompt on each new version; (c) none until legal text exists | (b), built behind a flag now, enabled when #165 text is approved | Proves what each person agreed to; no tracking consent is implied because none is collected | S6, NFR-012 | Product owner + Legal reviewer |
| **RV2-01 (new)** | Re-review of edits to a published video | (a) current: live immediately; (b) material edits (title, description, category, tags) re-reviewed, approved revision stays live; (c) every edit re-reviewed | (b), mirroring DR-EV-14 and Business material-change review | Today a creator can publish reviewed media under unreviewed text (abuse, spam, impersonation) | S10 | Product owner |
| **RV2-03 (new)** | Dead-letter values | Retry ceiling; DLQ TTL and length; replay authority | ceiling 10 with backoff; DLQ kept 14 days, bounded length; replay by an administrator only, through the normal publish path | Without a DLQ a rejected award or media task is lost with no record | S2, B7 | Infrastructure owner |
| **RV2-04 (new)** | Media retention values (under OD-07) | keep originals; delete after processing; delete after N days | keep originals until moderation is final plus a period you set; delete abandoned uploads after 24 h; delete superseded renditions and posters after 7 days | Fewer stored originals reduces breach impact; deletion credential must be separate from upload | #149, S4 cleanup | Product owner + Infrastructure owner |
| D11-007 / O-10 | Provision Creators and Content audit delivery | provision now; defer | Provision with S1 | Closes the accountability gap for creator approvals and publication | S1 deploy | Product owner |
| D11-008 / O-11 | Copyright claimant channel | in-app for signed-in claimants; administrator-entered from email; both | Administrator-entered for the pilot (no new public surface), in-app later | An open claim form is an abuse and takedown-weaponisation vector | S11 | Product owner + Legal reviewer |
| D-8 | Creator restriction write path | moderator decision; administrator only | Moderator decision with independent appeal, administrator restores | Restriction must be audited (S1) and appealable | S12 | Product owner |
| D-10 | Creator profile photo rules | approve as written; amend | Approve, and build one image pipeline for creators, Business (DR-BZ-19) and Events (DR-EV-17) | Image decoding is an attack surface; re-encode and strip metadata | photos in M-013/038/039/079 | Product owner |
| D-9 | Public play counts | show; hide | Hide in R1 (counts are creator-only analytics today) | Public counts invite view fraud | discovery polish | Product owner |
| O-12 / D11-009 | Schedule maintenance commands | schedule; stay manual | Schedule with S3 | Unbounded throttle and session tables; stuck media | S3 deploy | Infrastructure owner |
| O-5 | Registration budget 20/hour/origin | confirm; change | Confirm for the pilot, review after pilot data | Shared mobile NAT may hit the limit | B4 tuning | Product owner |
| O-3 then O-2 | Migration logins, then ownership conversion on staging | as runbook | As runbook, **after** O-6 backup is proven | Until done, a stolen service credential can disable ledger and audit guards | B1 | Infrastructure owner |
| O-6 / ADR-016 / OD-04 / INF-05 / INF-10 | Backup, restore, RPO/RTO, retention | managed snapshot; scheduled dump; both | Scheduled encrypted dump plus host snapshot, restore drill monthly; you set RPO/RTO | No recovery path exists today; the 14 Nov restore waiver covers staging only | B3, S9, NFR-008 | Infrastructure owner |
| ADR-017 / OD-08 / INF-09 | Observability and audit retention | self-hosted stack; managed service | Smallest self-hosted stack that fits capacity, or managed if INF-01 budget allows; you set retention | Without alerting, an attack or outage is found by users | S8, FR-019, #145 | Infrastructure owner |
| ADR-011, 012, 014, 015, 018, 021, 022 | Gateway, service identity, private transport, Swarm sizing, secrets/CI, Nginx HA/TLS, API versioning | per DOC-207 | Approve ADR-011, 012, 018, 022 as proposed (they describe what is built); decide 014, 015, 021 with INF-01 | Approving records what is enforced; 014/021 decide origin bypass protection | production architecture, #138 | Infrastructure owner + Security owner |
| INF-01 … INF-14 | Pilot vs HA, provider, origin protection, nodes, PostgreSQL topology, Redis, workload identity, DNS, observability, backups, video egress, registry, capacity/SLO, Nginx HA | per DOC-208 | Decide INF-01 (pilot, single region) first; most others follow | Origin protection (INF-03) and workload identity (INF-07) are security-critical | production readiness, #139 | Infrastructure owner |
| O-13 / DR-EV-07 | Capacity read-back and load test | approve; defer | Approve a read-only AWS capacity read-back now and a load test after B1 | A tenth service may starve existing ones | any new service deploy | Infrastructure owner |
| #142 | Required checks and review on `main` | enable; leave | Enable required CI checks now | Today a red build can be merged | release integrity | Product owner |
| #143 | OpenSSL scanner exception (expires 2026-11-28 UTC) | rebuild on a fixed base; renew with reason | Rebuild if a fixed package exists, otherwise renew for seven days with the advisory recorded | An expired exception turns CI red; a silent renewal hides risk | CI on every PR | Security owner |
| **X-01** | One monetary ledger | DR-EV-03 (ledger in Events); DR-AD-03 (open); DR-FIN-02 (one ledger in Finance, Events and Ads emit signed events) | **DR-FIN-02**, and amend DR-EV-03 and DR-AD-03 as the Phase 9 delivery plan lists | Two ledgers cannot both be the source of truth; reconciliation and fraud controls assume one | Events payments, Ads billing, Finance | Product owner + Independent accounting approver |
| DR-BZ-33 = DR-EV-05 = DR-FIN-06 (part) | Identity step-up proof | build once in Identity; per-module | Build once as a reviewed Identity task | Sensitive operations otherwise rely on a bearer token alone | Business four actions, event cancellation and refunds, payout release, privacy processing | Product owner + Security owner |
| DR-EV-01 / DR-AD-01 / DR-FIN-01 | Scope amendments (DOC-023 against DEC-001) | approve for development only; defer | Your choice of order; the packages recommend approval for development behind closed flags and sandbox only | Development-only approval keeps real money and providers off | all code in that module | Product owner |

### 5B. Module registers (unchanged, summarised)

All 116 rows from the four module registers are listed with their own recommendation in [Appendix A](#appendix-a-module-decision-rows). The gates that must be answered first:

| Module | First gate | Rows (all gates) | Security implication of the gate | Blocks |
| --- | --- | --- | --- | --- |
| Business | Gate A (DR-BZ-33, 29, 25, 26, verification, review values, 10, 9/11, 18/23) | 17 | step-up, suspension and dispute authority | sensitive operations, files, purge jobs |
| Events | Gate G (DR-EV-01…07) | 35 | service boundary, ledger, step-up, DB ownership, capacity | everything in Events |
| Advertising | Gate G (DR-AD-01…) | 38 | separate service so ad events can never reach Points (FR-016) | everything in Advertising |
| Finance | Gate G (DR-FIN-01…08) | 26 | one ledger, separation of duties, sandbox guard, independent approver | everything in Finance |


## 6. Dependency-ordered development plan (exit criteria)

### Track A — approved, independently implementable now (no policy needed)

Each is one focused PR with unit, PostgreSQL, contract and widget tests as applicable; none is deployed by merging.

| Order | Task | Depends on | Size | Deploy gate |
| --- | --- | --- | --- | --- |
| A1 | **S4** fix D-P2-01: re-render the poster after a cover edit | none | S | normal release |
| A2 | **S1** Creators audit outbox and delivery | none | M | O-10 credentials |
| A3 | **S1** Content audit outbox and delivery | A2 pattern | M | O-10 |
| A4 | **S5** M-050, M-051, M-052 live result screens | none | S | none |
| A5 | **S3** maintenance Swarm roles (`replicas: 0`) and contract tests | none | S | O-12 |
| A6 | **S2** dead-letter declarations, finite retry, DLQ count in console, with values as required configuration | RV2-03 values for defaults (code can land with configuration that refuses to start without them) | M | O-9 |
| A7 | Design-only: Identity step-up proof (DR-BZ-33) ADR and threat model, no code | none | S | DR-BZ-33 approval before code |

### Track B — owner and operations (parallel, outside the repository)

B1 order matters: **O-6 backup and restore → O-3 migration logins → O-2 ownership conversion**. Independently: O-4 edge deploy, O-8 R2, O-9 broker read-back, #142 required checks, #143 exception before 28 Nov, O-13 capacity read-back, O-7 device runs once Track A lands.

### Track C — policy-blocked R1 work (starts when its decision is recorded)

| Order | Task | Unblocked by |
| --- | --- | --- |
| C1 | S9 backup and restore tooling | ADR-016, INF-05, INF-10 |
| C2 | S8 observability and alerting | ADR-017, OD-08, INF-09 |
| C3 | S10 published-video material-edit re-review | RV2-01 |
| C4 | S6 consent and policy-acceptance record | RV2-02, #165 text |
| C5 | Identity step-up implementation | DR-BZ-33 |
| C6 | S7 privacy export and deletion processing | ADR-020, C5 |
| C7 | S11 copyright claimant intake | D11-008, legal review |
| C8 | S12 creator restriction | D-8, A2 |
| C9 | Shared image pipeline, then creator photos | D-10 (and DR-BZ-19, DR-EV-17) |

### Track D — later-release modules (only after scope amendment)

| Order | Module | Unblocked by | First slice |
| --- | --- | --- | --- |
| D1 | Business sensitive operations and extensions | DR-BZ-25…33, C5 | suspension and appeal (DR-BZ-25) |
| D2 | Finance foundation (sandbox book only) | DR-FIN-01…08, **X-01**, DR-FIN-04 named | ledger, environment guard, control model |
| D3 | Events and ticketing (sandbox payments only) | DR-EV-01…07, X-01 amendment of DR-EV-03, D2 | organizers and events (Gate A) |
| D4 | Advertising (sandbox billing, no network SDK) | DR-AD-01 and Gate G, X-01 amendment of DR-AD-03, D2 | advertiser accounts |

Finance before Events and Ads is the dependency order **if** X-01 is approved as recommended; if the owner keeps DR-EV-03 instead, Events can start first and Finance must later absorb its ledger, which the Phase 9 package advises against.

### Track E — comprehensive testing (after Tracks A–C needed for the pilot)

Staging re-acceptance on the current release (#155), device UAT (#158), real R2 journey (#156), engagement/points on staging (#157), ASVS/MASVS (#159), penetration test (#161), rollback and alerting drill (#162), pilot plan (#163), production readiness (#164), legal sign-off (#165), go/no-go (#168).

## 7. Phase boundary report

1. **Verified commit:** `8a6e7a0` (`main`, Phase 1 merged).
2. **Feature matrix:** unchanged from [Phase 1 §2](Phase1_Reverification_2026-11-25.md#2-authoritative-feature-matrix), plus defect D-P2-01 (S4).
3. **Files changed:** this document; `docs/architecture/R1_Completion_Design_PROPOSED.md`; a pointer in the R1 tracker. No application code.
4. **Database and API changes:** none made. Proposed: two audit tables in each of Creators and Content (S1); a Content poster task (S4); proposed only, behind decisions: `PolicyAcceptance` in Identity (S6), privacy processing operations (S7).
5. **Security findings:** new: published-video edits skip review (RV2-01); no consent record (RV2-02); poster loss after a cover edit (D-P2-01, functional). Carried: no dead-letter path, Creators/Content audit gap, B1–B7.
6. **Tests:** none run in this phase: no code changed after the Phase 1 run on `d56e7ce`; the only commit since is the Phase 1 documentation merge.
7. **PR:** documentation PR from `claude/project-thread-5fly00`; not merged.
8. **Outstanding decisions:** section 5 and Appendix A.
9. **Known defects:** D-P2-01 (new); D11-007, D11-008, D11-009; Business K4–K8.
10. **Next-phase prerequisites:** the owner's authorization to start Track A (A1–A7 need no policy), and any Track B–D decisions the owner chooses to answer.

**STOP AFTER PHASE 2.** The required approvals are in section 5.

## Appendix A. Module decision rows

Extracted verbatim (shortened where long) from the four module registers. The register remains the source; answer there with its decision template.

### Business (17 rows) — `docs/architecture/business/BIZ-Owner_Decisions_Required_PHASE6A.md`

| Id | Gate | Decision | Register recommendation | Unlocks / why |
| --- | --- | --- | --- | --- |
| DR-BZ-33 | A | Approve designing the purpose-bound step-up proof in Identity (P6B-04) | Approve as a separate, reviewed Identity task; keep the four actions disabled until it ships | live contact change, staff removal, closure, ownership transfer (BZ-R-002, 008, 036) |
| DR-BZ-29 | A | Accept the Business-local report queue or approve generalising Moderation | Accept the local queue for the pilot; build restoration (by a different reviewer), appeals and listing reports inside Business | BZ-R-025, 032; review restoration and appeals |
| DR-BZ-25 | A | (approved as recommended) Supply suspension and delisting grounds, the notice wording and the appeal route | Reuse the Moderation pattern: reason code, notice, independent appeal; administrator restores, never the suspender | BZ-R-009; the `suspended` and `closed` states become reachable |
| DR-BZ-26 | A | (approved) Supply the dispute adjudicator, evidence rules and time limit | Administrator with MFA; listing frozen on a credible report | BZ-R-008 disputes |
| DR-BZ-04 | A | Verification policy under DR-BZ-04, 19: the written evidence checklist, accepted methods, validity period, resubmission limit, reason codes… | A+B (document review plus contact-channel proof); no identity document; one resubmission cycle; re-verification at a fixed period you choose | file evidence; expiry; BZ-R-004 |
| DR-BZ-15 | A | Review policy values under DR-BZ-15, 16, 22: minimum review count before an average shows, edit window, author display form, account-age ga… | Show an average only after a count you set; pseudonymous author labels; the starting thresholds in `limits.py` until pilot data exists | BZ-R-021, 026, 028, 030, 031 |
| DR-BZ-10 | A | Initial category list and county/city lists | Two levels at most; you supply the list | category data; county validation |
| DR-BZ-09 | A | Public-field warning and notice copy; which profile fields are material; public coordinate precision | Keep `display_name`, category, address line, contacts as material; coordinates stay private | BZ-R-007, 012, 014 |
| DR-BZ-18 | A | A retention period and a purge trigger per data category; legal-hold rules; the legal reviewer (named) and outcome | Decide after legal input; until then nothing purges | purge jobs, export and erase (BZ-R-039, 040) |
| DR-BZ-14 | A | Whether inquiries and reviews send any notification | None in the first release | notification work |
| DR-BZ-19 | A | Whether files may ever be uploaded (evidence, images) and under what storage and scanning | No files in R2; build the shared image pipeline once (creator photos) first | BZ-R-045, images |
| DR-BZ-32 | B | Database ownership model for the Business schema (P6B-06) | Option B: migration-owner role owns objects; runtime login has DML only; Business only; applied only under an approved operations plan | The current script repeats the R-01 pattern |
| DR-BZ-24 | B | (approved: local and CI first, then rollout after R-01 remediation and R1 pilot acceptance) Record the AWS instance size and authorise a re… | Owner-run read-back; about 416 MiB of limits for one API plus one audit job is an unmeasured planning figure | The ninth service has never been shown to fit |
| DR-BZ-31 | B | Gateway validation of Business responses | Exact allowlists for the four anonymous reads; pass-through elsewhere | The public reads are the most exposed |
| DR-BZ-30 | B | Search technology | Accept substring search for the pilot; you set the measured trigger for an index | Performance gate before wider use |
| DR-BZ-27 | C | Approve the Figma designs and the route space for Business screens (the current route space and design audit are fixed at 108 screens) | Extend numbering from M-109, one design package per screen group, in the order discovery, owner onboarding and profile, inquiries, reviews, staff | Slices BZ-C-001…023 |
| DR-BZ-28 | C | Whether any link may leave the app | None in the first release (a link implies a web page) | share controls |

### Events (35 rows) — `docs/architecture/events/EVT-Owner_Decisions_Required_PHASE7A.md`

| Id | Gate | Decision | Register recommendation | Unlocks / why |
| --- | --- | --- | --- | --- |
| DR-EV-01 | G | Scope reconciliation. Approve developing R3 events and ticketing now, in development only, behind closed flags, sandbox payments only; rais… | Approve. Production stays NO-GO and real-money processing stays off until DR-EV-22 | Without it the registers contradict the work (the same gap Business had, BZ-B-000) |
| DR-EV-02 | G | Service boundary. A new `events` Django/DRF service (the tenth deployable) with its own schema and role | Approve (ADR-EVT-001 options table). Exit criterion: if the staging stack cannot carry it (DR-EV-07), deploy the same code inside an existing deployable only by owner de… | Ownership, blast radius, dark-by-default |
| DR-EV-03 | G | One financial-event ledger. The only monetary ledger is the append-only `financial_event` table owned by a `payments` module inside the Eve… | Approve. Extract to its own service only when R4 payouts need it | Meets "no ledgers in multiple services" and ADR-010 "separate monetary ledger" |
| DR-EV-04 | G | Organizer authority is membership, not an Identity role (same model as Business). Moderators and administrators cannot hold organizer membe… | Approve | Per-object authority, separation of duties, no Identity migration |
| DR-EV-05 | G | Shared Identity step-up proof (P6B-04 / DR-BZ-33, still unapproved). Needed for event cancellation, refund approval, team-role change, orga… | Approve designing it once as a separate reviewed Identity task. Until it ships those operations fail closed, exactly as the Business four do | Cancellation triggers mass refunds; it must not rely on a bearer token alone |
| DR-EV-06 | G | Database ownership model for the `events` schema (the R-01 finding; DR-BZ-32 for Business). Append-only enforcement of the ledger depends o… | Option B: migration-owner role owns objects, the runtime login has DML only, events only; plus a trigger that rejects UPDATE/DELETE on `financial_event` | The ledger's immutability is otherwise a convention |
| DR-EV-07 | G | Capacity. A tenth service has never been shown to fit the staging VMs (DR-BZ-24 for the ninth is itself unmeasured). Authorise an owner-run… | Approve; local and CI first, staging only after R-01 and R1 pilot acceptance | Gates any deployment, not development |
| DR-EV-10 | A | Who may register as an organizer. | Invitation or administrator grant only for the pilot (as Business DR-BZ-03); one organizer per account; at most 3 open organizers | E1 registration |
| DR-EV-11 | A | Organizer verification policy: accepted evidence, methods, validity period, resubmission limit, reason codes; whether a verified Business (… | Contact-channel proof plus a structured declaration reviewed by a grant-holder; no identity document and no file upload until DR-EV-17; one resubmission cycle; fixed re-… | E1 verification, E2 publication |
| DR-EV-12 | A | Team roles and limits. | Three roles: `owner`, `manager` (events, ticket types, orders view), `checkin` (scan only, per assigned event). At most 10 active members; invitation TTL 72 h (Business… | E1 team |
| DR-EV-13 | A | Organizer suspension and restriction. Grounds, notice wording, appeal route, and the effect on live events and sold tickets | Reason code plus notice plus independent appeal; the administrator who restores is not the one who suspended. A suspension hides new events and pauses sales but never ca… | E1 suspension, E7 |
| DR-EV-14 | A | Event publication review. What a reviewer checks, the review time limit, which edits to a published event are *material* and re-review, who… | Every event is reviewed before first publication by a reviewer holding an `event_review` grant (MFA). Material fields: title, date and time, venue, category, price, capa… | E2 publication |
| DR-EV-15 | A | Rules and lists: event categories (two levels at most), counties and cities, prohibited event types, minimum lead time before sales open, m… | You supply the lists. Default time zone `Africa/Monrovia`; no events with start in the past; sales window must end by event end | E2, E3 |
| DR-EV-16 | A | Event visibility. | `draft` (organizer only) and `public` (discoverable). No unlisted or private-link events, because a link implies a web page (DR-EV-52). Invite-only events are a later de… | E2, E3 |
| DR-EV-17 | A | Event images. No image pipeline exists (Content handles video only; creator photos D-10 are written but disabled; Business images S7 are de… | No images in the first slices; categories show built-in artwork. Build the image decode-and-re-encode pipeline once (it also unblocks creator photos and Business images)… | E2 images |
| DR-EV-18 | A | Event notifications. No notification delivery is enabled anywhere (Identity records delivery choices only). | In-app status only for the first release: order, ticket and event-change states appear in My tickets and are polled. No push, SMS or email until a delivery provider is a… | E3 |
| DR-EV-20 | B | Currency. USD, LRD, or both; display rules; whether one event may mix currencies | One currency per ticket type, chosen by the organizer from an approved list; amounts stored as integer minor units; no conversion between currencies; an order contains o… | E4, E5 |
| DR-EV-21 | B | Fees and tax. Platform fee percentage and fixed part, who bears it (buyer or organizer), rounding, whether the fee is refundable, tax treat… | Fee policy is versioned configuration, applied server-side to every order and recorded in the order's immutable pricing snapshot. Rounding half-up per line to the minor… | E5 |
| DR-EV-22 | B | Real payment provider. Selection, Liberia coverage, merchant onboarding and KYC, webhook signing method, settlement currency, fees, refund… | Blocker, not decided here. Phase 7 builds the adapter interface and a sandbox adapter only. A real adapter needs a separate owner approval naming the provider, the evide… | E5 (live only) |
| DR-EV-23 | B | Reservation and purchase limits. Hold time, maximum tickets per order, maximum per account per event, per-account purchase rate | Hold 10 minutes; at most 6 per order; at most 10 per account per event; starting abuse budgets in the same "configuration, change only by owner decision" style as Busine… | E4 |
| DR-EV-24 | B | Payment confirmed after the reservation expired. | If inventory is still available, re-acquire it and issue; if not, issue nothing and open an automatic full refund (`late_payment_no_inventory`). Never oversell, never ke… | E4, E5 |
| DR-EV-25 | B | Buyer refund rules. Whether buyers may request refunds, the window, whether the fee is refundable, partial refunds | Organizer sets one of two policies per event (`no_refund` or `refund_until` a time at least 24 h before start); the platform fee is not refundable on buyer-requested ref… | E5, E7 |
| DR-EV-26 | B | Organizer cancellation and postponement. | Cancelling a published event with sold tickets requires step-up (DR-EV-05) and a reason code, revokes all tickets and creates a full refund including the fee for every p… | E4, E5, E7 |
| DR-EV-27 | B | Refund approval authority. Who reviews refunds, thresholds, two-person rule | A distinct `refund_review` grant (MFA, step-up). Administrator approval for any refund not produced by a rule; a second approver for amounts above a threshold you set; t… | E7 |
| DR-EV-28 | B | Ticket disputes (wrong event details, not admitted despite a valid ticket, duplicate charge). Adjudicator, evidence rules, time limit, outc… | Administrator with a `dispute_review` grant (MFA); outcomes limited to dismiss, refund, reinstate ticket; 14-day target; the check-in log is the evidence of record | E7 |
| DR-EV-29 | B | Organizer settlement. | None in Phase 7. The ledger records what is owed to the organizer as a derived figure only. No payout, transfer or settlement operation exists (PRD R4; "payout automatio… | E5 |
| DR-EV-30 | B | Financial record retention and legal hold (ADR-020 is open) | Keep financial events for the period legal advice sets; until then nothing is purged | E5 |
| DR-EV-31 | B | Free events. | Allowed: a price of 0 skips payment but uses the same reservation, inventory, issuance and check-in path. Reduces the money path to paid events only | E4 |
| DR-EV-40 | C | QR credential design. | A signed, versioned, opaque credential (no personal data) that the server always re-checks; admission is a single atomic server-side transition. Screenshots can be share… | E6 |
| DR-EV-41 | C | Transfer, gifting, resale. | Out of scope. A ticket belongs to the buying account for its life | E6 |
| DR-EV-42 | C | Offline check-in. The Phase 7 instruction allows it only if its conflict model is approved. Liberian venues often have poor connectivity, s… | Do not build in Phase 7. The proposed model (signed per-event manifest, per-device keys, first-valid-scan-wins on reconciliation, conflicts flagged for organizer and rev… | E6 |
| DR-EV-43 | C | What a scan and the organizer can see. | A scan shows the result, ticket type and, if already admitted, the time and gate. No buyer name, email or phone anywhere in the Events service. Organizers see counts and… | E6, privacy |
| DR-EV-50 | D | Flutter designs and route space. The Business route space ends at M-144. Approve Figma designs for the Phase 7 screens (about 28 across org… | One design package per slice, in slice order | each slice's Flutter work |
| DR-EV-51 | D | Console pages and grants. Organizer verification, event review, moderation, disputes, fraud, cancellation oversight, refund review, audit h… | Approve; administrator-only for grants and for approving non-rule refunds | E7 |
| DR-EV-52 | D | Outward links and receipts. Any share link, web ticket page or emailed ticket | None. A link implies a web page; the QR is shown only in the app. A purchase receipt is an in-app order record | E3, E6 |

### Advertising (38 rows) — `docs/architecture/advertising/AD-Owner_Decisions_Required_PHASE8A.md`

| Id | Gate | Decision | Register recommendation | Unlocks / why |
| --- | --- | --- | --- | --- |
| DR-AD-01 | G | Scope reconciliation. Approve developing direct-sold advertising now: development only, closed flags, sandbox billing, no network SDK; rais… | Approve. Production NO-GO until separately approved | Registers must not contradict the work (Business BZ-B-000 precedent) |
| DR-AD-02 | G | Service boundary. A new `ads` service with its own schema and role; Engagement, Points, Content and Moderation are not modified | Approve. Exit criterion: if staging cannot carry it, deploy as a separately imaged module only by owner decision | BR-001 requires ad telemetry independent from engagement; a separate owner makes the zero… |
| DR-AD-03 | G | Billing records versus the money ledger. Ads keeps *billing facts only* (reservations, billable events, invoice data, corrections). It crea… | Approve; decide the ledger's owner jointly with DR-EV-03 before either context handles real money | Meets "no ledgers in multiple services"; Events and Ads cannot both own it inside their o… |
| DR-AD-04 | G | Advertiser authority is membership, not an Identity role (Business and Events pattern). Moderators and administrators cannot hold advertise… | Approve | Per-object authority and separation of duties |
| DR-AD-05 | G | Shared prerequisites, same as Phase 7: Identity step-up proof (DR-EV-05 / DR-BZ-33), database ownership model (DR-EV-06 / DR-BZ-32), capaci… | Answer once. Until step-up ships, campaign budget increase, team change, advertiser closure and refund-like corrections fail closed. Ask whether Business/Events/Ads may… | Gates deployment, and several actions |
| DR-AD-06 | G | Media pipeline for creatives. No image pipeline exists (Content is video-only; creator photos D-10 are disabled; Business images S7 and Eve… | Build the image decode-and-re-encode pipeline once, as its own approved task, then use it for all four. Until then Phase 8 ships text-only sponsored cards (headline, bod… | Without a decision A3's image/video upload is blocked, not worked around |
| DR-AD-07 | G | Consent store ownership. No consent record exists anywhere in the platform (PRD-F09 requires consent records). | Identity owns a versioned, purpose-bound, withdrawable consent record (an additive Identity change needing its own approval). Until it exists, no ad decision and no meas… | A4 and A5 cannot legally or safely run without it |
| DR-AD-10 | A | Who may register as an advertiser | Invitation or administrator grant only for the pilot; one advertiser per account; at most 3 open | A1 |
| DR-AD-11 | A | Business identity association. How an advertiser proves it is, or is linked to, a verified Business | Optional link to a verified Business (R2). Proof by a signed, read-only internal call to Business ("is this account an active owner of verified business B?"), an additiv… | A1 |
| DR-AD-12 | A | Advertiser verification policy: evidence, methods, validity period, resubmission limit, reason codes | Contact-channel proof plus structured declaration (legal name, trading name, contact, intended category); verified Business link counts as strong evidence; no files unti… | A1 |
| DR-AD-13 | A | Team roles and limits | `owner`, `manager` (campaigns and creatives), `analyst` (read results only); at most 10 active members; 72 h invitation | A1 |
| DR-AD-14 | A | Advertiser restriction and suspension. Grounds, notice, appeal, effect on live campaigns | Reason code, notice, independent appeal; restorer ≠ suspender; suspension pauses delivery immediately, billing facts for delivered impressions stay valid | A1, A6 |
| DR-AD-15 | A | Who may not advertise | Owner and legal supply the list. Recommended: political parties, candidates and issue campaigns (see DR-AD-24), unverified advertisers, advertisers under restriction | A1 |
| DR-AD-20 | B | Pricing model | Only validated impressions are billable (CPM). Clicks are measured and reported but not billed in the first release (smaller click-fraud exposure). A flat sponsorship pr… | A2, A7 |
| DR-AD-21 | B | Currency, price list, minimum and maximum budget | One currency per advertiser from an approved list; integer money; prices as configuration. No values invented: development uses placeholder values clearly labelled. Bloc… | A2, A7 |
| DR-AD-22 | B | Budget rules | Total and daily budget; reserve-then-settle at decision time so spend can never exceed budget (no over-delivery tolerance); budget can be raised, lowered only to spent-p… | A2 |
| DR-AD-23 | B | Schedule rules | Start at least 24 h after approval; maximum flight 90 days; times stored UTC, shown in `Africa/Monrovia`; advertiser may pause and resume an active campaign until it end… | A2 |
| DR-AD-24 | B | Creative content policy (prohibited and restricted categories, claims, political content, minors, health and finance) | You and legal supply the list. Recommended launch: prohibit political, electoral and issue advertising, adult content, tobacco, gambling, weapons, unlicensed health and… | A3 |
| DR-AD-25 | B | Creative review process | Every creative version is reviewed before it can serve, by a reviewer with an `ad_review` grant (MFA), different from any advertiser member; bounded rejection reason cod… | A3 |
| DR-AD-26 | B | Formats and limits | First release: text-only native card (headline ≤ 40, body ≤ 120, CTA from a fixed list). Images and video only after DR-AD-06, with size, dimension, duration and type li… | A3 |
| DR-AD-27 | B | Destinations | In-app typed destinations first (a verified Business listing, a published Event). External https URLs are built and fully tested but ship disabled until you approve any… | A3, A4 |
| DR-AD-30 | C | Approved placements | P1: a sponsored native card inside the video feed. P2: a sponsored card on Explore. Nothing else: no pre-roll or mid-roll, no interstitial, no ads on profiles, comments,… | A4 |
| DR-AD-31 | C | Density and frequency caps | Feed: first ad after the 4th organic item, at most 1 per 6; at most 1 ad visible per screen; per account per campaign 3 a day and 10 a week | A4 |
| DR-AD-32 | C | Targeting | Contextual only: placement, county, content category. No behavioural profiling, watch history, Points data, demographic or lookalike targeting, no cross-app identifiers,… | A4 |
| DR-AD-33 | C | Validation parameters | Impression = at least 50% of the card visible for 1 continuous second, reported with a server-issued single-use decision; click needs a validated impression of the same… | A5 |
| DR-AD-34 | C | Invalid-traffic thresholds and outcomes | Starting thresholds in the policies; outcomes `valid`, `invalid`, `held`; alerts and holds only; no automatic penalty on an account; whether advertisers are told the inv… | A5, A6 |
| DR-AD-35 | C | Unavailable-ad fallback | The slot collapses (no gap, no placeholder); never filled with unreviewed content. A platform house notice is not built | A4 |
| DR-AD-36 | C | Third-party network (AdMob or similar). Eligibility, publisher approval, store listing, app-ads.txt hosting, consent SDK, policy fit and ch… | Not decided here; no SDK is added in Phase 8. A network adapter interface is documented; any live adapter needs a separate owner approval with the evidence listed in the… | A4 |
| DR-AD-40 | D | Consent model. Purposes, opt-in versus notice, withdrawal, minors, legal basis | Opt-in per purpose (`ads_delivery`, `ads_measurement`), off by default, withdrawal effective on the next request. Users without consent see no sponsored items (option A)… | A4, A5 |
| DR-AD-41 | D | Retention of decisions, events, hashed network identifiers and invoices (ADR-020 open) | Decisions and raw events 90 days; hashed network identifiers 30 days; aggregates and invoices per legal advice; nothing purged until you decide | A5, A7 |
| DR-AD-42 | D | Advertiser reporting privacy | Aggregates only; a cell with fewer than 20 events is suppressed; results delayed by the hold window; no account, device or location below county | A5 |
| DR-AD-43 | D | Minors. Whether the platform has an age rule that excludes ads | Decide the age policy; if any account may be under 18, those accounts receive no sponsored items. Blocker: legal | A4 |
| DR-AD-50 | E | Billing scope and corrections. Billing periods, invoice numbering, who approves corrections and credits (including invalid-traffic credits… | Monthly sandbox invoices; corrections need `ad_billing` grant, requester ≠ approver, second approver above a threshold you set; append-only | A7 |
| DR-AD-51 | E | Invoice content and tax | Placeholders until legal input: legal entity, address, tax treatment. Blocker | A7 |
| DR-AD-52 | E | Reconciliation | Interface only. Sandbox statement source in Phase 8; differences are recorded and reviewed, never auto-corrected | A7 |
| DR-AD-60 | F | Flutter designs and route space. Phase 7 proposes numbering from M-145; Phase 8 should not collide | Reserve M-200 and up for Advertising. About 24 screens (advertiser onboarding, team, campaign list, create and edit, budget and schedule, placement picker, creative edit… | all Flutter work |
| DR-AD-61 | F | Console pages and grants | Advertiser verification, campaign review, creative moderation, fraud alerts, suspension, scoped analytics, audit; grants `advertiser_review`, `ad_review`, `ad_fraud`, `a… | A6 |
| DR-AD-62 | F | Sponsored label, wording and design. | Always-visible "Sponsored" label plus advertiser name, a card style unlike organic video cards, no like, share or comment, a "Why this ad / Report this ad" sheet; copy a… | A4 |

### Finance (26 rows) — `docs/architecture/finance/FIN-Owner_Decisions_Required_PHASE9A.md`

| Id | Gate | Decision | Register recommendation | Unlocks / why |
| --- | --- | --- | --- | --- |
| DR-FIN-01 | G | Scope reconciliation. Approve developing R4 revenue accounting, sharing and *sandbox* payouts now: closed flags, sandbox books only. Raise… | Approve. Production NO-GO | Registers must not contradict the work |
| DR-FIN-02 | G | Financial bounded context and ledger ownership. A new `finance` service owns the one double-entry ledger. Events and Ads keep operational s… | Approve. This is the answer to DR-EV-03 and DR-AD-03 | "One approved accounting source of truth"; no ledger logic in Events, Ads or Points |
| DR-FIN-03 | G | Accounting method. Double-entry, append-only, hash-chained journals; money as integer minor units after explicit decimal calculation; no st… | Approve | Core correctness |
| DR-FIN-04 | G | Independent accounting approver. Name the qualified independent person or firm who signs off the chart of accounts, recognition rules, post… | Supply. Design cannot be approved by the author. Until named, no policy version can reach `approved` in a live book | The instruction requires an "independently approved financial policy" |
| DR-FIN-05 | G | Control model (separation of duties). Maker-checker-releaser with mutually exclusive grants; the matrix in the control model | Approve the matrix as written; it is the "explicitly approved control model" the instruction requires. Without approval no one may both create and approve, or approve an… | Core control |
| DR-FIN-06 | G | Authority and shared prerequisites. Finance authority is Finance-owned grants, not new Identity roles, held only by named administrator acc… | Approve. Until step-up exists, grant changes, destination changes, policy approval, payout release and freeze-lift fail closed | Several controls depend on step-up |
| DR-FIN-07 | G | Environment guard. Ledger books are `sandbox` or `live`; data never moves between them; `live` cannot be created without a named approval c… | Approve | Prevents accidental real money |
| DR-FIN-08 | G | Audit integrity anchoring and retention. Daily signed digest of each ledger and audit chain stored outside the Finance database (for exampl… | Approve the mechanism; Supply the retention period (legal, ADR-020, DR-EV-30) | Hash chains alone do not defeat a database owner |
| DR-FIN-10 | A | Currencies and conversion | Currencies accepted; whether any conversion exists; rate source and date rule | Recommended default: no conversion; allocate and pay within the currency of the revenue;… |
| DR-FIN-11 | A | Revenue source classes and which are shareable | For each class (network ad revenue, direct-sold ad revenue, sponsorship, ticket platform fees, other): shareable yes or no | Ticket face value is a liability to the organizer and is never shareable; the design enfo… |
| DR-FIN-12 | A | Recognition and shareability rules | When revenue is *recognized* (accounting) and when it becomes *shareable* | Approved principle already: shareable only when collected and reconciled (BR-010); you su… |
| DR-FIN-13 | A | Allocation periods | Period type, close lag, who may close | Structure: periods are policy-defined, closed once, never reopened |
| DR-FIN-14 | A | Pool formation | How shareable revenue becomes a distributable pool: share, reserve, cost deductions | Supply; "revenue-sharing percentage only after collected revenue, costs, reserves and leg… |
| DR-FIN-15 | A | Allocation basis | What measurable, finalized quantity divides the pool among payees | Options for you: (a) finalized qualified-view counts per creator (an Engagement-owned, pe… |
| DR-FIN-16 | A | Eligible creator and business definitions | Status conditions (for example active, not restricted), identity and rights evidence, age, jurisdiction | Eligibility is a signed snapshot from Creators or Business, recorded in each run; Finance… |
| DR-FIN-17 | A | Holds | Hold period for new allocations; reasons for withholding; appeal window | Structure supports policy hold, fraud hold, eligibility hold, destination hold |
| DR-FIN-18 | A | Payout rules | Minimum threshold, schedule, who bears provider fees, retry and return handling | Supply; none invented |
| DR-FIN-19 | A | Payee onboarding | Payout destination verification, identity (KYC), AML and sanctions screening, tax and withholding | Legal blocker; nothing here assumes Liberian rules |
| DR-FIN-20 | A | Adjustments and clawbacks | Allowed reasons, evidence, what happens after payout (negative balance, offset against future allocations, write-off) | Structure: always two approvers, reason code, evidence reference; Supply the clawback pol… |
| DR-FIN-21 | A | Creator disputes | Window, adjudicator, outcomes, time limit | Recommended structure: finance reviewer ≠ the person who prepared the contested item |
| DR-FIN-22 | A | Statements | Content, issuing schedule, legal wording, retention | In-app only; no emailed or downloadable-link statement unless you decide (DR-BZ-28 positi… |
| DR-FIN-30 | B | Revenue-source providers (ad network statements, direct-ad invoices, ticket captures, bank statements) | Build the `RevenueStatementSource` interface and sandbox sources; no real connection. Real sources need their own approval (for AdMob see provider constraints) |  |
| DR-FIN-31 | B | Payout provider | Blocker, not decided here. Build the `PayoutProvider` interface and a sandbox adapter with failure injection. A real provider needs due diligence, Liberia coverage, lega… |  |
| DR-FIN-40 | C | Flutter designs and route space. Reserve M-300 and up (Phase 7 uses M-145+, Phase 8 M-200+). About 20 screens in a separate Finance section… | Approve per slice |  |
| DR-FIN-41 | C | Console pages and grants. Grants: `fin_preparer`, `fin_approver`, `fin_releaser`, `fin_reconciler`, `fin_policy_author`, `fin_policy_approv… | Approve; grant changes need two administrators |  |
| DR-FIN-42 | C | Notifications | None; in-app status only (no delivery provider exists) |  |
