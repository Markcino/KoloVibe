# R1 Creator role synchronization

Repository fix, 21 November 2026. AWS deployment and physical iPhone acceptance remain pending.

The gateway previously approved Creator applications without updating Identity's viewer role.
`GET /api/v1/creators/me` correctly required the creator role, so approved viewers could not open Studio.

## Workflow

- After a successful approval, the gateway rechecks the target account's eligibility with Creator over the existing signed connection. The returned profile must match the reviewed application.
- Creator checks approval, current attestations, profile ownership, active status, review and absence of restrictions.
- The gateway attests that evidence to the private `POST /internal/auth/creator-role` Identity endpoint. This endpoint accepts only the authenticated gateway and only a viewer-to-creator transition for an active, verified, nonstaff account. Public callers cannot submit role or eligibility overrides.
- Identity locks the account and atomically grants the role, revokes all existing sessions and reauthentication proofs, and records `account.creator_role_granted` with its audit outbox delivery. An already-creator retry does not revoke new sessions or duplicate the event.
- If approval commits but synchronization fails, the review returns 503. Retrying the same decision completes synchronization. Existing drift also reconciles on an eligible viewer's eligibility or Studio GET, which then returns 401 requiring a fresh sign-in.
- Mobile reads live `/me` after a positive eligibility response and requires the server-confirmed creator role before presenting Studio access.

Studio's server role check, profile ownership checks and upload restrictions remain enforced. Role reconciliation does not grant publishing permission independently of Creator's current eligibility. A restriction arriving after eligibility was checked is still enforced by subsequent Creator/upload operations.

## Validation

Regression coverage includes approval orchestration and retry, rejection of ineligible or mismatched evidence, unapproved viewers, privileged/inactive/unverified accounts, session and reauthentication revocation, idempotency, audit ingestion, restricted profiles and the mobile `/me` refresh.

`scripts/verify_local_journeys.py` reproduces an approved application with a viewer Identity account in disposable TLS PostgreSQL. Real signed gateway-to-Creator/Identity calls must reconcile it, reject old refresh credentials, allow a fresh creator sign-in and return its owned profile. Restricting that fixture must then deny Studio and eligibility. This is local integration evidence, not AWS acceptance.

Local results on 21 November: all seven real-service journeys and 61 targeted mobile tests passed. Gateway (163 tests, 14 skipped), Creator (69, one skipped), Audit (40, one skipped) and Identity (114, one skipped) suites passed; the three focused Identity transition tests also passed, including audit-failure rollback added after the full suite started. The 36 staging-policy/runtime/service-identity checks passed. Flutter analysis and OpenAPI validation passed. Skips belong to existing service test gates and are not reported as acceptance passes.

## Staging continuation

Publish and deploy a reviewed release using the existing release process. Update Audit and Identity before Gateway so the new audit kind and private transition are available; include Creator's ownership validation and the mobile update. No new database migration, peer credential or Identity onboarding flag is required. The private transition requires the existing Identity account capability; approval routes retain their current onboarding and MFA gates.

Retain the Test User's application and profile. With the repaired services deployed, open Studio or check eligibility using that account. Expect one 401 if its viewer role is reconciled, then sign in again. Verify `/api/v1/me` reports `creator`, `/api/v1/creators/me` returns 200 with the correct owned profile, and eligibility is true. Confirm unapproved viewers and restricted accounts remain denied, then resume the iPhone upload journey. Verify the role-grant audit event reaches Audit.

No manual promotion of the Test User or production/staging database edit is part of this fix.
