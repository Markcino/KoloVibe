# Phase 6C — Business administrator and moderator dashboard: results

**Date:** 24 November 2026. **Base:** `main` at `01b73e2` (Phases 5F, 6A and 6B merged). **Scope:** `apps/web_django` plus one Gateway validator fix. Repository changes only: no AWS or staging action, no migration, no deployment, no staging UAT. Production is NO-GO and every Business capability flag stays closed, so nothing here is reachable in any deployed environment.

**Architecture held (DR-BZ-21):** the existing protected console was *extended*, not replaced. Only administrators and moderators can open any page below. There is no public website and no page for business owners, staff or customers; those workflows stay in Flutter and are not touched.

## 1. What was found first
1. **All 13 Business reviewer and administrator operations already had approved backend contracts** (DOC-205, Phase 6B) and the console used none of them. Those 13 are exactly what this phase wires; nothing else was invented.
2. **A real integration defect:** the Gateway's and the console's audit-page validators listed the audit producers *without* `business`, so the first Business audit event would have turned the whole audit page into a 503. Fixed in both (they are drift-guarded to stay identical) with a Gateway regression test; the audit page also now offers the `business` producer filter.
3. **No backend exists for several requested items** (section 4). Per the instruction ("do not implement powers without approved backend contracts") they are not built and are stated on the overview page so no one assumes they exist.

## 2. Route inventory

All routes are under `/admin/business/`, behind `views.privileged` (active privileged role, fresh MFA, live session validation, 15-minute absolute and 30-minute idle limits, `no-store`). "Both" means moderator and administrator; a moderator sees only what the Business service's reviewer grants cover.

| Route name | Path | Methods | Who | Gateway operations used | Changes state |
| --- | --- | --- | --- | --- | --- |
| `business` | `/admin/business/` | GET | both | the three queue reads, in parallel | no |
| `business-verifications` | `/admin/business/verifications/` | GET | both | `GET /moderation/business-verifications` | no |
| `business-verifications-detail` | `…/verifications/{id}/` | GET, POST | both | `GET …/{id}`, `POST …/{id}/claim`, `POST …/{id}/decision` | claim, decision |
| `business-profiles` | `/admin/business/profiles/` | GET | both | `GET /moderation/business-profile-revisions` | no |
| `business-profiles-detail` | `…/profiles/{id}/` | GET, POST | both | `GET …/{id}`, `POST …/{id}/decision` | decision |
| `business-reports` | `/admin/business/reports/` | GET | both | `GET /moderation/business-reports` | no |
| `business-reports-detail` | `…/reports/{id}/` | GET, POST | both | `GET …/{id}`, `POST …/{id}/decision` | decision |
| `business-categories` | `/admin/business/categories/` | GET, POST | **administrator** | `GET /business-categories`, `PUT /admin/business-categories/{slug}` | upsert |
| `business-grants` | `/admin/business/access/` | GET, POST | **administrator** | moderator roster (existing), `POST /admin/accounts/lookup`, `PUT /admin/business-reviewer-grants`, `PUT /admin/business-registration-grants/{id}` | grant, revoke |
| `audit` (existing) | `/admin/audit/` | GET | existing rules | `GET /admin/audit?producer=business&kind=…` | no (now accepts the `business` producer) |

Console total after this phase: 40 routes, 31 privileged, **9 Business routes** (the 9 above `audit`). The 13 gateway operations are all covered: verification queue, case, claim, decision (4); profile queue, revision, decision (3); report queue, case, decision (3); reviewer grant, registration grant, category (3).

Also changed: sidebar entry "Business" (both roles), a section tab bar (administrator-only tabs hidden from moderators), the shared `account_lookup` helper (the creators page now uses it too, behaviour and copy unchanged), a Business icon.

## 3. Feature matrix against the instruction

