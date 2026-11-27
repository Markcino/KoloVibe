# Account erasure plan (Decision C, PROPOSED)

Status: **proposed**, 26 November 2026. It is not legal advice and not an approved retention schedule. Every period and every "keep" below needs the owner's and counsel's approval (ADR-020). Until then the mechanism runs only with the sandbox fixture policy in this repository.

## What already exists

Slice 1 (PR #260) covers the review side:
- An administrator reviews a deletion request.
- Holds can block approval.
- Approval deactivates the account and revokes every session at once. The person can no longer sign in, reset a password or use an old token.
- The request stays `processing`; nothing marks it `completed` by hand.

## What erasure must do

When a deletion is approved, every service removes or de-identifies the personal data it owns:
- It never reaches into another service's database.
- It reports back what it did.
- The request becomes `completed` only when every service has confirmed and Identity has erased its own records.
- A category whose handling still waits on a decision is reported as **retained, decision pending**. While any category is in that state, the request stays `processing`. This is the honest outcome, not a failure.

## Mechanism

1. **Jobs.** Approval creates one erasure job per participating service, in the same Identity transaction that deactivates the account. It also records an outbox event, `privacy.erasure_requested`, carrying `{request_id, account_id}` and nothing else, for each job that can start at once.
   - Moderation and Content key a creator's records by the creator profile id, which only Creators knows, and Creators deletes the profile while it erases. Their requests are therefore recorded only when Creators confirms, and carry the profile id Creators reported, or null for someone who was never a creator.
2. **Dispatch.** An Identity dispatcher (`dispatch_identity_events`) publishes each event to that service's existing queue, for example `kolovibe.engagement`. It uses the existing outbox pattern: publish, then mark sent; at-least-once delivery.
   - Identity gets a broker account that may *write* only to those exchanges, and *read* only `kolovibe.identity`.
   - The grants are in `generate_r1_secrets.PROPOSED_BROKER_PERMISSIONS`. They are proposed and not applied to staging.
3. **Erasure in each service.** A consumer takes the message once, through its idempotent inbox.
   - It applies its own policy table (below) in one transaction.
   - In the same transaction it records `privacy.erasure_confirmed`: `{request_id, service, counts per category, retained categories}`.
   - It publishes that confirmation to `kolovibe.identity`.
   - Running it twice changes nothing and confirms again.
4. **Completion.** An Identity consumer marks each job confirmed.
   - When all jobs are confirmed and none retained a pending category, Identity erases its own records (next section) and sets the request to `completed`.
   - It notifies the person by email at the address that is about to be removed, sent before the removal. Whether to send this notice is itself to be confirmed.
5. **Retries and dead letters.** Retries and dead letters follow RV2-03. Those values are still proposed: a ceiling of 10 retries, dead letters kept 14 days, replay by an administrator only. A job that does not confirm stays visible to administrators in the privacy queue as "waiting on <service>".
6. **Restored backups.** Each confirmation is also sent to the Audit service, which has a separate database and append-only storage. After any restore, a maintenance command re-applies every confirmed erasure recorded in Audit that the restored databases no longer reflect. That way a restore cannot bring a deleted account back.
   - The command will be listed in the maintenance runbook, and it is idempotent.

## Identity's own records, and the `PROTECT` references

`PrivacyRequest`, `LegalAcceptance`, `MarketingConsentEvent` and `AccountHold` point at `Account` with `on_delete=PROTECT`. The acceptance and consent rows are append-only by database trigger.

The plan **never disables those constraints or triggers.** Instead the `Account` row is kept and de-identified:
- the email becomes `erased-<account id>@invalid`, which is unique and undeliverable;
- the display name is cleared;
- the password is made unusable, and `is_active` stays false;
- MFA factors, recovery codes, sessions, preferences and pending codes are deleted.

What remains is an opaque UUID. It is still needed to prove which terms version an account accepted and that a deletion was honoured. How long these evidence rows are kept is a retention decision (ADR-020).

## Inventory and proposed handling

"Delete" removes the rows. "De-identify" keeps the row but replaces the account link with a one-way tombstone, or clears free text, so aggregate counts stay correct. "Retain" keeps the row unchanged until a decision says otherwise.

| Service | Data | Proposed handling | Decision needed |
| --- | --- | --- | --- |
| Identity | Email, display name, password, MFA, sessions, preferences, codes | Delete, or clear on the kept `Account` row (above) | None for the mechanism |
| Identity | Legal acceptances, marketing consent history, privacy requests, holds | Retain as evidence | Retention period (ADR-020) |
| Creators | Creator profile (handle, name, location, bio), application, copyright review grant, onboarding events | Delete the application and the grant. Delete the profile, or, when measures point at it (`PROTECT`), keep the row de-identified: a meaningless handle, no name, location or bio, status `suspended`. De-identify onboarding events. Creators stores no photo | None |
| Creators | Measures, appeals, and the append-only audit trail | Retain as enforcement evidence | Retention period |
| Content | Videos, media objects in R2, metadata revisions, upload records | Remove the R2 objects (original, rendition, poster) through the media worker first; then delete metadata revisions and upload records. Each video row is kept but emptied (no title, description, tags, category, cover or storage keys; `removed`, private, deleted), because attestations, prescreening and claim states point at it with `PROTECT` | None |
| Content | Older renditions and posters no row points at | Removed by the media lifecycle rule; reported as retained until it exists | **RV2-04** (lifecycle rule) |
| Content | Originality attestations, prescreen results, copyright claim states, fingerprints, rights events, screening records, source digests, moderation receipts, the append-only audit trail | Retain as copyright and safety evidence | Retention period, copyright counsel |
| Engagement | Likes, follows, shares, watch sessions | Delete (counts drop accordingly) | None |
| Engagement | Qualified watches, fraud holds | De-identify (Points evidence and abuse records) | Retention period |
| Points | Ledger entries, receipts, daily counts | Retain (append-only ledger; non-cash) | Retention period; whether a closed account's ledger is pseudonymized |
| Moderation | Reports the person made, other than copyright claims | De-identify the reporter. Clear the free-text details, unless a decision cites the report; then the details are retained with that decision | Retention period, for cited details only |
| Moderation | Decisions, appeals, strikes, copyright claims and counter notices, decisions the person took as staff, the append-only audit trail | Retain as evidence | Retention period, copyright counsel |
| Moderation | Rights-holder verification | Revoke it and replace the evidence note with a fixed line. `revoked_by` holds the erasure request id, since no administrator acts at that moment | None |
| Moderation | Reviewer previews, moderator assignments | Delete the previews; deactivate the assignments | None |
| Business | Staff memberships, open invitations they created, reviewer grants, registration grant | Revoke the memberships, invitations and grants (rows stay as history, as every revocation there does); delete the registration grant | None |
| Business | Owner memberships | Retain, decision pending: the last owner cannot be removed except by closing the business (BZ-R-002) | **DR-BZ-08** |
| Business | Reviews written, inquiry threads, messages and blocks | Retain, decision pending | **DR-BZ-25** (already waiting on the owner) |
| Business | Verification cases and decisions, profile revisions submitted or reviewed, the append-only audit trail | Retain as evidence | Retention period |
| Audit | Security events | Retain (append-only, separate store) | Retention period |
| Every service | Idempotency records and throttle counters | Expire on their normal schedule | None |

## Delivery in slices

- **2a (built):** the Identity outbox, jobs, dispatcher and confirmation worker, plus one participating service, Engagement (likes, follows, shares and watch sessions). Proven end to end on a real local RabbitMQ over TLS by `scripts/verify_erasure_pipeline_broker.py`.
- **2b (built):** Creators and Moderation, each with its own outbox, inbox, worker and dispatcher (`dispatch_creators_events`, `dispatch_moderation_events`). The same real-broker script proves all three services end to end and the proposed grants least-privilege.
- **Retention policy (27 November 2026, mandate 3.2):** which retained evidence is compatible with a completed request is now configurable, not hard-coded. `services/identity/service/retention_policy.py` reads an owner-approved JSON policy (`KOLOVIBE_ERASURE_RETENTION_POLICY_FILE`) naming, per service, the evidence categories that may stay; the completed request records the policy id. With no policy, as today, every retained category keeps the request `processing`. Unfinished work (`business_ownership`, `untracked_media`) can never be waived by a policy. A `sandbox` policy is refused outside local development and tests. No category is approved: the values are the ADR-020 / RV2-04 / #136 owner decision.
- **2c (built):** Content on its media worker, which alone holds the R2 credentials, removing objects before any database change. The real-broker script runs the real media worker with a file-backed stand-in for the bucket. Real R2 deletion also needs the staging R2 token to allow `DELETE`, which is not yet verified.
- **2d (built):** Business, limited to categories that need no pending decision. Its worker reads the broker URI from settings and starts only locally, because Business is not deployed to staging.
- **2e (built):**
  - Identity's own de-identification and completion, in one transaction with the last clean confirmation.
  - A later confirmation of the same job replaces the earlier counts, so a request completes once a retention decision lets every service erase the rest.
  - `reapply_erasures` asks every service to erase again after a restore. It is listed in the deployment and rollback runbook, and is idempotent.
- **2f (built):** each request row carries every service's part of an approved deletion (whether it confirmed, and the categories it kept, by name only). The privacy queue shows "Waiting on <service>" and "<service> kept pending a decision: <categories>" for a request that is still `processing`. Counts stay in Identity and are not shown.
- **Access export, 3.3a (built, 27 November 2026, mandate 3.3):** an access request is now approved with `approve-access`.
  - Approval opens one export in the approving transaction. Identity assembles its own part at once (account, preferences, session dates, whether two-factor is enrolled, privacy requests, security event kinds and times; never a credential, digest or token) and sends `privacy.export_requested` to each service whose assembly is built.
  - Each service assembles its own part (service-owned assembly) and returns `privacy.export_delivered` to `kolovibe.identity` through its outbox. Identity stores each part once, through its inbox.
  - The request becomes `completed` only when every service's part has arrived. Engagement is the only service built so far, so a real export waits on Creators, Moderation, Content and Business (slice 3.3b, **NOT IMPLEMENTED**). The privacy queue shows "Waiting on <service>".
  - Retrieval: `POST /api/v1/me/privacy-requests/{id}/export`, by the account itself only, with a fresh password or re-authentication token. Another account, an administrator, a deletion request or an unknown id gets 404; an unready export 409 `export_not_ready`; an expired one 410 `export_expired`. Every retrieval and denial is audited. The console sees the export's state, never its data.
  - Expiry: `KOLOVIBE_EXPORT_RETRIEVAL_SECONDS` sets the retrieval window. It is an owner decision with **no default**: without it an access request cannot be approved (409 `export_window_not_configured`). Expired data is removed on the first retrieval after expiry and by `purge_expired_exports`; the dated export row stays. A completed erasure also removes an earlier export.
  - Engagement withholds fraud holds by name (`withheld`), since whether a person may see an abuse-investigation record is an owner decision. A category over 5,000 rows is cut and named (`truncated`).
  - Proven by the Identity, Engagement, gateway and console suites, and over a real local RabbitMQ by test 3 of `scripts/verify_erasure_pipeline_broker.py`. No broker grant changes: the Identity→Engagement and Engagement→Identity paths are the ones erasure already uses.
- **Still to build:**
  - Reading confirmations back from Audit after a restore of Identity itself. That needs an Audit read contract, which does not exist yet.
  - The completion notice email, which is still undecided (step 4).

*Update, 27 November 2026:* the roles, the zero-replica stack processes and the erasure-only capability row are now in the repository, and the staging steps are in `docs/operations/R1_Erasure_Runtime_Plan_2026-11-27.md` (not applied). Business is not on staging, so requests there will wait on it.

*Earlier text (26 November):* Staging needs new broker accounts and queues for Identity, Creators, Moderation and Business, the `account_management` capability for the Creators and Moderation workers (they refuse to start in staging without it), worker and dispatch roles in `staging_runtime/roles.py`, and the secrets and stack entries for them. That is a broker change, so it needs an approved staging plan before it is applied. The repository side (the secrets generator, the permissions table and the verification script) changes with each slice.
