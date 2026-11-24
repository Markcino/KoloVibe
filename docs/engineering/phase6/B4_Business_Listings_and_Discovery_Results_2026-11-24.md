# Phase 6B · B4 — listings and discovery: results

Date: 24 November 2026. Local, disposable environments only. Builds on B1 to B3. Not independent assurance.

## Implemented

| Capability | Operation | Control summary |
| --- | --- | --- |
| Create / update / remove listing | `POST …/listing/publish`, `…/listing/unpublish`; refreshes automatically on profile approval, hours change and verification decisions | owner only (staff and strangers 404); publish succeeds only while the **single eligibility predicate** holds (verified + approved profile with category, county, city), otherwise 409 `not_eligible` with non-sensitive reason codes; throttled; idempotent; audited |
| Listing status | `GET …/listing` | owner or staff; listed, intent, eligible, reasons |
| Public read model | `business_listing` table | public columns only (schema test pins the column set); a row exists exactly while the business is eligible **and** the owner wants it; written in the same transaction as the change; `reconcile_listings` command reports and repairs drift |
| Search, category, location filter, pagination | `GET /businesses` | `q`, `category`, `county`, `city`, `open_now`, `verified`, `sort`; unknown or malformed parameters rejected (400); keyset pagination with an HMAC-signed cursor bound to the filters it was issued for; page size ≤ 20; wildcards and SQL-like input treated as literal text |
| Detail | `GET /businesses/{id}` | unknown, unlisted, revoked and closed are the same 404; no `legal_name`, private contacts or address unless opted in |
| Public and private visibility | field-level flags from B3 plus the projection | contacts go only to signed-in verified-email accounts within a 100/day reveal budget; anonymous callers get `contacts: null` with a reason |
| Categories | `GET /business-categories` | now public (anonymous allowed), flag `business_discovery` |

Gateway: new capability `business_discovery` (closed by default); **public routes treat a missing credential as anonymous but never downgrade a present, invalid one** (401); one live Identity call supplies the verified-email flag; the trusted client address is forwarded only when the edge vouches for it, and anonymous reads are throttled per account or per address. The three public operations are added to the route-contract test's pinned anonymous list on purpose.

## Verification run

| Check | Result |
| --- | --- |
| Business tests (SQLite) | 117 passed, 1 skipped (existing) — B4 adds 20 |
| Negative and permission tests | non-owner publish/unpublish 404; ineligible publish refused; revocation removes the listing in the same request; pending or rejected revisions never visible; private-field absence on the public body; anonymous envelope rules (nil actor only for `anonymous`, no MFA/email flags); throttle isolation by address; tampered, truncated, extended, wrong-filter cursors rejected; 15 malformed query shapes rejected; scan cap yields a resumable cursor |
| Gateway Business tests | 14 passed (adds anonymous, invalid-credential, verified-flag, trusted-address and bounds tests) |
| DOC-205 (+5 operations, one changed to public) | valid OpenAPI 3.1; route-contract (6) and role-matrix (5) tests pass with the new anonymous list |
| Disposable TLS PostgreSQL 16 | foundations suite passes for 9 services; `test_business_postgres.py`: 9 passed, adding paging through 8 listings in order with no gaps or duplicates, `%` as a literal, and an injection-shaped query returning nothing |
| Audit contract | new kinds accepted by Audit's list (test guards drift) |

## Migration plan

`business/0005_listings`: adds `business.owner_listed` and the `business_listing` table (two indexes). Additive. Disposable databases only. Rollout order when approved: migrate, run `reconcile_listings --apply` once, then open `business_discovery` last.

## Open items and deviations

1. **Search engine.** The approved ADR proposed PostgreSQL full-text and trigram indexes. B4 uses portable case-insensitive substring matching with two relevance tiers (name match, then other fields) because local development runs on SQLite, the least-privilege role cannot create the trigram extension, and no data volume justifies the index yet. The query is bounded and tested on PostgreSQL; an index migration is a measured follow-up.
2. **Coordinates are not exposed publicly** and there is no distance filter (DR-BZ-13). Public coordinate precision was never decided; the owner's flag exists but is not used.
3. **"Location filtering"** is county and city equality. County values are not validated against a list (owner-supplied, DR-BZ-10).
4. **Suspension and closure** (DR-BZ-25) are not built; listings leave on revocation, unpublish or profile ineligibility only.
5. **No caching** is introduced, so takedown is immediate; any edge cache needs an approved maximum age.
6. Contact-reveal and public-read limits are initial values in `limits.py`.
