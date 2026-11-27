# Advertising and sponsorship (Phase 8) — exact owner decisions required

> **Update, 27 November 2026 (records correction):** the "not approved" statements below are superseded for **development scope**. Owner Decisions H (Events), I (Advertising) and J (Finance) of 25 November 2026 ([record](../../planning/Owner_Decisions_A-J_2026-11-25.md)) approve these scopes for **sandbox development only**. Real payments, live payouts, live ads and production activation stay **not authorized**. Decision J and X-01 supersede any Events- or Advertising-owned monetary ledger: **Finance owns the one ledger**, and Points stays non-cash. Every policy value (rates, shares, thresholds, periods, windows, currencies) stays an unset owner decision. The original text is kept below as history.

**Status: request for owner decisions, 25 November 2026. Every item is OPEN. Nothing here is approved.** Accountable owner: Mark Allen Gbalazeh (@Markcino). Record each answer with the Business template ([decision record template](../business/BIZ-Owner_Decision_Register_PROPOSED.md#decision-record-template-use-when-the-owner-decides)).

**Read this first.**

1. Advertising is **not approved for development in the registers.** The approved PRD makes advertisers "later", PRD-F11/FR-020 allow only *test* ads with production "gated behind policy, privacy and publisher approval", tracker row B-19 is "Missing; Blocked by approval", and ADS-001 (ad policy) is "Pending, not started". DR-AD-01 reconciles that.
2. The Phase 8 instruction says to define and review ten policy areas before implementation. They are written in this package (see the [policies](AD-Policies_PROPOSED.md)); **the owner approves them here**. Nothing was built: no code, migration, flag, SDK, AWS or staging change.
3. **Real money is never charged and no provider approval is promised.** Billing is sandbox-only. AdMob or any network is a separate, later approval (DR-AD-36, [provider constraints](AD-Third_Party_Provider_Constraints_PROPOSED.md)).
4. **Phase 7 is also unapproved.** Five of the blockers below are the *same* decisions as Phase 7's (step-up, database roles, capacity, image pipeline, ledger). Answer each once; the cross-reference is given.

**Inherited, not asked again:** DR-BZ-21 (Flutter for advertisers, console for administrators and moderators only; **no advertiser web portal, no public website**), BR-001 / FR-016 / TM-030 (ad events produce zero Points or cash), ADR-009 and ADR-010.

## How to answer

Each row has a recommendation (least privilege, lowest risk). "Approve all recommendations" is a valid answer for a gate.

## Gate G — architecture and governance

| # | Decision | Recommendation | Why it matters |
| --- | --- | --- | --- |
| DR-AD-01 | **Scope reconciliation.** Approve developing direct-sold advertising now: development only, closed flags, sandbox billing, no network SDK; raise the DOC-023 change request moving PRD-F11, FR-020, ADS-001 and B-19 from "pending/blocked" | Approve. Production NO-GO until separately approved | Registers must not contradict the work (Business BZ-B-000 precedent) |
| DR-AD-02 | **Service boundary.** A new `ads` service with its own schema and role; Engagement, Points, Content and Moderation are not modified | Approve. Exit criterion: if staging cannot carry it, deploy as a separately imaged module only by owner decision | BR-001 requires ad telemetry independent from engagement; a separate owner makes the zero-Points guarantee structural |
| DR-AD-03 | **Billing records versus the money ledger.** Ads keeps *billing facts only* (reservations, billable events, invoice data, corrections). It creates **no monetary ledger**. When real charging is ever approved, an invoice posts a receivable to the **single** platform ledger through an interface. This needs Phase 7's DR-EV-03 amended: the ledger module must be extractable so two contexts can post to it | Approve; decide the ledger's owner jointly with DR-EV-03 before either context handles real money | Meets "no ledgers in multiple services"; Events and Ads cannot both own it inside their own services |
| DR-AD-04 | **Advertiser authority is membership, not an Identity role** (Business and Events pattern). Moderators and administrators cannot hold advertiser memberships; reviewers cannot be advertiser members | Approve | Per-object authority and separation of duties |
| DR-AD-05 | **Shared prerequisites, same as Phase 7:** Identity step-up proof (DR-EV-05 / DR-BZ-33), database ownership model (DR-EV-06 / DR-BZ-32), capacity for another service (DR-EV-07 / DR-BZ-24). Note: Business, Events and Ads would be the ninth, tenth and eleventh services on an unmeasured stack | Answer once. Until step-up ships, campaign budget increase, team change, advertiser closure and refund-like corrections fail closed. **Ask whether Business/Events/Ads may share one deployable** if capacity is short | Gates deployment, and several actions |
| DR-AD-06 | **Media pipeline for creatives.** No image pipeline exists (Content is video-only; creator photos D-10 are disabled; Business images S7 and Events DR-EV-17 wait too) | Build the image decode-and-re-encode pipeline **once**, as its own approved task, then use it for all four. Until then Phase 8 ships **text-only sponsored cards** (headline, body, call to action, typed destination). Video creatives wait for a generic Content media-job interface (separate approval) | Without a decision A3's image/video upload is blocked, not worked around |
| DR-AD-07 | **Consent store ownership.** No consent record exists anywhere in the platform (PRD-F09 requires consent records). | Identity owns a versioned, purpose-bound, withdrawable consent record (an additive Identity change needing its own approval). **Until it exists, no ad decision and no measurement event is accepted for anyone** (fails closed) | A4 and A5 cannot legally or safely run without it |

## Gate A — advertisers (A1)

| # | Decision | Recommendation | Unlocks |
| --- | --- | --- | --- |
| DR-AD-10 | **Who may register as an advertiser** | Invitation or administrator grant only for the pilot; one advertiser per account; at most 3 open | A1 |
| DR-AD-11 | **Business identity association.** How an advertiser proves it is, or is linked to, a verified Business | Optional link to a verified Business (R2). Proof by a signed, read-only internal call to Business ("is this account an active owner of verified business B?"), an additive Business change needing approval, so an advertiser cannot claim someone else's business. Fallback: reviewer-confirmed link | A1 |
| DR-AD-12 | **Advertiser verification policy:** evidence, methods, validity period, resubmission limit, reason codes | Contact-channel proof plus structured declaration (legal name, trading name, contact, intended category); verified Business link counts as strong evidence; **no files** until DR-AD-06; one resubmission; fixed re-verification period you choose; a campaign cannot be approved for an unverified advertiser | A1 |
| DR-AD-13 | **Team roles and limits** | `owner`, `manager` (campaigns and creatives), `analyst` (read results only); at most 10 active members; 72 h invitation | A1 |
| DR-AD-14 | **Advertiser restriction and suspension.** Grounds, notice, appeal, effect on live campaigns | Reason code, notice, independent appeal; restorer ≠ suspender; suspension pauses delivery immediately, billing facts for delivered impressions stay valid | A1, A6 |
| DR-AD-15 | **Who may not advertise** | Owner and legal supply the list. Recommended: political parties, candidates and issue campaigns (see DR-AD-24), unverified advertisers, advertisers under restriction | A1 |

## Gate B — campaigns and creatives (A2, A3)

| # | Decision | Recommendation | Unlocks |
| --- | --- | --- | --- |
| DR-AD-20 | **Pricing model** | Only **validated impressions are billable** (CPM). Clicks are measured and reported but not billed in the first release (smaller click-fraud exposure). A flat sponsorship price is a later option | A2, A7 |
| DR-AD-21 | **Currency, price list, minimum and maximum budget** | One currency per advertiser from an approved list; integer money; prices as configuration. **No values invented:** development uses placeholder values clearly labelled. **Blocker for real money:** collectable currencies need legal and provider input (same as DR-EV-20) | A2, A7 |
| DR-AD-22 | **Budget rules** | Total and daily budget; reserve-then-settle at decision time so spend can **never exceed** budget (no over-delivery tolerance); budget can be raised, lowered only to spent-plus-reserved; changes need an idempotency key (step-up to raise, DR-AD-05) | A2 |
| DR-AD-23 | **Schedule rules** | Start at least 24 h after approval; maximum flight 90 days; times stored UTC, shown in `Africa/Monrovia`; advertiser may pause and resume an active campaign until it ends; an administrator suspension cannot be resumed by the advertiser | A2 |
| DR-AD-24 | **Creative content policy** (prohibited and restricted categories, claims, political content, minors, health and finance) | You and legal supply the list. Recommended launch: prohibit political, electoral and issue advertising, adult content, tobacco, gambling, weapons, unlicensed health and financial claims, and content targeting minors; require substantiation for superlatives; allowed categories as an allowlist the reviewer picks from | A3 |
| DR-AD-25 | **Creative review process** | Every creative **version** is reviewed before it can serve, by a reviewer with an `ad_review` grant (MFA), different from any advertiser member; bounded rejection reason codes; one resubmission loop per version, appeal to an administrator; re-review on any edit; periodic re-check of external destinations | A3 |
| DR-AD-26 | **Formats and limits** | First release: text-only native card (headline ≤ 40, body ≤ 120, CTA from a fixed list). Images and video only after DR-AD-06, with size, dimension, duration and type limits you set | A3 |
| DR-AD-27 | **Destinations** | In-app typed destinations first (a verified Business listing, a published Event). **External https URLs are built and fully tested but ship disabled** until you approve any outward link (DR-BZ-28 says none in the first release): https only, no userinfo, no IP literals, no shorteners, no redirects, reviewed domain recorded per version, an "Opening outside KoloVibe" confirmation | A3, A4 |

## Gate C — delivery and measurement (A4, A5)

| # | Decision | Recommendation | Unlocks |
| --- | --- | --- | --- |
| DR-AD-30 | **Approved placements** | P1: a sponsored native card inside the video feed. P2: a sponsored card on Explore. Nothing else: no pre-roll or mid-roll, no interstitial, no ads on profiles, comments, settings, account, moderation or consent screens | A4 |
| DR-AD-31 | **Density and frequency caps** | Feed: first ad after the 4th organic item, at most 1 per 6; at most 1 ad visible per screen; per account per campaign 3 a day and 10 a week | A4 |
| DR-AD-32 | **Targeting** | Contextual only: placement, county, content category. **No** behavioural profiling, watch history, Points data, demographic or lookalike targeting, no cross-app identifiers, no advertising ID | A4 |
| DR-AD-33 | **Validation parameters** | Impression = at least 50% of the card visible for 1 continuous second, reported with a server-issued single-use decision; click needs a validated impression of the same decision and at least 500 ms of dwell; hold window 24 h before an event becomes billable | A5 |
| DR-AD-34 | **Invalid-traffic thresholds and outcomes** | Starting thresholds in the [policies](AD-Policies_PROPOSED.md#4-anti-fraud-rules); outcomes `valid`, `invalid`, `held`; alerts and holds only; **no automatic penalty on an account**; whether advertisers are told the invalid share | A5, A6 |
| DR-AD-35 | **Unavailable-ad fallback** | The slot collapses (no gap, no placeholder); never filled with unreviewed content. A platform house notice is not built | A4 |
| DR-AD-36 | **Third-party network (AdMob or similar).** Eligibility, publisher approval, store listing, app-ads.txt hosting, consent SDK, policy fit and child-directed treatment | **Not decided here; no SDK is added in Phase 8.** A network adapter interface is documented; any live adapter needs a separate owner approval with the evidence listed in the [provider constraints](AD-Third_Party_Provider_Constraints_PROPOSED.md). Provider approval is not promised | A4 |

## Gate D — consent and privacy

| # | Decision | Recommendation | Unlocks |
| --- | --- | --- | --- |
| DR-AD-40 | **Consent model.** Purposes, opt-in versus notice, withdrawal, minors, legal basis | Opt-in per purpose (`ads_delivery`, `ads_measurement`), off by default, withdrawal effective on the next request. **Users without consent see no sponsored items** (option A). Option B, contextual ads with aggregate-only measurement and session-level caps for non-consenting users, is a revenue trade-off you may choose. **Blocker:** the applicable data-protection obligations in Liberia need local legal review (PRD §11) | A4, A5 |
| DR-AD-41 | **Retention** of decisions, events, hashed network identifiers and invoices (ADR-020 open) | Decisions and raw events 90 days; hashed network identifiers 30 days; aggregates and invoices per legal advice; nothing purged until you decide | A5, A7 |
| DR-AD-42 | **Advertiser reporting privacy** | Aggregates only; a cell with fewer than 20 events is suppressed; results delayed by the hold window; no account, device or location below county | A5 |
| DR-AD-43 | **Minors.** Whether the platform has an age rule that excludes ads | Decide the age policy; if any account may be under 18, those accounts receive no sponsored items. **Blocker:** legal | A4 |

## Gate E — billing preparation (A7, sandbox only)

| # | Decision | Recommendation | Unlocks |
| --- | --- | --- | --- |
| DR-AD-50 | **Billing scope and corrections.** Billing periods, invoice numbering, who approves corrections and credits (including invalid-traffic credits after an invoice), thresholds | Monthly sandbox invoices; corrections need `ad_billing` grant, requester ≠ approver, second approver above a threshold you set; append-only | A7 |
| DR-AD-51 | **Invoice content and tax** | Placeholders until legal input: legal entity, address, tax treatment. **Blocker** | A7 |
| DR-AD-52 | **Reconciliation** | Interface only. Sandbox statement source in Phase 8; differences are recorded and reviewed, never auto-corrected | A7 |

## Gate F — clients

| # | Decision | Recommendation | Unlocks |
| --- | --- | --- | --- |
| DR-AD-60 | **Flutter designs and route space.** Phase 7 proposes numbering from M-145; Phase 8 should not collide | Reserve **M-200 and up** for Advertising. About 24 screens (advertiser onboarding, team, campaign list, create and edit, budget and schedule, placement picker, creative editor, review status, results, billing view) plus the sponsored card and "Why this ad" sheet | all Flutter work |
| DR-AD-61 | **Console pages and grants** | Advertiser verification, campaign review, creative moderation, fraud alerts, suspension, scoped analytics, audit; grants `advertiser_review`, `ad_review`, `ad_fraud`, `ad_billing`; administrators only for grants and suspension | A6 |
| DR-AD-62 | **Sponsored label, wording and design.** | Always-visible "Sponsored" label plus advertiser name, a card style unlike organic video cards, no like, share or comment, a "Why this ad / Report this ad" sheet; copy and Figma approved by you | A4 |

## What each capability needs before it can start

| Capability | Needs decided | Can be built without |
| --- | --- | --- |
| A1 Advertiser accounts | DR-AD-01 to 04, 10 to 15, 60, 61 (05 for step-up actions) | any money or consent decision |
| A2 Campaigns | A1, DR-AD-20 to 23 | creative media |
| A3 Creative | A1, DR-AD-24 to 27 (06 for media) | media upload |
| A4 Delivery | A2, A3, DR-AD-07, 30 to 32, 35, 40, 43, 62 | any network |
| A5 Measurement | A4, DR-AD-33, 34, 41, 42 | provider reports |
| A6 Console | one slice at a time, DR-AD-61 | — |
| A7 Billing prep | A5, DR-AD-03, 21, 50 to 52 | real charging; **DR-AD-36 not needed** |

## Minimum to start

Approve DR-AD-01 to 04, 10 to 15, 60 (A1 screens) and 61 (A1 pages) as recommended. That unlocks A1. Money, delivery and consent decisions can wait until A2, A4 and A7 begin. A4 cannot start until DR-AD-07 and DR-AD-40 are answered.

## Not requested

No real charging, no AdMob or other network, no advertiser web portal or public website, no change to Engagement, Points, Content or Moderation. Prerequisite changes to existing services (each needs approval): Audit producer list, Gateway flags and routes, Identity consent record and step-up, a Business read-only internal check.
