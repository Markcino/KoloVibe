# ADR-AD-001 — Advertising bounded context, measurement trust model and billing boundary

**Status: PROPOSED — needs owner approval. Not an approved ADR.** Phase 8A, 25 November 2026. The identifier is provisional; the DOC-207 register is not altered.

**Decision-maker.** Mark Allen Gbalazeh (@Markcino). **Related.** ADR-001, ADR-009 (non-cash points; ads never earn points), ADR-010 (financial separation), ADR-013, [ADR-BIZ-001](ADR-BIZ-001_Business_Bounded_Context_PROPOSED.md), [ADR-EVT-001](ADR-EVT-001_Events_and_Ticketing_Bounded_Context_PROPOSED.md) (also unapproved), ADR-020, DEC-001, PRD-F11, FR-016, FR-020, BR-001, TM-030, TM-031, [owner decisions](../architecture/advertising/AD-Owner_Decisions_Required_PHASE8A.md), [policies](../architecture/advertising/AD-Policies_PROPOSED.md).

## Context

The owner asks for direct-sold advertising in the Flutter app (advertisers, campaigns, creatives, delivery in the feed, validated measurement, console review, sandbox billing preparation). The approved scope allows only test ads in R1, treats advertisers as "later", and bars Points or cash for ad interaction (FR-016, BR-001, TM-030). Verified in the repository on 25 November 2026:

| Need | State | Consequence |
| --- | --- | --- |
| Ad code of any kind | None (tracker B-19 "Missing; Blocked by approval"; ADS-001 "Pending") | Greenfield, behind approval |
| Ad SDK in the app | None (`pubspec.yaml` has `http`, `video_player`, `image_picker`, secure storage) | No network dependency exists; none is added |
| Consent records | None in any service (PRD-F09 requires them) | A consent store is a prerequisite for delivery and measurement |
| Image/video creative processing | Video only in Content; **no image pipeline** | Text-only creatives first; media waits for a shared pipeline |
| Points separation | Points awards only from its own durable event queue (DEC-003) | Enforce structurally and by test |
| Step-up proof | Not built (Business fails closed) | Sensitive actions fail closed |
| Money ledger | None; Phase 7 proposes one inside Events (unapproved) | Ads must not create a second one |
| Business identity | Business service (R2), verified businesses | Association needs a read-only proof from Business |
| Public website | None by decision (DR-BZ-21) | Affects `app-ads.txt` for any network, see provider constraints |

## Decision 1 — Bounded context and service boundary

A new **`ads` Django/DRF service**, own schema and role, behind the Gateway with the shared HMAC service identity.

| Option | For | Against | Verdict |
| --- | --- | --- | --- |
| A. New `ads` service | Ad telemetry is structurally independent of engagement (BR-001); high-volume event writes isolated; ships dark; own blast radius | Another deployable on an unmeasured stack (with Business and Events, the ninth to eleventh) | **Recommended** |
| B. Module in Engagement | Has event ingestion | Engagement feeds Points; co-locating ad events removes the structural separation FR-016 and TM-030 depend on | Rejected |
| C. Module in Content | Owns feed and media | Content is video-only; couples ad availability to the media pipeline; mixes ad billing into content | Rejected |
| D. Module in Business | Has verified businesses | Business has no money or telemetry by design; different threat profile | Rejected |
| E. Logic in the Gateway | No new service | Gateway holds no data | Rejected |

**Exit criterion.** If staging cannot carry it, the owner may decide to deploy `ads` as a separately imaged module with other new services; schema, API and authorization do not change. DR-AD-05 asks the capacity question once for Business, Events and Ads together.

## Decision 2 — Authorization: advertiser membership

`AdvertiserMembership(advertiser_id, account_id, role)` with roles `owner`, `manager`, `analyst`; no Identity role. Campaign, creative, report and invoice access is resolved by joining object → advertiser → active membership **per request**; non-entitled callers receive **404**. Identity authenticates; the Gateway forwards a signed envelope. Reviewers hold explicit grants (`advertiser_review`, `ad_review`, `ad_fraud`, `ad_billing`) and cannot be advertiser members; advertiser members cannot review.

## Decision 3 — Structural separation from Points

The Ads service has **no import of, table reference to, queue binding with or signing key for** Points or Engagement. Points' consumer accepts only its allowlisted event types; ad event types are not among them and are never published to its queue. A static test scans both directions; a runtime test posts every ad event kind to the Points consumer path and asserts zero entries. "Advertising interactions must not automatically earn Points" becomes a property of the architecture, not of a rule.

