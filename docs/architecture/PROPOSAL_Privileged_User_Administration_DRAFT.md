# PROPOSAL: Privileged user administration for the web console

**Status:** Proposed — **not approved**. This is a draft for owner review. It does not change R1 scope. Nothing here is implemented, and no ADR number has been allocated.
**Author:** AI-assisted draft for Mark Allen Gbalazeh. **Date:** 2026-11-22.
**Decision needed from:** Product owner (scope), Security (controls), Platform (contracts).

**Narrow owner decision — 22 November 2026:** The owner instructed: “Add moderator invitations only, with administrator authorization, MFA enrollment and audit records.” This authorizes the separately reviewed moderator invitation implementation in R1. It does **not** approve this proposal as a whole, administrator invitations, role changes, deactivation/reactivation, MFA reset or assignment administration. The original broader R1.1 recommendation and open questions below remain proposals. See [the implementation contract and controls](../../apps/web_django/README.md#moderator-invitations-owner-approved-scope-exception); deployment still requires review and approval.

## 1. Context

- The approved SRS ([platform_SRS_v0_2_scope_approved.md](../requirements/platform_SRS_v0_2_scope_approved.md), section 10) states that the web console excludes **role administration**. [apps/web_django/README.md](../../apps/web_django/README.md) repeats this: "No routes/UI".
- Today a privileged account exists only through operator commands run on the Identity host:
  - `enroll_privileged_mfa` enrols TOTP for a reviewer account.
  - `promote_moderator_to_administrator` requires an approval reference, a dry-run by default, preserves MFA and revokes sessions.
- `Account.role` is a single value (`viewer`, `creator`, `moderator`, `administrator`). `AccountManager.create_superuser` deliberately raises: "Privileged account creation requires approved MFA and audit controls".
- Consequence: an administrator cannot add a moderator, deactivate a leaver or reset a lost authenticator without shell access to the server. That does not scale beyond the pilot and has no in-product audit trail for the approval.

## 2. Proposal (for decision)

Add a small, **invite-only** privileged user administration area for **administrators only**, delivered as a separate release (suggested "R1.1") after R1 acceptance. It would not exist in R1.

### 2.1 In scope
1. Invite a new moderator or administrator by email (no passwords chosen by the inviter).
2. List privileged accounts with role, status, MFA enrolment state and last sign-in.
3. Change role between moderator and administrator (two-person approval for administrator grants).
4. Deactivate and reactivate a privileged account.
5. Reset MFA enrolment for a privileged account (invalidates the old factor; forces re-enrolment).
6. Assign or revoke moderator queue assignments (links to the open FR-024 assignment model; see open questions).

### 2.2 Out of scope
- Viewer and creator account management, bulk import, SSO/SAML, custom roles, cash payouts, points award/reversal execution, public sign-up for privileged roles.

## 3. Permission model

| Capability | Moderator | Administrator | Notes |
| --- | --- | --- | --- |
| View privileged user list | No | Yes | Read is audited |
| Invite moderator | No | Yes | Step-up required |
| Invite administrator | No | Request only | Needs a second administrator to approve |
| Change role / deactivate / reset MFA | No | Yes, never on self | Step-up required; administrator grants need approval |
| Edit own display name, password, sessions | Yes | Yes | Existing account pages |

Rules enforced **in the Identity service**, never only in the web UI:
- An administrator cannot change their own role, deactivate themselves or reset their own MFA.
- The last active administrator cannot be demoted or deactivated.
- A request and its approval must come from two different active administrators.
- Every action requires a fresh MFA-backed step-up (re-authentication within the last 5 minutes).

## 4. Key flows

**Invite**
1. Administrator submits email, display name and role. Identity creates a pending account (inactive, no password) and a single-use invitation token (256-bit random, stored hashed, 24 h expiry).
2. Identity emails the link to the invitee. The response to the administrator never contains the token.
3. Invitee opens the link, sets a password (existing password policy), enrols TOTP and stores recovery codes. The account becomes active only after MFA enrolment succeeds.
4. Invitations can be revoked by an administrator, are single-use, and expire. Reuse, expiry and revocation return the same generic error.

**Administrator grant (two-person)**
1. Administrator A requests a grant for a named account with a reason and an approval reference.
2. Administrator B (different from A and from the target) approves within 24 h after step-up. Only then does the role change.
3. On success: the target's sessions are revoked, the new role is audited with both actors, and both administrators are notified.

**Deactivate / MFA reset**
- Deactivate: sets inactive, revokes all sessions and refresh tokens, keeps records for audit.
- MFA reset: marks the factor revoked, revokes sessions, and issues a new enrolment invitation. Recovery codes are regenerated.

## 5. Threat model (STRIDE summary)

| Threat | Example | Mitigation |
| --- | --- | --- |
| Spoofing | Stolen administrator session invites an attacker | Step-up MFA for every action, 15-minute session, session revoked on role or password change |
| Tampering | Role changed through a forged request | CSRF on all POSTs, role changes accepted only from the web service identity, server-side authorization, signed idempotency intent |
| Repudiation | Administrator denies granting access | Append-only audit events with actor, target, approval reference and both approvers |
| Information disclosure | User enumeration through invites or login | Generic responses, identical timing, redacted audit payloads, no token in any response or log |
| Denial of service | Mass invites flood email | Per-actor and global invite rate limits, pending-invite cap, email provider quota alert |
| Elevation of privilege | Self-promotion, last-admin removal, approval by the same person | Server-side rules in section 3, database constraints and tests for each |
| Insider collusion | Two administrators approve a rogue admin | Approval reference required, notification to all administrators, weekly review report |
| Invite hijack | Token leaked in email forwarding or logs | Single use, short expiry, hashed at rest, bound to the invited email, MFA enrolment required before activation |

## 6. API contract proposal (draft, not added to OpenAPI)

All paths are under `/api/v1`, administrator-only, and return 403 for any other role. All mutations require a step-up header proof and an `Idempotency-Key`.

| Method and path | Purpose | Request | Response |
| --- | --- | --- | --- |
| `GET /admin/privileged-users?cursor=` | List privileged accounts | none | `items[{id, display_name, email_masked, role, status, mfa_enrolled, last_sign_in_at}]`, `next_cursor` |
| `POST /admin/privileged-users/invitations` | Invite a moderator or administrator | `{email, display_name, role, approval_reference}` | `202 {id, status:"pending"}` |
| `DELETE /admin/privileged-users/invitations/{id}` | Revoke a pending invite | none | `204` |
| `POST /admin/privileged-users/{id}/role-changes` | Request a role change | `{target_role, reason, approval_reference}` | `202 {id, status:"awaiting_approval"}` or `200` for moderator-level changes |
| `POST /admin/privileged-users/role-changes/{id}/approve` | Second administrator approves | none | `200 {status:"applied"}` |
| `POST /admin/privileged-users/{id}/deactivate` and `/reactivate` | Change status | `{reason}` | `200` |
| `POST /admin/privileged-users/{id}/mfa-reset` | Reset MFA | `{reason}` | `202` |

Errors use the existing problem format: 400 validation, 401 expired, 403 role or self-action denied, 404 unknown, 409 last-administrator or state conflict, 429 rate limit. The web client never supplies permissions; the gateway forwards the caller identity as it does today.

## 7. Data model changes (illustrative)

- `Invitation(id, email, role, token_hash, created_by, expires_at, consumed_at, revoked_at)`
- `RoleChangeRequest(id, target_account, from_role, to_role, requested_by, approved_by, reason, approval_reference, status, created_at, decided_at)`
- Database constraints: `requested_by <> approved_by`, `requested_by <> target_account`, partial unique index on one open request per target.
- Reuse `LoginSession` revocation and `security_audit.record` from the promotion command.

## 8. Audit events (new kinds)

`privileged_user.invited`, `.invitation_revoked`, `.invitation_accepted`, `.role_change_requested`, `.role_change_approved`, `.role_change_denied`, `.deactivated`, `.reactivated`, `.mfa_reset`, `.listed`. Each stores actor, target, approval reference and outcome, with no secrets or tokens.

## 9. Web console UX (if approved)

- New "Team" section for administrators, using the existing Material 3 components: table with status chips, invite form, confirm step for destructive actions (same server-rendered pattern as moderation decisions), flash messages and an empty state.
- Pending approvals shown on the administrator dashboard.
- No JavaScript required (CSP stays `script-src 'none'`).

## 10. Verification plan

- Unit tests for every rule in section 3 (self-action, last administrator, same-approver, expired or reused token).
- Authorization matrix tests across roles for every endpoint (extend the existing role tests).
- Rate-limit, enumeration-timing and CSRF tests.
- Audit completeness test: every mutation emits exactly one event.
- Migration test and rollback note; threat-model review before release.
- Staging walkthrough with two administrator accounts and one invited moderator.

## 11. Open questions for the owner

1. Approve a scope change to include this in R1.1, or keep the operator-command process for R1?
2. Is a second administrator always available? If not, what is the break-glass procedure (suggested: keep the operator command, with its approval reference, as documented emergency access)?
3. Which email provider and sender domain deliver invitations in staging and production?
4. How does moderator assignment (FR-024) work, and does it belong in this change?
5. Is the 24-hour invite expiry and 5-minute step-up window acceptable?
6. Should role history be visible to the affected user?

## 12. Recommendation

Keep R1 as approved. Approve this proposal for R1.1, deliver Identity endpoints and tests first, then the web UI. Until then, continue using the operator commands with approval references, and record each use in the audit trail.
