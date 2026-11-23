# P1-01 — Gateway routes are default-deny against DOC-205

**Type:** regression guard (test only; no production code changed). **Baseline reference:** Phase 0 risk R-02, backlog B-02.

## Issue examined
Authorization at the gateway edge was verified route by route in individual tests, but nothing proved that *every* route rejects a credential-less caller, that no route reaches an internal service before authentication, or that a newly added route is declared in the API contract.

## Method
`scripts/probe_gateway_anonymous.py` runs the gateway (local profile, every capability on, no network or database) and sends GET, POST, PUT, PATCH and DELETE with no credential to every registered route. Every outbound internal-service call is replaced with a recorder, so the output shows the status and whether anything internal was contacted.

`scripts/test_gateway_route_contract.py` derives the permitted anonymous operations from DOC-205 itself (`security: []`) and asserts:

1. every gateway route is declared in DOC-205, apart from three documented exemptions;
2. every DOC-205 path (except `/health/ready`) is served;
3. every operation not declared anonymous answers 401, 404 or 405 to a credential-less caller and makes **zero** internal calls;
4. each protected route answers 401 on at least one declared method;
5. the anonymous list is exactly the 18 declared operations, so widening it is a visible change.

## Result
No bypass found at HEAD `bb79e1a`: all 81 registered routes behave as declared. The mutation check (temporarily adding an undeclared, unauthenticated route) fails four assertions, as intended.

## Observations (not changed, API compatibility)
- `GET /videos` is a legacy unprefixed alias of `GET /api/v1/videos`, undeclared in DOC-205 and listed in the staging public allowlist (`staging_runtime/middleware.py`). It is exempted in the test with that reason. Removing it needs an owner compatibility decision.
- `POST /auth/logout` is declared anonymous in DOC-205 but answers 401 without a bearer token.

## Not covered
Role (administrator, moderator, creator) and object-level checks happen in the owning services and are the subject of P1-02. Positive journeys are covered by existing suites.
