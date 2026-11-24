# Business module — data privacy and retention requirements

**Status: PROPOSED — for owner approval. Nothing is collected; the module does not exist.** Phase 6A, 24 November 2026. This document gives requirements, data inventory and *mechanisms*. It deliberately **proposes no retention periods and makes no legal or jurisdictional claim**: those are open owner and legal decisions (DR-BZ-18 retention, DR-BZ-19 evidence, DR-BZ-23 legal review; platform-wide ADR-020, OD-05 and OD-08). Compare the creator-photo rules ([D-10](creator-profile-photos.md)) and the [recent searches note](recent-searches.md) for the house style.

> **Status update, 24 November 2026 (Phase 6A reconciliation).** This is supporting design for decisions the owner approved as written (DR-BZ-01…26, [approval record](../architecture/business/BIZ-Owner_Approval_Record_2026-11-24.md)); no separate approval of this document is recorded, and the banner above is the original wording. DR-BZ-21 was decided formally (Flutter only; no public website or business portal). The backend was built in Phase 6B (PR #219, closed flags, **not deployed**; production NO-GO). Where this document and the as-built system differ, see the [architecture validation](../architecture/business/BIZ-Architecture_Validation_PHASE6A.md); what the owner must still decide is in [owner decisions required](../architecture/business/BIZ-Owner_Decisions_Required_PHASE6A.md).

## 1. What is and is not decided

| Item | State |
| --- | --- |
| Data categories, purposes, access and visibility defaults | **Proposed** here |
| Deletion and retention *mechanisms* (soft delete, purge, legal hold) | **Proposed** here |
| Retention periods and trigger events per category | **Open** (DR-BZ-18); the implementation must ship with *no automatic purge* until approved |
| Whether identity documents are collected as evidence | **Open** (DR-BZ-19) |
| Legal basis, notice wording, data-subject-rights process, minors, residency | **Open** (DR-BZ-23, ADR-020) |
| Existing Identity privacy requests | A **receipt only**: processing awaits an approved policy, so no export or erasure runs anywhere on the platform today |

## 2. Principles (proposed)

1. **Collect only what a stated purpose needs.** Each field in the [ERD](../architecture/business/BIZ-ERD_PROPOSED.md) has a purpose below; fields without one are not added.
2. **Private by default; public by owner action.** Optional contact and location fields are public only when the owner marks them so, after a plain warning at entry that public fields are visible to everyone and can be copied.
3. **Pseudonymous to the counterparty.** A business never receives a customer's account id or email; a customer sees a business's public profile only. A review author is shown only by the label policy (DR-BZ-16); the account id is never exposed.
4. **No covert tracking.** No IP addresses, device identifiers, precise location, advertising identifiers or behavioural profiles are stored for this module. Abuse controls use hashed throttle keys with short operational lifetimes and content-based signals. Any device or network signal needs separate owner approval with its own retention rule.
5. **Security of evidence.** Verification evidence is the most sensitive category: private storage, narrow access, audited reads, shortest feasible retention.
6. **Identifiers only in logs and audit.** No message text, review text, contact value, evidence content, token or file name in any log, audit event, metric or error (BZ-R-041).
7. **Deletion is designed in.** Every category has a lawful way to be deleted or anonymized, with legal hold respected, before collection starts.

## 3. Data subjects

| Subject | Examples | Notes |
| --- | --- | --- |
| Business owner or staff | Account id, membership, legal name, contact details, evidence | May be a sole trader whose business data **is** personal data (home address, personal mobile) |
| Customer (inquirer) | Account id, display name label, message text | Message text may contain anything the customer types |
| Review author | Account id, rating, review text | Text may include personal data about third parties |
| Reviewer (moderator/administrator) | Account id, decisions, reason codes | Employee-like records; audit |
| Third parties named in text | Staff, other customers | No consent; report path and removal |

## 4. Data inventory and classification

Legend — **Public**: visible to anyone permitted by DR-BZ-12. **Retention**: *Open* means the period and trigger need DR-BZ-18; the **mechanism** column is what ships.

| # | Category | Fields | Purpose | Class | Who can access | Mechanism for deletion | Retention |
| --- | --- | --- | --- | --- | --- | --- | --- |
| P-01 | Business identity (private) | legal name, creator account id, membership rows | Ownership, verification, disputes | Owner-private | Owner (own), reviewers (assigned) | Soft close; tombstone keeps ids and decisions; purge text fields | Open |
| P-02 | Business profile (public) | display name, category, county, city, summary, description, hours | Discovery | Public | Anyone permitted | Unlist; revision superseded; purge superseded revisions | Open |
| P-03 | Optional exact location | address line, coordinates | Customer navigation | Owner-private → public by opt-in | Owner; public only if opted in | Field-level clear; never in logs | Open |
| P-04 | Contact channels | phone, email, website, social | Customer contact | Public by per-channel flag | Per flag; reveal budget | Field-level delete on request or closure | Open |
| P-05 | Verification case and decision | state, reason code, reviewer id, times | Trust | Reviewer-private | Reviewers (grant), owner (applicant-visible fields) | Anonymize reviewer id? decision-record retention | Open |
| P-06 | Verification evidence | documents or proofs (if enabled) | Prove ownership | **Highest sensitivity** | Reviewers with evidence grant only | Object delete in private bucket; DB row to `purged`; verified with a listing check | Open (DR-BZ-19) |
| P-07 | Inquiry threads and messages | customer label, account id, text, timestamps, state | Customer-business contact | Customer-private (shared with the thread's business) | Customer; owner/staff of that business; moderators on report | Replace text with tombstone; remove account id link; keep counters only | Open |
| P-08 | Inquiry blocks | business id, customer account id | Harassment control | Operational/private | Owner (effect only), service | Delete with business or account deletion | Open |
| P-09 | Reviews | rating, title, text, basis, state, author account id, times | Reputation | Public (published) / private (author id, state) | Public text; author; moderators | Withdrawal and deletion semantics: delete vs anonymize author vs retain text | Open (DR-BZ-16/18) |
| P-10 | Review revision history | prior text and ratings | Dispute handling | Private | Moderators | Drop history on withdrawal or after window | Open |
| P-11 | Review responses | business text | Business reply | Public (published) | Public; owner; moderators | As review | Open |
| P-12 | Reports and moderation decisions | reporter id, subject, reason code, details text, decision | Safety | Moderation-private | Reviewers | Strip reporter id after resolution? | Open |
| P-13 | Fraud-hold records | reason codes only | Review integrity | Reviewer-private | Reviewers | Delete after release or removal | Open |
| P-14 | Audit events | actor id, kind, subject type and id, time | Accountability | Operational | Audit read grants (MFA) | Per Audit retention policy | Open (OD-08, ADR-017) |
| P-15 | Operational counters and nonces | hashed throttle keys, nonces, idempotency digests | Abuse control, replay defence | Operational | Service only | Bounded purge of expired rows | Proposed: follow the existing Identity pattern (window plus short grace; nonce table is already purged after 10 minutes) — owner to confirm |
| P-16 | Customer-facing notices | in-app text only | Transparency | n/a | n/a | n/a | n/a |

Not collected, by design: IP addresses and device ids for this module, precise customer location, government identity numbers unless DR-BZ-19 approves a specific document type, payment data, contact books, advertising identifiers.

## 5. Visibility defaults (proposed)

| Item | Default |
| --- | --- |
| Legal name | Never public |
| Address line and coordinates | Not public unless the owner opts in; public coordinates are coarsened (precision to be set by the owner when DR-BZ-13 decides on any “near me” use) |
| Phone, email, website, social | Each channel has `is_public`, default **false** |
| Review author | Label policy (DR-BZ-16); never account id; owner sees no more than the public does |
| Inquiry sender | Display-name label; business cannot see email or account id |
| Verification result | Public `verified` flag; reason codes only to the owner, and only those the policy allows |

## 6. Retention and deletion mechanism (proposed design, no periods)

1. **States.** Each personal-data row has an explicit lifecycle: `active` → `tombstoned` (content removed, identifiers or counters kept if required) → `purged` (row deleted). Moves are performed by bounded batch jobs, never by request handlers.
2. **Policy as configuration.** A per-category retention rule (trigger event + period + action) is read from approved configuration. **If a rule is absent, nothing is purged** and a report lists the categories with no rule. This is the same discipline as Identity's retention module, which leaves policy rows untouched until a decision exists.
3. **Legal hold.** A hold flag on a business, account or report prevents tombstoning and purging for its rows; setting and clearing a hold is a privileged, audited action. Hold criteria are an owner and legal decision.
4. **Evidence first.** Evidence objects are deleted from private storage *before* the row is marked `purged`, and the purge job verifies the object is gone. Abandoned or rejected uploads are covered by the same rule; the R2 lifecycle approval is already an open item (OD-07).
5. **Backups.** Deleted data can persist in backups until they expire. Backup retention and restore procedures are open (ADR-016, INF-05); a restore must re-apply deletions recorded since the backup. This requirement is carried to the operations runbook.
6. **Audit stays minimal** so it can outlive content: it holds ids and decisions, never content, and is therefore not a deletion blocker. Its own retention is OD-08.
7. **Tests.** For every category: deletion removes content, leaves no recoverable copy in an API or search index, respects holds, and is idempotent.

## 7. Account deletion and data-subject requests

**Today:** Identity records a `PrivacyRequest` (access or deletion) as a receipt with status `received`; nothing processes it, and no service exposes export or erase.

**Proposed requirement:** when the platform defines a privacy orchestration path (owner decision; not designed here), Business exposes two internal operations, reachable only by that orchestrator's service identity: **export** (the data subject's own records in a structured form) and **erase/anonymize** (per category rule). Until then the module must not store anything it could not later export or erase: every personal-data table is keyed by `account_id` or reachable from it.

| Category | Options for account deletion (owner chooses) |
| --- | --- |
| Review text and rating | Delete; or retain text with author detached (anonymous label) if the owner and legal advice allow; ratings may remain in aggregates |
| Inquiry messages | Delete the customer's messages; or keep the thread with tombstone for the business's own records |
| Membership | Remove; last-owner rule requires a transfer or closure first |
| Verification case/evidence | Deletion on closure per DR-BZ-19; decision record may need to remain for disputes |
| Reports | Detach reporter id once resolved |

## 8. Notices and transparency (to be written by the owner)

Before any collection, the product needs plain-language copy for: what is public on a listing; that contact details can be copied by anyone; what a business sees when a customer sends an inquiry; what a review shows about its author; what is reviewed and by whom; how long things are kept; how to withdraw a review, close a business and request deletion. These are copy and policy items; they are not drafted here to avoid inventing policy.

## 9. Abuse prevention and privacy together

| Abuse control | Privacy treatment |
| --- | --- |
| Throttles and velocity limits | Hashed keys, minimal lifetime, no raw identifiers stored |
| Similarity and spam signals on reviews and messages | Computed in process on the text; only a reason *code* is stored in the hold record |
| Duplicate-business detection | Normalized names and contacts compared inside the Business schema; matches shown to assigned reviewers only |
| Contact-reveal budget | Counter per account, not a log of which businesses were viewed |
| Reviewer anomaly checks | Aggregated per reviewer from decision rows, not from content reads |

## 10. Gates before any personal data is collected

1. Owner approval of this document and DR-BZ-18/19/23 (periods, evidence, legal review).
2. Privacy notice copy approved and present in the app screens.
3. Deletion tests passing for every category enabled in that slice.
4. Private bucket policy review (before evidence or images).
5. Confirmation that logs and audit contain no content (automated test).
6. Orchestration path for export and erase agreed, or the module scoped so that no category without one is enabled.
