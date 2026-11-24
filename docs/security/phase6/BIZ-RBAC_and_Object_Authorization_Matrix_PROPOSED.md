# Business module — RBAC and object-level authorization matrix

**Status: PROPOSED — Draft for owner review.** Phase 6A, 24 November 2026. Extends the [DOC-004 RBAC matrix](../../requirements/DOC-004_RBAC_Matrix_DRAFT.md) (also a draft). Roles for future modules in DOC-004 are generic; this document makes them concrete for Business. Cells that depend on an open policy name the decision (DR-BZ-nn) and must not be implemented until it is approved.

Rows are keyed **BZ-AZ-nn** and match `x-authz-ref` in the [OpenAPI proposal](../../architecture/business/BIZ-OpenAPI_3_1_PROPOSAL.yaml) one-to-one. Tests in Phase 6B are generated from this matrix (positive for the allowed actor, negative for every other actor class and for a foreign object).

## 1. Principles

1. **Deny by default.** A route exists only if declared in the contract and its capability flag is open; a new route that is not in the matrix fails the route-contract test.
2. **Three layers, none trusted alone.**
   - *Gateway:* authenticates against Identity's live session (no positive cache), applies the capability flag, role and MFA gate, validates request and response shapes.
   - *Business service:* resolves entitlement for the **specific object** on every request through one module (`authz.py`).
   - *Data:* queries are scoped by the authorized business or actor id; there is no “fetch by id then check” pattern.
3. **404, not 403, for non-entitlement.** A caller who is not entitled to an object receives the same 404 as for a missing one. 403 is used only for role, MFA or verified-email requirements that reveal nothing about a specific object.
4. **Client input never names authority.** `account_id`, owner, role, membership, state, verified, listed, rating and eligibility basis are not accepted in any body; unknown fields are rejected (400).
5. **Explicit ownership.** Business authority is a `BusinessMembership` row. There is no implicit authority from creating an object earlier or from holding another role.
6. **Least privilege.** Staff have a strict subset of owner rights; reviewers act only under explicit scoped grants; evidence access is a narrower grant than queue access.
7. **Immediate effect.** Revoking a membership or grant, suspending an account or changing a role applies on the next request (BZ-R-035).
8. **Privileged accounts cannot hold memberships.** Moderators and administrators are refused at registration and invitation (conflict of interest; DR-BZ-07).
9. **Separation of duties.** A reviewer cannot decide a case they submitted or are affiliated with; restoration needs a different reviewer than removal; an administrator cannot approve their own grant.
10. **Every state change and privileged read is audited** with identifiers and decisions only.
11. **The client surface is fixed by actor (DR-BZ-21, decided).** Visitors, customers, owners and staff use only the Flutter app; moderators and administrators use only the protected console. There is no public website and no business web portal, so no authorization rule may rely on a browser origin, cookie or CSRF token for Business routes. Client choice never grants authority: a request from the console or the app is authorized by the same server-side rules.

## 2. Actors and how each is established

| Actor | Client surface | Established by | Scope of authority |
| --- | --- | --- | --- |
| Visitor | Flutter app | no credential | Public read only (if DR-BZ-12 allows anonymous) |
| Customer | Flutter app | valid Identity session, role viewer or creator, verified email where required | Own inquiries, own reviews, reports |
| Business owner | Flutter app | active `BusinessMembership(role=owner)` for that business | That business only |
| Business staff | Flutter app | active `BusinessMembership(role=staff)` | That business only, owner-delegated subset |
| Moderator | Protected console | Identity role `moderator`, MFA-verified session, plus explicit `reviewer_grant` | Granted scope and target only |
| Administrator | Protected console | Identity role `administrator`, MFA-verified session | Administration; verification and moderation as granted; cannot approve own grant |
| Internal caller | none | HMAC service identity | Exact paths in `CALLER_PATHS` only (Moderation → decision application; **as built, the gateway is the only permitted caller**) |

## 3. Capability summary by role

`✓` allowed; `own` own objects only; `biz` objects of businesses where the caller holds the membership; `grant` only under an explicit reviewer grant; `—` denied. Cells in *italics* depend on an open decision.

