# Phase 6B · B1 — business identity and ownership: results

Date: 24 November 2026. Branch `claude/blissful-archimedes-ztoqko` (Phase 6B pull request). Local, disposable environments only; **no staging, AWS, or live deployment**. Not independent security assurance.

## Implemented (backend)

New service `services/business` (own schema `business`, own role, gateway-only caller policy `/internal/probe` and `/internal/business/`), the Gateway routes behind closed capability flags, and Audit support for the new producer.

| Operation (gateway route) | Who | Notes |
| --- | --- | --- |
| `POST /me/businesses` register | verified-email viewer/creator with an active registration grant | atomic business + owner membership; idempotent; capped; throttled; audited |
| `GET /me/businesses`, `GET /me/businesses/{id}` | active member | scoped by authenticated actor; staff never receive `legal_name`; non-member = 404 identical to unknown id |
| `POST …/members/invitations` | owner | single-use 72 h code, shown once, only a keyed digest stored |
| `DELETE …/members/invitations/{id}` | owner | revoke pending |
| `POST /me/business-invitations/redeem` | verified customer | unknown/used/revoked/expired codes indistinguishable; throttled; cap enforced under lock |
| `GET …/members` | owner | no account ids exposed (owner-assigned labels only) |
| `POST …/leave` | staff | immediate; owners cannot leave |
| `DELETE …/members/{id}` | owner | **fails closed**: needs step-up (P6B-04, not available) |
| `PUT /admin/business-registration-grants/{account}` | administrator with MFA | not for self; audited |

Reused, not rewritten: Gateway `authenticated_actor` and `principal` (live session, MFA), `signed_internal_request`, the shared service-identity verifier/signer, Moderation's audit-outbox pattern, Identity's hashed-throttle pattern, Creators' cursor pagination. Business rules live only in the Business service; the Gateway authenticates, bounds, binds the actor and forwards.

## Verification run (all local)

| Check | Result |
| --- | --- |
| Business service tests (SQLite) | 60 passed, 1 skipped (existing PostgreSQL-only identity check) |
| Gateway Business tests | 9 passed |
| Audit tests incl. new producer | passed |
| Shared-identity drift test, structure check | pass (9 services) |
| Gateway route-contract and role-matrix tests with the new routes | pass (6 and 5 tests) |
| DOC-205 after merging 9 operations | valid OpenAPI 3.1 (`openapi-spec-validator`), additions only |
| Real TLS PostgreSQL 16 (disposable): migrations under the least-privilege role; cross-service SQL denied for `business` | pass (`test_postgres_foundations.py`) |
| PostgreSQL concurrency (`test_business_postgres.py`): 5 racing identical registrations → 1 business; racing distinct registrations cannot exceed the cap; one code redeemed once under 6-way race; DB refuses duplicate active membership and invalid role | 5 passed |
| Bandit (repository enforcement) | 0 medium/high |
| `makemigrations --check` for every service | clean |
| Whole `scripts/` suite | 446 tests, passing (one earlier failure was my own unpinned gunicorn install; passes pinned) |

Permission evidence: `tests/test_ownership.py` covers BZ-NT-01 to 04, 08 to 10 and 12 for the B1 operations (cross-business, nested ids, staff vs owner, revoked membership on next request, privileged roles refused, banned-field mass assignment, idempotency conflicts, strict envelope, wrong caller).

## Migration plan (B1)

`business/0001_initial` (8 tables) and `0002_internal_nonce` (raw table, same as other services); Audit `0006_business_producer` (alters a choices list and a check constraint). Applied only to disposable databases. Rollout order when approved: schema and role SQL (`schema_isolation.sql` now lists `business`), Audit migration, Business migrations, Gateway with flags closed.

## Deviations and open items

1. **Gateway response allowlists.** AC-CON-002 asked for exact response validators in the Gateway. That would copy the Business response schemas into a second place, which the Phase 6B DRY rule forbids. The Gateway instead returns only bounded JSON objects and bounded `{detail, code}` refusals; exact shapes are enforced and tested in the Business service.
2. **Step-up (P6B-04).** Not implemented in Identity (unapproved). Staff removal fails closed; owner contact change on a live business, closure and ownership transfer are not exposed.
3. **Registration fields.** The proposal required category and county at registration; no category or county lists exist yet (owner-supplied, DR-BZ-10), so B1 registration takes names only and B3 adds them to the profile revision.
4. **Account-age gate** (DR-BZ-03 "then A") is not implemented: the Gateway's session validation does not currently carry account creation time into the envelope.
5. **Not touched** (no live deployments): cluster, secrets-generation and staging stack tooling still list eight services; adding `business` there is deferred to an approved rollout.
6. Registration throttle counts retries (5 per day); a client retrying more than five times is throttled even when requests would replay.
