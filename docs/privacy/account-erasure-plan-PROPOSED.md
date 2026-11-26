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

1. **Jobs.** Approval creates one erasure job per participating service, in the same Identity transaction that deactivates the account. It also records one outbox event per job, `privacy.erasure_requested`, carrying `{request_id, account_id}` and nothing else.
2. **Dispatch.** An Identity dispatcher publishes each event to that service's own privacy queue, `kolovibe.<service>.privacy`. It uses the existing outbox pattern: publish, then mark sent; at-least-once delivery.
   - Identity gets a broker account that may *write* only to those exchanges, and *read* only `kolovibe.identity.privacy`.
3. **Erasure in each service.** A consumer takes the message once, through its idempotent inbox.
   - It applies its own policy table (below) in one transaction.
   - In the same transaction it records `privacy.erasure_confirmed`: `{request_id, service, counts per category, retained categories}`.
   - It publishes that confirmation to `kolovibe.identity.privacy`.
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
| Creators | Creator profile (name, bio, photo), application, onboarding events | Delete the profile and photo; de-identify onboarding events | None |
| Creators | Measures and appeals | Retain as enforcement evidence | Retention period |
| Content | Videos, media objects in R2, metadata revisions, upload records | Delete, including the R2 objects through the media worker | None |
| Content | Originality attestations, fingerprints, rights events | Retain as copyright evidence | Retention period, copyright counsel |
| Engagement | Likes, follows, shares, watch sessions | Delete (counts drop accordingly) | None |
| Engagement | Qualified watches, fraud holds | De-identify (Points evidence and abuse records) | Retention period |
| Points | Ledger entries, receipts, daily counts | Retain (append-only ledger; non-cash) | Retention period; whether a closed account's ledger is pseudonymized |
| Moderation | Reports the person made | De-identify the reporter | None |
| Moderation | Decisions, appeals, strikes, copyright and counter notices | Retain as evidence | Retention period, copyright counsel |
| Moderation | Rights-holder verification | Revoke and de-identify the evidence note | None |
| Business | Memberships, invitations, registration grant | Delete; remove memberships | Ownership of a business the person solely owns: **DR-BZ-08** |
| Business | Reviews written, inquiry threads and messages | Retain, decision pending | **DR-BZ-25** (already waiting on the owner) |
| Business | Verification evidence submitted | Retain as evidence | Retention period |
| Audit | Security events | Retain (append-only, separate store) | Retention period |
| Every service | Idempotency records and throttle counters | Expire on their normal schedule | None |

## Delivery in slices

- **2a:** the Identity outbox, jobs, dispatcher and confirmation consumer, plus one participating service, Engagement (likes, follows, shares and watch sessions). Proven against a real local RabbitMQ over TLS, like `scripts/verify_event_pipeline_broker.py`.
- **2b:** Creators and Moderation.
- **2c:** Content, including R2 object removal through the media worker, with the fake object store locally.
- **2d:** Business, limited to categories that need no pending decision.
- **2e:** Identity's own de-identification, completion, the restore re-apply command, and the console's "waiting on" view.

Staging needs new broker accounts and queues for Identity, Creators, Moderation and Business. That is a broker change, so it needs an approved staging plan before it is applied. The repository side (the secrets generator, the permissions table and the verification script) changes with each slice.