| Capability | Visitor | Customer | Staff | Owner | Moderator | Administrator |
| --- | --- | --- | --- | --- | --- | --- |
| Search and read listed businesses | *✓ (DR-BZ-12)* | ✓ | ✓ | ✓ | ✓ | ✓ |
| See public contact channels | *— or ✓ (DR-BZ-12)* | ✓ | ✓ | ✓ | ✓ | ✓ |
| Register a business | — | ✓ *(DR-BZ-03)* | ✓ (separate business) | ✓ | — | — |
| Edit profile fields, contacts | — | — | — | biz | — | — |
| Edit operating hours | — | — | biz | biz | — | — |
| Submit for verification, read status | — | — | — | biz | — | — |
| Publish or unpublish listing | — | — | — | biz | — | — |
| Close business | — | — | — | biz (step-up) | — | — |
| Manage staff, transfer ownership | — | — | — | biz (step-up) | — | — |
| Send an inquiry to a listed business | — | ✓ (not a member of it) | — | — | — | — |
| Read and reply to a business's inquiries | — | — | biz | biz | — | — |
| Block a customer for a business | — | — | — | biz | — | — |
| Read own inquiry threads | — | own | — | — | — | — |
| Write, edit, withdraw own review | — | *own (DR-BZ-15)* | — (own business: no) | — (own business: no) | — | — |
| Respond to a review of own business | — | — | — | biz | — | — |
| Report a listing, review or message | — | ✓ | ✓ | ✓ | ✓ | ✓ |
| Decide verification cases | — | — | — | — | grant | grant |
| Read verification evidence | — | — | — | — | grant (evidence scope) | grant (evidence scope) |
| Decide business reports (remove, restore reviews) | — | — | — | — | grant | grant |
| Suspend a business | — | — | — | — | grant | ✓ |
| Restore a suspended business | — | — | — | — | — | ✓ (different from suspender) |
| Manage categories | — | — | — | — | — | ✓ |
| Create or revoke reviewer grants | — | — | — | — | — | ✓ (not for self) |
| Read business audit events | — | — | — | — | via existing Audit read grants | via existing Audit read grants |
| Appeal own suspension or rejection | — | — | — | biz | — | — |
| Appeal removal of own review | — | own | — | — | — | — |

A creator or viewer who is also staff or owner of business A is a customer for every other business.

## 4. Object-level matrix

Columns: **Allowed actor** (who may call); **Object rule** (the predicate the service must evaluate for the object, in addition to the gateway checks); **Controls** (MFA, step-up, SoD, idempotency, throttle, audit); **Denied as** (response for each class of denial). “Foreign” means an object the actor is not entitled to.

### 4.1 Public

| ID | Operation | Allowed actor | Object rule | Controls | Denied as |
| --- | --- | --- | --- | --- | --- |
| BZ-AZ-01 | List categories | Visitor+ | Only `active` categories | Throttle | 429 |
| BZ-AZ-02 | Search | Visitor+ *(DR-BZ-12)* | Rows exist only in `business_listing` (eligibility predicate already applied); filter allowlist | Throttle by caller; keyset cursor is HMAC-authenticated; unknown param → 400 | 400 / 429 |
| BZ-AZ-03 | Detail | Visitor+ | `business_listing.listed = true` for that id; contacts per reveal policy | Contact-reveal budget per account *(DR-BZ-12)* | 404 if unlisted, suspended, closed or unknown |
| BZ-AZ-04 | List published reviews | Visitor+ | Business listed; only `state = published` | Throttle | 404 (business) |

### 4.2 Customer

