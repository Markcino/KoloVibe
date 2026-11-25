# Phase 4: Business module completion (25 November 2026)

**Verification on disposable local services only.** Business was not activated on AWS or staging, no capability flag was opened, nothing was deployed or merged. **Production NO-GO stands.** Nothing here is staging or device acceptance.

## 0. Exit summary

All approved Business functionality is **Development complete**. All 57 DOC-205 operations are routed through the Gateway, behind closed flags, and each has a client: 44 in the Flutter app and 13 in the console. The exception is staff removal, which refuses every caller by design. Each of the eleven extensions listed in section B depends on a decision that is still open, so it stays **Blocked by approval**. Nothing was bypassed to make an extension look complete. Phase 4 made no application code change. It added one console test that closes the last open link in the reconciliation.

## A. Current Business functionality

| Feature | Classification | Code | Evidence (tests run in this phase) |
| --- | --- | --- | --- |
| Registration (invitation-only, cap 3, throttled) | Development complete | `ownership.py` | `test_ownership.py` registration tests |
| Ownership (one active owner, owner and staff roles) | Development complete | `ownership.py`, `authz.py` | `test_ownership.py`, `test_authorization_matrix.py` |
| Verification (case, claim, decide, request info, revoke, duplicates flagged) | Development complete; file evidence **Blocked by approval** (DR-BZ-19) | `verification.py` | `test_verification.py` |
| Profiles (draft, submit, material re-review, history) | Development complete; live contact change **Blocked by approval** (DR-BZ-33) | `profiles.py` | `test_profiles.py` |
| Operating hours | Development complete | `hours.py` | `test_profiles.py` |
| Listings (publish, unpublish, reconcile) | Development complete | `listings.py`, `reconcile_listings` | `test_listings.py` |
| Discovery (categories, search, detail, reviews) | Development complete; substring search (DR-BZ-30 open) | `listings.py` | `test_listings.py`, journeys |
| Inquiries (create, thread, close, confirm, block) | Development complete; notifications deferred (DR-BZ-14) | `inquiries.py` | `test_inquiries.py` |
| Reviews (basis, holds, edit, withdraw, one response, invitations) | Development complete; minimum count for the average is owner-set | `reviews.py` | `test_reviews.py` |
| Staff membership (invite, redeem, list, leave, revoke invitation) | Development complete; owner removal **Blocked by approval** (DR-BZ-33) | `ownership.py` | `test_ownership.py` |
| Reporting (messages and reviews, local queue, fraud holds) | Development complete; listing reports, restoration and appeals **Blocked by approval** (DR-BZ-29) | `reviews.py` | `test_reviews.py` |
| Administration (reviewer grants, registration grants, categories) | Development complete | `verification.py`, `ownership.py` | `test_verification.py`, `test_ownership.py` |
| Audit delivery (39 Business kinds, bounded delivery) | Development complete; deploy needs Business rollout approval | `security_audit.py`, `deliver_audit_events` | `test_audit_delivery.py`, journey audit check |

