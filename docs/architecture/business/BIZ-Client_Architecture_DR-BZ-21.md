# Business module — client architecture (DR-BZ-21)

**Status: DECIDED by the owner on 24 November 2026 (DR-BZ-21).** The screen inventory, console page list and client rules below are the **proposed design that implements that decision**; the screens themselves still need approved designs (DR-BZ-27) and none is built. Nothing here changes R1 behaviour. No code, migration or AWS change is part of Phase 6A.

Decision record: [DR-BZ-21 in the decision register](BIZ-Owner_Decision_Register_PROPOSED.md#dr-bz-21--where-business-owners-work). Backend as built: [Phase 6B completion report](../../engineering/phase6/Phase6B_Business_Backend_Completion_Report_2026-11-24.md). Contract of record: DOC-205.

## 1. The decision

> All business owners, customers and business staff use Flutter mobile. Only administrators and moderators use the protected Django web dashboard. There is no public website and no business web portal.

It restates the permanent product architecture (two user-facing application types) for the Business module and closes option B ("a separate owner web portal") and option C ("admin-assisted pilot") of the original DR-BZ-21 as **rejected**. It also establishes that a public, unauthenticated *API* read (categories, search, detail, public reviews) exists **only to serve the mobile app** and is not authority for any website.

## 2. Who uses which surface

| Actor | Surface | What they do |
| --- | --- | --- |
| Visitor (not signed in) | Flutter mobile | Browse categories, search, read a listing and its published reviews (the four anonymous reads; contact values follow the reveal policy, DR-BZ-12) |
| Customer (viewer or creator account, verified email) | Flutter mobile | Everything above, plus inquiries, reviews, reports |
| Business owner | Flutter mobile | Register, submit verification, manage profile, hours, listing, staff, inquiries, review responses and invitations |
| Business staff | Flutter mobile | Redeem an invitation; work the inbox; edit hours; leave the business. Staff have no verification, profile-edit, publish or staff-management rights (see the [capability summary](../../security/phase6/BIZ-RBAC_and_Object_Authorization_Matrix_PROPOSED.md#3-capability-summary-by-role)) |
| Moderator (explicit grant, MFA) | Protected Django console | Verification cases, profile-revision review, review/inquiry report decisions |
| Administrator (MFA) | Protected Django console | Everything a moderator may do plus categories, reviewer grants, registration grants |
| Internal service | none | Signed service calls only |

A privileged account (moderator, administrator) cannot own, staff or review a business, so no person uses both surfaces in a business role.

## 3. What is excluded

| Excluded | Why | How it is kept out (proposed controls) |
| --- | --- | --- |
| Public website, business directory pages, landing pages | Owner decision | No HTML route in Gateway or Business: neither has a template engine configured for pages; a test fails if a Business route returns `text/html` |
| Business-owner or staff web portal | Owner decision | The console routes are guarded for `moderator`/`administrator` with fresh MFA; the route security matrix already fails on an unclassified console route, so a new owner page cannot be added silently |
| Customer web app, web inquiry or review forms | Owner decision | Same; no Business browser-facing form exists |
| Cross-origin browser access | No browser client exists | No CORS middleware in Gateway (verified at `main` `5e7eda7`: none); a test asserts no `Access-Control-*` header on Business routes |
| Cookies and CSRF for Business APIs | Bearer-token mobile API | Business routes never set or read cookies; the console keeps its own server-side session and CSRF (unchanged) |
| Search-engine indexing, sitemaps, `robots` allow-lists, share-preview pages, embeds | Would create a public website | None are created; DR-BZ-28 decides whether any web link may exist at all |
| Admin-assisted pilot (option C) | Owner decision | Not designed |

The anonymous API reads are bounded, throttled and allowlisted exactly as before; their existence is **not** a reason to host a page.

## 4. Flutter design (proposed; reuses what exists)

New code lives under one feature folder (for example `features/business/`) and reuses, without copying:

| Need | Existing component |
| --- | --- |
| HTTP, error mapping, base URL, timeouts | `core/network/api_client.dart` (`ApiClient`, `ApiFailure`) |
| Sign-in, session restore, token refresh and rotation | `LiveAccountRepository.authenticatedRequest`; refresh credential in platform secure storage via `core/security/credential_store.dart`. **No second session system.** |
| App compatibility gate | existing `/app/compatibility` check in `kolovibe_app.dart` |
| Repository and state pattern | `core/presentation/feature_repository.dart` and the per-feature live repositories |
| Visual components, empty, loading, offline, error states | `shared/widgets/kolo_components.dart`, `design_view.dart`, the system-state screens (M-095–M-108) |
| Navigation | `app/screen_route.dart`. **Note:** `ScreenRoute.valid` accepts only 1–108 and the design audit asserts exactly 108 screens, so business screens need an approved extension of the route space and of `design_audit_test` (DR-BZ-27) |

Client rules (proposed requirements BZ-R-049…054 in [DOC-020](../../requirements/DOC-020_Business_Requirements_and_Scope_PROPOSED.md)): the client never decides ownership, eligibility, listing visibility, "verified", "open now", rating or review basis; it never sends an account, owner, role or state field; it renders every text field as plain text; it shows server-provided reason codes without interpreting them; invitation and review-invitation codes are shown once and never stored on the device.

### Screen groups and the operations they use

Operation counts are from DOC-205 as of `main` `5e7eda7` (57 Business operations: 44 serve the mobile app, 13 serve the console). Group names are working titles; screen numbers are assigned only with approved designs.

| Group | Screens (proposed) | DOC-205 operations | Backend today |
| --- | --- | --- | --- |
| **Customer discovery** | Directory with search, category, region, open-now, verified filters; business detail; published reviews; report sheet | `GET /business-categories`, `GET /businesses`, `GET /businesses/{id}`, `GET /businesses/{id}/reviews`, `POST /business-reports` | Built, flags closed (`business_discovery`, `business_reviews`) |
| **Customer inquiries** | Start inquiry; my inquiries; thread with reply, close, confirm completion | `POST /businesses/{id}/inquiries`, `GET /me/inquiries`, `GET /me/inquiries/{id}`, `POST …/messages`, `…/close`, `…/confirm` | Built (`business_inquiries`); no notifications (DR-BZ-14) |
| **Customer reviews** | Write review (basis shown); my reviews; edit; withdraw | `POST /businesses/{id}/reviews`, `GET /me/reviews`, `PATCH`/`DELETE /me/reviews/{id}` | Built (`business_reviews`); policy values pending |
| **Owner onboarding** | Register a business (invitation-gated pilot); my businesses; submit verification; answer a request for information; status | `GET`/`POST /me/businesses`, `GET /me/businesses/{id}`, `…/verification`, `…/verification/evidence` | Built (`business_owner`); text evidence only |
| **Owner profile and listing** | Business dashboard; profile editor with per-field public toggles; hours; submit for review; publish / unpublish | `…/profile`, `…/profile/submit`, `…/hours`, `…/listing`, `…/listing/publish`, `…/listing/unpublish` | Built; live contact change refuses until step-up exists (P6B-04) |
| **Staff management** | Team list; invite (code shown once); revoke invitation; staff redeem code; leave; remove member | `…/members`, `…/members/invitations[/{id}]`, `DELETE …/members/{id}`, `POST …/leave`, `POST /me/business-invitations/redeem` | Built except removal, which refuses until step-up exists |
| **Owner and staff inquiries** | Inbox; thread; reply; close; confirm; block (owner) | `…/inquiries[/{id}]`, `…/messages`, `…/close`, `…/confirm`, `…/block` | Built |
| **Owner reviews** | Respond to a review; delete own response; issue and revoke review-invitation codes | `PUT`/`DELETE …/reviews/{id}/response`, `POST`/`DELETE …/review-invitations[/{id}]` | Built |
| **Appeals** | Appeal a suspension, rejection or review removal | none in DOC-205 | **Not built** (DR-BZ-25, DR-BZ-17) |

### Existing mobile gaps this introduces (not in R1)

No Business screen, repository, route or test exists in `apps/mobile` today (verified by search). Client work is a later phase and is gated by DR-BZ-27 and by the copy and list inputs the owner still owes (categories, counties, warning and notice text).

## 5. Protected console design (proposed; reuses the existing console)

The 13 reviewer and administrator operations map to console pages in the existing `apps/web_django` project. **None exists today.**

| Page | Operations | Role |
| --- | --- | --- |
| Verification queue and case | `GET /moderation/business-verifications[/{id}]`, `POST …/claim`, `POST …/decision` | moderator or administrator with a `verification` grant |
| Profile-revision review | `GET /moderation/business-profile-revisions[/{id}]`, `POST …/decision` | moderator or administrator with a grant |
| Business report review | `GET /moderation/business-reports[/{id}]`, `POST …/decision` | moderator or administrator with a `review_queue` grant |
| Reviewer grants | `PUT /admin/business-reviewer-grants` | administrator only; never for self |
| Registration grants (pilot invitation) | `PUT /admin/business-registration-grants/{account_id}` | administrator only |
| Categories | `PUT /admin/business-categories/{slug}` | administrator only |
| Suspension and restoration | none yet (DR-BZ-25) | — |

Console rules are inherited unchanged: privileged role with fresh MFA, 15-minute absolute and 30-minute idle sessions, signed session-bound intent per mutation, CSRF on every decision, confirmation step for decisions, owning-service scope enforcement, `no-store`, and registration in the route security matrix (a new console route fails the matrix until classified). Evidence shown to a reviewer is bounded private text only; no file evidence exists.

## 6. Consequences for security design

| Topic | Effect of "mobile only" |
| --- | --- |
| Authentication | Bearer access token (300 s) and rotating refresh token in platform secure storage for every Business actor; no cookie sessions for Business |
| Browser attack classes | CSRF, clickjacking, reflected or stored XSS on Business content and CORS misconfiguration have no Business browser target; they remain relevant **only** to the privileged console, which renders reviewer-visible Business text and must escape it (see BZ-T-076) |
| Scraping | The API is open to scripts regardless of client; controls are throttles, minimal anonymous fields and signed-in contact reveal, not "no website" |
| Token theft | A lost or rooted device is the main account-takeover path; mitigations are existing short access tokens, rotation and replay revocation, session list and revoke, and step-up for sensitive owner actions (P6B-04 still unbuilt) |
| Sharing | No external web link may exist until DR-BZ-28 is decided; a link to a public page would be a public website |
| Rollout | Mobile app versions in the field will call the contract; additive-only changes and the existing compatibility gate apply |

New threats and acceptance criteria: [STRIDE section 3.8](../../security/phase6/BIZ-STRIDE_Threat_Model_PROPOSED.md), [AC-CLI-001…008](../../engineering/phase6/BIZ-Acceptance_Criteria_PROPOSED.md).

## 7. Documents reconciled by this decision

README, DOC-020 (actors, new requirements), ADR-BIZ-001 (Decision 6), architecture (diagram and gateway note), authorization matrix (client column), STRIDE (section 3.8), acceptance criteria (section 15), backlog (P6B-07 and client slices), dependency diagram, OpenAPI proposal header, decision register (DR-BZ-21 decided; DR-BZ-27 and 28 added), approval record (addendum), and the tracker row.

## 8. Not decided here

DR-BZ-27 (approved designs and route space for business screens) and DR-BZ-28 (whether any link may leave the app) are **open**. Neither is implied by this decision.