## Decision 4 — Measurement trust model (decision, impression, click, billable)

Four distinct things, never collapsed:

1. **Decision**: server-created, single-account, five-minute, carries the price snapshot and reserves budget.
2. **Reported event**: a client *claim* against a decision.
3. **Validated event**: a claim that passed signature, ownership, timing, volume and consent checks, and the invalid-traffic rules.
4. **Billable event**: a validated event that survived the hold window, written only by a finalizer, append-only, unique per decision and kind.

Spend is derived from billable events; budget is protected by reservations taken at decision time. Details in [policies §3](../architecture/advertising/AD-Policies_PROPOSED.md#3-impression-and-click-verification-policy). The click operation **returns the destination from stored data**, so a client cannot inject a URL and every click passes one checkpoint.

## Decision 5 — Budget control: reserve then settle

Decision time: one conditional atomic update on the campaign budget row (`spent + reserved + unit_cost <= total` and the daily equivalent). A database `CHECK` is the backstop. Reservations expire with their decisions; the finalizer settles or releases. Overspend is impossible by construction; the trade-off is slight under-delivery near the budget end, which is the desired failure direction.

## Decision 6 — Billing preparation without a ledger

The Ads service stores *billing facts*: reservations, billable events, invoice and invoice lines (derived, recomputable), corrections (append-only, two-person). It has **no charge, payment, refund or settlement operation** and no payment adapter; a guard test fails the build otherwise. Real charging, when separately approved, posts an invoice receivable to the single platform ledger through an interface, so the ledger decision (DR-EV-03 and DR-AD-03) is taken once for both Events and Ads and no second ledger appears.

## Decision 7 — Consent first, fail closed

Consent is an Identity-owned, versioned, purpose-bound record (additive Identity change, needing its own approval). The Gateway puts the consent state in the signed envelope. With no record, the decision and measurement operations refuse. Until Identity ships it, **the delivery and measurement flags cannot be opened** (a startup check refuses to serve them without the consent source).

## Decision 8 — Creatives, review and safe delivery

Creatives are immutable versions reviewed before they can serve (reuse the Business/Moderation reviewer-grant pattern; no change to Moderation). Phase 8 ships text-only native creatives; images and video use the shared media pipeline once it exists (DR-AD-06) and the existing copyright screening where applicable. The client renders only server-returned fields as plain text. Destinations are typed: in-app (Business listing, Event) or external https URL, the latter validated and shipped disabled until the owner approves any outward link.

## Decision 9 — Third-party networks

A `NetworkAdapter` interface (request, validate, report) is documented but **no network SDK is added** and no adapter is registered. A guard test fails the build if a network SDK dependency appears without an approval constant. Eligibility and policy evidence is in [provider constraints](../architecture/advertising/AD-Third_Party_Provider_Constraints_PROPOSED.md). Provider approval is never assumed.

## Decision 10 — Client surfaces

Flutter for advertisers (all roles) and for viewing sponsored items; the protected Django console for administrators and moderators only; **no advertiser web portal, no public website, no ad-serving web endpoint**. Route numbers M-200 and up.

## Consequences

**Positive.** Ad events cannot reach Points by construction; spend cannot exceed budget; no client claim is billable by itself; no second ledger; text-only ads ship without waiting for a media pipeline; consent is enforced at the edge and the service.

**Negative and risks.** Another service on an unmeasured stack; delivery and measurement are blocked until Identity has a consent record; a modified client can still fabricate plausible events (mitigated, not eliminated); revenue is lower if consent is opt-in; the AdMob path is unverified and may be impossible without a developer website; step-up and image pipeline are shared unapproved dependencies; DR-EV-03 must be amended for the ledger to be extractable.

## Compliance with the instruction

| Rule | How |
| --- | --- |
| Advertisers on Flutter; admins and moderators on the console; no portal or website | Decision 10 |
| Do not promise provider approval | Decision 9; provider constraints list unknowns |
| Never trust client events alone | Decision 4 |
| Ads must not earn Points | Decision 3 |
| Sandbox billing only; no real charges | Decision 6 |
| Reuse media and moderation components | Decision 8, and only where they exist |
| Clear distinction from organic content | Policies §2 |
| No migrations, AWS or SDK change in 8A | Documentation only |

## Approval record

**Not approved.** Awaiting DR-AD-01 to DR-AD-07 and the gates that follow.
