# Phase 6B (second pass) — Business backend hardening and gap closure: results

**Date:** 24 November 2026. **Base:** `main` at `09a5bc9` (Phase 5F, the DR-BZ-21 client decision and the Phase 6B backend all merged). **Scope:** repository changes only. No AWS or staging action, no migration applied outside disposable databases, no merge, no deployment. Production remains NO-GO. Capability flags stay closed.

## 1. What this pass found before writing any code

1. **The Phase 6B backend already exists.** B1–B5 of the first pass (registration, verification, profiles, listings, inquiries, reviews, and the first half of staff) were merged by the owner in PR #219 and are described in the [completion report](Phase6B_Business_Backend_Completion_Report_2026-11-24.md). The instruction's seven slices (B1–B7) map onto that work; nothing was rebuilt.
2. **Most of what is left is blocked by decisions the owner has not made**, not by engineering. They are listed with recommendations in the [owner decisions required](../../architecture/business/BIZ-Owner_Decisions_Required_PHASE6A.md). The instruction says "do not invent eligibility rules" and "implement only approved role definitions"; this pass followed that and built **only policy-free gaps**.
3. **A process failure on my side was found and repaired.** Phase 6A part 2 (validation, requirements reconciliation, security completion, owner decisions, DR-BZ-29…33) was stacked on the DR-BZ-21 branch; #221 merged to `main` first and #222 then merged into the *old branch*, so **those documents never reached `main`** (the same failure Phase 5 recorded for #205 and #210). They are restored by a separate documentation pull request cherry-picked onto current `main`; see section 6.

## 2. B1–B7 against the instruction

| Slice | Requested | State on `main` | Evidence | Still open and why |
| --- | --- | --- | --- | --- |
| **B1** Registration | Authenticated creation, server-side ownership, duplicate prevention, validation, draft state, owner-only management, audit | **Built** (6B-1) | `test_ownership.py`; PostgreSQL races (5 identical registrations → 1 business; cap holds) | Duplicate handling is **idempotency, a per-account cap and a reviewer duplicate flag**, not rejection, as approved (BZ-R-003). Invitation-only pilot. Account numbers await owner confirmation |
| **B2** Verification | Requests, evidence, private storage, status, decisions, resubmission, revocation/suspension, history | **Built, text evidence only** | `test_verification.py`; claim and decision races on PostgreSQL | **File evidence and private storage:** needs the owner's checklist and storage and scanning approval (DR-BZ-04, 19; decision A5, A12). **Suspension:** grounds, notice and appeal route are owed (DR-BZ-25; A3). Revocation is built |
| **B3** Profiles | Name, categories, description, contacts, location and hours, visibility, editing, material re-review, history | **Built** | `test_profiles.py` | Initial category and county lists, warning copy, material-field list, coordinate precision (A7, A8). Live contact change refuses until step-up exists (DR-BZ-33) |
| **B4** Listings and discovery | Listing CRUD, filters, search, region, cursor, verified display, safe projections, removal | **Built** | `test_listings.py`; paging on PostgreSQL | Search is substring, not full-text (DR-BZ-30); Gateway does not re-validate Business response shapes (DR-BZ-31) |
| **B5** Inquiries | Create, inbox, replies, status, access, spam protection, **notification event contracts where approved** | **Built; no notification contract** | `test_inquiries.py` | **Notifications are not approved** (DR-BZ-14 chose none), so no event contract was invented |
| **B6** Reviews | Eligibility, submission, edit/withdraw, responses, moderation, fraud, reports, aggregates, audit | **Built** | `test_reviews.py`; aggregate races on PostgreSQL | Policy numbers (minimum count, edit window, account age) are owner-owed (A6). Moderation is a **Business-local queue** (DR-BZ-29); no restoration or appeals |
| **B7** Staff | Invitations, scoped membership, role management, revocation, ownership continuity, denial | **Partly built** | `test_ownership.py` | **Staff removal, closure and ownership transfer refuse for every caller** until the purpose-bound step-up proof exists (DR-BZ-33, A1). Roles are the two approved ones, owner and staff; no role editor exists by design |

## 3. What was added in this pass (all policy-free)

### 3.1 Registry-driven negative-authorization matrix
`services/business/tests/test_authorization_matrix.py` (12 tests). The instruction says every protected operation needs negative authorization tests; that was true by hand-written tests per slice, but nothing proved it for **all** operations. The matrix reads the dispatcher's own operation registry:

- **Gate matrix, every registered operation:** each role the operation does not allow gets 403; each privileged operation refuses a caller without fresh MFA; each verified-email operation refuses an unverified caller; a caller that is not the Gateway is refused; and a refusal writes nothing (a full snapshot of every Business table is compared).
- **Object matrix, 39 operations against real data** (a listed business, a thread, a review with a response, a staff invitation, a review invitation, a member, a verification case, a pending profile revision, an open report): every actor who is not entitled gets the **same 404 as for a random id** and changes nothing. Eleven actor classes: owner, staff, stranger, owner of another business, thread customer, review author, owner and staff of a second business, and three reviewers (fully granted, granted only for another business, not granted). The other 18 of the 57 registered operations have no object id and each names an existing covering test.
- **Nested-id swap (BZ-NT-02, 19):** a genuine member of business B names B in the path and a real id belonging to business A: 10 operations, each refused identically to an unknown id.
- **Positive controls:** every entitled call is run in a rolled-back savepoint and must not be refused, so the denials cannot be explained by invalid payloads. `member_remove` is the one listed exception: it correctly stays closed for everyone (step-up).
- **Coverage guard:** a registered operation that is neither in the object matrix nor named in an exemption table with an existing covering test **fails the suite**. Verified by registering a throwaway operation: the guard failed.