Suites run on `main` (after PR #233): Business 232 (1 skipped), Gateway 224, Audit 51, console 180 (179 existing plus 1 new), `scripts` 475 (4 skipped) including the Business contract reconciliation and Gateway role matrix, Business on PostgreSQL (`scripts/test_business_postgres.py`), and real-HTTP journeys (`scripts/verify_local_journeys.py`, 11, including the Phase 6E Business journey). Flutter Business tests: 267 passed (`flutter test test/business_*.dart test/live_business_repository_test.dart`).

## B. Listed gaps against the approval register

| Gap | Classification | Blocked by |
| --- | --- | --- |
| Identity step-up for sensitive operations | **Blocked by approval** | DR-BZ-33 (Open): approval to design the Identity change |
| Staff removal | **Blocked by approval** | DR-BZ-33. Refuses every caller (`step_up_unavailable`). The app shows an explanation, not a control |
| Business contact changes (live profile) | **Blocked by approval** | DR-BZ-33. Changes to a draft or unverified profile work |
| Suspension and restoration | **Blocked by approval** | DR-BZ-25 needs the owner to approve the grounds; DR-BZ-29 (Open) decides where the workflow lives |
| Business closure | **Blocked by approval** | DR-BZ-33, DR-BZ-25 |
| Ownership transfer | **Blocked by approval** | DR-BZ-33, DR-BZ-08 (step-up required) |
| Impersonation disputes | **Blocked by approval** | DR-BZ-26 needs listing reports and a listing freeze, which depend on DR-BZ-29 and DR-BZ-25 |
| Appeals | **Blocked by approval** | DR-BZ-29 |
| Business images and file evidence | **Blocked by approval** | DR-BZ-20 (no images in the first slices; image pipeline shared with D-10), DR-BZ-19 and OD-07 |
| Notifications | **Blocked by approval** | DR-BZ-14: delivery deferred by the approved recommendation |
| Retention and deletion | **Blocked by approval** | DR-BZ-18: periods and deletion semantics owed after legal review (DR-BZ-23); ADR-020 privacy orchestration |

## C. Flutter

M-109 to M-144 (36 screens) are live Business screens. `business_routes_test.dart` asserts that no Business screen is a placeholder. `live_business_repository_test.dart` asserts that the app covers every app-facing operation in the contract, except `member_remove`, and calls nothing undeclared. `_operations.json` is checked against DOC-205 by `services/business/tests/test_mobile_fixtures.py`. The screen tests use a recording repository to check that each enabled control produces its repository call. Refused actions (M-130 contact change, M-139 staff removal) show one explanatory row and no control. Visual design approval is still open (DR-BZ-27). Owners, staff and customers use only Flutter (DR-BZ-21).

## D. Django dashboard

| Operation | Classification | Page |
| --- | --- | --- |
| Business verification | Development complete | `admin/business/verifications/` (queue, claim, decide) |
| Reviewer assignments | Development complete | `admin/business/access/` (reviewer and registration grants) |
| Evidence inspection | Development complete for text evidence; files **Blocked by approval** (DR-BZ-19) | verification case detail |
| Profile review | Development complete | `admin/business/profiles/` |
| Business reports | Development complete | `admin/business/reports/` |
| Fraud review | Development complete | system fraud holds in the report queue (`holds` count); release or remove |
| Dispute review | **Blocked by approval** | DR-BZ-26, DR-BZ-29 |
| Suspension and restoration | **Blocked by approval** | DR-BZ-25, DR-BZ-29 |
| Audit history | Development complete | `admin/audit/` with the `business` producer filter |

Every page sits behind the privileged MFA wrapper (`test_route_security_matrix.py`). There is no ordinary-user business web portal.

## E. Security

| Area | Evidence (all passed) |
| --- | --- |
| Cross-business IDOR and BOLA | `test_object_matrix_non_entitled_actors_get_the_unknown_id_answer_and_change_nothing`, `test_nested_ids_must_belong_to_the_path_business`, `test_cross_business_isolation_for_owners`, `test_a_grant_for_one_business_does_not_cover_another` |
| Forged ownership | `test_no_operation_accepts_a_field_that_names_authority`, `test_the_actor_is_only_ever_read_from_the_attested_envelope`, `test_client_cannot_name_authority_or_state`, the signed-envelope tests in `test_security_hardening.py` |
| Role changes | `test_authority_in_the_body_changes_nothing_for_the_main_write_operations`, `test_staff_cannot_use_owner_operations`, `test_only_an_mfa_administrator_grants_and_never_to_self`. No role editor exists, by design |
| Revoked staff permissions | revoked membership refused on the next request (`test_ownership.py`), `test_revoking_a_grant_takes_effect_on_the_next_request_even_mid_case`, journey step 13 |
| Unauthorized verification | `test_an_owner_cannot_decide_claim_or_grant_in_their_own_verification`, `test_a_reviewer_cannot_skip_the_claim_or_decide_a_case_that_is_not_theirs`, `test_conflict_of_interest_blocks_the_submitter_creator_and_members` |
| Review abuse | affiliation refusal, one review per author, burst and duplicate holds, `test_a_business_has_no_operation_that_hides_edits_or_removes_a_review`, report throttles |
| Sensitive information leakage | `test_no_response_names_an_account_other_than_the_caller_or_carries_an_internal_field`, `test_public_projections_carry_only_what_a_stranger_may_see`, `test_every_refusal_is_a_bounded_message_without_ids_or_internals`, audit events carry ids only |
| Replay and duplicate actions | `test_a_replayed_write_is_never_applied_twice`, `test_a_captured_request_cannot_be_sent_twice`, `test_a_decided_case_cannot_be_decided_again_with_a_new_key`, decision replays |
| Privileged MFA enforcement | `test_gate_matrix_refuses_wrong_role_missing_mfa_unverified_email_and_foreign_caller`, console MFA alignment, Gateway role matrix |

No new security defect was found. Observation for the owner, not a defect: an account that reviewed a business before later joining it as staff keeps its published review. Affiliation is checked only when a review is created. A policy for existing reviews belongs to DR-BZ-15.

## F. Integration reconciliation

`scripts/test_business_contract_reconciliation.py` checks contract against Gateway against service: routing, flags, authority, statuses, query parameters, matrix rows and fixture schemas. The Flutter coverage test checks contract against app. The console alignment test checks console against contract. **New in Phase 4:** `test_every_privileged_business_operation_has_a_console_consumer` checks the reverse direction for the console, so every declared operation now has a client or a recorded reason.

### Verified Business completion matrix (57 operations)

Every row: backend handler registered in the service, Gateway route present (`routed`), contract entry in DOC-205 with an authorization-matrix row, an automated test (reconciliation, authorization matrix and the client's coverage test).

| Operation | Method and path | Capability | Authz row | Gateway | Client |
| --- | --- | --- | --- | --- | --- |
| `category_list` | `GET /business-categories` | business_discovery | BZ-AZ-01 | routed | Flutter and console |
| `public_detail` | `GET /businesses/{business_id}` | business_discovery | BZ-AZ-03 | routed | Flutter |
| `public_search` | `GET /businesses` | business_discovery | BZ-AZ-02 | routed | Flutter |
| `inquiry_block` | `POST /me/businesses/{business_id}/inquiries/{thread_id}/block` | business_inquiries | BZ-AZ-30 | routed | Flutter |
| `inquiry_close_business` | `POST /me/businesses/{business_id}/inquiries/{thread_id}/close` | business_inquiries | BZ-AZ-29 | routed | Flutter |
| `inquiry_close_customer` | `POST /me/inquiries/{thread_id}/close` | business_inquiries | BZ-AZ-09 | routed | Flutter |
| `inquiry_confirm_business` | `POST /me/businesses/{business_id}/inquiries/{thread_id}/confirm` | business_inquiries | BZ-AZ-29 | routed | Flutter |
| `inquiry_confirm_customer` | `POST /me/inquiries/{thread_id}/confirm` | business_inquiries | BZ-AZ-09 | routed | Flutter |
| `inquiry_create` | `POST /businesses/{business_id}/inquiries` | business_inquiries | BZ-AZ-05 | routed | Flutter |
| `inquiry_get_mine` | `GET /me/inquiries/{thread_id}` | business_inquiries | BZ-AZ-07 | routed | Flutter |
| `inquiry_inbox` | `GET /me/businesses/{business_id}/inquiries` | business_inquiries | BZ-AZ-26 | routed | Flutter |
| `inquiry_inbox_get` | `GET /me/businesses/{business_id}/inquiries/{thread_id}` | business_inquiries | BZ-AZ-27 | routed | Flutter |
| `inquiry_list_mine` | `GET /me/inquiries` | business_inquiries | BZ-AZ-06 | routed | Flutter |
| `inquiry_message_customer` | `POST /me/inquiries/{thread_id}/messages` | business_inquiries | BZ-AZ-08 | routed | Flutter |
| `inquiry_reply` | `POST /me/businesses/{business_id}/inquiries/{thread_id}/messages` | business_inquiries | BZ-AZ-28 | routed | Flutter |
| `get_mine` | `GET /me/businesses/{business_id}` | business_owner | BZ-AZ-17 | routed | Flutter |
| `hours_replace` | `PUT /me/businesses/{business_id}/hours` | business_owner | BZ-AZ-20 | routed | Flutter |
| `list_mine` | `GET /me/businesses` | business_owner | BZ-AZ-16 | routed | Flutter |
| `listing_publish` | `POST /me/businesses/{business_id}/listing/publish` | business_owner | BZ-AZ-21 | routed | Flutter |
| `listing_status` | `GET /me/businesses/{business_id}/listing` | business_owner | BZ-AZ-17 | routed | Flutter |
| `listing_unpublish` | `POST /me/businesses/{business_id}/listing/unpublish` | business_owner | BZ-AZ-22 | routed | Flutter |
| `member_leave` | `POST /me/businesses/{business_id}/leave` | business_owner | BZ-AZ-35 | routed | Flutter |
| `member_list` | `GET /me/businesses/{business_id}/members` | business_owner | BZ-AZ-33 | routed | Flutter |
| `member_remove` | `DELETE /me/businesses/{business_id}/members/{member_id}` | business_owner | BZ-AZ-35 | routed | none (refused until step-up, DR-BZ-33) |
| `profile_edit` | `PATCH /me/businesses/{business_id}/profile` | business_owner | BZ-AZ-18 | routed | Flutter |
| `profile_get` | `GET /me/businesses/{business_id}/profile` | business_owner | BZ-AZ-17 | routed | Flutter |
| `profile_submit` | `POST /me/businesses/{business_id}/profile/submit` | business_owner | BZ-AZ-19 | routed | Flutter |
| `register` | `POST /me/businesses` | business_owner | BZ-AZ-15 | routed | Flutter |
| `staff_invitation_revoke` | `DELETE /me/businesses/{business_id}/members/invitations/{invitation_id}` | business_owner | BZ-AZ-34 | routed | Flutter |
| `staff_invite` | `POST /me/businesses/{business_id}/members/invitations` | business_owner | BZ-AZ-34 | routed | Flutter |
| `staff_redeem` | `POST /me/business-invitations/redeem` | business_owner | BZ-AZ-34 | routed | Flutter |
| `verification_respond` | `POST /me/businesses/{business_id}/verification/evidence` | business_owner | BZ-AZ-23 | routed | Flutter |
| `verification_status` | `GET /me/businesses/{business_id}/verification` | business_owner | BZ-AZ-24 | routed | Flutter |
| `verification_submit` | `POST /me/businesses/{business_id}/verification` | business_owner | BZ-AZ-23 | routed | Flutter |
| `category_put` | `PUT /admin/business-categories/{slug}` | business_review_admin | BZ-AZ-48 | routed | Console |
| `profile_decide` | `POST /moderation/business-profile-revisions/{revision_id}/decision` | business_review_admin | BZ-AZ-42 | routed | Console |
| `profile_queue` | `GET /moderation/business-profile-revisions` | business_review_admin | BZ-AZ-40 | routed | Console |
| `profile_revision` | `GET /moderation/business-profile-revisions/{revision_id}` | business_review_admin | BZ-AZ-41 | routed | Console |
| `registration_grant` | `PUT /admin/business-registration-grants/{account_id}` | business_review_admin | BZ-AZ-50 | routed | Console |
| `report_case` | `GET /moderation/business-reports/{report_id}` | business_review_admin | BZ-AZ-44 | routed | Console |
| `report_decide` | `POST /moderation/business-reports/{report_id}/decision` | business_review_admin | BZ-AZ-45 | routed | Console |
| `report_queue` | `GET /moderation/business-reports` | business_review_admin | BZ-AZ-44 | routed | Console |
| `reviewer_grant` | `PUT /admin/business-reviewer-grants` | business_review_admin | BZ-AZ-50 | routed | Console |
| `verification_case` | `GET /moderation/business-verifications/{case_id}` | business_review_admin | BZ-AZ-41 | routed | Console |
| `verification_claim` | `POST /moderation/business-verifications/{case_id}/claim` | business_review_admin | BZ-AZ-42 | routed | Console |
| `verification_decide` | `POST /moderation/business-verifications/{case_id}/decision` | business_review_admin | BZ-AZ-42 | routed | Console |
| `verification_queue` | `GET /moderation/business-verifications` | business_review_admin | BZ-AZ-40 | routed | Console |
| `report_create` | `POST /business-reports` | business_reviews | BZ-AZ-14 | routed | Flutter |
| `review_create` | `POST /businesses/{business_id}/reviews` | business_reviews | BZ-AZ-10 | routed | Flutter |
| `review_edit_mine` | `PATCH /me/reviews/{review_id}` | business_reviews | BZ-AZ-12 | routed | Flutter |
| `review_invite_create` | `POST /me/businesses/{business_id}/review-invitations` | business_reviews | BZ-AZ-34 | routed | Flutter |
| `review_invite_revoke` | `DELETE /me/businesses/{business_id}/review-invitations/{invitation_id}` | business_reviews | BZ-AZ-34 | routed | Flutter |
| `review_list_mine` | `GET /me/reviews` | business_reviews | BZ-AZ-11 | routed | Flutter |
| `review_list_public` | `GET /businesses/{business_id}/reviews` | business_reviews | BZ-AZ-04 | routed | Flutter |
| `review_respond` | `PUT /me/businesses/{business_id}/reviews/{review_id}/response` | business_reviews | BZ-AZ-31 | routed | Flutter |
| `review_response_delete` | `DELETE /me/businesses/{business_id}/reviews/{review_id}/response` | business_reviews | BZ-AZ-32 | routed | Flutter |
| `review_withdraw_mine` | `DELETE /me/reviews/{review_id}` | business_reviews | BZ-AZ-13 | routed | Flutter |

## Phase boundary report

1. **Verified commit:** `main` after PR #233 merged. The Phase 3 PRs #234 to #237 are not merged and none of them touches Business.
2. **Feature matrix:** sections A to F above.
3. **Files changed:** this report; a tracker pointer; one test in `apps/web_django/tests/test_business_contract_alignment.py`.
4. **Database and API changes:** none.
5. **Security findings:** none new. One policy observation (section E).
6. **Tests:** the counts in section A, all run in this container.
7. **PR:** documentation and test PR from `claude/project-thread-5fly00-p4-business`; not merged.
8. **Outstanding decisions:** DR-BZ-14, 18, 19, 20, 23, 25 (grounds), 26 to 33, OD-07, ADR-020, and the owner values listed in the Business approval record.
9. **Known defects:** the Phase 6E known issues K4 to K8 are unchanged (duplicate scan, category list, listing reconciliation query pattern).
10. **Next-phase prerequisites:** DR-BZ-33 to unblock four owner actions; DR-BZ-25 and 29 for suspension, appeals and disputes; DR-BZ-32 and the rollout approval before any Business staging activation.

**STOP AFTER PHASE 4.**
