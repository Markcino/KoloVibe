# P1-02 — Gateway role and MFA matrix for privileged routes

**Type:** regression guard (test only; no production code changed). **Baseline reference:** Phase 0 risk R-02, backlog B-03.

## Issue examined
Phase 0 found only positive-path evidence for privileged routes. Role rules are tested inside each owning service, but nothing proved at the gateway that every privileged route refuses a viewer, creator, or privileged caller without fresh MFA *before* anything is forwarded, or that a new privileged route cannot forward unauthorised callers.

## Method
`scripts/probe_gateway_roles.py` runs the gateway (local profile, no network) with Identity simulated for six callers (viewer, creator, moderator with/without MFA, administrator with/without MFA) and sends every method to every route with a bearer token. Business-service calls are replaced by a recorder.

`scripts/test_gateway_role_matrix.py` asserts, over the 24 privileged routes (`/admin/*`, `/moderation/*`, `/creator-invitations`, `/creator-applications`, `/engagement/fraud-holds`):

1. every route gated by the gateway refuses viewer, creator, and moderator/administrator without MFA (401/403/404/405) and makes zero business-service calls;
2. positive control: a moderator (administrator for the two administrator-only routes) with MFA gets past the gateway, so the refusals are not a dead route;
3. administrator-only assignment routes refuse a moderator even with MFA;
4. only six listed routes may forward a viewer or creator. Those delegate the role decision to the owning service (Identity for moderator invitations and account lookup, Creators for creator onboarding), each of which has its own role tests (`test_account_lookup.py`, `test_moderator_invitations.py`, `test_onboarding.py::test_denies_unauthorized_review...`).

## Result
No defect found at HEAD `bb79e1a`. Mutation check: removing the MFA requirement in `admin_reads.principal` fails the matrix on audit, assignments and other gated routes; reverted.

## Observation (not changed)
The six delegated routes validate the request body before the role check at the gateway (a viewer with an invalid body gets 400, with a valid body is forwarded and refused by the owning service). Nothing is disclosed either way, but a gateway-side role pre-check would give uniform defence in depth. Candidate hardening, not done here because it changes response codes for unauthorised callers (API compatibility).
