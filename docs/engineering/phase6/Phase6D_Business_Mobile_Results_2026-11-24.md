# Phase 6D — Flutter Business experience: results

**Date:** 24 November 2026. **Base:** `main` at `01b73e2` plus the Phase 6D approval-request commits. **Scope:** `apps/mobile` (Flutter), plus one Business-service test that captures contract fixtures. Repository changes only: no AWS or staging action, no migration, no backend behaviour change, no deployment. Every Business capability flag is still closed and production is NO-GO, so nothing here is reachable in any deployed environment.

**Architecture held (DR-BZ-21):** owners, staff and customers use the one Flutter app. There is no business website, no second login flow and no second app. The creator-content app (the 108 designed screens, Points, moderation, settings) is untouched except that the bottom bar gained a sixth tab.

> **Not visually approved.** No Figma design for any Business screen exists. By the owner's decision A1 (24 November 2026) every screen below was **built from the design system** (the existing components, tokens, fonts and system states) and is **implementation-led, not visually approved**. It is not a claim that the original 108 creator-content screens include Business screens. Visual approval, the public-field explainer wording and the review-basis wording remain with the owner.

## 1. Owner decisions that shaped the work

| # | Decision (24 November 2026) | Effect |
| --- | --- | --- |
| A1 | Build from the design system | All 36 screens are labelled implementation-led |
| A2/A3 | Route numbers from M-109 and a new bottom-bar tab | Business is **M-109 to M-144**; the shell has six tabs (Home, Explore, Create, Videos, Profile, **Businesses**) |
| A4 | All of D1 to D4 | Delivered |
| A5 | Fixed lists approved as proposed | Inquiry subjects, report reasons, verification method (`manual_review`), evidence kinds and the 15 counties are app policy in `business_lists.dart` |
| A6 | Hide what a role cannot do; one explanatory row each for the two refused actions | Contact change on a live profile (M-130) and staff removal (M-139) show one row and no control |
| A7 | Neutral, flagged placeholder copy | Reviewer reason codes and review-basis labels are shown plainly, not styled as policy |
| A8 | Show review edit and withdraw | M-123 and M-124 |

## 2. Screen inventory and implementation matrix

All screens: native Flutter in `apps/mobile/lib/features/business/`, on the shared page frame (`BusinessPage`), the existing design tokens and components, and the shared system states (loading, offline, rate limited, not found, session expired). A screen is **built** only when it shows real service data and every action it offers works against the repository; the tests below prove that against real captured service responses.

| M-no | Screen | Who | Service operations | States covered | Tests |
| --- | --- | --- | --- | --- | --- |
| 109 | Businesses home | anyone | categories, search | loading, empty, per-section failure | discovery |
| 110 | Categories | anyone | categories | empty, offline then retry | discovery |
| 111 | Results | anyone | search (paged) | empty, next-page failure, rate limited, hostile text | discovery, audit |
| 112 | Filters | anyone | categories | reset, returns a validated value | discovery |
| 113 | Business detail | anyone | detail | not found, invalid id, rating average only when sent | discovery |
| 114 | Opening hours | anyone | detail (reused) | hours not published is never "closed" | discovery |
| 115 | Contact details | signed-in, verified email | detail (reused) | all five reveal states, copy only | discovery |
| 116 | Reviews | anyone | reviews (paged) | empty, failure, owner reply, report | discovery |
| 117 | What you can see here | anyone | none | static | discovery |
| 118 | Ask a question | customer | ask | validation, retry key, existing thread, expired, offline, unverified email, double tap | customer |
| 119 | My questions | customer | my inquiries | empty, expired | customer |
| 120 | Conversation | customer | inquiry, message, close, confirm | removed message, closed, confirm keeps messages | customer |
| 121 | Write a review | customer | write review | proof is conversation or code never both, held, already reviewed | customer |
| 122 | My reviews | customer | my reviews | held, removed, withdrawn, no edit when not active | customer |
| 123 | Edit review | customer | my reviews (lookup), edit | only changed fields sent, not editable | customer |
| 124 | Withdraw review | customer | my reviews (lookup), withdraw | asks first | customer |
| 125 | Report | customer, owner | report | reason required, already reported, own content | customer |
| 126 | My businesses | owner, staff | my businesses | empty, expired, remembers choice | owner |
| 127 | Register a business | invited account | register | **invitation-required state**, limit, validation | owner |
| 128 | Manage business | owner (staff see staff rows) | business, listing | owner and staff rows, access removed | owner, staff |
| 129 | Business details | owner | profile, categories, edit profile | only changed fields, pending review | owner |
| 130 | Contact details | owner | profile, edit profile | **locked on a live profile**, https only | owner |
| 131 | Opening hours | owner, staff | profile, replace hours | order, date, empty set | owner |
| 132 | Profile review | owner | profile, submit | draft, pending, rejected reason | owner |
| 133 | Verification | owner | status, submit, answer | declaration, text evidence only, needs info, rejected | owner |
| 134 | Listing | owner | listing, publish, unpublish | ineligible reasons, asks before hiding | owner |
| 135 | Inbox | owner, staff | inbox | empty, blocked shown as closed | inbox |
| 136 | Inbox conversation | owner, staff | thread, reply, close, confirm, block | **block owner-only**, block never disclosed | inbox |
| 137 | Reviews and replies | owner | reviews, respond, delete response | no hide/edit control exists, reply removed by reviewers | inbox |
| 138 | Review invitations | owner | create, revoke | code shown once, fresh key each time | inbox |
| 139 | Team | owner | members, invite, revoke invitation | code shown once, **no remove control** | inbox |
| 140 | Join a business team | invited person | redeem | one answer for any bad code, hidden code field | staff |
| 141 | Switch business | owner, staff | my businesses | remembered business no longer listed, paging | staff |
| 142 | Access removed | anyone | none | state only | staff |
| 143 | Leave business | staff | business, leave | asks first, owner told they cannot leave | staff |
| 144 | Staff home | staff | business | staff rows only, no owner reads | staff |

