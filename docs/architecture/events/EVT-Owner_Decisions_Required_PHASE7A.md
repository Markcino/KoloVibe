# Events and ticketing (Phase 7) — exact owner decisions required

**Status: request for owner decisions, 25 November 2026. Every item below is OPEN. Nothing here is approved.** Accountable owner: Mark Allen Gbalazeh (@Markcino). Record each answer with the same template the Business register uses ([decision record template](../business/BIZ-Owner_Decision_Register_PROPOSED.md#decision-record-template-use-when-the-owner-decides)): revision, option, evidence link, date.

**Read this first.**

1. Events and ticketing are **Release 3** in the approved PRD (PRD-F13) and are **deferred** by DEC-001, ADR-010 and DOC-021. The Phase 7 instruction is the owner's request to start the work; it is not an approved design, and the registers still say "Deferred". Decision DR-EV-01 reconciles that.
2. The Phase 7 instruction says to obtain approval for product-policy decisions *before* the functionality that depends on them. Almost every slice depends on at least one policy. **No code, migration, flag, AWS or staging change has been made.** This package is the Phase 6A equivalent: documents only.
3. **Real payment providers stay off.** Nothing here asks you to choose or activate one. DR-EV-22 lists what must be known before that separate approval can be asked for.

**Already decided and not asked again (inherited):** ADR-001 (microservices), ADR-010 (financial separation), ADR-013 (identity), DR-BZ-21 (Flutter for every non-privileged actor; the protected Django console for moderators and administrators only; **no event website**). The Business position on outward links (DR-BZ-28, no links in the first release) is *not* inherited automatically: it is asked again as DR-EV-52.

## How to answer

Each row has a **recommendation** (the least-privilege, lowest-risk option). Replying "approve all recommendations" is a valid answer for any gate. A gate's rows are grouped by the slice they unlock so you can answer in the order the work needs.

## Gate G — architecture and governance (before anything is built)

| # | Decision | Recommendation | Why it matters |
| --- | --- | --- | --- |
| DR-EV-01 | **Scope reconciliation.** Approve developing R3 events and ticketing now, in development only, behind closed flags, sandbox payments only; raise the DOC-023 change request that moves PRD-F13, DOC-021, ADR-010 and DEC-001 wording from "Deferred" to "approved for development, not for release" | Approve. Production stays NO-GO and real-money processing stays off until DR-EV-22 | Without it the registers contradict the work (the same gap Business had, BZ-B-000) |
| DR-EV-02 | **Service boundary.** A new `events` Django/DRF service (the tenth deployable) with its own schema and role | Approve (ADR-EVT-001 options table). Exit criterion: if the staging stack cannot carry it (DR-EV-07), deploy the same code inside an existing deployable only by owner decision | Ownership, blast radius, dark-by-default |
| DR-EV-03 | **One financial-event ledger.** The only monetary ledger is the append-only `financial_event` table owned by a `payments` module inside the Events service. Points (non-cash, ADR-009) is not reused for money. No other service holds balances | Approve. Extract to its own service only when R4 payouts need it | Meets "no ledgers in multiple services" and ADR-010 "separate monetary ledger" |
| DR-EV-04 | **Organizer authority is membership, not an Identity role** (same model as Business). Moderators and administrators cannot hold organizer memberships | Approve | Per-object authority, separation of duties, no Identity migration |
| DR-EV-05 | **Shared Identity step-up proof** (P6B-04 / DR-BZ-33, still unapproved). Needed for event cancellation, refund approval, team-role change, organizer closure | Approve designing it once as a separate reviewed Identity task. Until it ships those operations fail closed, exactly as the Business four do | Cancellation triggers mass refunds; it must not rely on a bearer token alone |
| DR-EV-06 | **Database ownership model** for the `events` schema (the R-01 finding; DR-BZ-32 for Business). Append-only enforcement of the ledger depends on it | Option B: migration-owner role owns objects, the runtime login has DML only, events only; plus a trigger that rejects UPDATE/DELETE on `financial_event` | The ledger's immutability is otherwise a convention |
| DR-EV-07 | **Capacity.** A tenth service has never been shown to fit the staging VMs (DR-BZ-24 for the ninth is itself unmeasured). Authorise an owner-run, read-only capacity check | Approve; local and CI first, staging only after R-01 and R1 pilot acceptance | Gates any deployment, not development |

## Gate A — organizers and events (E1, E2, E3)

| # | Decision | Recommendation | Unlocks |
| --- | --- | --- | --- |
| DR-EV-10 | **Who may register as an organizer.** | Invitation or administrator grant only for the pilot (as Business DR-BZ-03); one organizer per account; at most 3 open organizers | E1 registration |
| DR-EV-11 | **Organizer verification policy:** accepted evidence, methods, validity period, resubmission limit, reason codes; whether a verified Business (R2) may be linked as a shortcut | Contact-channel proof plus a structured declaration reviewed by a grant-holder; no identity document and **no file upload** until DR-EV-17; one resubmission cycle; fixed re-verification period you choose; an organizer must be `verified` before it can publish a paid event | E1 verification, E2 publication |
| DR-EV-12 | **Team roles and limits.** | Three roles: `owner`, `manager` (events, ticket types, orders view), `checkin` (scan only, per assigned event). At most 10 active members; invitation TTL 72 h (Business values) | E1 team |
| DR-EV-13 | **Organizer suspension and restriction.** Grounds, notice wording, appeal route, and the effect on live events and sold tickets | Reason code plus notice plus independent appeal; the administrator who restores is not the one who suspended. A suspension hides new events and pauses sales but **never cancels paid tickets automatically**; cancellation and refunds are a separate, explicit decision | E1 suspension, E7 |
| DR-EV-14 | **Event publication review.** What a reviewer checks, the review time limit, which edits to a published event are *material* and re-review, who reviews | Every event is reviewed before first publication by a reviewer holding an `event_review` grant (MFA). Material fields: title, date and time, venue, category, price, capacity reduction. After publication, material edits create a new revision that stays unpublished until approved; the current approved revision stays live | E2 publication |
| DR-EV-15 | **Rules and lists:** event categories (two levels at most), counties and cities, prohibited event types, minimum lead time before sales open, maximum event length, time zone | You supply the lists. Default time zone `Africa/Monrovia`; no events with start in the past; sales window must end by event end | E2, E3 |
| DR-EV-16 | **Event visibility.** | `draft` (organizer only) and `public` (discoverable). **No unlisted or private-link events**, because a link implies a web page (DR-EV-52). Invite-only events are a later decision | E2, E3 |
| DR-EV-17 | **Event images.** No image pipeline exists (Content handles video only; creator photos D-10 are written but disabled; Business images S7 are deferred). | No images in the first slices; categories show built-in artwork. Build the image decode-and-re-encode pipeline **once** (it also unblocks creator photos and Business images) as a separate approved task, then add event images. This is a **blocker** for the "event images" part of E2, not for the rest | E2 images |
| DR-EV-18 | **Event notifications.** No notification delivery is enabled anywhere (Identity records delivery choices only). | In-app status only for the first release: order, ticket and event-change states appear in My tickets and are polled. No push, SMS or email until a delivery provider is approved. This is a **blocker** for "event notifications", recorded rather than worked around | E3 |

## Gate B — pricing, payments and refunds (E4, E5; E7 refund review)

These are product, financial and legal policies. Where a decision needs legal or provider input it is marked **Blocker**: development uses clearly labelled configuration placeholders and the sandbox, and nothing is enabled for real money.

| # | Decision | Recommendation | Unlocks |
| --- | --- | --- | --- |
| DR-EV-20 | **Currency.** USD, LRD, or both; display rules; whether one event may mix currencies | One currency per ticket type, chosen by the organizer from an approved list; amounts stored as integer minor units; **no conversion** between currencies; an order contains one currency. **Blocker for real money:** legal and provider input on which currencies can be collected | E4, E5 |
| DR-EV-21 | **Fees and tax.** Platform fee percentage and fixed part, who bears it (buyer or organizer), rounding, whether the fee is refundable, tax treatment | Fee policy is versioned configuration, applied server-side to every order and recorded in the order's immutable pricing snapshot. Rounding half-up per line to the minor unit. **No values are invented**: development uses `0` and the documented formula until you set them. **Blocker:** tax and fee rules need legal input | E5 |
| DR-EV-22 | **Real payment provider.** Selection, Liberia coverage, merchant onboarding and KYC, webhook signing method, settlement currency, fees, refund API support, settlement reports | **Blocker, not decided here.** Phase 7 builds the adapter interface and a sandbox adapter only. A real adapter needs a separate owner approval naming the provider, the evidence above, the legal review and the network change for an inbound webhook | E5 (live only) |
| DR-EV-23 | **Reservation and purchase limits.** Hold time, maximum tickets per order, maximum per account per event, per-account purchase rate | Hold 10 minutes; at most 6 per order; at most 10 per account per event; starting abuse budgets in the same "configuration, change only by owner decision" style as Business `limits.py` | E4 |
| DR-EV-24 | **Payment confirmed after the reservation expired.** | If inventory is still available, re-acquire it and issue; if not, issue nothing and open an automatic full refund (`late_payment_no_inventory`). Never oversell, never keep the money silently | E4, E5 |
| DR-EV-25 | **Buyer refund rules.** Whether buyers may request refunds, the window, whether the fee is refundable, partial refunds | Organizer sets one of two policies per event (`no_refund` or `refund_until` a time at least 24 h before start); the platform fee is not refundable on buyer-requested refunds; a request inside the window is approved automatically by rule, outside it goes to review; one refund per ticket; never above the captured amount | E5, E7 |
| DR-EV-26 | **Organizer cancellation and postponement.** | Cancelling a published event with sold tickets requires step-up (DR-EV-05) and a reason code, revokes all tickets and creates a **full refund including the fee** for every paid order, automatically and idempotently. Rescheduling is a material edit; buyers keep valid tickets and may request a refund under DR-EV-25 for 7 days | E4, E5, E7 |
| DR-EV-27 | **Refund approval authority.** Who reviews refunds, thresholds, two-person rule | A distinct `refund_review` grant (MFA, step-up). Administrator approval for any refund **not** produced by a rule; a second approver for amounts above a threshold you set; the requester can never be the approver. A separate Finance role is not created in R3 | E7 |
| DR-EV-28 | **Ticket disputes** (wrong event details, not admitted despite a valid ticket, duplicate charge). Adjudicator, evidence rules, time limit, outcomes | Administrator with a `dispute_review` grant (MFA); outcomes limited to dismiss, refund, reinstate ticket; 14-day target; the check-in log is the evidence of record | E7 |
| DR-EV-29 | **Organizer settlement.** | **None in Phase 7.** The ledger records what is owed to the organizer as a derived figure only. No payout, transfer or settlement operation exists (PRD R4; "payout automation until control validation") | E5 |
| DR-EV-30 | **Financial record retention and legal hold** (ADR-020 is open) | Keep financial events for the period legal advice sets; until then nothing is purged | E5 |
| DR-EV-31 | **Free events.** | Allowed: a price of 0 skips payment but uses the same reservation, inventory, issuance and check-in path. Reduces the money path to paid events only | E4 |

## Gate C — tickets and check-in (E6)

| # | Decision | Recommendation | Unlocks |
| --- | --- | --- | --- |
| DR-EV-40 | **QR credential design.** | A signed, versioned, opaque credential (no personal data) that the server always re-checks; admission is a single atomic server-side transition. Screenshots can be shared, so the **first scan wins** and later scans are refused with when and where. A short-lived rotating credential shown by the app is documented as a later option, not built | E6 |
| DR-EV-41 | **Transfer, gifting, resale.** | Out of scope. A ticket belongs to the buying account for its life | E6 |
| DR-EV-42 | **Offline check-in.** The Phase 7 instruction allows it only if its conflict model is approved. Liberian venues often have poor connectivity, so this is a real need, not a nicety | **Do not build in Phase 7.** The proposed model (signed per-event manifest, per-device keys, first-valid-scan-wins on reconciliation, conflicts flagged for organizer and review, revocation lag shown) is described in the [ADR](../../adr/ADR-EVT-001_Events_and_Ticketing_Bounded_Context_PROPOSED.md#decision-7--offline-check-in-not-built-model-for-approval). Approve it only if you want it built as its own later task | E6 |
| DR-EV-43 | **What a scan and the organizer can see.** | A scan shows the result, ticket type and, if already admitted, the time and gate. **No buyer name, email or phone anywhere in the Events service.** Organizers see counts and ticket identifiers, never buyer identity | E6, privacy |

## Gate D — clients (all slices)

| # | Decision | Recommendation | Unlocks |
| --- | --- | --- | --- |
| DR-EV-50 | **Flutter designs and route space.** The Business route space ends at M-144. Approve Figma designs for the Phase 7 screens (about 28 across organizer, attendee and check-in) and numbering from M-145 | One design package per slice, in slice order | each slice's Flutter work |
| DR-EV-51 | **Console pages and grants.** Organizer verification, event review, moderation, disputes, fraud, cancellation oversight, refund review, audit history; reviewer grant scopes `organizer_review`, `event_review`, `dispute_review`, `fraud_review`, `refund_review` | Approve; administrator-only for grants and for approving non-rule refunds | E7 |
| DR-EV-52 | **Outward links and receipts.** Any share link, web ticket page or emailed ticket | None. A link implies a web page; the QR is shown only in the app. A purchase receipt is an in-app order record | E3, E6 |

## What each slice needs before it can start

| Slice | Needs decided | Can be built without |
| --- | --- | --- |
| E1 Organizer management | DR-EV-01 to 04, 10 to 13, 50, 51 (DR-EV-05 for the step-up actions; those fail closed until it ships) | any payment decision |
| E2 Event management | E1, DR-EV-14, 15, 16 (DR-EV-17 for images) | images, notifications |
| E3 Discovery | E2, DR-EV-15, 16, 52 (DR-EV-18 for notifications) | notifications |
| E4 Ticket inventory | E2, DR-EV-20, 23, 24, 26, 31 | any provider |
| E5 Sandbox checkout | E4, DR-EV-03, 06, 20, 21, 24, 25, 29, 30 | **DR-EV-22 (real provider): not needed for sandbox** |
| E6 Tickets and check-in | E5, DR-EV-40, 41, 43 (DR-EV-42 only if offline is wanted) | offline mode |
| E7 Administration | E1 to E6 data, DR-EV-27, 28, 51 | — |
| E8 Security and quality | none of its own; its tests ship with every slice | — |

## Minimum to start (what I would ask you to answer first)

Approve DR-EV-01 to 04, 10 to 13, 50 (E1 screens) and 51 (E1 pages) with the recommendations. That unlocks E1. E2 needs DR-EV-14 to 16. Gate B can wait until E4 starts.

## Not requested from the owner

No real payment provider, no payout, no live streaming, no event website, no AWS or staging change, no migration, no change to Identity, Moderation, Points or Content in this phase. The only prerequisite changes to existing services, each needing its own approval, are Identity step-up (DR-EV-05), the Audit producer list, and the Gateway capability flags and routes.
