# Advertising policies (proposed)

**Status: PROPOSED — not approved.** 25 November 2026. Covers the Phase 8 policy areas: creative review, placement, impression and click verification, anti-fraud, consent and privacy, billing and reporting. Numbers are **proposed starting values** held as configuration (as Business `limits.py` is) and change only by owner decision. The decisions that approve them are in [owner decisions](AD-Owner_Decisions_Required_PHASE8A.md).

## 1. Creative review policy

| Rule | Content |
| --- | --- |
| Unit of review | A **creative version**. Versions are immutable. Editing a creative creates version N+1; the approved version keeps serving until the new one is approved, except that a *destination* or *advertiser name* change never alters a version already approved |
| Who reviews | A reviewer with an `ad_review` grant, MFA, who is not a member of the advertiser. The submitter is never the decider. Restoration of a suspended creative is by a different reviewer |
| Checks | Category allowed for this advertiser; claims substantiated; no impersonation of KoloVibe, creators, authorities or other brands; no content that imitates organic video UI or system dialogs; no prohibited content (DR-AD-24); destination valid and matches the stated purpose; text bounded and free of markup; for media (later): image/video passes the shared media pipeline and copyright screening |
| Outcomes | `approved`, `changes_requested`, `rejected`, each with a **bounded reason code** from a fixed list (for example `prohibited_category`, `misleading_claim`, `impersonation`, `unsafe_destination`, `rights_unclear`, `inappropriate_content`, `policy_other_with_note_id`). Free text is not stored in audit |
| Appeal | One appeal per rejected version to an administrator; the reviewer who rejected cannot decide it |
| Post-approval | A user report or fraud signal can suspend a creative at once (reviewer or administrator); external destinations are re-checked on a schedule and on report |
| Safe delivery | The client renders **only fields the server returns for the approved version**; text is plain, never HTML; no client-supplied styling; media (later) is served from private storage through short-lived signed URLs as video is today; the destination is resolved server-side at click time and never taken from the client |
| Records | Every decision, reason code, reviewer and time is append-only and audited (ids only) |

## 2. Advertising placement policy

| Rule | Content |
| --- | --- |
| Approved placements | P1: sponsored native card in the video feed. P2: sponsored card on Explore. A placement is a server configuration row (`placement`), approved by an administrator; the client cannot name an unapproved one |
| Excluded surfaces | Profiles, comments, settings, account, sign-in, moderation, appeals, consent and any screen shown to a person in a sensitive flow; no pre-roll, mid-roll, interstitial, pop-up or full-screen ads; no ads that interrupt playback |
| Identification | Every sponsored item is returned by the server in a **separate response and field** (`sponsored: true`), never mixed into the organic feed payload; the client must render the label **"Sponsored"**, the advertiser's name and a card style that differs from organic cards; label cannot be hidden by the advertiser or the client theme |
| Interaction limits | No like, share, comment or follow on a sponsored card; no interaction that reaches Engagement; the only actions are the call to action, "Why this ad", and "Report this ad" |
| Density and frequency | Feed: first ad after the 4th organic item, at most 1 per 6, at most 1 per screen; per account per campaign 3 a day and 10 a week; all values configuration |
| Eligibility | Campaign `active`, inside its schedule, budget available, advertiser verified and in good standing, creative version approved, placement approved, consent present (DR-AD-40), account not excluded (DR-AD-43), not the advertiser's own member |
| Selection | Deterministic and auditable: among eligible campaigns, lowest recent delivery share first (pacing), ties by campaign id. **No bidding, no paid priority, no personal data in ranking** |
| Fallback | If nothing is eligible or the ad service is down, the slot is **omitted**: no empty box, no placeholder, no unreviewed content. Organic content never waits for ads |
| Organic separation | Sponsored items never enter creator analytics, qualified-engagement, Points or recommendations |

## 3. Impression and click verification policy

**Principle.** A client report is a *claim*, never a trusted event. A billable event requires a **server-issued decision**, a **plausible report**, a pass through **invalid-traffic filtering** and survival of a **hold window**.

### 3.1 Decision

The client asks for a placement. The server (after consent and eligibility) creates an `ad_decision` row (random 128-bit id, account id, placement, creative version, issued and expiry time five minutes, price snapshot) and **reserves** the unit cost against the campaign budget in the same transaction. It returns the decision id plus a MAC over its fields. Only decisions the server created can be reported against.

### 3.2 Impression

An impression report carries the decision id, the MAC and the measured visible time. It is accepted as **valid** only if all hold:

1. The MAC verifies and the decision exists, belongs to the signed-in account of this session, has not expired and has no impression yet (unique `(decision_id, kind)`).
2. Reported visible time is at least the viewability threshold (50% area, 1 s continuous) and the **server-observed gap** between decision and report is at least that threshold and at most the expiry. A report faster than physically possible is `invalid`.
3. The session is live; the account is not an advertiser member of the campaign's advertiser; the account is not excluded.
4. Per-account and per-session report rates are within bounds, and the number of impressions never exceeds the number of decisions issued.
5. The invalid-traffic rules (§4) do not flag it.

Duplicate, late, unsigned, cross-account or unknown-decision reports are counted as rejected (for monitoring) and **never** change spend.

### 3.3 Click

The client calls a click operation with the decision id. The server verifies a **valid impression exists for the same decision**, a minimum dwell has passed, no click exists yet for it, per-account click rate is bounded, then **resolves the destination from the stored creative version** and returns it. The client never supplies a URL. A second click on the same decision is `duplicate` and returns the same destination without a new event (replay-safe).

