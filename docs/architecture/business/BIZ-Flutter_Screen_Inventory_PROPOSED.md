# Business in the Flutter app — screen inventory and design approvals (Phase 6D)

**Status: DECISIONS RECORDED 24 November 2026 (see section 6); the screens themselves are built from the design system and are "implementation-led, not visually approved".** Originally proposed for approval before any screen was built. 24 November 2026. Accountable owner: Mark Allen Gbalazeh (@Markcino). This follows DR-BZ-21 (decided: owners, staff and customers use Flutter; no public website or business portal) and is the "approved designs and route space" step of DR-BZ-27 (open). This document changes nothing by itself. **Built (24 November 2026):** all 36 screens as M-109 to M-144, with the results, operation list and test evidence in the [Phase 6D results](../../engineering/phase6/Phase6D_Business_Mobile_Results_2026-11-24.md). Still open: visual review of the screens (DR-BZ-27) and the owner's wording for the public-field explainer and review basis.

## 1. What was checked

| Question | Evidence | Result |
| --- | --- | --- |
| Do approved Business screens exist in Figma? | The Figma file `ANaV0jnwjZ0LEcByTc98HP` has two pages: *Mobile Designed* (the 108 approved screens) and *R1 adaptations (pending owner review)*. The adaptations page was read in full: M-033, M-034, M-019, M-078 (five states), M-096, M-089 and a change record; **none is a Business screen**. The main page's 108 screens were checked through the repository's design coverage register, which is keyed to that file's node ids: **no entry is a Business screen** (the only "review" entries are M-078 *Appeal / Review Request*, a moderation appeal) | **No approved Business designs exist.** The main page's full node tree was not opened (about 10,000 lines); this rests on the register and on the adaptations page read directly |
| Do the original 108 screens include Business? | Same | **No.** This document does not claim they do. The original 108 are creator-content screens (accounts, discovery, Creator Studio, Points, trust, settings, system states) |
| Is any Business code in the app? | search of `lib`, `test`, `assets` | none |
| What does the app already provide? | `ApiClient` and `authenticatedRequest` (idempotency key supported), `LiveAccountRepository` (session, refresh rotation, secure storage), `AppDependencies`, a five-tab shell (Home, Explore, Create, Videos, Profile), design tokens and shared widgets (`kolo_components`, service tiles, chips, search bar, skeletons, system states) | reusable as is |
| How are screens routed? | `ScreenRoute` accepts only 1–108; the design audit asserts exactly 108; the home hub has three service tiles (Videos, Explore, Creator Studio) and the line "More approved services as available" | a Business namespace needs an approved extension |

## 2. Proposed inventory: 36 screens in the established system

IDs use a **separate `MB-nnn` namespace** (decision A2), so the original M-001–M-108 and their audit stay untouched. "API" cites DOC-205 operations (57 Business operations: 44 serve the app). Every screen has loading, empty and failure states from the existing shared components unless stated; none shows an action the caller's role cannot use, and the API decides again on every request.

### D1 — Business discovery (visitors and customers; four anonymous reads, the rest signed-in)

| ID | Screen | API | Notes |
| --- | --- | --- | --- |
| MB-001 | Local businesses home: search bar, category chips, "open now" and "verified" quick filters, results list | `GET /businesses`, `GET /business-categories` | no paid placement, no ads, no "near me" (DR-BZ-13) |
| MB-002 | Categories (two levels) | `GET /business-categories` | list comes from the API, never hard-coded |
| MB-003 | Search results with cursor paging | `GET /businesses` | query ≤ 100 characters; filters validated before any request |
| MB-004 | Filters sheet: category, county, city, open now, verified, sort | `GET /businesses` | county list needs approval (A5) |
| MB-005 | Business detail: name, verified indicator, summary, rating count, today's hours, description, actions | `GET /businesses/{id}`, `GET …/reviews` | average rating shown only if the service returns one (hidden until the owner sets a minimum) |
| MB-006 | Opening hours: weekly rules, exceptions, "open now" computed by the server | same | time zone shown |
| MB-007 | Location and contact | same | address line only if the owner made it public; **no map, no coordinates** (never exposed by the service); contacts follow the reveal states: sign in required, verified email required, available, limit reached |
| MB-008 | Reviews of a business: published reviews, basis label, owner response | `GET /businesses/{id}/reviews` | reviewer shown as a label, never an account |
| MB-009 | "What others can see" privacy explainer | none | **copy is owner-written (DR-BZ-09); placeholder blocked** |

