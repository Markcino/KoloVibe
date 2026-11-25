# Phase 6E — Business development integration and hardening: results

**Date:** 25 November 2026. **Base:** `main` at `fa6fd3f` (Phases 6A to 6D merged). **Scope:** repository changes only: tests, three small defect fixes, two behaviour-preserving refactors, records. **No** AWS or staging action, no migration, no deployment, no merge. Every Business capability flag is still closed and production is NO-GO.

This is **development integration**, not staging UAT. Everything below ran on this machine against disposable databases and processes. Section 7 lists what was not run.

## 1. Contract reconciliation (Step 1)

DOC-205 is the one approved contract. Before this phase each pair of neighbours was partly guarded (Gateway routes against the contract, the app's operation list against the contract, the fixtures against their own shape) but **nothing compared all four sides together, and nothing validated a real service answer against the contract's schemas.** `scripts/test_business_contract_reconciliation.py` (11 tests) now does, reading each side in its own process through `scripts/probe_business_surface.py`.

| Check | Result |
| --- | --- |
| Every declared Business operation has a Gateway route, and every Gateway Business route is declared | 57 = 57, no difference |
| Each route sits behind the capability the contract names; no route is served while every flag is closed | 19 + 3 + 12 + 10 + 13 = 57; 0 when closed |
| Gateway table, service registry and contract describe the same authority (who may call, MFA, verified email, idempotency, public or signed in) | agree for all 57 |
| Every status the service can return is declared; every query parameter the Gateway accepts is declared and no other | agree |
| Every operation names a row of the RBAC matrix (11 rows govern several operations, as designed) | all real rows |
| Real service answers the app depends on validate against the contract's response schemas | 48 captured answers: 47 validate against their schema, the one error answer has the bounded `{detail, code}` shape |
| Operations only the superseded 6A proposal describes (suspension, appeals, closure, transfer, evidence read grant…: 11) are not routed | none routed |
| Console requests (`apps/web_django/tests/test_business_contract_alignment.py`, 5 tests) | every request is a declared operation; every privileged one needs MFA and the right roles (administrator-only under `/admin/`); decision and scope vocabularies equal the contract's; the console calls no owner or customer operation |
| Mobile models against API answers | the Dart parsers run against 48 captured real service answers (drift-tested) and those answers now validate against DOC-205 |

**Three real discrepancies found and fixed**

1. **DOC-205 was stale.** `BusinessReviewerGrant.scope` listed only `verification` and `review_queue`; the service, the console and the approved ERD also use `profile_review`. The contract now lists all three (documentation change, no behaviour change). The console would otherwise have sent a value its own contract forbade.
2. **The local Gateway could not reach the Business service.** `services/gateway/service/internal_client.py` built its local peer table without `business`, so with the local profile every Business request answered 503. Staging reads a peers file and was not affected. Found by the first end-to-end run; one word added.
3. **The app tested "answer a request for information" against the 201 *submit* answer.** No real `verification_respond` answer had ever been captured. It is captured now (`verification_respond.json`, 200) and the Dart case uses it. The fixture set is 48 files (was 47).

**Mutation checks of the reconciliation test:** dropping the verified-email flag from one Gateway route and dropping MFA from one service operation were both caught. A third mutation (forcing a flag open in the local profile) changes nothing by design and is not counted.

**Not a defect, recorded:** the 57 operations are in DOC-205; the 6A proposal file (`BIZ-OpenAPI_3_1_PROPOSAL.yaml`, 50 operations) is superseded and differs on 11 operations by design.

## 2. End-to-end development wiring (Step 2)

`scripts/business_journey.py`, run by `scripts/verify_local_journeys.py` (so by the existing CI step), is one ordered journey over **real HTTP between real processes**: the Gateway, Identity (sessions, verified email, MFA), the Business service and the web console, each with its own TLS PostgreSQL role. The Business service was added to that harness. Mail is captured; MFA uses the enrolled recovery codes. Every success body is validated against its DOC-205 schema.

| Step | What the journey does | Proved |
| --- | --- | --- |
| 1 | A customer registers, verifies email, signs in | `/me` answers; owner and moderation routes answer 401 with no credential |
| 2 | An owner registers | refused with `invitation_required` until an MFA administrator grants it; a retry with the same key is the same business; a stranger gets 404; the owner is server-assigned |
| 3 | Profile, hours, profile submission, verification submission | state `submitted`; not discoverable yet; search returns nothing |
| 4 | A reviewer with grants inspects the case | queue, case and evidence read; a moderator **without** a grant sees an empty queue and 404s; a customer is 403; deciding without claiming is 409 |
| 5 | The reviewer decides **through the real console** (claim, confirm step, decision), and approves the profile by API | a double submit is one claim; the confirm step records nothing; a replayed confirmed form records exactly one decision; a new key on a decided case is refused; the business becomes `verified` |
| 6 | Eligibility, then the owner lists it | `eligible: true` only after both approvals |
| 7 and 8 | The customer searches and reads the listing | found anonymously and signed in; contacts only for a verified-email account; no legal name, owner or member data anywhere |
| 9 and 10 | The customer asks; the owner replies | the customer is not on the business side (404); the thread shows both messages |
| 11 | Both sides confirm; the customer reviews | `interaction_confirmed`, published; a second review is refused; the owner reviewing their own business is refused; the author is a pseudonym |
| 12 | A second customer reports it; a moderator handles it | the reporter's own content check; a moderator without a grant sees nothing; removal replays to the same answer; a new key on the closed report is 404; the review leaves the public list |
| 13 | Staff receive an invitation and act within their scope | a guessed code is refused; one use only; staff reply and set hours; every owner operation is refused; owner removal of staff answers `step_up_unavailable` |
| 14 | Revoked staff access | leaving ends access at once (404); a second staff member revoked in the data is denied the same way; the owner is unaffected |
| end | Audit evidence | 16 event kinds present; exactly one `verification_decided` and one `report_decided` despite the replays and refusals |

Result: **11 of 11** journeys pass (10 existing plus this one), about 60 to 130 seconds on this machine.

## 3. Security hardening (Step 3)

New tests found **no new authorization defect** in the Business service. They cut across every operation and are driven by the registry and the source, so a new operation or field cannot escape them. `services/business/tests/test_security_hardening.py` has 42 tests; two Gateway tests were added.

| Area | Where it is proved |
| --- | --- |
| Anonymous denial | `scripts/test_gateway_route_contract.py` (every non-public route refuses a request with no credential before forwarding), Gateway `test_business`, journey step 1, the matrix's "caller is not the Gateway" |
| Cross-business IDOR/BOLA | existing 39-operation object matrix and nested-id swap (Phase 6B); journey: stranger 404, revoked staff 404 |
| Business ownership forgery | an AST guard fails if any handler accepts a field that names authority (owner, role, state, basis, verified, listed, eligible…); a functional check sends eight forged fields to six write operations (all 400, nothing created); a Gateway test shows a body cannot reach the signed envelope's actor, role, MFA or key |
| Unauthorized review | existing review tests plus journey step 11 (own business, second review, unconfirmed or foreign conversation) |
| Verification bypass | every non-verified business state (8) cannot be listed or found; an owner cannot claim, read or decide their own case; claim is required and belongs to the claimant; a decided case cannot be decided again with a new key |
| Moderator assignment bypass | a grant opens only its own queue (verification, profile, report); administrators are not reviewers until granted; revoking a grant takes effect on the next request even mid-case; a grant for one business does not cover another; journey: ungranted moderator |
| MFA requirements | the matrix gate (Phase 6B), the reconciliation test (contract, Gateway and service agree on every operation), the Gateway role matrix and the console alignment test |
| Rate limiting | every budget is enforced by something and every named budget exists; every creating write has one; an exhausted budget stops the request **before the handler runs**; budgets are per account, hashed at rest and recover; anonymous reads are limited per client address and the caller cannot choose the address |
| Duplicate submissions | all 36 idempotent operations refuse a missing or malformed key (6 forms each); the same key from two accounts gives two independent results; a second open request of the same kind is refused; PostgreSQL race tests (Phase 6B) |
| Privileged decision replay | verification, profile and report decisions replay to the first answer and record one decision and one audit event; the same key with a different decision is `idempotency_conflict`; another reviewer's key and another operation's key are not a free pass |
| Sensitive-data disclosure | 28 responses across 8 roles are scanned: none contains another account's id, and none carries an internal field; public projections are an exact field list; every refusal is a bounded `{detail, code}` with no ids or internals; a database failure is a generic 503 and the database's words do not reach the log; audit events hold ids and codes, never text |
| Unsafe file access | no model has a file or image field; no request-handling module imports the file system, network, process or archive libraries (only `urllib.parse`); the contract has no file, URL or non-JSON surface for Business; hostile evidence and message text (`file://`, `../`, `http://127.0.0.1`) is stored as text and never fetched or opened; ids must be UUIDs; the dispatcher and the Gateway refuse multipart and non-JSON bodies |
| Service identity failure | through the real middleware, **every one of the 57 operations** refuses a request with any signature header missing, a wrong key, another caller (even with its own valid key), an unlisted peer, a wrong audience, a tampered body, a stale or future timestamp, and never runs its handler; a signature cannot move to another operation; a replayed nonce is refused; every refusal is the same `Forbidden`; weak or missing credentials close the service |

**Mutation checks: 12 of 12 caught** (control removed, suite must fail): eligibility ignoring verification, the grant check, the claim requirement, idempotency keys shared across actors, across operations, key not required, throttle never refusing, authority accepted from the body, review exposing the author account, signed path policy removed, a file import added, nonce replay allowed.

**Design note, accepted:** a replayed idempotent request returns the recorded answer before the handler runs, so a reviewer whose grant was revoked after deciding who replays their own key sees their own earlier answer. Nothing new is read or changed.

## 4. Code quality (Step 4)

| Finding | Action |
| --- | --- |
| The reason-code validator and its regex existed **four times** (`profiles`, `reviews`, `verification`, and `_subject` in `inquiries`) | one `code_text` and `CODE` in `validation.py` |
| The role tuples were defined **six times** (`CUSTOMER`, `REVIEWERS`, `EVERYONE`) | defined once in `authz.py`, the entitlement module |
| The cursor/limit spec was written five times | one `PAGE` in `validation.py` |
| Two unused imports, one more in `ownership.py` and `reviews.py` | removed |
| Flutter: `_go` (identical to `openBusiness`) in three files, `_signIn` in four, `_replace` in two | `openBusiness` used directly; `signInForBusiness` and `replaceBusiness` added once in `business_page.dart` |
| The Business audit delivery command was not in the repository's lock-scope guard | added; it already locks only its own row |
| Gateway `OPERATIONS` repeats facts the service knows | not deduplicated across deployables; the reconciliation test is the guard |
| Console validators are their own copy of the service's rules | by design (separate deployable, independent validation); the alignment test pins vocabularies |

Behaviour-preserving evidence: the 181 existing Business tests, 267 Business Flutter tests and the 1,823-test Flutter suite pass unchanged. `services/business/tests/test_code_quality.py` (4 tests) pins one definition of each rule and fails on an unused import.

**Reviewed and left alone, recorded as known issues (section 6):** the duplicate-business scan, the unbounded category list, the audit delivery lock, the listing reconciliation query pattern. Pagination exists on every list that can grow with use; background commands are bounded (audit batch 1 to 1,000 with a 2-second call and capped backoff).

## 5. Test and CI evidence (local, 25 November)

| Check | Result |
| --- | --- |
| Business | **227** pass, 1 skipped (181 before) |
| Gateway | **223** pass, 18 skipped (221 before) |
| Console | **179** pass (174 before) |
| Identity, Creators, Content, Engagement, Points, Moderation, Audit | 157, 84, 135, 72, 68, 71, 51: unchanged, passing |
| `makemigrations --check` | clean for all nine services and the console |
| Repository script suite | **458** pass (446 before; +11 reconciliation, +1 lock scope) |
| `flutter test` (all suites) | **1,823** pass (unchanged; one existing case now uses a real fixture) |
| `flutter analyze` | no errors or warnings (the SDK on this machine reports 88 deprecation notes for `flutter/material.dart`, none from this change) |
| Local journeys (`verify_local_journeys.py`) | **11 of 11** pass |
| Business and Audit on PostgreSQL (`test_business_postgres.py`) | 13 and 2 pass (PostgreSQL 14 here; CI uses 16) |
| `verify_staging_runtime`, `verify_r1_db_preflight`, `verify_event_pipeline` | pass |
| OpenAPI validation of `health.yaml` and DOC-205 | valid |
| `check_structure`, `check_mobile_design` | OK (9 services; 108 entries) |

The same commands are the CI job's steps. **The pull request's own CI has not run yet** (security scans, SBOM, image build and the pinned Flutter SDK are CI-only).

## 6. Status

The full table is in the [tracker](R1_Application_Tracker.md). In short:

**Code-complete and integrated in development (repository scope):** registration and ownership, staff join and leave, verification (text evidence), profiles and hours, listings and discovery, inquiries, reviews and responses and review invitations, reports and moderation, categories and access grants, audit delivery. 57 of 57 operations are implemented, declared, routed and exercised; 43 are used by the app and 13 by the console.

**Policy-blocked (the code fails closed or is absent; the owner decides):**
- Step-up (P6B-04, DR-BZ-33): staff removal, contact change on a live profile, closure, ownership transfer.
- File evidence and private storage (A5, A12); suspension and appeals (DR-BZ-25); notifications (DR-BZ-14); images, share links, listing and reply reports.
- Review policy values (A6): the average rating stays hidden until a minimum is set; edit window, account age.
- Visual approval of the 36 screens and the public-field and review-basis wording (DR-BZ-27); whether any link may leave the app (DR-BZ-28).
- Database owner/runtime separation (DR-BZ-32); full-text search (DR-BZ-30); Gateway response validation (DR-BZ-31); the owner-approved release record that opens any flag.

**Known defects and risks**

| # | Issue | State |
| --- | --- | --- |
| K1 | Local Gateway peer table lacked `business` | **Fixed** |
| K2 | DOC-205 reviewer-grant scope enum lacked `profile_review` | **Fixed** |
| K3 | App "answer for information" case used the wrong fixture; no real answer captured | **Fixed** |
| K4 | `verification._duplicates` compares a submitted business against **every** business in Python on each submission. Fine at pilot size (three businesses per account, invitation-only); it will not scale. The fix is a normalised-name column and index, which needs a migration | Open; needs a reviewed migration |
| K5 | `category_list` returns every category in one answer; administrators create them and nothing caps the count | Open; low |
| K6 | Business audit delivery makes the Audit call (2-second timeout) while holding its own delivery row lock; Points and Moderation share the pattern | Open; bounded; low |
| K7 | `reconcile_listings` runs two queries per business (a maintenance command, not a request path) | Open; low |
| K8 | In one of about six full journey runs the unrelated **copyright** journey answered 403 where it expects 200 (an administrator's appeal decision); the next four runs, including the final one, passed. It runs before the Business journey in the same fixture, and no Business code is involved. **Not diagnosed** | Open; watch in CI |
| K9 | After sign-in from a Business screen the app returns to the screen type, not to the item (6D) | Open; known |

## 7. Not run (unexecuted live UAT)

- **No staging, AWS, R2, RabbitMQ or real mail provider.** No deployment of any kind.
- **No device, simulator or screen-reader run.** The ten device recipes in the [Phase 6D results](Phase6D_Business_Mobile_Results_2026-11-24.md) remain written and unexecuted (Phase 11).
- **No browser pass over the console pages.** The console journey drives the real console process over HTTP, not a browser.
- **Real authenticator-app MFA**: the journeys use the enrolled recovery codes.
- **Audit delivery over HTTP**: the journey checks the Business service's own audit rows; delivery to the Audit service is covered by unit tests and the Audit suite, not by this journey.
- **The pull request's CI** (dependency, secret and image scans, SBOM, pinned Flutter SDK) and any independent review. The tests here were written together with the code under test and are not independent assurance.
- **Visual approval** of the screens.

## 8. Files

New: `scripts/probe_business_surface.py`, `scripts/test_business_contract_reconciliation.py`, `scripts/business_journey.py`, `services/business/tests/test_security_hardening.py`, `services/business/tests/test_code_quality.py`, `apps/web_django/tests/test_business_contract_alignment.py`, `apps/mobile/test/fixtures/business/verification_respond.json`, this record. Changed: `scripts/verify_local_journeys.py` (Business added), `scripts/test_audit_delivery_lock_scope.py`, `services/gateway/service/internal_client.py`, `services/gateway/tests/test_business.py`, `services/business/service/{validation,authz,inquiries,ownership,profiles,reviews,verification,listings}.py`, `services/business/tests/test_mobile_fixtures.py`, `apps/mobile/lib/features/business/*` (navigation helpers), `apps/mobile/test/live_business_repository_test.dart`, `docs/architecture/DOC-205_OpenAPI_3_1_DRAFT.yaml` (one enum value), the tracker and the Business README.

## 9. Next

Phase 6E is the last Business development phase. **Events are not begun.** Remaining Business work is policy-blocked (section 6) or CI and staging acceptance. K4 is the one engineering item worth scheduling before real data volume.
