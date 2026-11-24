# Business requirements — reconciliation with owner decisions and the as-built backend (Phase 6A)

**Status: reconciliation record, 24 November 2026.** It does not change the wording of [DOC-020 (proposed)](DOC-020_Business_Requirements_and_Scope_PROPOSED.md). It states, for every requirement BZ-R-001…054, (1) what the owner has approved, (2) what Phase 6B built, and (3) what the owner still has to supply or decide. Nothing here approves anything new.

**Evidence base.** The [owner approval record](../architecture/business/BIZ-Owner_Approval_Record_2026-11-24.md) (all 26 original recommendations approved as written; PR #218 merged at 10:08:56 UTC on 24 November), the DR-BZ-21 decision of the same day, and the Phase 6B results B1–B5 and completion report, checked against the code at `main` `5e7eda7` (Business service 162 tests re-run and passing on SQLite in Phase 6A; the 11 PostgreSQL 16 tests are as recorded in 6B and were not re-run). Phase 6B code is merged but **not deployed**; production is NO-GO.

## 1. Legend

| Approval state | Meaning |
| --- | --- |
| **A** | Approved as written (the matching DR-BZ-nn was approved "as recommended") |
| **A + owed** | Approved, but the owner still owes content, a list or a number that approval cannot contain (see section 4) |
| **D** | Formally decided by the owner (DR-BZ-21) |
| **P** | Proposed in Phase 6A reconciliation; **not approved** |
| **A, deviates** | Approved design, but the as-built backend differs and the owner must accept or reject the difference (section 5) |

| As built | Meaning |
| --- | --- |
| Built | Implemented and tested locally behind closed flags |
| Partial | Implemented with a stated gap |
| Not built | No code |
| n/a | Not applicable to the backend |

## 2. Requirement-by-requirement status

### Registration and ownership

| ID | Gate | Approval | As built | Owner still owes |
| --- | --- | --- | --- | --- |
| BZ-R-001 | DR-BZ-03, 22 | A + owed | Built: invitation-only registration grant (administrator, MFA, never for self), cap of 3 open businesses, 5 registrations per day, atomic first owner, idempotent | Confirm the numbers in `limits.py`; say when invitation-only ends |
| BZ-R-002 | DR-BZ-08 | A + owed | Partial: invariant holds (owners cannot leave; DB refuses duplicate active membership). **Closure and ownership transfer are not built** (need step-up) | Approve step-up design (DR-BZ-33) |
| BZ-R-003 | DR-BZ-04 | A | Built: normalised-name duplicate flag at verification submission; never auto-rejects | — |
| BZ-R-004 | DR-BZ-04, 19 | A + owed | Partial: case states `submitted`, `under_review`, `needs_info`, `verified`, `rejected`, `revoked`; **no `withdrawn` state**; text evidence only; free reason codes | Evidence checklist, accepted methods, validity period, reason-code list; whether an owner may withdraw a case |
| BZ-R-005 | DR-BZ-07 | A | Built: scoped grant + MFA + claim-then-decide; submitter, creator and affiliate refused with a 404 identical to unknown; idempotent; one decision under concurrency (PostgreSQL race test) | — |
| BZ-R-006 | DR-BZ-05 | A | Built: "verified" separate from "listed"; revocation decision implemented | — |
| BZ-R-007 | DR-BZ-11 | A + owed | Built: material fields pre-moderated, previous approved revision stays public. Live contact change **refuses** until step-up exists | Confirm which fields are material (`MATERIAL_FIELDS`); DR-BZ-33 |
| BZ-R-008 | DR-BZ-08, 26 | A | **Not built**: transfer, disputes, listing freeze | Reviewer, evidence rules and time limits for disputes |
| BZ-R-009 | DR-BZ-25 | A + owed | **Not built**: `suspended` and `closed` exist as states but no operation reaches them; no appeal | Grounds, notice wording, appeal route |

### Profiles, categories, contacts, hours

| ID | Gate | Approval | As built | Owner still owes |
| --- | --- | --- | --- | --- |
| BZ-R-010 | DR-BZ-11 | A | Built: working revision; public sees last approved revision only | — |
| BZ-R-011 | DR-BZ-10 | A + owed | Built: administrator-managed, two levels, owners cannot create | The initial category list; county and city lists (county is pattern-checked, not validated) |
| BZ-R-012 | DR-BZ-09 | A + owed | Built: kinds phone/email/website/social, `https` only, private unless `is_public` | Public-field warning copy |
| BZ-R-013 | — | A | Built: weekly rules, dated exceptions, IANA zone (default `Africa/Monrovia`), shared `is_open()` | — |
| BZ-R-014 | DR-BZ-09, 13 | A + owed | Partial: address and coordinates private unless opted in; **coordinates never exposed publicly**; no distance | Public coordinate precision (never decided) |
| BZ-R-015 | — | A | Built: bounded, normalised plain text | — |

### Listings, discovery, search

| ID | Gate | Approval | As built | Owner still owes |
| --- | --- | --- | --- | --- |
| BZ-R-016 | DR-BZ-05 | A | Built: one eligibility predicate (verified + approved profile + category, county, city); public-columns-only projection; `reconcile_listings` drift report | — |
| BZ-R-017 | DR-BZ-13 | **A, deviates** | Partial: filters `q`, `category`, `county`, `city`, `open_now`, `verified`; **substring match with two relevance tiers, not full-text/trigram**; no paid placement | Accept or reject the search technology (DR-BZ-30) |
| BZ-R-018 | — | A | Built: ≤ 20 per page, keyset cursor signed with a service key and bound to its filters, unknown parameters 400 | — |
| BZ-R-019 | DR-BZ-12 | A + owed | Built: anonymous callers get `contacts: null`; signed-in verified accounts get public channels within 100 reveals per day | Confirm 100/day |
| BZ-R-020 | — | A | Built: no cache; revocation, unpublish and ineligibility remove the listing in the same request | An approved maximum age before any edge cache |

### Inquiries

| ID | Gate | Approval | As built | Owner still owes |
| --- | --- | --- | --- | --- |
| BZ-R-021 | DR-BZ-14, 22 | A + owed | Built: verified email, one open thread per pair, 10 per day and 30 per hour per business. **Account-age gate not built** (the Gateway does not carry account age) | Account-age number and whether to add it to Identity's response |
| BZ-R-022 | DR-BZ-14 | A | Built: plain text, no attachments, 100-message cap | — |
| BZ-R-023 | — | A | Built: business sees `Customer N` only, never an account id | — |
| BZ-R-024 | DR-BZ-22 | A | Built: undisclosed block, close, throttles that count only real eligible attempts | — |
| BZ-R-025 | DR-BZ-17 | **A, deviates** | Built into the Business-local report queue (not Moderation) | DR-BZ-29 |

### Reviews and moderation

| ID | Gate | Approval | As built | Owner still owes |
| --- | --- | --- | --- | --- |
| BZ-R-026 | DR-BZ-15 | A + owed | Built: basis stored and shown (`interaction_confirmed`, `invited`, `open`) | Minimum account age; whether `open` reviews show |
| BZ-R-027 | DR-BZ-15 | A | Built: one review per author per business **ever**; owners, staff and the registering account refused | Whether a re-review after a period is allowed |
| BZ-R-028 | DR-BZ-16 | A + owed | Built: `published`, `held`, `removed`, `withdrawn`; three fraud signals hold a review | Confirm hold thresholds (`limits.py`) |
| BZ-R-029 | DR-BZ-16 | A | Built: one response per published review; no business operation hides, edits or removes a review | Whether responses are pre-moderated |
| BZ-R-030 | DR-BZ-16 | A + owed | Built: aggregate recomputed in the same transaction; **average hidden until a minimum count is set** | The minimum count |
| BZ-R-031 | DR-BZ-16, 18 | A + owed | Partial: withdrawal built (blanks text now); **edit window not set**; no edit history | Edit window; whether edit history is kept |
| BZ-R-032 | DR-BZ-17 | **A, deviates** | Partial: report, audited case read, remove or keep, idempotent, MFA + `review_queue` grant, conflicts blocked. **No restoration, no appeals, no listing reports** | DR-BZ-29; DR-BZ-25 |

### Authorization

| ID | Gate | Approval | As built | Owner still owes |
| --- | --- | --- | --- | --- |
| BZ-R-033 | — | A | Built: gateway authenticates and gates; service authorizes every object | — |
| BZ-R-034 | — | A | Built: 404 for non-entitlement, tested across every owner operation | — |
| BZ-R-035 | — | A | Built: membership and grants resolved per request, no cache | — |
| BZ-R-036 | DR-BZ-08 | A + owed | **Fails closed**: step-up consumption does not exist in Identity | DR-BZ-33 (design approval) |
| BZ-R-037 | — | A | Built: no new Identity role or credential | — |

### Privacy, retention and abuse

| ID | Gate | Approval | As built | Owner still owes |
| --- | --- | --- | --- | --- |
| BZ-R-038 | — | A | Built: classification in the privacy document; staff never see legal name; business never sees customer account ids | — |
| BZ-R-039 | DR-BZ-18 | A + owed | Partial: withdrawal blanks review text; **no purge jobs, no legal hold** | Retention period per category; legal-hold rule |
| BZ-R-040 | DR-BZ-18 | A + owed | **Not built**: no export or erase operation, and no privacy orchestration path exists on the platform | A privacy orchestration decision (ADR-020) |
| BZ-R-041 | — | A | Built: ids-only audit payloads; a contract test guards the Business and Audit kind lists against drift | — |
| BZ-R-042 | DR-BZ-22 | A + owed | Built: hashed-key throttles on every listed action | Confirm all numbers (section 4) |
| BZ-R-043 | — | A | Built: strict allowlist parsing, body capped before read | — |
| BZ-R-044 | — | A | Built: audit outbox on every state change and privileged read | Schedule the delivery job (operations) |
| BZ-R-045 | DR-BZ-19, 20 | A + owed | **Not built**: no file evidence, no images | Evidence checklist; private storage and scanning; image pipeline |

### Architecture and delivery

| ID | Gate | Approval | As built | Owner still owes |
| --- | --- | --- | --- | --- |
| BZ-R-046 | DR-BZ-24 | A | Built: five flags, closed by default | An owner-approved release record before any flag opens |
| BZ-R-047 | DR-BZ-02 | **A, deviates** | Built: own schema and role, UUID references, no cross-service SQL. **Owner/runtime separation is not met** (same pattern as R1; P6B-06) | DR-BZ-32 |
| BZ-R-048 | — | A | Built: 57 operations merged into DOC-205 before use; route-contract and role-matrix tests extended | — |

### Client surfaces

| ID | Gate | Approval | As built | Owner still owes |
| --- | --- | --- | --- | --- |
| BZ-R-049 | DR-BZ-21 | **D** | n/a. No Business screen or web page exists | Designs (DR-BZ-27) |
| BZ-R-050 | DR-BZ-21 | **D** | Not built: no console Business page | Designs and priorities for console pages |
| BZ-R-051 | DR-BZ-21 | **D** | Holds today: Gateway and Business have no templates, CORS or HTML; no test pins it | — (a guard is backlog item BZ-C-000) |
| BZ-R-052 | — | **P** | n/a | Approval of the requirement |
| BZ-R-053 | — | **P** | n/a | Approval of the requirement |
| BZ-R-054 | DR-BZ-28 | **P** | Built on the server (codes shown once, digest only) | DR-BZ-28 |

## 3. By the fourteen topics the owner asked about

| Topic | Requirements | Approved | Built | Still blocked |
| --- | --- | --- | --- | --- |
| Registration | 001, 003 | yes | yes | numeric confirmation; end of invitation-only |
| Ownership | 002, 008, 033–037 | yes | partly | closure, transfer, disputes, step-up |
| Verification | 004–006 | yes | partly | checklist, methods, validity, withdraw |
| Business profiles | 010, 012, 014, 015 | yes | yes | warning copy; coordinate precision |
| Categories | 011 | yes | yes | initial lists |
| Operating hours | 013 | yes | yes | — |
| Listings | 016, 020 | yes | yes | cache maximum age |
| Search | 017–019 | yes | partly | search technology (DR-BZ-30) |
| Customer inquiries | 021–025 | yes | yes | account-age gate; notifications (DR-BZ-14) |
| Reviews | 026–031 | yes | yes | policy numbers; edit window; response moderation |
| Staff permissions | 002, 034, 036 | yes | partly | removal and transfer need step-up |
| Moderation | 005, 009, 025, 032 | yes | partly | Moderation placement (DR-BZ-29); restoration; appeals |
| Suspension and appeals | 009 | yes | **not built** | grounds, notice, appeal route (DR-BZ-25) |
| Privacy and retention | 038–041, 045 | yes | partly | every retention period; export/erase; legal review (DR-BZ-23) |

## 4. Values and content the approval cannot supply (consolidated)

Everything below needs the owner. None is invented in code; where a number exists it is a **starting value in `services/business/service/limits.py`**, labelled for confirmation.

| Item | Where it matters | Starting value in code |
| --- | --- | --- |
| Verification evidence checklist, accepted methods, validity period, review target, resubmission limit, reason codes | BZ-R-004 | none; 1–5 text items, free codes |
| Category taxonomy; county and city lists | BZ-R-011, 014 | none |
| Public-field warning and notice copy; suspension and removal notice copy | BZ-R-012, 009 | none |
| Retention period per data category; legal-hold rules | BZ-R-039 | none; nothing purges |
| Legal review owner and outcome (DR-BZ-23) | BZ-R-004, 032 | none |
| Review policy: minimum count for an average, edit window, author display, account age, hold thresholds | BZ-R-026–031 | average hidden; hold 10 per business per day, 3 per author per day, duplicate text 30 days |
| Registration numbers: 3 businesses, 5 per day, 10 staff, 10 pending invitations, 72 h staff codes | BZ-R-001 | as listed |
| Throttles: 5 verification submissions per day, 60 profile edits and 30 listing changes per hour, 10 inquiries per day, 30 new threads per business per hour, 60 messages per hour, 5 reviews per day, 20 reports per day, 1,200 public reads per hour, 100 contact reveals per day | BZ-R-042 | as listed |
| Which profile fields are material | BZ-R-007 | name, category, address line, contacts |
| Public coordinate precision | BZ-R-014 | not exposed |
| Maximum cache age at any edge | BZ-R-020 | no cache |

## 5. Requirements and decisions that need explicit owner approval now

1. **Deviations from the approved design** the owner must accept or reject: BZ-R-017 (search), BZ-R-025 and 032 (Moderation placement), BZ-R-047 (database ownership), and the gateway response validation described in [the architecture validation](../architecture/business/BIZ-Architecture_Validation_PHASE6A.md). Decisions DR-BZ-29 to DR-BZ-32.
2. **New requirements proposed in this phase:** BZ-R-052, 053, 054. BZ-R-049 to 051 only restate the decided DR-BZ-21.
3. **Step-up (BZ-R-036):** an Identity change; DR-BZ-33.
4. **Not-built approved requirements** that need a design before they can be built: BZ-R-008, 009, 031 (edit window), 040, 045.
5. **Governance:** the formal change request (DOC-023) that moves the DOC-020 register row and the DOC-207 decision and ADR logs from "Deferred" to the approved state has **not** been raised (backlog item BZ-B-000). The registers still say "Deferred — no standalone specification". This record does not edit them.

The consolidated list, with recommendations, is in [the owner decisions required](../architecture/business/BIZ-Owner_Decisions_Required_PHASE6A.md).