Test files: `business_discovery_screens_test`, `business_customer_screens_test`, `business_owner_screens_test`, `business_inbox_screens_test`, `business_staff_screens_test`, `business_routes_test`, `business_layout_audit_test`.

## 3. Service operations integrated (44 app-facing, 43 integrated)

Every operation goes through `LiveBusinessRepository` over the existing `ApiClient` and `LiveAccountRepository.authenticatedRequest` (refresh rotation, secure storage, sign-out unchanged). The four public reads send no credential unless a session exists.

| Operation | Repository method | Screens |
| --- | --- | --- |
| GET /business-categories | `categories` | 109, 110, 112, 129 |
| GET /businesses | `search` | 109, 111 |
| GET /businesses/{id} | `detail`, `detailCached` | 113, 114, 115, 118, 121 |
| GET /businesses/{id}/reviews | `reviews` | 116, 137 |
| POST /businesses/{id}/inquiries | `ask` | 118 |
| GET /me/inquiries | `myInquiries` | 119 |
| GET /me/inquiries/{id} | `inquiry` | 120 |
| POST /me/inquiries/{id}/messages, /close, /confirm | `sendMessage`, `closeInquiry`, `confirmInquiry` | 120 |
| POST /businesses/{id}/reviews | `writeReview` | 121 |
| GET /me/reviews | `myReviews`, `findOwnReview` | 122, 123, 124 |
| PATCH /me/reviews/{id} | `editReview` | 123 |
| DELETE /me/reviews/{id} | `withdrawReview` | 124 |
| POST /business-reports | `report` | 125 |
| GET /me/businesses | `myBusinesses` | 126, 141 |
| POST /me/businesses | `register` | 127 |
| GET /me/businesses/{id} | `business` | 128, 136, 143, 144 |
| GET, PATCH /me/businesses/{id}/profile | `profile`, `editProfile` | 129, 130, 131, 132 |
| POST …/profile/submit | `submitProfile` | 132 |
| PUT …/hours | `replaceHours` | 131 |
| GET, POST …/verification; POST …/verification/evidence | `verificationStatus`, `submitVerification`, `respondToVerification` | 133 |
| GET …/listing; POST …/listing/publish, /unpublish | `listingStatus`, `publish`, `unpublish` | 128, 134 |
| GET …/inquiries, …/inquiries/{id} | `inbox`, `inboxThread` | 135, 136 |
| POST …/inquiries/{id}/messages, /close, /confirm, /block | `reply`, `closeThread`, `confirmThread`, `blockCustomer` | 136 |
| PUT, DELETE …/reviews/{id}/response | `respondToReview`, `deleteResponse` | 137 |
| POST, DELETE …/review-invitations[/{id}] | `createReviewInvitation`, `revokeReviewInvitation` | 138 |
| GET …/members | `team` | 139 |
| POST, DELETE …/members/invitations[/{id}] | `inviteStaff`, `revokeInvitation` | 139 |
| POST /me/business-invitations/redeem | `redeem` | 140 |
| POST …/leave | `leave` | 143 |
| **DELETE …/members/{id}** | **not integrated, on purpose** | none |

