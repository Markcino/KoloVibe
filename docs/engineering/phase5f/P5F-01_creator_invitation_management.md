# P5F-01 — Creator invitation listing and revocation

**Date:** 24 November 2026. **Scope:** Creators, Gateway, administrator console, DOC-205. Repository change only; nothing deployed, no staging migration run. Closes the item Phase 5 left open ("no approved contract").

## Definition (written before the code)
**Authorization.** Administrator only, at three independent layers: the console (`creators` view), the Gateway (refuses any other role before forwarding) and Creators (refuses any other role). Least privilege: the pre-existing *invite* and *review* operations still accept moderators (DOC-205 `x-required-roles`); seeing and withdrawing invitations does not. Self-revocation is refused (same rule as self-review). Fresh MFA for privileged roles is enforced by Identity session validation, as for the sibling creator routes.

**State transitions** (`CreatorApplication.status`):

| From | Operation | To | Notes |
| --- | --- | --- | --- |
| *(none)* | invite | `invited` | unchanged |
| `invited` | **revoke** | `revoked` | repeat is a no-op (200), one event |
| `revoked` | invite (administrator only) | `invited` | new inviter and time; reviewer fields cleared; moderators get 403 |
| `pending`, `approved`, `rejected` | revoke | refused, 409 | a submitted application is decided by review; an approved creator is never changed here (standing and restrictions belong to moderation) |
| `revoked` | applicant submit | refused, 403 | same as "no invitation" |

An applicant sees a revoked invitation as **404** on `GET /creators/me/application`, so the mobile contract (statuses `invited`/`pending`/`approved`/`rejected`) is unchanged and the app needs no change.

**Audit.** Creators has no Audit delivery credential, so a service-owned `OnboardingEvent` row (`invited`, `reinvited`, `revoked`, `approved`, `rejected`; account, actor, time) is written in the same transaction as each administrative change. The application also keeps the revoker in `reviewed_by`/`reviewed_at`. Rows are only ever added by the code; **the table is not protected by a database append-only trigger** (unlike Points and Audit), and delivery of these events to the central Audit service is not built — both are listed below as follow-ups.

**Listing.** `GET /creator-invitations?cursor=` returns only `invited` accounts (20 per page, ordered by account id): `account_id`, `status`, `creator_id` (always null), `invited_at`. No email or name.

## Changes
- Creators: `revoked` status, `OnboardingEvent`, migration `0006` (choices change plus one new table; no existing row altered), `outstanding` and `revoke` operations, event rows for invite, re-invite, revoke and the review decisions.
- Gateway: `GET /creator-invitations`, `POST /creator-invitations/{account_id}/revoke` (target from the path only, empty body required, response validated, administrator gate), staging allowlist extended for the two paths and two internal operations.
- Console: "Outstanding invitations" panel, confirm page, signed session-bound intent per row, own cursor (`invited`), failure of the list does not hide the rest of the page.
- DOC-205 updated; `valid_outstanding_invitations` declared as a web-only validator in the drift guard.

## Tests (all local, disposable SQLite test databases)
Creators 84 (8 new), Gateway 215 (+6), Web 138 (+7 and updated mocks), script tests 446 (matrix now includes the revoke route). Other six services unchanged and passing. OpenAPI validates. Each control was removed in turn and the matching test failed: Creators role gate, state guard, applicant 404, revoked-cannot-apply; Gateway administrator gate; console intent check.

## PostgreSQL evidence
On a disposable PostgreSQL 16 cluster (Unix socket, trust auth, destroyed afterwards) Creators migrations `0001`–`0006` applied, `sqlmigrate 0006` is a single `CREATE TABLE "service_onboardingevent"` plus the `creator_event_account_idx` index (the status-choices change is a no-op), `makemigrations --check` reports no changes, and the whole Creators suite (84 tests) passes there. The runtime login needs INSERT and SELECT on the new table.

## Not done
- **Deployment:** migration `0006` must be applied by the owner on staging under an approved operations plan; the capability stays behind `KOLOVIBE_STAGING_CREATOR_ONBOARDING`.
- **Audit service delivery and a DB append-only trigger** for `OnboardingEvent` (needs an Audit credential for Creators and an ops-approved migration). Recommended: reuse the Points outbox pattern.
- Creator standing/restriction administration is a different capability (see the Phase 5F matrix).