### D2 — Customer experience

| ID | Screen | API | Notes |
| --- | --- | --- | --- |
| MB-010 | Ask a business a question (subject, message ≤ 1,000) | `POST /businesses/{id}/inquiries` | verified email; the app never sends an owner or account id; blocked, unlisted and own business all look the same (404) |
| MB-011 | My inquiries with status (open, closed, blocked) | `GET /me/inquiries` | |
| MB-012 | Conversation: messages, reply, close, confirm completion | `GET /me/inquiries/{id}`, `POST …/messages`, `…/close`, `…/confirm` | business appears as the business, customer as "Customer N" to the business |
| MB-013 | Write a review: stars, title, text; optional proof (an interaction you confirmed, or an invitation code) | `POST /businesses/{id}/reviews` | **eligibility is decided by the service**; the basis it derives is shown afterwards; held reviews are explained, not hidden |
| MB-014 | My reviews with state (published, held, removed, withdrawn) | `GET /me/reviews` | |
| MB-015 | Edit a review | `PATCH /me/reviews/{id}` | see decision A8 (edit window not set) |
| MB-016 | Withdraw a review (confirmation) | `DELETE /me/reviews/{id}` | text is blanked immediately by the service |
| MB-017 | Report sheet for a review, an owner response or an inquiry message | `POST /business-reports` | **a report on the business itself (listing complaint, impersonation) is not supported by the service** |

### D3 — Business owner

| ID | Screen | API | Notes |
| --- | --- | --- | --- |
| MB-020 | My businesses (role and state chips; register entry) | `GET /me/businesses` | |
| MB-021 | Register a business (trading name, legal name) | `POST /me/businesses` | **pilot is invitation-only**: without an administrator's grant the service answers "invitation required" and the screen explains it; cap of 3 |
| MB-022 | Business home: state, verified, listed, tasks, shortcuts | `GET /me/businesses/{id}`, `…/listing` | |
| MB-023 | Profile editor: name, category, description, county, city, address and its public toggle | `GET`/`PATCH …/profile` | material changes go to review; the live profile stays public until approved; no coordinates input |
| MB-024 | Contacts: kind, value, public toggle | `PATCH …/profile` | websites `https` only; **changing contacts on a live profile is refused by the service until a step-up proof exists (DR-BZ-33)**; the screen says so |
| MB-025 | Opening hours: weekly rules, exceptions, time zone | `PUT …/hours` | owner and staff |
| MB-026 | Profile review status: approved, working copy, last rejection and reason code; submit for review | `GET …/profile`, `POST …/profile/submit` | |
| MB-027 | Verification: status, submit evidence, answer a request for information | `GET`/`POST …/verification`, `POST …/verification/evidence` | **text evidence only, no files**; method and kind lists need approval (A5) |
| MB-028 | Listing: status, eligibility reasons, publish and unpublish | `GET …/listing`, `POST …/listing/publish`, `…/unpublish` | |
| MB-029 | Business inbox | `GET …/inquiries` | owner and staff |
| MB-030 | Inbox conversation: reply, close, confirm, block (owner only) | `GET`/`POST …/inquiries/{id}/…` | block is never disclosed to the customer |
| MB-031 | Reviews of my business, respond and remove my response | `PUT`/`DELETE …/reviews/{id}/response` | owner only; a business can never hide or edit a review |
| MB-032 | Review invitations: issue a code (shown once), revoke | `POST`/`DELETE …/review-invitations` | the code is never stored on the device |
| MB-033 | Team: members, invite staff (code shown once), revoke an invitation | `GET …/members`, `POST …/members/invitations`, `DELETE …/members/invitations/{id}` | **removing a member refuses until step-up exists**, so no remove control is shown |