The one operation left out removes a staff member. The service refuses it for every caller until the step-up proof exists (P6B-04, DR-BZ-33), so the app shows no control and one explanatory row on M-139. A guard test (`live_business_repository_test`) compares the repository with the committed list of the 44 contract operations and fails if one is added, removed or missed. The Business-service test regenerates that list from DOC-205 and fails when the contract changes.

The 13 reviewer and administrator operations stay in the console (Phase 6C) and are not in the app.

## 4. Security and authorization

The app never decides ownership, eligibility, role, state, listing visibility, "verified", "open now" or the rating average. The service decides each, and the tests prove the app does not send them.

| Requirement | How it holds |
| --- | --- |
| No client-selected ownership or role | No request body contains an account, owner, role, state, verified, listed, eligible or basis field (tested for every body). A business id comes from the service's own list or from the route and the service re-checks it. The remembered business (`BusinessContext`) is a device convenience only |
| Review eligibility not client-decided | `writeReview` sends only the proof the customer holds (a conversation id or an invitation code, never both); the service derives the basis |
| Owner-only actions hidden from staff, and re-enforced | M-128/M-144 show owner rows only when the service says the role is owner; staff never ask for the listing or the verification; Block is owner-only. Every call is checked again by the service, and a refusal is shown as a plain state |
| Permission revoked | A business the service answers 404 or 403 for shows the access-removed state, forgets the remembered choice and offers another; a service outage is **not** treated as lost access |
| One-time codes (staff invitation, review invitation) | Held in memory only while their screen is open, wiped on Done or leaving, never stored or logged (`OneTimeCode` prints as hidden). Each request gets a fresh key because the service cannot replay a code. The staff invitation code is typed in a hidden field and wiped with the screen |
| Idempotency | One key per attempt: a retry re-sends the key, changed content gets a new one, a busy guard stops a second send |
| Strict parsing | Every answer is parsed with exact keys and ranges; an unknown key, a wrong type, contacts disclosed without access, a message that is both removed and has text, or a role/legal-name mismatch is refused |
| No links leave the app | Contact values are copy-only; the app opens no call, email or web link (DR-BZ-28 is open) |
| Plain text only | Business text is always drawn as plain `Text`; hostile markup renders literally (tested) |
| No second login | Sign-in is the existing M-004 with a return screen |
| A block is never disclosed | The owner's inbox shows a blocked conversation as "Closed"; the customer sees "Closed" |

## 5. Test evidence

| Check | Result |
| --- | --- |
| `flutter analyze` | No issues |
| `flutter test` (all suites) | **1,823 passed** (1,556 before Phase 6D: +267) |
| Business service (`manage.py test`) | 181 passed, 1 skipped (includes the three fixture tests) |
| `scripts/check_mobile_design.py` | 108 entries, valid (the catalog is unchanged; Business screens are outside it) |
| Layout audit | All 36 screens render at 390×844 and 375×667, at 1× and 2× text, with no exception, placeholder, error page or not-found page |

**Contract fixtures.** `services/business/tests/test_mobile_fixtures.py` runs the real Business service handlers and writes 47 response fixtures to `apps/mobile/test/fixtures/business/`. A drift test fails if any response's keys, value kinds or status change, and another fails if the app-facing operation list stops matching DOC-205. The Dart parsers and every screen test run against those files, so the app and the service cannot silently disagree. Fixtures contain no usable secret or address (a test forbids `@example`, `Bearer ` and `password`; one-time codes are replaced by a fixed placeholder).

**Mutation checks (a control is removed, a test must fail): 22 of 22 caught, after correcting two mutations that had not been applied.**

| Area | Controls checked |
| --- | --- |
| Shell | selected-tab rule for Business screens |
| Discovery | unknown hours shown as closed, county not validated, detail not reused, sign-in return dropped |
| Customer | busy guard, per-attempt key, edit sends every field, report reason not required, proof sent with code |
| Owner | staff see owner rows, contacts always editable, block shown to staff, code kept after Done, code request reuses a key, hide without asking |
| Staff | lost access not forgotten, outage mistaken for lost access, leave without asking, unlisted remembered business kept, code not hidden |
| Audit | the M-111 overflow reintroduced |

