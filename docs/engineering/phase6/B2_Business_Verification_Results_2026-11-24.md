# Phase 6B · B2 — business verification: results

Date: 24 November 2026. Local, disposable environments only. Builds on B1; no staging, AWS or live deployment. Not independent assurance.

## Implemented

| Capability | Operation(s) | Control summary |
| --- | --- | --- |
| Verification request | `POST /me/businesses/{id}/verification` | owner only (staff and foreign ids 404); declaration required; 1 to 5 text evidence items; one open case; throttled 5/day; idempotent; audited |
| Evidence handling (text only) | same, plus `POST …/verification/evidence` to answer a request for information | evidence is bounded private text (kind code + value ≤ 300), never returned to the public or to staff; stored per case |
| Verification status | `GET …/verification` | owner only; state, times and reason code only (reviewer notes are never exposed) |
| Reviewer grants | `PUT /admin/business-reviewer-grants` | administrator + MFA; scope `verification` or `review_queue`; optional target business; never for self; upsert |
| Reviewer queue and case | `GET /moderation/business-verifications[/{case}]` | moderator or administrator with MFA **and** an active grant covering that business; case outside the grant, or one the reviewer submitted or is affiliated with, is a 404 identical to an unknown id; each read audited |
| Claim and decision | `POST …/claim`, `POST …/decision` | claim required before deciding; decisions `verify`, `reject`, `request_info`, `revoke`; reason code required; idempotent (key + payload digest); one decision per case under concurrency |
| Revocation | decision `revoke` on a verified case | allowed by the approved design (BZ-R-006); business becomes `revoked` and may resubmit |
| Duplicate and look-alike flag | computed at submission | normalised name match across businesses; shown to the assigned reviewer; never auto-rejects |

All state changes go through one transition table (`verification.move`); no code path sets a business to verified without a decision row. Reused: B1 dispatcher, idempotency, throttling, audit outbox, authz module (grant checks live there), Gateway `principal()` MFA gate, DOC-205 route-contract and role-matrix tests (both pass with the new routes).

## Verification run

| Check | Result |
| --- | --- |
| Business service tests (SQLite) | 79 passed, 1 skipped (existing PostgreSQL-only) — B2 adds 18 |
| Permission and negative tests | reviewer routes refused for viewer, creator, moderator without MFA and administrator without MFA on all four reviewer operations; no-grant reviewers get indistinguishable 404 and cause no state change; grant for another business ineffective; conflict-of-interest (submitter, creator) blocked on read, claim and decide; foreign owners 404 on submit, respond and status; banned-field and bound tests; idempotency conflict |
| Audit contract test | every kind the Business service can emit is accepted by Audit's producer list (guards against the two lists drifting) |
| DOC-205 after merge (7 more operations) | valid OpenAPI 3.1; route-contract (6) and role-matrix (5) tests pass |
| Disposable TLS PostgreSQL 16 | foundations suite passes for all 9 services; `test_business_postgres.py`: 6 passed including a claim race (exactly one of four concurrent claims wins; three conflict) and a decision race (exactly one of four concurrent decisions is recorded) |

## Migration plan

`business/0003_verification` creates four tables and two constraints: one open case per business and a case-state check (partial unique index). Additive, no data migration. Audit gains eight Business kinds (code only; no migration beyond B1's). Apply to disposable databases only.

## Open items and deviations

1. **File evidence is not implemented.** It needs the owner's evidence checklist (DR-BZ-04/19) and approved private storage plus a scanning step; no live R2 is available here. B2 ships text evidence only and the contract says so.
2. **Policy not encoded:** accepted methods, evidence kinds and reason-code vocabularies are free codes (`[a-z_]{3,40}`); validity period and **re-review/expiry are not implemented** (no approved period). Revocation is.
3. The minimum of one evidence item is a technical floor (a case must carry something), not an approved checklist rule.
4. An administrator cannot grant themselves, so a first reviewer grant needs two privileged accounts (one administrator plus one moderator or second administrator).
5. Suspension and restoration (DR-BZ-25) are not in B2's scope list and are not built; B4 treats only `verified` as listable.