| ID | Operation | Allowed actor | Object rule | Controls | Denied as |
| --- | --- | --- | --- | --- | --- |
| BZ-AZ-05 | Create inquiry | Customer, verified email | Business listed; caller is not a member of it; caller not blocked by it; no open thread beyond the limit | Idempotency-Key; per-customer, per-business and global throttles *(DR-BZ-22)*; body bound 1000 | 404 if unlisted **or blocked** (blocking is never disclosed); 429; 403 if email unverified |
| BZ-AZ-06 | List own threads | Customer | `thread.customer_account_id = actor` (query-scoped) | — | empty list |
| BZ-AZ-07 | Read own thread | Customer | same; `thread.id` and actor must match | — | 404 |
| BZ-AZ-08 | Customer message | Customer | same; thread `open` | Idempotency-Key; throttle | 404; 409 if closed |
| BZ-AZ-09 | Close own thread | Customer | same | — | 404 |
| BZ-AZ-10 | Create review | Customer, verified email, eligible per *(DR-BZ-15)* | Business listed; actor not member or affiliated; no active review by actor for it; `interaction_thread_id` (if given) belongs to actor and that business and is confirmed | Idempotency-Key; throttle; fraud signals may place it `held` | 404 (unlisted); 409 duplicate; 403 ineligible |
| BZ-AZ-11 | List own reviews | Customer | `review.author_account_id = actor` | — | empty |
| BZ-AZ-12 | Edit own review | Customer | author = actor; state in {published, held, pending}; within edit window *(DR-BZ-16)* | Re-enters moderation checks | 404; 409 |
| BZ-AZ-13 | Withdraw own review | Customer | author = actor | Text handling per *(DR-BZ-18)*; aggregate recomputed in the same transaction | 404 |
| BZ-AZ-14 | Report subject | Any signed-in account | The reporter must be *able to see* the subject: public listing/review/response, or an inquiry message in a thread the reporter participates in; one open report per (reporter, subject) | Idempotency-Key; throttle; routed to moderation *(DR-BZ-17)* | 404 if not visible to reporter; 409 duplicate |
| BZ-AZ-53 | Appeal review removal | Customer (author) | `review.author_account_id = actor`; review `removed` by moderation; one appeal per removal | Idempotency-Key | 404; 409 |

### 4.3 Owner and staff

“Member” below means an **active** membership; every business route path contains `business_id` and **every nested id must belong to that business** (a thread, review or member id from another business returns 404).

| ID | Operation | Allowed actor | Object rule | Controls | Denied as |
| --- | --- | --- | --- | --- | --- |
| BZ-AZ-15 | Register business | Customer (not moderator/administrator) *(DR-BZ-03)* | Per-account cap *(DR-BZ-22)*; duplicate check | Idempotency-Key; throttle; audit | 403 (privileged role, email unverified); 409; 429 |
| BZ-AZ-16 | List my businesses | Member | Query scoped to `account_id = actor`, status active | — | empty |
| BZ-AZ-17 | Get my business | Owner, Staff | Active membership for `business_id`. Staff response omits `legal_name` and verification details | — | 404 |
| BZ-AZ-18 | Edit working profile | Owner | Owner of business; business not `closed`; fields allowlisted; banned: state, verified, listed, rating, role, owner | Contact changes need step-up (P6B-04) and notify owner *(DR-BZ-11)*; audit | 404; 409 closed/suspended; 400 banned field |
| BZ-AZ-19 | Submit working revision | Owner | Owner; working revision exists and is valid | Idempotency-Key; audit | 404; 409 |
| BZ-AZ-20 | Replace hours | Owner, Staff | Member; hours validated (non-overlap, bounds) | Audit | 404; 400 |
| BZ-AZ-21 | Publish listing | Owner | Owner; eligibility predicate true | Idempotency-Key; audit | 404; 409 with non-sensitive reason code |
| BZ-AZ-22 | Unpublish listing | Owner | Owner | Audit | 404 |
| BZ-AZ-23 | Submit verification case | Owner | Owner; no open case; business state allows | Idempotency-Key; throttle; audit | 404; 409 |
| BZ-AZ-24 | Read verification status | Owner (staff: no) | Owner | Applicant-visible fields only | 404 for staff and foreign |
| BZ-AZ-25 | Close business | Owner | Owner; last-owner invariant; open inquiries/reviews handling per *(DR-BZ-25/18)* | Step-up; Idempotency-Key; audit | 404; 409 |
| BZ-AZ-52 | Appeal suspension or rejection | Owner | Owner; a decision exists to appeal; one appeal per decision | Idempotency-Key; audit | 404; 409 |
| BZ-AZ-26 | Inbox list | Owner, Staff | Query scoped to `business_id` from an active membership | — | 404 |
| BZ-AZ-27 | Read thread | Owner, Staff | `thread.business_id = path business_id` AND membership; response carries `customer_label` only | — | 404 |
| BZ-AZ-28 | Reply | Owner, Staff | same; thread `open`; business not suspended | Idempotency-Key; throttle | 404; 409 |
| BZ-AZ-29 | Close thread | Owner, Staff | same | — | 404 |
| BZ-AZ-30 | Block customer (via thread) | Owner | same; creates `inquiry_block` | Idempotency-Key; audit | 404 |
| BZ-AZ-31 | Put review response | Owner | `review.business_id = path business_id` AND owner; review `published` | Moderated per *(DR-BZ-16)*; audit | 404; 409 |
| BZ-AZ-32 | Delete response | Owner | same | Audit | 404 |
| BZ-AZ-33 | List members | Owner | Owner | — | 404 |
| BZ-AZ-34 | Invite staff | Owner | Owner; staff cap; invitee not privileged *(DR-BZ-08)* | Step-up; Idempotency-Key; audit | 404; 409; 429 |
| BZ-AZ-35 | Remove member | Owner | Owner; target belongs to business; last-owner invariant; transaction-locked | Step-up; audit | 404; 409 |
| BZ-AZ-36 | Transfer ownership | Owner | Owner; target is an active member; business verification policy *(DR-BZ-04)* | Step-up; Idempotency-Key; audit | 404; 409 |

