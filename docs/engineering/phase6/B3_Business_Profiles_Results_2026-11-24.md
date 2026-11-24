# Phase 6B · B3 — business profiles: results

Date: 24 November 2026. Local, disposable environments only. Builds on B1 and B2. Not independent assurance.

## Implemented

| Capability | Operation | Control summary |
| --- | --- | --- |
| Name, description, category, location, contacts | `PATCH /me/businesses/{id}/profile` | owner only; edits a **working revision** created from the approved one; allowlist and bounds on every field; unknown fields and authority fields (state, verified, ids) rejected; throttled; idempotent; audited |
| Categories | `GET /business-categories`; `PUT /admin/business-categories/{slug}` | administrator-managed vocabulary, two levels at most, owners cannot create categories; inactive ones are not selectable |
| Contact details | inside the revision | kinds phone, email, website, social; websites and social links `https` only, no credentials, no `javascript:`; each channel **private unless the owner sets `is_public`** (DR-BZ-09) |
| Address and location | inside the revision | free address line and paired coordinates (fixed 6-decimal precision) private unless `address_public` / `coordinates_public` are set |
| Opening hours | `PUT …/hours` | owner or staff; non-overlapping intervals, `24:00` closing, dated exceptions, time zone validated against the zone database (default `Africa/Monrovia`); replace-all in one transaction; shared `is_open()` for B4 |
| Authorized editing and visibility | `POST …/profile/submit`; `GET …/profile` | the public will see only the last **approved** revision; `GET …/profile` shows owner and staff the approved, working and last rejected revision with the reason code and the list of changed fields |
| Review of material changes | `GET/POST /moderation/business-profile-revisions…` | new scope `profile_review` (a verification grant does not confer it); MFA moderator or administrator with an explicit grant; revision outside the grant, submitted by the reviewer, or of a business they are affiliated with is a 404; approve or reject with a reason code; idempotent; audited |

Rules applied as approved (DR-BZ-11): first submission and changes to display name, category, address line or contacts are **pre-moderated**; other changes apply on submit and stay reportable. A previous approved revision stays current until a new one is approved. Changing a live (approved) contact set needs step-up and **fails closed** until P6B-04 exists; contacts can be set freely before a first approval because nothing is live yet (my reading of the design, flagged below).

## Verification run

| Check | Result |
| --- | --- |
| Business tests (SQLite) | 97 passed, 1 skipped (existing PostgreSQL-only) — B3 adds 18 |
| Negative and permission tests | staff cannot edit or submit (404) but can read and set hours; strangers 404 on all five owner operations; mass-assignment and bound table (24 invalid payloads, nothing half-created); reviewer with only a verification grant refused; submitter blocked from deciding; role/MFA matrix; closed business refuses edits; live-contact change refused and leaves no draft |
| Hours | boundary tests: closing minute excluded, exception days, other time zones, unknown hours reported as unknown rather than closed |
| DOC-205 (+9 operations) | valid OpenAPI 3.1; route-contract (6) and role-matrix (5) tests pass; Gateway Business tests (9) pass, including "every operation is routed" |
| Disposable TLS PostgreSQL 16 | foundations suite passes for all 9 services; `test_business_postgres.py`: 8 passed (adds: four concurrent first edits create one revision; database refuses a second working revision, a duplicate revision number, half-set coordinates, weekday 9 and a zero-length interval) |
| Audit contract | all Business kinds accepted by Audit's producer list (test) |

## Migration plan

`business/0004_profiles`: six tables (categories, revisions, contacts, hours rules, hours exceptions) plus the widened reviewer-grant scope constraint. Additive. Apply to disposable databases only.

## Open items and deviations

1. **Images are not built** (DR-BZ-20: no images until the shared pipeline exists; the creator-photo pipeline is itself unbuilt). Uploads, decode/re-encode and quarantine are therefore not implemented or tested.
2. **Initial category list and county list** are owner-supplied (DR-BZ-10): no seed data is shipped; an administrator creates categories. County is a pattern-checked code, not a validated list.
3. **Which fields are material** is the owner's call; the register's own examples are in `limits.MATERIAL_FIELDS` for confirmation.
4. **Step-up** (P6B-04) is still missing; the only consequence in B3 is the live-contact rule above.
5. Public-field warning copy and the public view itself arrive with B4 and the owner's notice text.
