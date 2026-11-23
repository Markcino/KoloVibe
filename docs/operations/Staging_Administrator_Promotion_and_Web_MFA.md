# Staging administrator promotion and web MFA sign-in

> **Current console note (23 November 2026):** The originally described promotion command remains a distinct role-elevation procedure requiring explicit owner authorization; **do not rerun it** merely to resolve review queue 403s. The v0.357.1 Django administrator console supports same-origin moderator invitation QR MFA enrollment and explicit review-item assignments. The owner reported six/six administrator/moderator positive UAT checks on v0.357.1, but individual QR enrollment, negative assignment authorization, MFA/session replay and audit delivery are not certified by that result. An earlier read-only audit showed one administrator, one moderator and zero active assignments during 403 reports. See [current staging reconciliation](R1_AWS_Staging_Reconciliation_2026-11-23.md); use the administrator assignment workflow rather than widening moderator privileges.

This procedure promotes an existing, active, verified moderator with an enrolled MFA factor. It preserves the password, encrypted factor, factor replay counter and unused recovery codes. It revokes existing Identity sessions and invalidates outstanding MFA challenges and reauthentication tokens, so the next sign-in requires password and MFA again.

The command grants the application `administrator` role. It does not set Django `is_staff` or `is_superuser` and does not create a Django admin site or a new administrative dashboard.

## Release prerequisites

Deploy reviewed, digest-pinned images containing this change before running the command. Update Audit before Identity or before applying a promotion: Audit must accept `account.administrator_role_granted`. Update the Identity audit delivery worker to the matching release as well. Deploy the web image containing `/login/mfa/`. Do not paste a promotion script into an older running image or bypass the existing deployment guards.

No new database migration or secret is required by this change. The Identity runtime must already have privileged access enabled, its existing MFA encryption key, and the normal database permissions. The web runtime retains its existing encrypted database session configuration.

## Operator steps on VM2

Run in the worker's existing administrator terminal. The prompt keeps the selected email out of shell history; it is not a credential. Use a reference identifying the owner's authorization and retain the command output privately with deployment evidence.

```bash
(
set -euo pipefail
set +x
identity_cid=$(docker ps -q --filter status=running \
  --filter label=com.docker.swarm.service.name=kolovibe-identity)
test -n "$identity_cid"
read -r -p 'Existing moderator email: ' promotion_email
read -r -p 'Owner approval reference: ' approval_ref

docker exec --workdir /app/services/identity "$identity_cid" \
  python manage.py promote_moderator_to_administrator \
  --email "$promotion_email" --approval-reference "$approval_ref"

# After reviewing the dry-run account ID and target role, apply the authorized change.
docker exec --workdir /app/services/identity "$identity_cid" \
  python manage.py promote_moderator_to_administrator \
  --email "$promotion_email" --approval-reference "$approval_ref" --apply
)
```

The default invocation is a dry run. Application is transactional: a missing/unusable MFA factor, an ineligible account, or audit write failure commits no promotion. A repeated invocation for an eligible existing administrator makes no further change and emits no duplicate role-grant event. The role change and local audit outbox entry commit together; confirm delivery to the Audit service through the normal audit delivery process. The approval reference appears in operator output; the existing event schema stores the event kind, target account ID and timestamp, not the approval reference.

## Browser acceptance

1. Open the staging web `/login/` page and enter the existing email and password.
2. Confirm the next page requests the authenticator code or one unused recovery code.
3. Complete MFA and confirm the account page opens. No browser authentication is granted after the password step alone.
4. Sign out and verify protected pages require sign-in again.

The pending challenge is encrypted in the server-side Django session, expires within five minutes and never appears in a form, URL or browser token cookie. Successful verification rotates the browser session and CSRF token. Privileged credentials remain encrypted server-side with a 15-minute absolute browser lifetime. Every protected request revalidates Identity authorization; backend session rejection or a role mismatch clears browser access. Ordinary account sign-in remains unchanged.

Local tests cover web MFA success/rejection/expiry/CSRF/recovery behavior, transactional promotion and audit ingestion. Real PostgreSQL, deployed image provenance, audit delivery and browser MFA acceptance still require release verification.