### 3.4 Finalization

A scheduled finalizer, not the request path, converts `valid` events older than the hold window into append-only `billable_event` rows (unique `(decision_id, kind)`), settles the reservation into spend, and releases reservations of unreported decisions. Events marked `held` stay out until reviewed. This is the only writer of billable events.

### 3.5 What cannot be proved

A modified client can fabricate plausible viewability claims. The controls are server-issued decisions, timing bounds, volume bounds, statistical rules and the hold window; **device attestation** (Play Integrity, App Attest) would raise the bar and is not part of Phase 8 (DR-AD-36 context). This is stated as residual risk, not hidden.

## 4. Anti-fraud rules

Signals are evidence for review; they hold or exclude events and raise alerts. **They never penalise an account automatically.** Starting thresholds are configuration.

| Rule | Starting trigger | Outcome |
| --- | --- | --- |
| Self-interaction | Account is a member of the advertiser or shares a verified Business with it | `invalid`, alert |
| Excess per account | More than 30 impressions or 5 clicks per account per hour | excess `invalid`; account flagged |
| Impossible timing | Report earlier than the viewability time, or click before dwell | `invalid` |
| Click without impression | Click for a decision with no valid impression | `invalid` |
| Replay | Same decision reported twice | second counted as `duplicate`, no effect |
| Metronomic pattern | Reports at near-identical intervals (low variance) across many decisions | `held`, alert |
| CTR anomaly | Campaign click-through above 5× the placement median over 200 or more impressions | campaign alert; new events `held` |
| Concentration | One account or one network hash produces over 20% of a campaign's clicks | `held`, alert |
| New-account burst | Accounts under 24 h old producing events | `held` |
| Decision hoarding | Many decisions with no reports from one account | rate limit decisions |
| Post-invoice discovery | Invalid traffic found after invoicing | billing correction (§6) |

Network identifiers (the address the Gateway sees) are used only as a **keyed hash with a rotating salt, kept 30 days**, solely for concentration and burst rules. No advertising ID, device fingerprint or location is collected.

## 5. Consent and privacy requirements

| Requirement | Content |
| --- | --- |
| Lawful basis | To be set by local legal review (blocker). Until then the **default is no ad processing** |
| Consent record | Identity owns a versioned consent record per account and purpose (`ads_delivery`, `ads_measurement`); granted explicitly, withdrawable, timestamped and tied to a notice version; withdrawal applies to the next request |
| Enforcement | The decision operation refuses with `consent_required` when the record is absent; the impression and click operations refuse when `ads_measurement` is absent; the **Gateway forwards the consent state in the signed envelope** so the Ads service cannot be called around it |
| Minimisation | Ads stores `account_id` only on decisions, counters and events; no name, email, phone, contacts, device ids, precise location or content-viewing history; targeting is contextual |
| Separation | Ads has no read path to Engagement, Points or watch history, and none of them reads Ads. **A static test fails the build if any such import or table reference appears** |
| Transparency | A "Why this ad" sheet says who paid, that targeting is contextual, and how to withdraw consent; a "Report this ad" action |
| Advertiser view | Aggregates only; small cells suppressed; no account-level or device-level data ever leaves the service |
| Retention | Decisions and raw events 90 days; hashed identifiers 30 days; aggregates and invoices per legal advice; purge jobs only after DR-AD-41 |
| Rights | Export and erase requests for Ads data follow the platform privacy orchestration decision (ADR-020); deleting an account removes decisions and counters but keeps invoices' non-personal totals |
| Minors | No sponsored items for accounts the age policy marks under 18 (DR-AD-43) |
| Logs | No tokens, MACs, consent details, URLs from creatives or free text in logs or audit |

## 6. Billing and reporting rules (sandbox only)

| Rule | Content |
| --- | --- |
| Nothing is charged | There is no charge, payment or collection operation. A guard test fails the build if one appears or if any payment adapter is imported |
| Money | Integer minor units plus a currency; per-impression cost in **micro-minor units** (CPM ÷ 1000) so rounding happens once per invoice line, half-up |
| Budget reservation | Decision-time reservation against `total` and `daily` budgets under a conditional atomic update; reservations expire with the decision; spend plus reservations never exceed budget |
| Billable events | Append-only, created only by the finalizer, unique per `(decision_id, kind)`; carry the price snapshot, campaign, creative version and time. They are *facts about delivery*, not money movements |
| Invoice data | Per advertiser per period: lines per campaign and placement from billable events; states `draft`, `issued` (sandbox), `reconciled`, `void`; unique invoice number; totals recomputable from billable events; **no payment status exists** |
| Corrections | Credit or debit **adjustments** linked to an invoice or billable event, append-only, with reason code; require `ad_billing` grant, requester ≠ approver, second approver above a threshold; invalid-traffic credits allowed within a window the owner sets |
| Reconciliation | An interface `ReconciliationSource.report(period)`; Phase 8 ships a sandbox source; the job compares totals, records `recon_difference` rows and alerts. It **never auto-corrects** |
| Advertiser reporting | Delivered, valid, invalid-filtered (share only), clicks, click-through, spend, remaining budget; by day and placement; no per-user data; small cells suppressed; shown only after the hold window for billable figures; clearly labelled "sandbox" in non-production |
| Console reporting | Scoped analytics per grant; fraud signals and billing differences; every read of an advertiser's data is audited |
| Money ledger | Not created here (DR-AD-03). A future real charge posts an invoice receivable to the single platform ledger via interface |