### 4.4 Reviewers and administrators (MFA-verified session required)

| ID | Operation | Allowed actor | Object rule | Controls | Denied as |
| --- | --- | --- | --- | --- | --- |
| BZ-AZ-40 | Verification queue | Moderator/Administrator | Cases within the reviewer's active `verification` grant (target-scoped or all) | MFA; audit of read | 403 (role/MFA); empty list (no grant) |
| BZ-AZ-41 | Read case | same | Case within grant; **reviewer ≠ submitter**, not affiliated | MFA; each read audited | 404 |
| BZ-AZ-42 | Decide case | same | same; case state allows the decision | Idempotency-Key and payload digest; reason code required; audit; no self-decision | 404; 409 |
| BZ-AZ-43 | Evidence read grant | same, **evidence scope** | Evidence belongs to a case within the grant; evidence not `quarantined`/`purged` | Short-lived signed URL; one use; audit every issue; no listing | 404 |
| BZ-AZ-44 | Report queue | Moderator/Administrator | Reports within the reviewer's `review_queue` grant | MFA | 403; empty |
| BZ-AZ-45 | Decide report | same | Same; restoration only by a reviewer different from the remover | Idempotency; receipt makes application at Business idempotent | 404; 409 |
| BZ-AZ-46 | Suspend | Moderator (granted), Administrator | Business exists, not closed | MFA; reason code; notify owner; audit | 404; 409 |
| BZ-AZ-47 | Restore | Administrator | Different from suspender | MFA; reason code; audit | 404; 409 |
| BZ-AZ-48 | Create category | Administrator | Slug unique; depth ≤ 2 | MFA; audit | 409 |
| BZ-AZ-49 | Update category | Administrator | Exists | MFA; audit | 404 |
| BZ-AZ-50 | Put reviewer grant | Administrator | Grantee is moderator or administrator, not the actor; target business valid | MFA; audit | 404; 409 |
| BZ-AZ-51 | Revoke grant | Administrator | Grant exists | MFA; effect on next request | 404 |

### 4.5 Internal

| ID | Operation | Allowed caller | Object rule | Controls |
| --- | --- | --- | --- | --- |
| BZ-AZ-60 | Apply moderation decision at Business | `moderation` service identity only; exact path | Subject exists; `action_id` not already applied (receipt) | HMAC with per-caller key, 60 s window, nonce; idempotent by action id; audit |

## 5. Field-level visibility

