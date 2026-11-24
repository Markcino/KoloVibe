# Business module — security design completion (Phase 6A)

**Status: design record, 24 November 2026.** It completes the security items the Phase 6A instruction lists where the existing package was thin or has been overtaken by the Phase 6B backend, and it states plainly what is *as built* (merged in PR #219, closed flags, not deployed, authored together with its tests: not independent assurance) and what is still only designed. It approves nothing new. It sits beside the [authorization matrix](BIZ-RBAC_and_Object_Authorization_Matrix_PROPOSED.md), the [STRIDE model](BIZ-STRIDE_Threat_Model_PROPOSED.md), the [API security matrix](BIZ-API_Security_Matrix_PHASE6A.md) and the [privacy and retention document](../../privacy/business-data-privacy-and-retention-PROPOSED.md).

**Correction to an earlier statement.** The STRIDE document's banner says no control is implemented or tested. Since Phase 6B many are; section 8 maps the highest risks to their as-built status. The STRIDE register itself is unchanged.

## 1. Where the model stands

| Item asked for | Where it is now |
| --- | --- |
| RBAC matrix | Complete (51 rows) plus the client column and principle 11 added in the DR-BZ-21 pull request; this record adds the staff model |
| Business object ownership rules | Section 3 |
| Staff permission model | Section 2 |
| Verification state transitions | Section 4 |
| Fraud prevention, review eligibility, abuse controls | Section 6 |
| Cross-business data isolation | Section 5 |
| Private verification-evidence handling | Section 7 |
| Threat model | STRIDE (61 threat rows: 53 original and 8 client rows) plus section 3.8 for clients; status in section 8 |
| Retention requirements | Section 9 |

## 2. Staff permission model

Principle: **staff hold a strict subset of owner authority, checked per business on every request, and can never widen it.** An owner is the only person who can create staff, change what staff see, or touch ownership. There is no per-staff permission editor: the subset is fixed by role, which keeps the model testable (a custom permission matrix per staff member is rejected as an unnecessary source of bugs).

| Capability | Owner | Staff | Enforced in | Note |
| --- | :---: | :---: | --- | --- |
| Read the business (no legal name for staff) | ✓ | ✓ | `ownership.get_mine`, `business_view` | Staff never receive `legal_name` |
| Read profile (approved, working, last rejected) | ✓ | ✓ | `profiles` | |
| Edit working profile; submit for review | ✓ | — (404) | `profiles` owner-only | |
| Replace opening hours | ✓ | ✓ | `profiles` owner or staff | Applies immediately; refreshes the listing |
| Read listing status | ✓ | ✓ | `listings` any member | |
| Publish or unpublish the listing | ✓ | — (404) | `listings` owner-only | |
| Submit or answer verification; read verification status | ✓ | — (404) | `verification` owner-only | Status shows state and reason code only |
| List members | ✓ | — | `ownership.member_list` | No account ids; owner-assigned labels |
| Invite staff; revoke an invitation | ✓ | — | `ownership` | Code shown once; 72 h; keyed digest stored |
| Remove a member | ✓ (**refuses until step-up exists**) | — | `ownership.member_remove` | Staff only; never an owner |
| Leave the business | — (owners cannot) | ✓ | `ownership.member_leave` | Immediate |
| Read inbox and threads; reply; close; confirm completion | ✓ | ✓ | `inquiries` default roles | Customer appears only as `Customer N` |
| Block a customer | ✓ | — | `inquiries` owner-only | The customer is never told |
| Respond to a review; delete own response | ✓ | — | `reviews` owner-only | |
| Issue or revoke review-invitation codes | ✓ | — | `reviews` owner-only | |
| Close the business; transfer ownership | **not built** | — | needs step-up | |

Staff rules: a staff member is a customer for every other business; privileged accounts (moderator, administrator) can hold no membership; a business has at most 10 active staff and 10 pending invitations (owner to confirm); staff removal and revocation take effect on the next request; an owner can never be removed, and there is always at least one active owner.

**Test evidence (6B, local):** staff refused on every owner-only operation with a 404 identical to an unknown id; revoked membership refused on the next request; last-owner and duplicate-membership races on PostgreSQL.

## 3. Business object ownership rules

1. **Authority is a membership row**, never an Identity role, never a client claim. The client does not send an owner or account id; the Gateway binds the authenticated actor.
2. **One module answers entitlement** (`authz.py`). Views do not query memberships directly.
3. **Every nested id is checked against the path business.** A thread, review, invitation or member id belonging to another business returns the same 404 as a random id.
4. **Customers own their own threads and reviews** by author id; the business never receives the customer's account id, only a label.
5. **A business can never hide, edit or remove a review**, and cannot start a thread; it can only reply, respond once, report and block.
6. **Registration is account-bound.** The registering account becomes the first owner atomically; moderators and administrators cannot register.
7. **Creation caps and conflicts are database-enforced**: one active membership per (business, account), one open verification case per business, one working revision, one review per author per business, one open thread per customer and business pair.
8. **Public data comes from a projection** whose column set is pinned by a test; private columns are never selectable by a public route.
9. **A conflicted person decides nothing:** reviewers cannot act on a case or business they submitted, created, are a member of or reported.

## 4. Verification state transitions

### 4.1 Verification case (as built, `VerificationCase`)

| From | Action | To | Actor | Guards |
| --- | --- | --- | --- | --- |
| *(none)* | submit | `submitted` | owner | declaration; 1–5 text evidence items; no open case; 5 per day; idempotent |
| `submitted` | claim | `under_review` | moderator or administrator, MFA, `verification` grant covering the business | not the submitter, creator or affiliate; one winner under concurrency |
| `under_review` | decide `request_info` | `needs_info` | granted reviewer, after the case is claimed | reason code |
| `needs_info` | owner answers | `submitted` | owner | evidence bounded |
| `under_review` | decide `verify` | `verified` | granted reviewer, after the case is claimed | reason code; idempotency key and payload digest |
| `under_review` | decide `reject` | `rejected` | granted reviewer, after the case is claimed | reason code |
| `verified` | decide `revoke` | `revoked` | a granted reviewer | reason code; the listing is removed in the same transaction |
| `rejected`, `revoked` | owner resubmits | `submitted` | owner | new case |

Not built and not approved: owner **withdrawal** (the design had a `withdrawn` state), **re-review on expiry** (no approved validity period), **appeal of a rejection** (DR-BZ-25).

### 4.2 Business state (one function, `verification.move`)

`draft → submitted → under_review → verified | rejected | needs_info`, `verified → revoked`, `rejected → submitted`, `revoked → submitted`, `needs_info → submitted`. The enumeration also contains `suspended` and `closed`; **no operation moves a business into either**, so they are unreachable today. The design's `suspended → verified` (restore, by a different person from the suspender) and `→ closed` need DR-BZ-25 and step-up.

### 4.3 Invariants

A business never becomes `verified` without a decision row; a decision is recorded once per case (database race test); a listing exists exactly while the business is verified, the approved profile is complete and the owner wants it listed; "verified" is revocable and every transition is audited with the actor, case and reason code.

## 5. Cross-business data isolation

| Layer | Control | Status |
| --- | --- | --- |
| Gateway | Capability flag, role and MFA gate, shape and size limits, bound actor | Built; route-contract and role-matrix tests |
| Business service | `authz.require_member`, path-bound nested ids, query scoping by actor or business | Built; non-member and nested-id swap tests on every owner operation |
| Data | Partial unique indexes, projection-only public reads, hashed throttle keys | Built; PostgreSQL race tests |
| Between services | Schema and role per service, UUID references, per-caller keys | Built for isolation; owner/runtime separation **not met** (DR-BZ-32) |
| Audit and logs | Ids and decisions only | Built; drift test between Business and Audit kind lists |

Residual risk: a single defect in `authz.py` would expose any business. Mitigation is the shared module, a test per operation, and the planned mutation check (remove a membership check; the matrix must fail), which 6B did not record for every operation.

## 6. Fraud prevention, review eligibility and abuse controls

All numbers are **starting values** in `services/business/service/limits.py`, approved only as "start conservative, record as configuration" (DR-BZ-22); the owner has not confirmed any of them.

| Control | Mechanism as built | Starting value |
| --- | --- | --- |
| Who may register | Active registration grant from an administrator (invitation-only pilot), verified email, no privileged role | 3 open businesses per account; 5 attempts per day |
| Duplicate and look-alike businesses | Normalised-name match shown to the reviewer; never auto-rejects | — |
| Staff abuse | Single-use code, keyed digest, expiry, cap | 72 h; 10 staff; 10 pending; 20 invites per day; 10 redemptions per hour |
| Verification abuse | One open case; throttle; reviewer conflicts blocked | 5 submissions per day |
| Scraping | Anonymous callers get no contacts; signed-in verified accounts get public channels under a reveal budget; page size, bounded query, keyed cursor; per-address throttle for anonymous | 100 reveals per day; 1,200 public reads per hour |
| Inquiry spam | Verified email; one open thread per pair; per-customer and per-business budgets that count only real eligible attempts; undisclosed block; 100-message cap | 10 per day; 30 new threads per business per hour; 60 messages per hour |
| Review eligibility | The basis is derived from proof and stored: `interaction_confirmed`, `invited` or `open`; shown on the review. Owners, staff and the registering account refused with the same 404 as an unlisted business; one review per author per business ever | account-age gate **not built** |
| Review fraud holds | A burst for one business, a burst by one author, identical text anywhere inside the window → `held`, not public until a reviewer decides | 10 per business per day; 3 per author per day; 30 days |
| Review manipulation | Aggregate computed in the same transaction; no business operation touches it; average hidden until the owner sets a minimum | minimum **unset** |
| Review-invitation fraud | A business-issued code is single-use, expires, is labelled `invited`, and only its keyed digest is stored | 30 days; 50 pending |
| Report abuse | Reporter must be able to see the subject; not their own; once per subject; throttle | 20 per day |
| Reviewer abuse | MFA, scoped grant, distinct person, idempotency, audited reads; an administrator cannot grant themselves, so the first grant needs two privileged accounts | — |

Gaps: no account-age signal, no similarity beyond exact normalised text, no device or IP signal (deliberately not collected), no restoration or appeal for wrongly removed reviews, no notification to authors.

## 7. Private verification-evidence handling

**As built: text evidence only.** Each case holds 1–5 bounded text items (a code and a value of at most 300 characters). It is stored in the Business schema, never returned to the public or to staff, not returned by the owner's own status read (state, times and reason code only), shown to a reviewer only through the audited case read, and never placed in an audit payload or log.

**Rules that stay in force when files are ever added** (BZ-R-045; none is built or approved): private bucket only; size-bound create-only upload grants; exact-object completion; decode and re-encode; metadata stripped; malware and decompression-bomb defences; a `quarantined` state that reviewers can never read; short-lived, single-use signed reads issued only to a reviewer holding an *evidence* grant (narrower than queue access) and audited on every issue; no public object URL; no listing; evidence objects deleted before the database row is marked purged; retention per DR-BZ-18.

**Minimisation:** prefer evidence that needs no personal identity document (contact-channel proof, business licence). Collecting any identity document needs an explicit owner decision under DR-BZ-19.

**Open:** the owner's evidence checklist, the accepted methods, the validity period, whether text-only evidence is acceptable for the pilot at all, and legal review (DR-BZ-23).

## 8. Threat model status (highest risks)

Status is from the Phase 6B evidence and is **local test evidence only**.

| Risk (STRIDE id) | As-built status | Remaining |
| --- | --- | --- |
| Cross-business access (BZ-T-001…003) | Controls built and tested on every owner operation | Independent review; mutation check per operation |
| Impersonation passing verification (BZ-T-010/011) | Mechanism built (case, grant, SoD, duplicate flag, revocation) | Policy: checklist, methods, validity (DR-BZ-04); legal (DR-BZ-23) |
| Account takeover then contact change (BZ-T-015) | **Mitigated by failing closed**: no live contact change, staff removal, closure or transfer until step-up exists | Step-up design (DR-BZ-33) |
| Contact scraping (BZ-T-030) | Anonymous gets no contacts; reveal budget; throttles | Confirm numbers; edge limits; no scraping defence is perfect |
| Evidence disclosure (BZ-T-017) | Text evidence reviewer-only and audited; no files | Storage and scanning decisions before files |
| Fake or hostile reviews (BZ-T-050…055) | Basis stored; three hold signals; one review ever; aggregate server-side | Policy numbers; account-age; restoration and appeal |
| Moderator abuse (BZ-T-056) | Reason codes, MFA, grants, conflicts, audit | Restoration by a different reviewer; sampling |
| Forged internal call (BZ-T-060) | Per-caller keys, audience, nonce, path allowlist; gateway-only | — |
| Cross-service data access (BZ-T-061) | Schema and role isolation tested on a disposable cluster | **Owner/runtime separation unmet (R-01 pattern)** |
| Web surface added by drift (BZ-T-070) | Holds in code today (no templates, CORS, cookies, HTML) | No test pins it (AC-CLI-001…004) |

## 9. Retention requirements

Principle (approved): deletion mechanisms ship; **periods do not until the owner approves them**; if a rule is absent nothing is purged and a report lists categories without a rule. As built, **no category has a purge job, no legal hold exists, and no export or erase operation exists** (the platform has no privacy orchestration path; Identity's `PrivacyRequest` is a receipt only).

| Category | Where | Built mechanism today | Owner must decide |
| --- | --- | --- | --- |
| Business identity (legal name, membership) | Business schema | Closure not built | Retention after closure; tombstone content |
| Public profile and revisions | Business schema | Superseded revisions kept | Purge of superseded revisions |
| Contact channels, exact location | Business schema | Edited through profile revisions | Retention after closure |
| Verification case and decision | Business schema | None | Retention of decision records; reviewer-id anonymisation |
| Verification evidence (text) | Business schema | None | Period and purge trigger; file rules if added |
| Inquiry threads and messages | Business schema | Close and block only | Tombstone vs delete; account-deletion behaviour |
| Reviews and responses | Business schema | Withdrawal blanks the text immediately; no history kept | Retention of removed reviews; anonymise author vs delete |
| Reports and fraud holds | Business schema | None | Reporter-id stripping after resolution; hold-record deletion |
| Audit events | Business outbox then Audit | Delivered, retried | Audit retention (OD-08, ADR-017) |
| Throttle counters, idempotency records, nonces | Business schema | Nonce table pattern exists; others not purged | Grace periods (propose Identity's pattern) |
| Backups | Infrastructure | None recorded | ADR-016; a restore must re-apply deletions |

Every period and trigger above is an owner decision, informed by legal review (DR-BZ-23, DR-BZ-18).
