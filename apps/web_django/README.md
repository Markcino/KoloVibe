# Django R1 administration console

This server-rendered web client serves moderators and administrators only. Its interface follows Material Design 3: color roles with automatic light and dark schemes (WCAG AA contrast checked for every pair), the M3 type scale and shape tokens, tonal navigation with a permanent drawer on wide screens and a CSS-only modal drawer on narrow ones, state layers, 48px touch targets, tables that reflow into cards on phones, and reduced-motion, high-contrast and forced-colors support. It uses no JavaScript, inline styles, web fonts or CDN assets, as the CSP requires. `/` always redirects directly to the headerless `/login/` page. Successful MFA opens `/admin/`; every protected view revalidates Identity before rendering. Anonymous flows are sign-in, its pending MFA challenge, and mailbox-bound moderator invitation acceptance. Health and bundled static assets remain accessible. Former public, viewer and creator routes return 404.

The console reuses `_api()`, Identity's password → MFA → logout flow, encrypted server-side credentials and the existing staging session model. Every protected request checks Identity, account, role, MFA state and session deadlines. Authorization for resource scope, audit subsets and points access is enforced in the owning service; the web never supplies client-selected permissions or guesses endpoints. Unsupported contracts are labelled **Not available in R1**.

## Routes and contracts

All gateway paths below use the `/api/v1` prefix. Every `/admin/` route requires an MFA-authenticated privileged session. All browser mutations are CSRF-protected POSTs; audit and points have only GET routes.

| Web route | Gateway contract / behavior |
| --- | --- |
| `/login/`, `/login/mfa/` | `POST /auth/login`, `POST /auth/mfa/verify` |
| `/moderator-invitation/` | Invite-only `POST /auth/moderator-invitations/setup` and `/complete`; password and current-period authenticator enrollment before account creation |
| `/admin/creators/` | Administrator-only. `POST /admin/accounts/lookup` finds an invitable account by exact email; `POST /creator-invitations` invites it; `GET /creator-applications` lists pending applications (handle and submitted time); `POST /creator-applications/<uuid>/decision` approves or rejects after a confirmation step. Needs the staging creator-onboarding flag |
| `/admin/team/` | Administrator-only `GET/POST /admin/moderator-invitations`; `POST /admin/moderator-invitations/<uuid>/revoke`; accepted moderators are listed with open-assignment counts from `GET /admin/moderation/assignments/summary` |
| `/admin/` | `GET /moderation/totals`, `/engagement/fraud-holds`, `/admin/audit`; audit denial leaves an explicit unavailable card |
| `/admin/moderation/{videos,reports,appeals}/` | Matching `GET /moderation/<kind>?cursor=…&status=…` |
| `/admin/moderation/{videos,reports,appeals}/<uuid>/` | Matching reviewer detail GET; decision POST calls `/moderation/<kind>/<uuid>/decisions` |
| `/admin/moderation/{videos,reports,appeals}/<uuid>/assignments/` | Administrator-only POST. Grants or revokes one moderator's access to the item through `GET/POST /admin/moderation/assignments`; the detail page lists current grants and assignable (accepted) moderators |
| `/admin/moderation/previews/<uuid>/` | Authenticated proxy for `/moderation/previews/<uuid>`; no storage redirect |
| `/admin/fraud/` | Moderator and administrator, read-only. `GET /engagement/fraud-holds?cursor=…`: every active hold in the caller's scope, 20 per page, each linked to its video review. A moderator with no assignment sees the explicit empty state. The dashboard shows the first five and links here |
| `/admin/points/` | `GET /admin/points/balances`; `?account=<uuid>` reads `/admin/points/accounts/<uuid>` |
| `/admin/audit/` | `GET /admin/audit` with cursor, kind, producer, since and until filters; since/until are UTC `datetime-local` inputs sent to the gateway as ISO 8601 `Z` values |
| `/admin/account/` | Own identity from `GET /me` |
| `/admin/account/profile/` | `PATCH /me` |
| `/admin/account/password/` | `PATCH /me/password`; success clears browser state |
| `/admin/account/sessions/` | `GET /me/sessions` |
| `/admin/account/sessions/<uuid>/revoke/` | `DELETE /me/sessions/<uuid>`; gateway ownership denials preserved |
| `/admin/logout/` | `POST /auth/logout`; browser state clears even if server revocation fails |
| `/health/live`, `/static/<asset>` | Liveness and allowlisted bundled assets |