**Defects the tests found in my own work, and fixed:** a `setState` that returned a future (retry control crashed); an undecodable filter string crashed instead of being ignored (`ArgumentError`); close and confirm answers drop the message list, which blanked the conversation (both customer and inbox); a state badge beside the stars on the My reviews card overflowed at normal text size, and the M-111 Filters and Clear buttons overflowed at large text (the layout audit found the second); the same-key replay problem for one-time codes (no screen retries a code request with the same key); a second tap could send twice before a rebuild (busy guards added). One process slip: a commit was made while one test, whose expectation was now out of date, failed; the next commit corrected the test, and the suite was green before every later commit.

### 5a. What the 267 new Flutter tests cover

Repository against the real captured responses (95 including 46 security and validation cases), Business context (remembered choice per account, cleared on sign-out), routes and the six-tab bar (13), discovery screens (34), customer screens (37), owner screens (33), inbox, replies, invitations and team (24), staff screens (20), and the layout audit (4 runs of 36 screens each). The 1,556 earlier tests, including the 108-screen design audit, still pass.

## 6. Real-device acceptance recipes (written, not run)

Physical-device UAT is **deferred to Phase 11**. These recipes assume a staging build with the Business flags opened by an owner-approved release record, an account with a registration invitation, a second account, and one account per role. **None has been run.**

1. **Browse (anyone, signed out).** Open Businesses, search "bread", filter by category and county, open a business. Expect: hours, rating count, no contact values; the contact screen asks you to sign in.
2. **Contact reveal.** Sign in with an unverified email: the contact screen says to verify. Verify the email: contacts appear, tap one, confirm "Copied" and that no call or link opens. Repeat until the limit message appears.
3. **Question and reply.** As a customer ask "Opening hours"; as the owner see it in the inbox and reply; as the customer see the reply. Close the conversation as the owner; confirm the customer cannot send.
4. **Confirm and review.** Both sides tap "We dealt with each other"; the customer writes a review from the conversation; confirm it says "Interaction confirmed"; edit it, then withdraw it.
5. **Owner onboarding.** With an invited account register a business; without an invitation confirm the invitation-required state. Fill details and contacts, add hours, submit for review, submit verification with a registration number; confirm no file option exists.
6. **Console decision, then publish.** After a console reviewer approves, confirm the listing screen no longer lists reasons, show it in search, hide it again.
7. **Staff.** As owner make a staff invitation; confirm the code shows once and is gone after Done or leaving the screen. As a second account join with the code; confirm staff see only the inbox, hours and Leave; confirm Block is absent. Remove access in the data (or revoke by the owner when step-up exists) and confirm the access-removed state.
8. **Leave.** As staff leave the business; confirm the list updates and the owner cannot leave.
9. **Sizes.** Run 2 to 5 at the largest text size and on a 375-wide phone; confirm nothing is clipped; step through the main flow with VoiceOver.
10. **Offline and sign-out.** Turn on aeroplane mode on every screen type and confirm the offline state and retry; sign out and confirm the remembered business and any visible code are gone.

## 7. Not done, and why

- **No visual approval.** The screens are built from the design system only. Treat them as a working draft for the owner's visual review.
- **No device, screen-reader or real-service run.** Everything above is automated tests over captured responses. The fixtures come from the Business service handlers directly, not over HTTP through the Gateway, so Gateway pass-through, headers and throttling are not exercised here.
- **Sign-in returns to the screen, not to the item.** The existing route carries one return screen number, so after signing in from a Business screen the person lands on that screen type without the business, thread or review they were on.
- **My reviews shows no business name.** The contract's review answer has only a business id; the card offers "View business". Fetching names would use up the contact-reveal limit.
- **Owner replies cannot be reported from the app.** The public review answer does not carry the reply's id, which the report operation needs. Reviews and inquiry messages can be reported.
- **Not in the contract, so not built:** appeals, notifications, images, file evidence, map or coordinates, share links, closing a business, reporting a listing, ownership transfer, removing a staff member (refused by the service), contact change on a live profile (refused by the service).
- **Owed by the owner:** visual designs or review (DR-BZ-27), the public-field explainer and review-basis wording, the reviewer reason-code vocabulary (codes are shown as the service sends them), and a decision on whether any link may leave the app (DR-BZ-28).
- **Operational prerequisites before anyone can use it:** the five Business capability flags are closed; opening them needs an owner-approved release record, step-up (P6B-04) for the two refused actions, and Phase 11 device acceptance.
