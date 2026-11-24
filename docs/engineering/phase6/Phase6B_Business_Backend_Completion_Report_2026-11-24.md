# Phase 6B — Business backend: completion report

Date: 24 November 2026. Branch `claude/blissful-archimedes-ztoqko`; the Phase 6A design reached `main` in [PR #218](https://github.com/Markcino/KoloVibe/pull/218) (merged by the owner), and this Phase 6B work is a separate, unmerged pull request from the same branch. Approval basis: the owner's "approve all 26 as recommended" in session ([record](../../architecture/business/BIZ-Owner_Approval_Record_2026-11-24.md)) and the merge of #218. **Local and disposable environments only: no staging or AWS change, no deployment, no payments, ticketing, live streaming or advertising. Production remains NO-GO. Every capability is behind a gateway flag that is closed by default. Not independent security assurance.**

Subphase evidence: [B1](B1_Business_Identity_and_Ownership_Results_2026-11-24.md), [B2](B2_Business_Verification_Results_2026-11-24.md), [B3](B3_Business_Profiles_Results_2026-11-24.md), [B4](B4_Business_Listings_and_Discovery_Results_2026-11-24.md), [B5](B5_Inquiries_and_Reviews_Results_2026-11-24.md).

## 1. Backend capability matrix

Status: **Done** = implemented and tested as approved; **Partial** = implemented with a stated gap; **Blocked** = not built, reason given.

| Requested capability | Status | Where / notes |
| --- | --- | --- |
| **B1** Register a business; link to authenticated owner; validate ownership; prevent unauthorized modification; audit | Done | invitation-only pilot registration grant, one owner membership, one entitlement module, 404 for non-members |
| B1 Manage business staff and roles | Partial | staff invite (single-use code), redeem, list, leave done; **owner removal of staff fails closed** until step-up exists (P6B-04); no ownership transfer or closure (also step-up) |
| **B2** Verification requests; authorized administrator review; approve/reject; status; revocation | Done | claim then decide; scoped reviewer grants; separation of duties; idempotent; revocation implemented |
| B2 Evidence handling | Partial | **text evidence only**; file evidence needs the owner's checklist and approved private storage (DR-BZ-04/19) |
| B2 Re-review | Blocked | no approved validity period or trigger |
| **B3** Name, description, categories, contact, address/location, opening hours, visibility, authorized editing | Done | revisions; material fields pre-moderated; field-level privacy flags; hours with a shared open-now helper |
| B3 Images | Blocked | DR-BZ-20: no images until the shared image pipeline exists (creator photos are themselves unbuilt) |
| B3 Live contact change | Partial | fails closed until step-up (P6B-04) |
| **B4** Create/update/remove listings; status; search; category and location filters; pagination; public/private visibility | Done | single eligibility predicate, public-columns-only projection, drift reconciliation, signed filter-bound cursors |
| B4 Search engine | Partial | portable substring search with relevance tiers; PostgreSQL full-text/trigram index deferred (see deviations) |
| B4 Distance / "near me", paid placement | Blocked by design | DR-BZ-13: not in scope |
| **B5** Customer inquiries, ownership and access | Done | pseudonymous, bound threads, undisclosed blocking |
| B5 Review eligibility; submission; duplicate and fraud protection | Done | basis stored and shown; invitation proofs; three hold signals; aggregates exact under concurrency |
| B5 Review moderation and abuse reporting | Partial | **Business-local queue** (Moderation generalisation not approved); remove/keep only; no restoration or appeals |
| Cross-cutting: audit, throttles, idempotency, validation, isolation | Done | audit outbox and Audit producer with a drift-guard test; hashed throttle keys; idempotency with payload digest; strict allowlists |

## 2. API verification results

- **Contract:** the Business operations were merged into DOC-205 as they were built: **57 operations** (4 anonymous, 13 requiring an MFA privileged session) under five capability flags: `business_owner` 19, `business_review_admin` 13, `business_inquiries` 12, `business_reviews` 10, `business_discovery` 3. DOC-205 validates as OpenAPI 3.1 after each merge (`openapi-spec-validator`).
- **Default-deny guard:** `test_gateway_route_contract.py` (6 tests) passes: every Business route is declared, every non-anonymous route answers 401 to a credential-less caller with **zero** internal calls, and the anonymous list was extended deliberately by exactly four public reads. `test_gateway_role_matrix.py` (5 tests) passes: every privileged Business route refuses viewer, creator and moderator/administrator without MFA before anything is forwarded.
- **Gateway:** 14 Business tests: actor bound from the session, exact envelope, bounded input, upstream refusal pass-through limited to `{detail, code}`, oversize/non-object responses rejected, anonymous handling, invalid credentials never downgraded, trusted-address forwarding.
- **Business service:** 162 tests (SQLite) plus 11 on a real TLS PostgreSQL 16 with the service's least-privilege role.
- **Deviation recorded:** the Gateway does **not** keep exact response schemas for Business (that would duplicate the Business service's own response shapes, against the "no duplicated business logic" rule); it forwards bounded JSON objects and bounded refusals. Exact shapes are tested in the Business service.

## 3. Permission test evidence

All in `services/business/tests/` and `scripts/test_business_postgres.py`.

| Class of control | Evidence |
| --- | --- |
| Cross-business isolation / IDOR-BOLA | non-member answers identical to unknown id on every owner operation (B1); nested-id swaps for threads, reviews, invitations, members (B1, B5); strangers and other owners tested on every owner operation (B2, B3, B4, B5) |
| Staff vs owner separation | staff blocked from invite, remove, verification, profile edit/submit, publish, block, respond, invitations; allowed hours, inbox, replies, reading status |
| Customer isolation | other customers' threads and reviews 404; business never receives an account id (schema tests) |
| Reviewer authority | role + MFA + explicit scoped grant on every reviewer route; wrong scope refused; no-grant reviewers see empty queues and 404; submitter/creator/affiliate/reporter/author conflicts blocked; claim race: exactly one winner |
| Privilege boundaries | moderators and administrators refused as owners, staff, customers, reviewers-of-own; administrators cannot grant themselves |
| Mass assignment | banned-field tables for registration, evidence, profile, review, report, decision |
| Anonymous surface | nil actor only for `anonymous`; no MFA/email flags; public bodies hold no private column (projection column set pinned) |
| Idempotency and replay | same key replays, different payload 409; codes returned once and never replayed; single-use under concurrent redemption |
| Fail-closed step-up | owner contact change on a live profile and staff removal refuse every caller |
| Service identity | shared verifier copy identical in nine services (drift test), `business` accepts only the gateway, Audit accepts `business` only on the events path |

## 4. Database migration plan

Nothing was applied outside disposable databases. Service `business`, schema `business`, role `kolovibe_business` (`schema_isolation.sql`).

| Order | Migration | Contents |
| --- | --- | --- |
| 1 | Audit `0006_business_producer` | producer list and check constraint (existing service; additive) |
| 2 | Business `0001_initial`, `0002_internal_nonce` | businesses, memberships, staff invitations, registration grants, idempotency, throttles, audit outbox |
| 3 | `0003_verification` | reviewer grants, cases, evidence, decisions; one open case per business |
| 4 | `0004_profiles` | categories, revisions (one working and one approved per business), contacts, hours; widened grant scopes |
| 5 | `0005_listings` | `owner_listed`, public projection |
| 6 | `0006_inquiries`, 7 `0007_reviews` | threads, messages, blocks; reviews, responses, invitations, aggregate, reports |

Rollout when approved (not now): schema/role SQL, Audit migration, Business migrations, one `reconcile_listings --apply`, gateway deployed with flags closed, flags opened one at a time. All migrations are additive; rollback before any data exists is dropping the schema; after data exists it needs a reviewed plan. Migration ownership should be separate from the runtime login from the start (R-01 lesson).

## 5. Unresolved blockers and deviations

| # | Item | Needs |
| --- | --- | --- |
| 1 | Step-up authentication: staff removal, live contact change, closure, ownership transfer unavailable | Identity design and approval (P6B-04) |
| 2 | File evidence and its checklist; evidence retention | Owner checklist (DR-BZ-04/19), approved private storage, scanning |
| 3 | Images | DR-BZ-20; shared image pipeline first |
| 4 | Moderation generalisation; restoration; appeals; listing reports and suspension | Separate approval (DR-BZ-17, 25) |
| 5 | Category and county lists; field materiality; reason-code vocabularies | Owner (DR-BZ-10/11) |
| 6 | Retention periods, export and erase, legal hold | DR-BZ-18/23 and a privacy orchestration path |
| 7 | Review policy values: minimum count for an average, edit window, author display, account-age gate, hold thresholds | Owner (DR-BZ-15/16/22) |
| 8 | Search index (full-text/trigram) | measured need; role/extension decision |
| 9 | Notifications for inquiries and reviews | DR-BZ-14 |
| 10 | Deployment tooling (cluster, secrets generation, staging stacks) still lists eight services; CI loops and PostgreSQL job were extended | approved rollout (DR-BZ-24) |
| 11 | One PR instead of one per feature | branch rule: only the designated branch may be pushed; per-feature PRs need your permission for extra branches |
| 12 | The Phase 6B pull request is unreviewed and unmerged; approval of the *design* is recorded (session answer and the merge of #218), approval of this *code* is not | owner review of the diff |

## 6. Phase 6C prerequisites

6C is not defined here; any client work (mobile owner and customer screens, admin-console reviewer pages) needs: approved Figma designs (DR-BZ-21), the public-field and notice copy (privacy section 8), the owner's lists (categories, counties, reason codes), a decision on step-up (P6B-04) because several owner screens depend on it, and the contract in DOC-205 as the single source. Backend flags must stay closed until an owner-approved release record names them.
