# Business module — acceptance criteria

**Status: PROPOSED — Draft for owner review.** Phase 6A, 24 November 2026. These criteria define when a Phase 6B slice may be called done. They are testable statements, not evidence: **no criterion has been run** and none may be marked passed without a recorded run (command, commit, result), in line with the repository's evidence rules. Criteria that need an unmade policy say `[DR-BZ-nn]`; the policy value must be approved and written into the criterion before the slice starts.

> **Status update, 24 November 2026 (Phase 6A reconciliation).** This is supporting design for decisions the owner approved as written (DR-BZ-01…26, [approval record](../../architecture/business/BIZ-Owner_Approval_Record_2026-11-24.md)); no separate approval of this document is recorded, and the banner above is the original wording. DR-BZ-21 was decided formally (Flutter only; no public website or business portal). The backend was built in Phase 6B (PR #219, closed flags, **not deployed**; production NO-GO). Where this document and the as-built system differ, see the [architecture validation](../../architecture/business/BIZ-Architecture_Validation_PHASE6A.md); what the owner must still decide is in [owner decisions required](../../architecture/business/BIZ-Owner_Decisions_Required_PHASE6A.md).

Trace: [requirements BZ-R](../../requirements/DOC-020_Business_Requirements_and_Scope_PROPOSED.md) · [authorization matrix BZ-AZ and negative tests BZ-NT](../../security/phase6/BIZ-RBAC_and_Object_Authorization_Matrix_PROPOSED.md) · [threats BZ-T](../../security/phase6/BIZ-STRIDE_Threat_Model_PROPOSED.md) · [backlog](BIZ-Implementation_Backlog_PROPOSED.md).

## 1. Definition of done for every slice

1. Contract operations for the slice exist in the contract **before** code; the gateway route-contract test passes and fails when an undeclared route is added (mutation check recorded).
2. Every route in the slice has authorization-matrix tests: allowed actor positive; every other actor class negative; foreign object negative (the BZ-NT cases that apply).
3. Every request body, query and header is allowlist-validated; unknown fields rejected; bounds tested at the limit and one past it.
4. Audit events are emitted for every state change and privileged read, and contain no content (test asserts the payload keys).
5. Capability flags default closed; with the flag closed the routes behave as unknown routes.
6. The module's test suite, the affected existing suites (gateway, audit, and any touched service), the shared-identity drift test, structure check, Bandit, and dependency/secret scans pass in CI.
7. No migration touches another service's tables; no cross-service SQL; no new third-party service.
8. Docs updated: contract, matrix, tracker; open decisions referenced by ID, none silently resolved.
9. Reported as: actual changes, tests run with results, failures, PR link and unresolved work. No claim of staging acceptance without an owner-run staging record.

## 2. Registration and ownership (S2)

| ID | Criterion | Req | Verification |
| --- | --- | --- | --- |
| AC-REG-001 | Given a verified-email viewer or creator, when they register a business with valid fields, then a draft business and exactly one active owner membership for that account are created atomically, and the response carries no other account's data. | 001 | integration |
| AC-REG-002 | Given an unverified email, a moderator or an administrator, when they register, then the request is refused and nothing is created `[DR-BZ-03]`. | 001, 037 | matrix |
| AC-REG-003 | Given the per-account cap, when exceeded, then the request is refused with 429 or 409 as specified `[DR-BZ-22]`. | 042 | integration |
| AC-REG-004 | Given a repeated registration with the same Idempotency-Key and payload, then the same business is returned; with a different payload, then 409. | 001 | integration |
| AC-REG-005 | Given concurrent removal of the last two owners, then exactly one succeeds and a business never reaches zero active owners. | 002 | concurrency test on PostgreSQL |
| AC-REG-006 | Given a submitted business similar to an existing one, then a duplicate flag is recorded for the reviewer and the submission is not rejected automatically `[DR-BZ-04]`. | 003 | integration |

## 3. Authorization (all slices)

| ID | Criterion | Req | Verification |
| --- | --- | --- | --- |
| AC-AZ-001 | For every `/me/businesses/{id}` route, a caller with no membership for `{id}` receives a response byte-identical in status and body to a random unknown UUID, and no state changes (BZ-NT-01). | 033, 034 | generated matrix |
| AC-AZ-002 | For every nested route, an id that belongs to another business returns the same 404 (BZ-NT-02, 19). | 034 | generated matrix |
| AC-AZ-003 | After a membership or grant is revoked, the next request with the same bearer token is refused (BZ-NT-04). | 035 | integration |
| AC-AZ-004 | The service never reads an owner, account, role or state value from a request body; the banned-field test posts each and receives 400 (BZ-NT-09). | 043 | unit |
| AC-AZ-005 | Static test: no view module queries `BusinessMembership` or `reviewer_grant` directly; all decisions go through `authz.py`. | 033 | CI test |
| AC-AZ-006 | With a capability flag closed, its routes answer as unknown routes and make zero internal calls (BZ-NT-23). | 046 | gateway test |
| AC-AZ-007 | Every privileged route refuses viewer, creator and moderator/administrator without live MFA before any Business call (BZ-NT-17), and the positive control passes. | 036 | gateway matrix |

## 4. Verification and moderation of ownership (S3)

| ID | Criterion | Req | Verification |
| --- | --- | --- | --- |
| AC-VER-001 | Given a draft business, when the owner submits a verification case, then exactly one open case exists and a second submission returns 409. | 004 | integration |
| AC-VER-002 | Public search, detail and inquiry creation do not expose a business until the eligibility predicate allows it `[DR-BZ-05]`. | 006, 016 | integration |
| AC-VER-003 | A reviewer without a `verification` grant cannot list, read or decide a case; a reviewer with a queue grant cannot read evidence. | 005 | matrix |
| AC-VER-004 | A reviewer cannot decide a case they submitted or are affiliated with (BZ-NT-11). | 005 | integration |
| AC-VER-005 | A decision requires a reason code from the approved vocabulary and is idempotent by key and payload digest; a different key on a decided case returns 409 (BZ-NT-12). | 004, 005 | integration |
| AC-VER-006 | No code path sets `verified` without a decision row (static check and test of every transition). | 006 | unit |
| AC-VER-007 | Every decision, evidence read and grant change writes one audit event with ids and decision only. | 044 | integration |
| AC-VER-008 | Evidence read grants are short-lived and single-use, issued only for evidence in the case and grant scope, and every issue is audited (BZ-NT-22). | 045 | integration |
| AC-VER-009 | Ownership disputes freeze or flag the listing as the approved policy states and are adjudicated by an administrator with MFA `[DR-BZ-26]`. | 008 | integration |

## 5. Profiles, categories and hours (S2)

| ID | Criterion | Req | Verification |
| --- | --- | --- | --- |
| AC-PRO-001 | Fields accept plain text only within bounds; control characters, surrogates and over-length values are rejected; `http` or non-URL websites are rejected; stored values are returned unchanged as text. | 012, 015 | unit |
| AC-PRO-002 | Categories are selected only from the administrator-managed vocabulary; unknown or inactive slugs are rejected `[DR-BZ-10]`. | 011 | unit |
| AC-PRO-003 | A submitted revision does not change the public view until approved where the policy requires approval; the previous approved revision remains public meanwhile `[DR-BZ-11]`. | 007, 010 | integration |
| AC-PRO-004 | Hours with overlapping intervals, invalid times or more than the allowed count are rejected; overnight intervals are split correctly; “open now” is correct across the time-zone boundary and for dated exceptions. | 013 | unit with fixed clock |
| AC-PRO-005 | Staff can change hours but no other profile field; owner can change all editable fields; the foreign owner cannot. | 033 | matrix |
| AC-PRO-006 | Changing a contact channel requires a valid purpose-bound step-up proof and notifies the owner `[DR-BZ-11, P6B-04]`. | 036 | integration |
| AC-PRO-007 | Private fields (`legal_name`, non-public contacts, coordinates without opt-in) never appear in any public or staff response (BZ-NT-14). | 019 | schema test |

## 6. Listings, discovery, search and filtering (S4)

| ID | Criterion | Req | Verification |
| --- | --- | --- | --- |
| AC-DIS-001 | Search returns only rows from the listing projection; unlisted, suspended, closed, rejected and draft businesses never appear. | 016, 020 | integration |
| AC-DIS-002 | Filters `category`, `county`, `open_now`, `verified` and `sort` each narrow or order results correctly; unknown parameters return 400. | 017, 018 | integration |
| AC-DIS-003 | Query inputs containing SQL fragments and tsquery operators are treated as plain text; results are unaffected and no error leaks internals. | 018, 043 | unit and integration |
| AC-DIS-004 | Contact channels are returned only as the reveal policy allows; an anonymous or over-budget caller receives null contacts `[DR-BZ-12]`; scraping beyond the throttle returns 429. | 019, 042 | integration |
| AC-DIS-005 | After suspension or unpublish, the next search and detail request excludes the business (no stale projection) and the reconciliation report shows no drift. | 020 | integration |
| AC-DIS-006 | Ranking is deterministic for a fixed dataset; the ranking function is documented, versioned and contains no input from payments, ads or owner-controlled boosts `[DR-BZ-13]`. | 017 | unit |
| AC-DIS-007 | Page size is capped; cursors are tamper-evident; a forged or foreign cursor returns 400 (BZ-NT-16); the slowest tested query on the reference dataset stays within the approved timeout `[parameter to be approved]`. | 018 | integration, EXPLAIN review |
| AC-DIS-008 | Public detail for an unlisted id equals a random unknown id in status and body (BZ-NT-13). | 034 | integration |

## 7. Customer inquiries (S5)

| ID | Criterion | Req | Verification |
| --- | --- | --- | --- |
| AC-INQ-001 | A verified-email customer can open one thread with a listed business; the thread appears in their list and in the business inbox. | 021 | integration |
| AC-INQ-002 | No business-side response contains a customer account id, email or any field outside the allowlist; only `customer_label` appears. | 023 | schema test |
| AC-INQ-003 | Per-customer, per-business and global budgets are enforced; blocked customers receive the same response as for an unlisted business (BZ-NT-18) `[DR-BZ-14, DR-BZ-22]`. | 021, 024, 042 | integration |
| AC-INQ-004 | Messages exceeding the bound, containing control characters, or including an attachment field are rejected. | 022 | unit |
| AC-INQ-005 | A business cannot start a thread, cannot message a closed or blocked thread, and every attempt is refused. | 022, 024 | integration |
| AC-INQ-006 | A thread and message list is stable and ordered; a removed message appears as a tombstone to participants. | 022, 025 | integration |
| AC-INQ-007 | A report on a message is accepted only from a thread participant. | 025 | matrix |

## 8. Reviews and review moderation (S6)

| ID | Criterion | Req | Verification |
| --- | --- | --- | --- |
| AC-REV-001 | An eligible author can create one review per business; a second returns 409; a member or affiliated account is refused (BZ-NT-07) `[DR-BZ-15]`. | 026, 027 | integration |
| AC-REV-002 | The eligibility basis is stored with the review exactly as the policy defines and displayed accordingly. | 026 | integration |
| AC-REV-003 | The aggregate (count, sum, average) always equals the recomputation from published reviews, including after edit, withdrawal, hold, removal and restoration, under concurrency. | 030, 031 | integration, concurrency |
| AC-REV-004 | Velocity rules hold reviews as specified when a business or an author exceeds thresholds `[DR-BZ-22]`; held reviews are not public and not counted. | 028 | integration |
| AC-REV-005 | Content-similarity and new-account signals produce reason codes only; no raw signal values are stored. | 028, 041 | unit |
| AC-REV-006 | No review, response or API payload exposes an author account id; the author label follows the approved policy `[DR-BZ-16]`. | 029 | schema test |
| AC-REV-007 | A business can respond once, cannot hide, edit or remove a review, and can report it. | 029 | matrix |
| AC-REV-008 | Review creation is throttled per account and per business; excess returns 429. | 042 | integration |
| AC-REV-009 | Withdrawal and edit rules match the approved policy, and history exists only as the policy allows `[DR-BZ-16, DR-BZ-18]`. | 031 | integration |

## 9. Moderation (S6, with S3 for verification)

| ID | Criterion | Req | Verification |
| --- | --- | --- | --- |
| AC-MOD-001 | A report is accepted for a subject the reporter can see; duplicates return 409; unknown or unseen subjects return 404 (BZ-NT-21). | 032 | integration |
| AC-MOD-002 | Reviewers see only reports within their grant; a decision needs MFA and a reason code and is idempotent. | 032, 005 | matrix |
| AC-MOD-003 | Restoration after removal is refused for the reviewer who removed (BZ-NT-20). | 005 | integration |
| AC-MOD-004 | The appeal path exists for removed reviews and suspended or rejected businesses and is handled by a different reviewer `[DR-BZ-16, DR-BZ-25]`. | 009, 032 | integration |
| AC-MOD-005 | Application of a Moderation decision at Business is idempotent by action id, accepted only from the Moderation caller on its single path, and replays are no-ops (BZ-NT-15) `[DR-BZ-17]`. | 032, 047 | integration |

## 10. Abuse prevention (all slices)

| ID | Criterion | Req | Verification |
| --- | --- | --- | --- |
| AC-ABU-001 | Every write route listed in the matrix with a throttle has a test showing the limit trips and the response is 429 with no state change `[DR-BZ-22]`. | 042 | integration |
| AC-ABU-002 | Verification submissions are bounded per account and per business. | 042 | integration |
| AC-ABU-003 | Throttle keys stored are digests; no raw account, address or contact value is stored in throttle rows. | 041 | unit |
| AC-ABU-004 | Search and contact-reveal limits are enforced per caller class and tested for anonymous and signed-in callers. | 042 | integration |

## 11. Audit (all slices)

| ID | Criterion | Req | Verification |
| --- | --- | --- | --- |
| AC-AUD-001 | Each state change (registration, revision submit/approve/reject, verification decisions, listing changes, membership changes, review lifecycle, suspensions) produces exactly one audit event with actor, kind, subject type and id. | 044 | integration |
| AC-AUD-002 | An audit payload contains no keys outside the allowlist and stays within the 2048-byte Audit cap; a content value in a log line or audit event fails the test. | 041 | unit, log capture |
| AC-AUD-003 | Privileged reads (evidence, moderator reads of inquiry or review content, queues) are audited, and Audit outage does not block routine operations but does block the privileged read that requires audit. | 044 | integration |

## 12. Privacy and retention (gates, per slice)

| ID | Criterion | Req | Verification |
| --- | --- | --- | --- |
| AC-PRV-001 | The module stores no IP address, device identifier, precise customer location or payment data (schema review test). | 038 | schema test |
| AC-PRV-002 | With no approved retention rule, no purge job deletes anything and a report lists the categories lacking a rule. | 039 | unit |
| AC-PRV-003 | For each enabled category, deletion removes content, leaves no recoverable copy in API or search, respects legal hold and is idempotent `[DR-BZ-18]`. | 039 | integration |
| AC-PRV-004 | Export and erase operations exist for each enabled personal-data category, callable only by the approved orchestrator caller `[DR-BZ-18]`. | 040 | integration |
| AC-PRV-005 | Notice copy approved by the owner is present on each screen that collects data before the slice is enabled. | 038 | owner review |

## 13. Uploads (S3 evidence, S7 images — only when enabled)

| ID | Criterion | Req | Verification |
| --- | --- | --- | --- |
| AC-UPL-001 | Upload grants are size-bound, create-only, short-lived and for a private bucket; no public object URL or listing exists. | 045 | integration |
| AC-UPL-002 | Images are decoded and re-encoded; metadata is gone; corrupt, mismatched-type, oversized, animated and decompression-bomb inputs are rejected. | 045 | fixtures |
| AC-UPL-003 | Evidence of disallowed type or failing scan is quarantined and never readable by reviewers. | 045 | integration |
| AC-UPL-004 | Rejected and abandoned objects are deleted per the approved lifecycle; deletion is verified. | 045 | integration |

## 14. Isolation, contract and operations

| ID | Criterion | Req | Verification |
| --- | --- | --- | --- |
| AC-ISO-001 | The Business role has no privileges on other schemas and no other service role has privileges on `business`; the isolation preflight passes and the migration owner is not the runtime login. | 047 | SQL preflight |
| AC-ISO-002 | No foreign key references another service's table; cross-service ids are UUID columns. | 047 | schema test |
| AC-CON-001 | Every Business gateway route is in the contract; the anonymous list is exactly the approved public operations. | 048 | route-contract test |
| AC-CON-002 | Gateway responses are re-validated against exact allowlists; an extra or missing field yields 503. | 033 | gateway tests |
| AC-OPS-001 | In staging and production configuration, all Business flags are absent or closed unless the owner-approved release record enables them. | 046 | config test |
| AC-OPS-002 | With the Business service stopped, sign-in, video, points and moderation pass their smoke tests; Business routes return 503. | 046 | integration |
| AC-OPS-003 | The shared service-identity verifier in `business` is byte-identical to the others (drift test), and dependencies are pinned and scanned. | 047 | CI |
| AC-OPS-004 | Health and probe endpoints exist; resource limits and timeouts are configured; no secret is in the repository. | 047 | CI, secret scan |

## 15. Client surfaces (DR-BZ-21)

**None of these has been run.** AC-CLI-001…004 are cheap, repository-only tests that can protect the decision today; AC-CLI-005…008 need the console and Flutter work and cannot pass before it exists.

| ID | Criterion | Req | Verification |
| --- | --- | --- | --- |
| AC-CLI-001 | Every Business route in DOC-205, called through the Gateway test client with and without credentials, returns JSON or an empty `204`; none returns `text/html`. | 051 | route-contract extension |
| AC-CLI-002 | No Business response carries an `Access-Control-*` header, an `OPTIONS` preflight is not answered with CORS permission, and neither the Gateway nor the Business settings list a CORS middleware. | 051 | gateway test, settings test |
| AC-CLI-003 | No Business response sets a cookie, and a request with a cookie but no bearer token is 401 (or 404 for anonymous-only routes). | 051 | gateway test |
| AC-CLI-004 | The Gateway and Business settings define no `TEMPLATES`; the console URL table contains no Business owner, staff or customer page; every console Business page is registered as privileged in the route security matrix. | 049, 050 | settings and matrix tests |
| AC-CLI-005 | Each console Business page refuses anonymous, non-privileged, MFA-pending, idle and over-age sessions, requires CSRF and a valid signed intent on every mutation, and makes no Business call when it refuses; hostile text (markup, script) in Business fields renders escaped. | 050 | console route matrix, rendering test |
| AC-CLI-006 | Flutter Business repositories use the shared `ApiClient` and session manager and no other HTTP client or token store; every screen group has tested loading, empty, error and offline states. | 052 | static check, widget tests |
| AC-CLI-007 | Repository tests assert the exact request body for every Business mutation: no account, owner, role, state, verified, listed, eligibility or rating field is ever sent. | 053 | repository tests |
| AC-CLI-008 | A staff or review-invitation code is not written to storage or logs and is cleared when its screen closes; a second display is impossible. | 054 | widget and repository tests |