| Item | Status | How |
| --- | --- | --- |
| **C1** Business administration navigation | **Done** | sidebar entry plus section tabs |
| C1 Scoped business lists | **Partial** | "Businesses needing attention": businesses with an item in the caller's authorised queues, from the queue answers only. **There is no backend operation that lists businesses**, so a full or status-filtered list is not possible |
| C1 Verification statuses | **Done** | status chips on the queue, claim state ("claimed by you"), full state on the case |
| C1 Review queues | **Done** | verification, profile revisions, business reports; cursor paging; find-by-id |
| C1 Filter and search tools | **Done, scoped** | business-name filter, "claimed by me", queue filter. They filter the page already loaded and say so; names never go to the gateway |
| C1 Safe operational summaries | **Done** | counts per queue (first page, "+" if more), oldest age, claimed-by-you, automatic holds |
| **C2** Pending applications; assigned reviewer queues | **Done** | verification queue with `assigned_to_you`; scope is the service's grants |
| C2 Authorised evidence inspection | **Done** | case page: legal name, text evidence, similar businesses. Opening it is audited by the service. Text evidence only; **file evidence does not exist** |
| C2 Approval, rejection, request for information | **Done** | claim, then verify / reject / request information; verify and reject need a confirmation step; revoke offered only for a verified case |
| C2 Decision history | **Not available** | no backend operation returns it. The case page links to the audit log (`business.verification_decided`); that is an administrator view with audit grants |
| C2 Audit evidence | **Done** | every read and decision is audited by the service; the console adds none of its own |
| **C3** Business reports (reviews, review responses, inquiry messages) | **Done** | queue, case with the reported content, keep or remove |
| C3 Listing complaints, impersonation reports | **Not available** | the backend accepts reports only on reviews, responses and messages |
| C3 Suspension and restoration | **Not available** | no backend operation (DR-BZ-25 inputs outstanding) |
| C3 Independent appeals | **Not available** | no backend operation |
| C3 Separation of duties | **Enforced by the service**, surfaced by the console | a reviewer cannot read or decide a case they submitted, created, belong to, or reported; the console shows the same 404 as an unknown item and decides nothing itself |
| **C4** Business status review | **Partial** | state visible on each item; no status list (see C1) |
| C4 Category administration | **Done** (administrator) | list active categories, create, rename, reparent, deactivate; inactive ones reactivated by slug |
| C4 Reviewer and registration access | **Done** (administrator) | grant or revoke reviewer scope per business or for all; invite or remove registration access; self-grant refused by the service. **Existing grants cannot be listed** (no operation) |
| C4 Staff and ownership dispute review | **Not available** | disputes are not built in the backend |
| C4 Verification audit history; business-related audit queries | **Done** | audit page now accepts the `business` producer and offers the filter |
| C4 Moderation metrics | **Not available** | no backend operation |

Panels on the overview page state the unavailable items plainly. Nothing is mocked or simulated.

## 4. Security design as built

| Requirement | How it is enforced |
| --- | --- |
| Active administrator or moderator, MFA, current session | the existing `privileged` guard on every route; validated against Identity on each request; idle and age limits |
| Reviewer assignment scope; object authorization; cross-business | **only the Business service decides** (grants, conflicts of interest, 404 for out-of-scope). The console fetches the item before rendering any action and the service re-decides on every POST |
| Administrator-only functions | categories and access pages refuse a moderator in the console before any gateway call, and the gateway and service refuse again |
| CSRF | Django CSRF on every POST; plus a signed per-form intent |
| Intent | signed, expires after 15 minutes, bound to the actor, the session, the one item and the one operation; carries the idempotency key. A decision intent cannot claim, a claim intent cannot decide, another item's or another session's intent is refused |
| Decision idempotency | the key travels as the `Idempotency-Key` header; re-submitting the same form re-sends the same key and body, so the service replays rather than applies twice; a changed body under the same key is a 409 shown as fixed copy |
| Never from frontend-only state | decisions are chosen from the service's current answer, then re-validated server-side; the POST accepts only a fixed field set (an unknown or duplicated field is a 400), and the console never forwards a state, role or reviewer field |
| Strict input | reason code `[a-z][a-z_]{2,39}`, note ≤ 500 characters without control characters, ids as UUIDs, cursors as UUIDs, search text ≤ 80 characters |
| Never trust a gateway body | exact validators for every response (`business_contracts.py`); an extra field, wrong type, wrong id or a result that does not match the requested decision fails closed (503), never "success" |
| Never echo the gateway | refusals are fixed copy; known business codes (claim required, invalid transition, idempotency conflict, self-grant, depth) get specific fixed advice |
| No sensitive data in browser logs or URLs | URLs carry only ids and the user's own filter text; no evidence, legal name or reason in any URL; no logging added (a test asserts a successful decision logs nothing at INFO); `no-store`; `same-origin` referrer policy |
| Safe rendering | Django auto-escaping only; a test forbids `|safe`, `mark_safe`, `autoescape off` in the Business templates and modules; hostile markup in names, evidence, descriptions and report text renders escaped |