| Field | Visitor/Customer | Staff | Owner | Reviewer |
| --- | --- | --- | --- | --- |
| display name, category, county, city, summary | public | ✓ | ✓ | ✓ |
| `legal_name` | — | — | ✓ | ✓ (assigned case) |
| address line, coordinates | only if owner opted in | ✓ | ✓ | ✓ |
| contact channels | `is_public` only, per reveal policy | ✓ | ✓ | ✓ |
| verification state | `verified` flag only | flag | state, applicant-visible reason | full |
| verification evidence | — | — | — (owner uploaded it) | ✓ (evidence grant) |
| customer account id | — | **never** | **never** | audit/privileged tooling only |
| customer label in inquiry | — | ✓ | ✓ | ✓ |
| review author id | — | — | — | ✓ (moderation) |
| review author label | per *(DR-BZ-16)* | same | same | ✓ |
| fraud-hold reason codes | — | — | — | ✓ |

## 6. Mass-assignment and response rules

- **Banned in any request body:** `id`, `account_id`, `author_account_id`, `customer_account_id`, `business_id` (when in path), `role`, `state`, `status`, `verified`, `listed`, `rating*`, `eligibility_basis`, `created_*`, `reviewed_*`, `decided_*`. A test posts each and expects 400.
- **Response allowlists:** the gateway re-validates every Business response with an exact field set (like `valid_audit_page`); an extra field is a 503, not passed through.
- **Public views read only `business_listing` and published review rows.**

## 7. Negative-test catalogue (generated into Phase 6B tests)

| ID | Scenario | Expected |
| --- | --- | --- |
| BZ-NT-01 | Owner of A requests B's `business_id` on every `/me/businesses/{id}` route (GET, PATCH, PUT, POST, DELETE) | 404, identical to a random UUID; no side effect |
| BZ-NT-02 | Nested id swap: A's owner uses thread/review/member id belonging to B under A's path | 404 |
| BZ-NT-03 | Staff of A calls each owner-only route | 404 (or 403 only where role is disclosable); no change |
| BZ-NT-04 | Membership revoked; same bearer token used again | 404 on next request |
| BZ-NT-05 | Customer reads another customer's thread by id | 404 |
| BZ-NT-06 | Customer reads, edits, withdraws another author's review | 404 |
| BZ-NT-07 | Owner or staff reviews own business; affiliated account reviews | refused |
| BZ-NT-08 | Moderator/administrator calls registration or staff-invite | refused |
| BZ-NT-09 | Request bodies containing each banned field | 400 |
| BZ-NT-10 | Last owner removed concurrently (two requests) | exactly one succeeds; invariant holds |
| BZ-NT-11 | Reviewer decides case they submitted; reviewer without grant; reviewer with queue grant requesting evidence | 404 / 403; audited as denied |
| BZ-NT-12 | Same idempotency key, different payload; different key on decided case | 409; no second state change |
| BZ-NT-13 | Public detail/search for unlisted, suspended, closed, rejected business | 404 / absent |
| BZ-NT-14 | Public JSON schema contains a column not allowlisted (private field leak test over `business_listing` columns) | build fails |
| BZ-NT-15 | Forged, replayed or foreign-key-signed internal call (wrong caller, wrong audience, stale timestamp, reused nonce, path not allowed) | 403 |
| BZ-NT-16 | Tampered or foreign cursor; unknown query param; oversize query | 400 |
| BZ-NT-17 | Role or MFA missing on every reviewer/admin route, with zero Business calls made | refused at gateway |
| BZ-NT-18 | Blocked customer sends inquiry | indistinguishable from unlisted business |
| BZ-NT-19 | Staff reads inquiry of a different business via the right thread id and wrong path business id | 404 |
| BZ-NT-20 | Restoration by the remover | 409 |
| BZ-NT-21 | Report of a subject the reporter cannot see | 404 |
| BZ-NT-22 | Evidence read grant reused or after expiry | refused; second use audited |
| BZ-NT-23 | Capability flags closed: every route returns the same as unknown route | 404 |

## 8. Open items affecting this matrix

DR-BZ-03, 04, 05, 07, 08, 11, 12, 14, 15, 16, 17, 22, 25 change specific cells. The matrix is complete for the *mechanism*; cells marked with a decision must be re-checked when the decision is made. P6B-04 (purpose-bound step-up in Identity) is required before any “step-up” control can be implemented.