## Roles and data scope

| Operation | Moderator | Administrator | Other roles |
| --- | --- | --- | --- |
| Own account/profile/password/sessions | Own, with MFA | Own, with MFA | 403 |
| Queues, detail and decisions | Active resource assignment, enforced by Moderation | Global supervision | 403 |
| Grant or revoke assignments | 403 | MFA session; audited as `moderation.assignment_changed` | 403 |
| Dashboard totals | Assigned resources; with no assignments the dashboard shows a "No review assignments yet" state (Moderation still audits the 403) | Global supervision | 403 |
| Active fraud holds | Videos in active video/report/appeal assignments | Global active holds | 403 |
| Audit | Own actions | Explicit active producer grants in Audit | 403 |
| Points | Audited 403 | Audited, read-only ledger review | 403 |
| Moderator invitations | 403 | List masked invitations; create/revoke with MFA sign-in within five minutes | 403 |
| Other role administration, award/reversal execution, cash payouts | No routes/UI | No routes/UI | No routes/UI |

`ModeratorAssignment` records explicit moderator, queue kind, target UUID and active state. There are no wildcard or implicit grants. Assignment checks cover reads, decisions, replay, inactive/revoked grants and delivery retries. Existing independent-appeal rules remain authoritative. **Open owner question:** broader assignment/routing model and moderation SLAs. This implementation does not choose automatic routing, workload or SLA policy and has no assignment UI. Moderator invitations grant no assignments.

## Moderator invitations (owner-approved scope exception)

On 22 November 2026 the owner approved **moderator invitations only**, with administrator authorization, MFA enrollment and audit records. This does not approve the broader [privileged administration proposal](../../docs/architecture/PROPOSAL_Privileged_User_Administration_DRAFT.md). Administrator invitations, existing-account promotion, deactivation, MFA resets and role editing remain absent.

An administrator opens **Team**, signs in again if their MFA proof is older than five minutes, and supplies the invitee's email, display name and reason. Identity authorizes every operation, including idempotent replay. The 24-hour, single-use code goes only to the invited mailbox; administrator responses and lists never contain it. Limits are five sends per administrator/hour, twenty globally/hour, one pending invitation per email, and one hundred live pending invitations. Existing accounts cannot be converted. Lists are masked and cursor-paginated to fifty records.

The invitee uses **Accept moderator invitation** on the sign-in page, enters the mailbox-bound code, chooses a password, and adds the privately displayed setup key to an authenticator. Five-minute setup, current-period TOTP and five failed enrollment attempts are enforced by Identity. No account exists until enrollment succeeds. Acceptance creates only a moderator, consumes the TOTP step, returns ten recovery codes once, and requires a separate sign-in with the next code or a recovery code. The code, setup key and pending email stay encrypted in a server session; the password is never retained by the web. Enrollment HTML necessarily displays the setup key and recovery codes privately to the invitee under no-store headers.

Revoked/expired/consumed invitations, wrong mailboxes and inviters who lose administrator status, activity or MFA enrollment fail closed. Create/revoke/list/setup/accept/denial events use the existing immutable Identity audit outbox; owning-service event links correlate the invitation and reasons without changing Audit's redaction. Migration `0011_moderator_invitations` adds the invitation state, constraints and append-only event correlation. Staging routes additionally require existing account-management and privileged-MFA gates. No runtime flags, secret mounts, peer credentials, SMTP provider or deployment is changed.

Video statuses are review/published/rejected/removed; reports open/resolved/dismissed; appeals open/denied/restored. Unsupported/repeated filters are rejected. Pages are bounded to 20 records and reject malformed data, duplicates and invalid cursors. Totals use the same owning-service filters, never a partial page count. Video scope forwarding is bounded to 1,000 assignments and fails closed above that limit. Fraud-hold reads describe active, unexpired inventory; no fraud policy or hold execution is added.