## 5. Security test results (local, mocked gateway)

| Check from the instruction | Evidence |
| --- | --- |
| Anonymous denial | route matrix: every privileged route, all methods, sent to login with no gateway call (the 9 new routes included) |
| Viewer / creator denial | matrix: a non-privileged account is refused on every privileged route before any business call |
| Moderator scope | moderator sees review pages and an empty state when nothing is in scope; categories and access refuse a moderator (403, zero gateway calls); out-of-scope item = same 404 page as an unknown item |
| Administrator-only operations | matrix (console-checked set) plus dedicated tests for categories and both grant types |
| MFA failure | matrix: session whose MFA flag is not true is refused on every route; password-only sign-in reaches nothing |
| CSRF rejection | matrix: every state-changing Business route refuses a POST with no token or another session's token before any gateway call |
| Cross-business access | gateway 404 renders the generic page without the item; a response for a different item id is never rendered (503) |
| Decision replay | same intent re-posted: same key and body both times; changed body: 409 copy; forged, foreign-item, foreign-session, wrong-operation, expired (real time travel: valid at 14 minutes, refused at 16) and missing intents refused with no gateway call |
| Expired sessions | matrix: idle (31 min) and over-age (16 min) sessions refused on every route; a 401 mid-flow signs out |
| Invalid input | 13 verification decision variants, 8 category variants, grant and lookup variants, queue parameters, duplicated fields: all 400 before any gateway call |
| Safe rendering | hostile strings on all three item pages and the profile page; static ban on unescaped output |

**Results:** console suite **174 pass** (was 138): 35 new Business tests, 1 structure test, matrix extended. Gateway 221 (+3), Business service 178, Audit 51, script suite 446, `manage.py check` clean, no model or migration change. The new accessibility checks render all ten new pages and a test proves they are the real pages, not error pages.

**Mutation checks (each control removed, a test must fail):** intent binding, intent lifetime, administrator-only gate on categories, decision response validation, confirmation step, idempotency key, note control characters, unknown POST fields, cursor validation, reason-code validation, evidence escaping, queue shape validation, case-id match, registration-account binding: **14 of 14 caught.** The first run missed two (the lifetime, because the test overrode the constant; the key, because the fake gateway never required one). Both were test gaps; the fake now rejects any mutating call without a valid key and expiry is tested with real time travel.

## 6. Not done and why
- **Not built, no approved backend contract:** suspension and restoration, appeals, listing and impersonation complaints, ownership and staff disputes, moderation metrics, a business list or status endpoint, decision-history endpoint, evidence files. Each needs a backend contract and an owner decision first (see [owner decisions required](../../architecture/business/BIZ-Owner_Decisions_Required_PHASE6A.md)).
- **Not run:** staging, a browser, a screen reader, keyboard walk-through at real widths, devices. Accessibility is static checks only. The tests use a recording fake of the gateway and were written with the code; they are not independent assurance.
- **Operational prerequisites before anyone can use these pages:** the five Business capability flags must be opened by an owner-approved release record (they are closed), an administrator needs Audit read access to the `business` producer, and reviewers need grants created through the Access page (a first grant needs two privileged accounts, since an administrator cannot grant themselves).

## 7. Prerequisites for the next phase
Owner decisions for the not-built items above; DR-BZ-27 designs before any Flutter work; DR-BZ-32 and DR-BZ-33 before any enablement. Phase 11 owns browser, device and screen-reader acceptance.
