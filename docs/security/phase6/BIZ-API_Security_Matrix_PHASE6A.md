# Business module — API security matrix by client surface (Phase 6A)

**Status: derived record, 24 November 2026.** Every row is generated from the 57 Business operations in DOC-205 (`x-capability` starting `business`) joined to the allowed actors of the [authorization matrix](BIZ-RBAC_and_Object_Authorization_Matrix_PROPOSED.md). DOC-205 is the contract of record; the earlier [50-operation proposal](../../architecture/business/BIZ-OpenAPI_3_1_PROPOSAL.yaml) is superseded where they differ. This table assigns each operation to a **client surface** under the owner's decision DR-BZ-21 (Flutter for visitors, customers, owners and staff; protected console for moderators and administrators; no public website or business portal). It adds no authorization rule: object-level rules, denial responses and controls stay in the matrix.

Regenerate by re-running the classification below against DOC-205; if the totals differ, this file is stale.

## 1. Totals (verified against DOC-205 at `main` `5e7eda7`)

| Surface | Operations | Flags | Gateway gate |
| --- | ---: | --- | --- |
| Flutter, customer and visitor | 15 | `business_discovery` 3, `business_inquiries` 6, `business_reviews` 6 | 4 anonymous reads; 11 signed-in |
| Flutter, owner and staff | 28 | `business_owner` 18, `business_inquiries` 6, `business_reviews` 4 | signed-in; per-business membership in the Business service |
| Flutter, staff invitation redemption | 1 | `business_owner` | signed-in |
| Protected console, moderator and administrator | 13 | `business_review_admin` 13 | privileged role with fresh MFA; 10 moderator-or-administrator (grant-scoped), 3 administrator only |
| **Total** | **57** | five flags, all closed by default | 4 anonymous, 13 MFA |

## 2. Classification rule

| Rule (first match) | Surface |
| --- | --- |
| path starts `/moderation/business` or `/admin/business` | console |
| `/business-categories`, `/businesses`, `/businesses/{id}`, `/businesses/{id}/reviews` (GET or POST), `/businesses/{id}/inquiries` (POST), `/business-reports`, anything under `/me/inquiries` or `/me/reviews` | Flutter, customer and visitor |
| `/me/business-invitations/redeem` | Flutter, staff redemption |
| anything else under `/me/businesses` | Flutter, owner and staff |

An operation matching no rule fails the generation, so a new Business operation cannot be added without a surface.

## 3. Flutter — customer and visitor (15)

| Method | Path | Flag | Gateway gate | Matrix row | Allowed actor (RBAC matrix) |
| --- | --- | --- | --- | --- | --- |
| GET | `/business-categories` | business_discovery | anon | BZ-AZ-01 | Visitor+ |
| GET | `/businesses` | business_discovery | anon | BZ-AZ-02 | Visitor+ *(DR-BZ-12)* |
| GET | `/businesses/{biz}` | business_discovery | anon | BZ-AZ-03 | Visitor+ |
| POST | `/businesses/{biz}/inquiries` | business_inquiries | bearer | BZ-AZ-05 | Customer, verified email |
| GET | `/me/inquiries` | business_inquiries | bearer | BZ-AZ-06 | Customer |
| GET | `/me/inquiries/{thread_id}` | business_inquiries | bearer | BZ-AZ-07 | Customer |
| POST | `/me/inquiries/{thread_id}/messages` | business_inquiries | bearer | BZ-AZ-08 | Customer |
| POST | `/me/inquiries/{thread_id}/close` | business_inquiries | bearer | BZ-AZ-09 | Customer |
| POST | `/me/inquiries/{thread_id}/confirm` | business_inquiries | bearer | BZ-AZ-09 | Customer |
| GET | `/businesses/{biz}/reviews` | business_reviews | anon | BZ-AZ-04 | Visitor+ |
| POST | `/businesses/{biz}/reviews` | business_reviews | bearer | BZ-AZ-10 | Customer, verified email, eligible per *(DR-BZ-15)* |
| GET | `/me/reviews` | business_reviews | bearer | BZ-AZ-11 | Customer |
| PATCH | `/me/reviews/{review_id}` | business_reviews | bearer | BZ-AZ-12 | Customer |
| DELETE | `/me/reviews/{review_id}` | business_reviews | bearer | BZ-AZ-13 | Customer |
| POST | `/business-reports` | business_reviews | bearer | BZ-AZ-14 | Any signed-in account |