Reviewer detail contains metadata, rights status, and the latest 20 authorized report/decision records with explicit truncation flags. Moderators receive assigned report history and their own decisions. Rights status now uses Content-owned `attested`, `flagged`, `claimed`, `removed` and `restored` states. These are operational evidence labels, not legal ownership findings; legacy records without upload attestation are flagged. See [copyright pipeline](../../docs/architecture/copyright-review-pipeline.md) and the [policy draft — needs legal review](../../docs/privacy/copyright-policy-draft.md). A 60-second account-bound preview lease rechecks MFA, role, assignment and expiry on every fetch and audits access. Content, Moderation and Gateway proxy a bounded MP4 (maximum 50 MiB); object-store keys and raw storage URLs never reach the browser. R2 preview bytes require a real processed asset and approved R2 credentials. The current proxy buffers this bounded object and does not support byte-range streaming.

Audit returns a newest-first, cursor-paginated projection and omits actor/subject IDs, payload digests and payloads. Administrators without `AuditReadGrant` records receive 403. Reads and denials create immutable evidence. **Open owner questions:** broader audit redaction policy and retention; the conservative projection does not decide retention.

Points balance is `SUM(delta)` at the returned `as_of` snapshot, retained across pagination. History filters are all/awards/reversals/adjustments. Reversal-review state describes ledger relationships (reversed/not_reversed/reversal/not_applicable); it is not an approval or eligibility decision. There is no web-reachable write path or cash value. Automated award evidence retains a null actor; privileged review evidence identifies the reviewer.

## Sessions, security and activation

Staging preserves PostgreSQL sessions, separately encrypted credential rows and encryption/signing secrets, verified TLS, the `__Host-kolovibe_session` cookie, and security headers. Privileged sessions have a **15-minute absolute** and **30-minute idle** limit; activity/refresh never extend the absolute deadline. Password-only responses cannot enter the console. Credentials and MFA challenges never appear in URLs, HTML or browser storage. CSRF, stable gateway idempotency keys, account/session-bound decision intents, immutable audit evidence and role revalidation remain enforced.

HTML uses Django autoescaping. Documents, redirects, errors and preview bytes use private/no-store cache controls. CSP permits only bundled styles/images and same-origin media, forbids scripts/objects/framing/base URLs, and restricts form actions. Logout/expiry clears client caches/cookies/storage. The restricted-staging HSTS profile is 30 days without includeSubDomains or preload, because the apex hosts other sites; full ASVS L2 acceptance is not claimed. See [security evidence](../../tests/security/README.md).

Audit reads introduce the explicit `audit_read` staging capability, requiring account management, moderation and MFA on Gateway. It needs a distinct Gateway → Audit credential and explicit HTTPS peer entry, plus Audit's capability and producer grants. Existing deployments do not gain this capability automatically. `generate_r1_secrets.py --audit-read` explicitly prepares the expanded peer set; its default preserves the reviewed six-peer rollout. The currently reviewed cluster profile keeps audit reads off and needs separate owner approval before activation. Credential generation never activates or deploys it. No current secret, Swarm configuration, role grant, merge or deployment is changed by this branch. New models require migrations; production remains unsupported.

## Tests and local checks

After initializing the existing private `.env`, from the repository root:

```sh
.venv/bin/python scripts/run_local_web.py migrate
.venv/bin/python scripts/run_local_web.py test tests
PATH="$(pg_config --bindir):$PATH" .venv/bin/python scripts/verify_local_journeys.py
```

The real-service fixture uses disposable TLS PostgreSQL, distinct per-peer keys and task-owned local web sessions. It exercises existing MFA enrollment/verification, both privileged roles, scoped queues/detail/totals/holds/audit/points, CSRF, decision replay, escaping, OpenAPI response validation and logout. Its Identity MFA opt-in is isolated to fixture processes; real local/staging settings are unchanged. Unit tests cover expiry, cookies, IDOR, invalid records, preview ownership/expiry, audit redaction and immutable ledger balances. Browser evidence covers keyboard navigation and 390px layout with synthetic records. Real staged R2 delivery, independent ASVS review and owner acceptance remain release work.

Local `runserver` is for isolated fixture work; real privileged use requires an approved MFA-enabled Identity/Gateway profile. Session cleanup retains `clearsessions` and bounded `purge_expired_web_sessions`; expired preview leases are purged in bounded batches during issuance.
