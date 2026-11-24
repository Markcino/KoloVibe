# Business module — exact owner decisions required (Phase 6A)

**Status: request for owner decisions, 24 November 2026. Every item below is OPEN unless it says otherwise; nothing here is approved.** Accountable owner: Mark Allen Gbalazeh (@Markcino). Record each answer with the [register's decision template](BIZ-Owner_Decision_Register_PROPOSED.md#decision-record-template-use-when-the-owner-decides) (revision, option, evidence link, date).

**Read this first.** The Phase 6A instruction asks for the decisions needed "before Business backend implementation". The backend **already exists**: Phase 6B (B1–B5) was merged by the owner in PR #219 behind five closed capability flags and is not deployed. The decisions are therefore grouped by what they gate: *finishing* the backend, *enabling* it anywhere, and *building clients*. Production remains NO-GO and no AWS or staging change has been made.

**Already decided (not asked again):** all 26 original recommendations DR-BZ-01…26 as written (24 November, [approval record](BIZ-Owner_Approval_Record_2026-11-24.md)); DR-BZ-21, formally: **Flutter mobile for visitors, customers, owners and staff; the protected Django console for administrators and moderators only; no public website and no business web portal** ([client architecture](BIZ-Client_Architecture_DR-BZ-21.md)).

## Gate A — before the unbuilt backend can be finished

These are the approved requirements that have no code because they need a policy, a value or a design.

| # | Decision the owner must make | Recommendation (least privilege) | Unlocks |
| --- | --- | --- | --- |
| A1 | **DR-BZ-33** Approve designing the purpose-bound step-up proof in Identity (P6B-04) | Approve as a separate, reviewed Identity task; keep the four actions disabled until it ships | live contact change, staff removal, closure, ownership transfer (BZ-R-002, 008, 036) |
| A2 | **DR-BZ-29** Accept the Business-local report queue or approve generalising Moderation | Accept the local queue for the pilot; build restoration (by a different reviewer), appeals and listing reports inside Business | BZ-R-025, 032; review restoration and appeals |
| A3 | **DR-BZ-25** (approved as recommended) Supply suspension and delisting **grounds, the notice wording and the appeal route** | Reuse the Moderation pattern: reason code, notice, independent appeal; administrator restores, never the suspender | BZ-R-009; the `suspended` and `closed` states become reachable |
| A4 | **DR-BZ-26** (approved) Supply the dispute adjudicator, evidence rules and time limit | Administrator with MFA; listing frozen on a credible report | BZ-R-008 disputes |
| A5 | **Verification policy** under DR-BZ-04, 19: the written evidence checklist, accepted methods, validity period, resubmission limit, reason codes; and **whether an owner may withdraw a case** | A+B (document review plus contact-channel proof); no identity document; one resubmission cycle; re-verification at a fixed period you choose | file evidence; expiry; BZ-R-004 |
| A6 | **Review policy values** under DR-BZ-15, 16, 22: minimum review count before an average shows, edit window, author display form, account-age gate, hold thresholds; **and whether to add account age to Identity's response** | Show an average only after a count you set; pseudonymous author labels; the starting thresholds in `limits.py` until pilot data exists | BZ-R-021, 026, 028, 030, 031 |
| A7 | **DR-BZ-10** Initial category list and county/city lists | Two levels at most; you supply the list | category data; county validation |
| A8 | **DR-BZ-09, 11** Public-field warning and notice copy; which profile fields are **material**; public coordinate precision | Keep `display_name`, category, address line, contacts as material; coordinates stay private | BZ-R-007, 012, 014 |
| A9 | **DR-BZ-18, 23** A retention period and a purge trigger per data category; legal-hold rules; the legal reviewer (named) and outcome | Decide after legal input; until then nothing purges | purge jobs, export and erase (BZ-R-039, 040) |
| A10 | **Privacy orchestration** (ADR-020): who processes export and erase requests across services | A platform decision, not a Business one | BZ-R-040 |
| A11 | **DR-BZ-14** Whether inquiries and reviews send any notification | None in the first release | notification work |
| A12 | **DR-BZ-19, 20** Whether files may ever be uploaded (evidence, images) and under what storage and scanning | No files in R2; build the shared image pipeline once (creator photos) first | BZ-R-045, images |

## Gate B — before any Business capability is enabled in any deployed environment

| # | Decision | Recommendation | Why it gates enabling |
| --- | --- | --- | --- |
| B1 | **DR-BZ-32** Database ownership model for the Business schema (P6B-06) | Option B: migration-owner role owns objects; runtime login has DML only; Business only; applied only under an approved operations plan | The current script repeats the R-01 pattern |
| B2 | **DR-BZ-24** (approved: local and CI first, then rollout after R-01 remediation and R1 pilot acceptance) Record the **AWS instance size** and authorise a read-only capacity check | Owner-run read-back; about 416 MiB of limits for one API plus one audit job is an unmeasured planning figure | The ninth service has never been shown to fit |
| B3 | **DR-BZ-31** Gateway validation of Business responses | Exact allowlists for the four anonymous reads; pass-through elsewhere | The public reads are the most exposed |
| B4 | **DR-BZ-30** Search technology | Accept substring search for the pilot; you set the measured trigger for an index | Performance gate before wider use |
| B5 | **Confirm or change the starting numbers** in `services/business/service/limits.py` (registration, staff, inquiry, review, report, search, reveal and hold limits; listed in the [requirements reconciliation](../../requirements/BIZ-Requirements_Reconciliation_PHASE6A.md#4-values-and-content-the-approval-cannot-supply-consolidated)) | Confirm as pilot values | They are policy once approved (DR-BZ-22) |
| B6 | **Governance:** raise the DOC-023 change request that moves the DOC-020 register row and the DOC-207 logs from "Deferred" to approved, assigns an ADR number if wanted, and splits tracker row B-19 (BZ-B-000, P6B-01, P6B-09) | Approve the change request; the registers still contradict the approval record | The registers are the control record |
| B7 | **Review the Phase 6B code** (PR #219 is merged; the approval of the *design* does not approve the *code* for release) | Owner review of the diff and an owner-approved release record naming the flags, evidence and decisions resolved | No flag may open without it |
| B8 | **Operations:** schedule the audit-delivery job; accept a kill-switch and rollback procedure | As for the three existing audit jobs | Evidence must reach Audit |

## Gate C — before any client work (Flutter or console)

| # | Decision | Recommendation | Unlocks |
| --- | --- | --- | --- |
| C1 | **DR-BZ-27** Approve the Figma designs and the route space for Business screens (the current route space and design audit are fixed at 108 screens) | Extend numbering from M-109, one design package per screen group, in the order discovery, owner onboarding and profile, inquiries, reviews, staff | Slices BZ-C-001…023 |
| C2 | **DR-BZ-28** Whether any link may leave the app | None in the first release (a link implies a web page) | share controls |
| C3 | Approve the console page list and priority for moderators and administrators (verification, profile revisions, reports, grants, categories, suspension) | In that order; suspension waits for A3 | Slices BZ-C-030…032 |
| C4 | Approve the three new requirements **BZ-R-052, 053, 054** (shared client stack, no client authority, one-time codes) | Approve | Client acceptance criteria AC-CLI-006…008 |

## Not needed from the owner

Payments, ticketing, advertising and live streaming remain excluded; no new service, queue, broker permission, AWS change or migration is requested; the Moderation service stays untouched unless you choose A2 option B.

## Suggested order

1. B6 and B7 (governance and code review) — they make the record consistent.
2. A1, A5, A6 — they unlock the most blocked backend work.
3. B1, B2 — they decide whether and where the service can ever run.
4. C1 — it starts the client track while the rest is decided.