## 4. Flutter — business owner and staff (28 + 1)

Allowed actors are per business; the Business service resolves membership for the specific `business_id` on every request and answers 404 to anyone else.

| Method | Path | Flag | Gateway gate | Matrix row | Allowed actor (RBAC matrix) |
| --- | --- | --- | --- | --- | --- |
| GET | `/me/businesses` | business_owner | bearer | BZ-AZ-16 | Member |
| POST | `/me/businesses` | business_owner | bearer | BZ-AZ-15 | Customer (not moderator/administrator) *(DR-BZ-03)* |
| GET | `/me/businesses/{biz}` | business_owner | bearer | BZ-AZ-17 | Owner, Staff |
| GET | `/me/businesses/{biz}/members` | business_owner | bearer | BZ-AZ-33 | Owner |
| POST | `/me/businesses/{biz}/members/invitations` | business_owner | bearer | BZ-AZ-34 | Owner |
| DELETE | `/me/businesses/{biz}/members/invitations/{inv}` | business_owner | bearer | BZ-AZ-34 | Owner |
| DELETE | `/me/businesses/{biz}/members/{member_id}` | business_owner | bearer | BZ-AZ-35 | Owner |
| POST | `/me/businesses/{biz}/leave` | business_owner | bearer | BZ-AZ-35 | Owner |
| GET | `/me/businesses/{biz}/verification` | business_owner | bearer | BZ-AZ-24 | Owner (staff: no) |
| POST | `/me/businesses/{biz}/verification` | business_owner | bearer | BZ-AZ-23 | Owner |
| POST | `/me/businesses/{biz}/verification/evidence` | business_owner | bearer | BZ-AZ-23 | Owner |
| GET | `/me/businesses/{biz}/profile` | business_owner | bearer | BZ-AZ-17 | Owner, Staff |
| PATCH | `/me/businesses/{biz}/profile` | business_owner | bearer | BZ-AZ-18 | Owner |
| POST | `/me/businesses/{biz}/profile/submit` | business_owner | bearer | BZ-AZ-19 | Owner |
| PUT | `/me/businesses/{biz}/hours` | business_owner | bearer | BZ-AZ-20 | Owner, Staff |
| GET | `/me/businesses/{biz}/listing` | business_owner | bearer | BZ-AZ-17 | Owner, Staff |
| POST | `/me/businesses/{biz}/listing/publish` | business_owner | bearer | BZ-AZ-21 | Owner |
| POST | `/me/businesses/{biz}/listing/unpublish` | business_owner | bearer | BZ-AZ-22 | Owner |
| GET | `/me/businesses/{biz}/inquiries` | business_inquiries | bearer | BZ-AZ-26 | Owner, Staff |
| GET | `/me/businesses/{biz}/inquiries/{thread_id}` | business_inquiries | bearer | BZ-AZ-27 | Owner, Staff |
| POST | `/me/businesses/{biz}/inquiries/{thread_id}/messages` | business_inquiries | bearer | BZ-AZ-28 | Owner, Staff |
| POST | `/me/businesses/{biz}/inquiries/{thread_id}/close` | business_inquiries | bearer | BZ-AZ-29 | Owner, Staff |
| POST | `/me/businesses/{biz}/inquiries/{thread_id}/confirm` | business_inquiries | bearer | BZ-AZ-29 | Owner, Staff |
| POST | `/me/businesses/{biz}/inquiries/{thread_id}/block` | business_inquiries | bearer | BZ-AZ-30 | Owner |
| PUT | `/me/businesses/{biz}/reviews/{review_id}/response` | business_reviews | bearer | BZ-AZ-31 | Owner |
| DELETE | `/me/businesses/{biz}/reviews/{review_id}/response` | business_reviews | bearer | BZ-AZ-32 | Owner |
| POST | `/me/businesses/{biz}/review-invitations` | business_reviews | bearer | BZ-AZ-34 | Owner |
| DELETE | `/me/businesses/{biz}/review-invitations/{inv}` | business_reviews | bearer | BZ-AZ-34 | Owner |