**Mutation checks (each control removed, matrix must fail):** dispatcher role gate, dispatcher MFA gate, reviewer grant check on verification cases, reviewer grant check on reports, review author filter, thread-to-path-business binding, review-response-to-business binding, staff publishing a listing, staff listing members, staff reading verification status, "my reviews" and "my inquiries" leaking everything. **The first run missed two** (thread binding and staff reading verification status): the first because the matrix only proved non-members were denied, the second because the verifying business had no staff member. Both gaps were closed (nested-id layer; a staff member added) and all twelve mutations are caught, re-run against the final matrix.

### 3.2 Migration upgrade and rollback, tested
The instruction asks for "tested upgrade and rollback behavior"; none was recorded before.
- `services/business/tests/migration_checks.py`, used by `test_migrations.py` (SQLite) **and** by `scripts/test_business_postgres.py` (disposable TLS PostgreSQL 16 as the least-privilege login, run in CI): every Business migration unapplies one at a time to zero, leaves no Business table, reapplies in order, and the **schema after the round trip equals the original**; rows written at migration 0004 survive an upgrade to 0007 and a rollback back to 0004 (rollback drops only what the later migrations created).
- `services/audit/tests/migration_checks.py` and `test_migrations.py` (SQLite and PostgreSQL): Audit `0006_business_producer` rolls back and forward over existing producers, and **rollback is refused and loses nothing while a `business` read grant exists**; with the grant removed it rolls back cleanly. This is the documented "after data exists a rollback needs a reviewed plan" case, now pinned.
- Mutation: an irreversible operation added to `0007` fails the test with `IrreversibleError`.
- Finding recorded, not changed: `0002_internal_nonce` reverses as a no-op (the nonce table is created by raw SQL and also by the isolation script), so a rollback to zero leaves `internal_request_nonce` behind. That is intentional and harmless; the test counts only Business-owned tables.

### 3.3 Client-surface guard (BZ-R-051, AC-CLI-001…004, decided DR-BZ-21)
- Gateway `test_business_client_surface.py` (3 tests): the Gateway configures no template, session, CORS, CSRF or common middleware (the middleware list is pinned exactly), and every Business route, for every method it allows plus `OPTIONS`, `TRACE` and a wrong method, hostile `Origin` and `Cookie` headers and a peer that is down, answers JSON (or an empty body not labelled HTML), sets no cookie and sends no `Access-Control-*` header.
- Business `test_client_surface.py` (2 tests): same configuration pin and JSON-only refusals.
- **One real defect fixed:** Django's stock `HttpResponseNotAllowed` labelled the empty 405 body `text/html`. The Business endpoint now returns a JSON 405 with an `Allow` header (`services/gateway/service/business.py`). No contract change: DOC-205 does not describe the 405 body.

## 4. Verification run (24 November, local, disposable databases)

| Check | Result |
| --- | --- |
| Business (SQLite) | **178** pass (162 + 12 matrix + 2 migrations + 2 surface), 1 skipped (pre-existing PostgreSQL-only) |
| Audit (SQLite) | **51** pass (49 + 2) |
| Gateway (SQLite) | **218** pass (215 + 3), 18 skipped (pre-existing) |
| Identity, Creators, Content, Engagement, Points, Moderation | unchanged and passing (157, 84, 135, 72, 68, 71) |
| Console | 138 pass |
| `makemigrations --check` | clean for all nine services (no model or migration was changed) |
| Repository script suite | 446 pass; DOC-205 unchanged |
| PostgreSQL 16 (`scripts/test_business_postgres.py`, run as the `postgres` OS user) | Business **13** pass (11 existing + 2 migration round-trip); Audit **2** pass |

Not run: staging, live R2, RabbitMQ (Business uses none), devices, Flutter (no Business client exists), independent review.

## 5. Security findings
1. **No new authorization defect found.** The matrix and its mutation checks found only gaps in the *tests*, which are closed.
2. **Defect fixed:** `text/html` label on Business 405 responses (low severity: empty body, but it contradicted the decided "no web surface" rule).
3. **Still true and unchanged:** database owner/runtime separation is not met (DR-BZ-32); step-up does not exist (DR-BZ-33); Moderation untouched (DR-BZ-29). The tests here were written together with the code and are not independent assurance.

## 6. Pull requests and the lost documentation
- This work: branch `feat/business-6b-hardening` (tests, one gateway fix, this record, tracker).
- Restoration of Phase 6A part 2: branch `docs/phase6a-part2-restore`, one commit cherry-picked from the stacked branch onto current `main` with no conflicts. A direct pull request from the old stacked branch would have **deleted the Phase 5F work** (it forked before #220 merged), so it must not be used.
- **Process change:** documentation and code pull requests are no longer stacked on one another; each targets `main`.

## 7. Prerequisites for the next phase
The decisions in [Gate A](../../architecture/business/BIZ-Owner_Decisions_Required_PHASE6A.md) unlock the remaining B2, B3, B6 and B7 work (file evidence, suspension and appeals, review policy values, step-up, closure and transfer). Gate B decisions (database ownership, capacity, response validation, search, confirmation of the starting numbers, release record) gate enabling anything anywhere. No Business capability may be enabled without an owner-approved release record.