### D4 — Business staff

| ID | Screen | API | Notes |
| --- | --- | --- | --- |
| MB-040 | Accept an invitation (enter the code you were given) | `POST /me/business-invitations/redeem` | signed-in, verified email; unknown, used, revoked and expired codes look the same |
| MB-041 | Business switcher: your businesses, your role in each | `GET /me/businesses` | the choice is remembered on the device as a convenience only; every request is authorised again |
| MB-042 | Access removed: shown when the service says a business you were using is no longer yours | 404 on a business route | clears the remembered choice |
| MB-043 | Leave a business (staff) | `POST …/leave` | owners cannot leave |
| MB-044 | Staff view of the business home | as MB-022 | staff see hours, inbox, replies, close and confirm; **not** profile edit, verification, listing, blocking, responses, invitations or team |

**Not in the inventory because the backend does not support it:** appeals, suspension notices, notifications (DR-BZ-14 chose none), logos or photos (DR-BZ-20), file evidence, map or directions, sharing links (DR-BZ-28), ownership transfer, closing a business, removing staff, a report on a business listing.

## 3. Decisions needed (please approve, change or reject each)

| # | Decision | Recommendation | Effect |
| --- | --- | --- | --- |
| **A1** | **Design source.** No Figma Business designs exist | Build from the existing design system and components, mark every Business screen **"implementation-led, not visually approved"** (as the R1 adaptation frames are), and review them as screenshots; designs can replace them later without changing behaviour | Work can start now. Alternative: wait for Figma designs, which pauses the phase |
| **A2** | **Route space** (DR-BZ-27) | A separate `MB-nnn` namespace with its own route builder and its own audit test; the 108-screen audit is untouched | Keeps the original 108 exact. Alternative: extend to M-109 onward and change the 108 assertions |
| **A3** | **Entry points** | A fourth **"Businesses"** tile on the Home hub (where the page already promises "more approved services"), and **"My businesses"** and **"Join a business"** on Profile; the bottom bar is unchanged | No new tab. Alternative: a sixth bottom-bar item or an Explore segment |
| **A4** | **Scope and order** | All of D1–D4 as above, in five focused pull requests: foundation (route namespace, models, repository, contract fixtures); discovery; customer inquiries and reviews; owner; staff | Alternative: ship discovery and customer first and hold owner and staff |
| **A5** | **Fixed lists the app needs, which the service leaves open** (inquiry subjects, report reasons, verification methods, evidence kinds, county values) | Approve the proposed lists below; the service only checks a pattern, so these become app policy | Without them the pickers cannot be built |
| **A6** | **Unavailable actions** | Hide anything the role cannot do; show one short explanatory row only for the two things an owner will look for and cannot do yet (contact change on a live profile, removing staff) | Alternative: hide those too |
| **A7** | **Copy** | The owner writes the public-field explainer (MB-009) and the review-basis wording; until then the screens use neutral, factual placeholders flagged in the code | Final wording is yours |
| **A8** | **Review edits** | Show edit and withdraw (the service allows both; no edit window is set) | Alternative: withdraw only until a window is chosen (DR-BZ-16) |

### Proposed fixed lists (A5, for approval; each is a proposal, not policy)

| List | Proposed values |
| --- | --- |
| Inquiry subjects | `order_question`, `opening_hours`, `price_question`, `availability`, `general_question` |
| Report reasons | `misleading`, `spam`, `abusive`, `personal_data`, `impersonation`, `other` |
| Verification methods | `manual_review` (the only method the service has exercised) |
| Evidence kinds | `registration_number`, `licence_number`, `tax_number`, `website_or_social_proof`, `note` |
| Counties (15) | `bomi`, `bong`, `gbarpolu`, `grand_bassa`, `grand_cape_mount`, `grand_gedeh`, `grand_kru`, `lofa`, `margibi`, `maryland`, `montserrado`, `nimba`, `river_cess`, `river_gee`, `sinoe` |