Staff invitation redemption (called by the invited account while signed in; it needs no business id because the code names it):

| Method | Path | Flag | Gateway gate | Matrix row | Allowed actor (RBAC matrix) |
| --- | --- | --- | --- | --- | --- |
| POST | `/me/business-invitations/redeem` | business_owner | bearer | BZ-AZ-34 | Owner |

## 5. Protected console — moderators and administrators (13)

| Method | Path | Flag | Gateway gate | Matrix row | Allowed actor (RBAC matrix) |
| --- | --- | --- | --- | --- | --- |
| PUT | `/admin/business-registration-grants/{account_id}` | business_review_admin | MFA | BZ-AZ-50 | Administrator |
| GET | `/moderation/business-verifications` | business_review_admin | MFA | BZ-AZ-40 | Moderator/Administrator |
| GET | `/moderation/business-verifications/{case_id}` | business_review_admin | MFA | BZ-AZ-41 | same |
| POST | `/moderation/business-verifications/{case_id}/claim` | business_review_admin | MFA | BZ-AZ-42 | same |
| POST | `/moderation/business-verifications/{case_id}/decision` | business_review_admin | MFA | BZ-AZ-42 | same |
| PUT | `/admin/business-reviewer-grants` | business_review_admin | MFA | BZ-AZ-50 | Administrator |
| PUT | `/admin/business-categories/{slug}` | business_review_admin | MFA | BZ-AZ-48 | Administrator |
| GET | `/moderation/business-profile-revisions` | business_review_admin | MFA | BZ-AZ-40 | Moderator/Administrator |
| GET | `/moderation/business-profile-revisions/{revision_id}` | business_review_admin | MFA | BZ-AZ-41 | same |
| POST | `/moderation/business-profile-revisions/{revision_id}/decision` | business_review_admin | MFA | BZ-AZ-42 | same |
| GET | `/moderation/business-reports` | business_review_admin | MFA | BZ-AZ-44 | Moderator/Administrator |
| GET | `/moderation/business-reports/{report_id}` | business_review_admin | MFA | BZ-AZ-44 | Moderator/Administrator |
| POST | `/moderation/business-reports/{report_id}/decision` | business_review_admin | MFA | BZ-AZ-45 | same |

## 6. What the matrix shows about the client decision

1. **No operation is reachable only from a browser.** All 44 non-privileged operations use the bearer token the app already holds; none depends on a cookie, CORS or CSRF token.
2. **The console surface is exactly the 13 MFA operations.** Every one needs a privileged role with fresh MFA, so a console page for them inherits the existing console controls. No console page exists yet.
3. **Four operations are anonymous** (categories, search, detail, public reviews). They are API reads for the app and are rate-limited and allowlisted; they authorize no web page.
4. **Owner and staff share a route family.** The gateway admits any viewer or creator; whether the caller is owner, staff or neither is decided only in the Business service. A privileged account (moderator, administrator) is refused there.
5. **Gaps against the original proposal.** Eleven proposed operations are not in DOC-205 (suspension, restoration, the two appeals, closure, ownership transfer, evidence read grant, grant revocation by DELETE, category create/patch, and the original staff-invitation shape); eighteen operations in DOC-205 were not in the proposal. See the validation document in the Phase 6A reconciliation.

## 7. Existing automated coverage of this surface

`scripts/test_gateway_route_contract.py` (every route declared; anonymous list exactly the declared operations; protected routes answer 401 to a credential-less caller with zero internal calls) and `scripts/test_gateway_role_matrix.py` (privileged routes refuse viewer, creator and no-MFA privileged callers before forwarding) already cover these routes. Neither asserts the client-surface properties in [AC-CLI-001…004](../../engineering/phase6/BIZ-Acceptance_Criteria_PROPOSED.md#15-client-surfaces-dr-bz-21), which are therefore proposed, not passing.