## 4. Implementation plan once approved

Reuse everything: `ApiClient` and `authenticatedRequest`, `LiveAccountRepository` and secure storage, `AppDependencies` (one new `LiveBusinessRepository`), typed models that reject drift as the creator repositories do, `kolo_components`, system states, form validation and error mapping. No second login, no second client, no separate app.

| PR | Content | Tests |
| --- | --- | --- |
| 1 Foundation | `MB` route namespace and audit, models with strict parsers, `LiveBusinessRepository` (all 44 app operations, exact request bodies), contract fixtures, dependency wiring, entry-point tiles | repository tests against `MockClient` for every operation; parser drift tests; route audit; existing 1,556-test suite unchanged |
| 2 Discovery | MB-001–009 | widget, navigation, offline, empty and failure tests; contact-reveal states |
| 3 Customer | MB-010–017 | exact-body tests (no owner, account or eligibility field is ever sent); held and removed states |
| 4 Owner | MB-020–033 | permission and fail-closed tests; one-time codes never persisted |
| 5 Staff | MB-040–044 | role-gated actions; revoked-access state; switcher |

Every PR runs `flutter analyze` and the full suite on the CI-pinned SDK 3.47.8, includes security and error-state tests, and ends with real-device acceptance recipes (written, not run; physical-device acceptance is Phase 11). Nothing is merged or deployed.

## 5. Not decided here
Final visual design (A1), notifications (DR-BZ-14), images (DR-BZ-20), sharing links (DR-BZ-28), step-up actions (DR-BZ-33), and every policy value the owner still owes (see the [owner decisions required](BIZ-Owner_Decisions_Required_PHASE6A.md)).

## 6. Owner decisions recorded (24 November 2026)

Answered by Mark Allen Gbalazeh in the Phase 6D working session, against this document as merged in PR #225 (`7fb3427`). Where an answer differs from the recommendation, the answer governs and the inventory below is amended to follow it.

| # | Decision | Owner's answer | Effect on this inventory |
| --- | --- | --- | --- |
| A1 | Design source | **Build from the design system** (recommended) | Every Business screen is labelled "implementation-led, not visually approved" in code, tests and the completion record. Visual approval stays open until designs or screenshot review |
| A2/A3 | Route space and entry points (DR-BZ-27) | **Extend the numbering from M-109 and add a new bottom-bar tab** (not the recommendation) | The `MB` namespace is **replaced by M-109 onward** (mapping below). The 108-screen assertions that bind the original catalog are kept for the catalog and the route range is extended; a sixth tab, **Businesses**, is added to the shell. The proposed Home tile and Profile entries were part of the declined option and are **not built**; "My businesses" and "Join a business" live inside the Businesses tab |
| A4 | Scope | **All of D1–D4**, five focused pull requests in order | as section 4 |
| A5 | Fixed lists | **Approved as proposed** | The lists in section 3 are app policy |
| A6 | Unavailable actions | **Approved as proposed** | Hide what a role cannot do; one explanatory row each for contact change on a live profile and removing staff |
| A7 | Copy | **Approved as proposed** | Neutral, flagged placeholder copy until the owner writes the public-field explainer and review-basis wording |
| A8 | Review edits | **Approved as proposed** | Edit and withdraw are both shown |

### Screen numbers (MB working IDs to route numbers)

| Group | Screens |
| --- | --- |
| D1 discovery | MB-001…009 → **M-109…M-117** |
| D2 customer | MB-010…017 → **M-118…M-125** |
| D3 owner | MB-020…033 → **M-126…M-139** |
| D4 staff | MB-040…044 → **M-140…M-144** |

These numbers do **not** appear in the Figma file or in the 108-entry design register, and the original 108 are still the creator-content set. The coverage register gains a separate "Business (M-109–M-144), implementation-led" section when the screens land.
