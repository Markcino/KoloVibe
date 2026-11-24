# Business module (R2) — owner decision register

**Status update, 24 November 2026: the owner approved all 26 recommendations as written; see the [approval record](BIZ-Owner_Approval_Record_2026-11-24.md), which also lists what that approval does not supply.** The original proposal text follows unchanged.

**Original status: PROPOSED for owner review. Nothing here is approved.** Phase 6A, 24 November 2026. Accountable owner: Mark Allen Gbalazeh (@Markcino).

This register lists every policy the Phase 6A design deliberately does **not** decide. Each entry gives the question, why it matters, the realistic options, a recommendation (a recommendation is a proposal, not a decision) and what it blocks. Per [DOC-023](../../requirements/DOC-023_Change_Control_Proposed.md), a decision is recorded only when the owner decides against an exact document revision, with a link and actual date. Until then the status stays **Open**.

IDs are `DR-BZ-nn`. After approval they should be merged into the [DOC-207 open decision log](../DOC-207_Open_Decision_Log.csv) under that log's numbering; this file does not edit the log. Related open items that already exist: [ADR-020 privacy retention and data residency](../DOC-207_ADR_Register.csv), OD-05 and OD-08 ([Stage 3 open decisions](../../engineering/Stage3_Open_Decisions.csv)), and the [DOC-004 RBAC open decisions](../../requirements/DOC-004_RBAC_Matrix_DRAFT.md).

Legend — **Blocks**: the first slice in the [backlog](../../engineering/phase6/BIZ-Implementation_Backlog_PROPOSED.md) that cannot start until the decision is made (S0 = governance, S1 = foundation, S2 = registration and profiles, S3 = verification, S4 = discovery, S5 = inquiries, S6 = reviews, S7 = images, S8 = staff and later).

## A. Scope and governance

### DR-BZ-01 — Authorize the Business module and amend DEC-001
- **Question.** DEC-001 puts business discovery **out of Release 1**; PRD-F12 places it in R2; DOC-020 is "Deferred — no standalone specification". May the project begin Business work (design approval, then implementation) and, if so, relative to what R1 milestone?
- **Why it matters.** AGENTS.md forbids implementing deferred features. R1 production is still NO-GO ([go-live readiness](../../planning/go_live_readiness.md)). Starting R2 code before the owner changes scope would breach the rule; starting it before R1 closes competes for the single developer.
- **Options.** (A) Approve the design only; implementation waits for R1 pilot go-live. (B) Approve design and allow implementation behind closed capability flags in parallel with R1 closure. (C) Reject or postpone the whole module.
- **Recommendation.** A for implementation start, with the design approved now so that R1 choices (shared audit kinds, schema isolation, contract rules) do not paint R2 into a corner.
- **Required record.** A change request per DOC-023 amending the DEC-001 interpretation and promoting the Business requirements (this package's [requirements document](../../requirements/DOC-020_Business_Requirements_and_Scope_PROPOSED.md)) from *Proposed* to *Approved*; PRD/SRS detail approval is still the open #133 item.
- **Blocks.** S0 (everything).

### DR-BZ-02 — Separate Business service
- **Question.** Approve a new independently deployable `business` service ([ADR-BIZ-001](../../adr/ADR-BIZ-001_Business_Bounded_Context_PROPOSED.md))?
- **Options.** (A) New service. (B) Module inside Creators. (C) Module inside Content. (D) Defer the choice.
- **Recommendation.** A. See the ADR for the reasoning, the operating cost and the exit criteria.
- **Blocks.** S1.

### DR-BZ-23 — Legal and regulatory review
- **Question.** Which legal review is required before launch: terms of service for businesses, defamation and takedown handling for reviews, consumer-protection rules for reviews and endorsements, data-protection obligations for the personal data in this module, and any business-registration regulation that bears on "verified"?
- **Why it matters.** The design makes **no jurisdictional or legal claim**. Verification wording ("verified") can create expectations; review removal can create liability.
- **Options.** (A) Commission legal review before S3 (verification) and S6 (reviews). (B) Review only before public launch. (C) None (not recommended).
- **Recommendation.** A. The owner names the reviewer; the design records the dependency but not the answer.
- **Blocks.** S3, S6.

### DR-BZ-24 — Sequencing against R1 and staging capacity
- **Question.** When may a ninth service, its secrets, schema, role and image join the AWS staging stack?
- **Context.** The staging stack is two VMs; the 23 November catalog audit found 26 runtime-role-owned tables and eight sequences (open High risk R-01, [P1-06](../../security/phase1/P1-06_db_role_ownership_report.md)). A new service created before migration-owner separation is fixed would add to that debt.
- **Options.** (A) No staging rollout until R-01 is remediated and R1 pilot acceptance closes. (B) Roll out the closed (disabled) service earlier to rehearse deployment. (C) Local and CI only until approved.
- **Recommendation.** C then A. No AWS or staging change is made in Phase 6A or 6B without separate approval.
- **Blocks.** First staging deployment (after S1).

## B. Registration, ownership and verification

### DR-BZ-03 — Who may register a business
- **Question.** Which accounts may create a Business: any verified-email account, only creators, only accounts older than a threshold? How many businesses per account?
- **Options.** (A) Verified-email account, small per-account cap. (B) Verified-email plus minimum account age. (C) Creator-approved accounts only. (D) Invitation only for the first cohort (mirrors creator onboarding).
- **Recommendation.** D for the pilot cohort, then A with a cap and an age gate. Numeric caps and ages are **Owner-approved parameters (DR-BZ-22)**.
- **Blocks.** S2.

### DR-BZ-04 — Business verification policy
- **Question.** What does "verified" mean, what evidence proves ownership or authority to act for a business, who decides, how long does a decision last, and what happens on rejection or expiry?
- **Why it matters.** This is the product's trust claim. The design provides a *mechanism* (case, evidence record, reviewer decision, reason code, audit) and takes no position on the policy.
- **Options for the proof of ownership** (combinable): (A) manual review of documents the owner supplies (business registration or licence, tax or utility document, identity of the owner); (B) proof of control of a published contact channel (a one-time code to the listed phone or email, or a code placed on an owned website or social page); (C) in-person or video visit or third-party attestation; (D) an external registry lookup. D and C need integrations or operations that do not exist; A and B can be built on the platform's existing patterns.
- **Further sub-decisions.** Verification validity period and re-verification triggers; allowed number of resubmissions; service-level target for review; what the reviewer may tell the applicant; whether partial states ("contact verified") are shown.
- **Recommendation.** Decide A+B as the minimum, treat C and D as later options, and require the owner to write the evidence checklist. No evidence list, validity period or SLA is proposed here.
- **Blocks.** S3.

### DR-BZ-05 — Public visibility of unverified businesses
- **Question.** What is publicly visible while a business is draft, submitted, rejected or verified?
- **Options.** (A) Only *verified* businesses are discoverable; everything else is private. (B) Unverified-but-approved profiles are discoverable with a clear "not verified" label. (C) Visibility chosen by the owner of each business.
- **Recommendation.** A for the first release (smallest impersonation surface); revisit with real data.
- **Design note.** Visibility is computed by one server-side predicate ([BZ-R-016](../../requirements/DOC-020_Business_Requirements_and_Scope_PROPOSED.md)), so any option is a change to that predicate and its tests, not a redesign.
- **Blocks.** S4.

### DR-BZ-06 — Pre-existing or seeded listings and claims
- **Question.** Will the platform create listings that owners later *claim* (PRD journey "claims listing"), and if so from what source?
- **Why it matters.** Seeding requires lawful provenance for third-party business data and creates a large impersonation and takeover surface (claim fraud).
- **Options.** (A) No seeding: owners register themselves; "claim" means only resolving a duplicate. (B) Administrator-seeded listings from owner-supplied data, claimed through verification. (C) Imported datasets.
- **Recommendation.** A for the first release; B only after verification has run in practice.
- **Blocks.** S8 (claim flow); S2 only for the duplicate rule.

### DR-BZ-07 — Verification reviewers and separation of duties
- **Question.** Who decides verification and ownership disputes: moderators with an explicit assignment, administrators only, or a new "verifier" role? May privileged accounts also own or staff a business?
- **Context.** Identity has four roles (viewer, creator, moderator, administrator). Adding a role means Identity, invitation and MFA changes. Moderators already work through explicit [ModeratorAssignment](../../../services/moderation/service/models.py) grants.
- **Options.** (A) Moderators with an explicit assignment grant for the *verification* scope; administrators supervise. (B) Administrators only. (C) New Identity role.
- **Recommendation.** A, with no new Identity role; privileged accounts (moderator, administrator) **cannot hold a membership** (conflict of interest) and a reviewer can never decide a case they submitted or are affiliated with. Evidence viewing needs a narrower grant than queue viewing.
- **Blocks.** S3.

### DR-BZ-08 — Staff, owners and ownership transfer
- **Question.** Owner and staff capabilities, maximum staff per business, whether a business may have several owners, how staff are invited (the platform has no outbound email path outside Identity), how ownership transfers, and what happens when the sole owner's account is deleted or compromised.
- **Options.** Staff invitation by (A) a single-use code the owner shares out of band and the staff member redeems while signed in; (B) an Identity-mediated email invitation like moderator invitations; (C) in-app search of accounts (**rejected** by the design: enumeration).
- **Recommendation.** Owner-only in the first slices; staff in S8 with option B if Identity can send the mail, otherwise A. Ownership transfer requires step-up authentication and, per DR-BZ-04, possibly re-verification. At least one active owner at all times.
- **Blocks.** S8 (S2 only for the one-owner invariant).

### DR-BZ-25 — Suspension, delisting and closure
- **Question.** Grounds, notice, appeal path and data consequences for suspending, delisting or closing a business; how long reviews and inquiries survive closure.
- **Options.** Reuse the removal, notice and appeal pattern that Moderation applies to videos, or define a lighter admin-only suspension.
- **Recommendation.** Reuse the Moderation pattern (reason code, notice, independent appeal); owner approves grounds.
- **Blocks.** S3 (suspension), S6.

### DR-BZ-26 — Ownership dispute and impersonation handling
- **Question.** How is a competing or impersonation claim resolved ("someone registered my business")? Who adjudicates, on what evidence, within what time, and can a listing be frozen meanwhile?
- **Recommendation.** A reportable-dispute record, administrator adjudication with MFA, listing frozen on credible report; evidence rules follow DR-BZ-04.
- **Blocks.** S3 (reporting), S8 (full workflow).

## C. Profiles, listings and discovery

### DR-BZ-09 — Public business data fields
- **Question.** Which fields are public: trade name, legal name, description, address line, coordinates, phone, email, website, social links, hours? What about sole traders whose business details are their personal data (for example a home address or personal mobile number)?
- **Options.** (A) Coarse location (county, city) public; exact address and coordinates owner-opt-in per field. (B) Everything the owner enters is public. (C) Minimal public set; contacts only through in-platform inquiries.
- **Recommendation.** A, with a per-channel public flag and a warning on entry that public fields are visible to everyone; legal name private (reviewers and owner only).
- **Blocks.** S2.

### DR-BZ-10 — Category taxonomy and region values
- **Question.** The initial category list, its depth, who changes it, and the county/city value lists.
- **Recommendation.** Administrator-managed controlled vocabulary with stable slugs, two levels at most; the owner supplies the initial list. Owners cannot create categories.
- **Blocks.** S2.

### DR-BZ-11 — Profile changes after verification
- **Question.** Which edits are *material* (trade name, category, address, phone, email, website) and what happens: immediate and audited, held for review, or cause re-verification? Is there a cooling-off delay for contact changes (a classic scam vector)?
- **Options.** (A) Pre-moderation of material fields, free text post-moderated by report. (B) Everything pre-moderated. (C) Everything immediate.
- **Recommendation.** A with the previous approved revision staying public until the new one is approved; contact changes also notify the owner and require step-up authentication (see prerequisite P6B-04). Which fields are "material" is the owner's call.
- **Blocks.** S2.

### DR-BZ-12 — Anonymous versus signed-in discovery; contact reveal
- **Question.** (Also open as DOC-004 item "whether viewers can browse anonymously".) May anyone read listings, and are phone, email and exact address shown to anonymous callers or only to signed-in users with a verified email?
- **Recommendation.** Anonymous read of the minimal public set; contact channels visible to signed-in verified accounts only, with a per-account reveal rate limit, to slow scraping and spam. The owner confirms.
- **Blocks.** S4.

### DR-BZ-13 — Search capabilities and ranking
- **Question.** Is "near me" (distance from the viewer, which requires device location) in scope? Is relevance ranking acceptable? Is any paid placement, sponsorship or boosting permitted?
- **Recommendation.** First release: keyword, category, region, open-now, verified; sort by relevance then name; **no distance and no paid placement** (advertising and sponsorship remain outside this module, see the tracker row "Advertising and sponsorship"). Distance needs its own privacy decision (location data).
- **Blocks.** S4.

### DR-BZ-20 — Images
- **Question.** When may business logos or photos exist, who moderates them, and which pipeline processes them?
- **Context.** The creator-photo rules ([D-10](../../privacy/creator-profile-photos.md)) are written but the feature is disabled and no image pipeline exists; Content's pipeline handles video only.
- **Recommendation.** No images in the first slices. Build the image pipeline once for creator photos, then extend it (S7) rather than writing a second one.
- **Blocks.** S7.

### DR-BZ-21 — Where business owners work
- **Question.** The R1 web client is an administration console with no public or non-privileged pages; the mobile app has no business screens, and the exported designs under `docs/designed` contain none (the Figma file itself was not inspected). Where do owners manage a business and where do customers browse it?
- **Options.** (A) Mobile for customers, owner tools in mobile too. (B) Mobile for customers, a separate owner web portal. (C) Admin-assisted for the pilot.
- **Recommendation.** A for customers; owner tools in mobile in the same app; the admin console gains only reviewer pages. Needs designs approved before any client work.
- **Blocks.** S4 (client), S2 (owner client).

## D. Inquiries

### DR-BZ-14 — Inquiry rules
- **Question.** Who may send an inquiry (verified email, minimum account age); whether replies stay in-platform; whether a customer can choose to share a phone or email; message length; whether attachments are allowed; how users are notified (Identity notification preferences exist but no delivery is enabled); what response-time information is shown.
- **Recommendation.** Verified email; in-platform thread only; no attachments; notification delivery deferred; no displayed response-time metric until real data exists.
- **Blocks.** S5.

## E. Reviews and moderation

### DR-BZ-15 — Review authenticity and eligibility
- **Question.** Who may leave a review, and what must exist first? This is the central fraud-control policy; the PRD's draft journey says "service completion evidence → customer review → fraud checks" without defining the evidence, and the platform has no payments or tickets to prove a purchase.
- **Options.** (A) Any signed-in verified account (lowest friction, highest fraud). (B) Only after an inquiry thread with that business that both sides confirm as "completed" (interaction-based, no payment needed; gameable by colluding accounts). (C) Receipt or proof upload reviewed by a moderator (heavy; sensitive data). (D) Business-issued single-use review invitation (gameable by the business, so must be labelled). (E) A labelled combination, e.g. "interaction confirmed" and "invited" shown differently from "unconfirmed".
- **Sub-decisions.** Minimum account age; affiliation rules (owner, staff, their relatives and employees cannot review); one review per author per business; whether an author can re-review after a defined period; whether reviews are visible when authenticity is unconfirmed.
- **Recommendation.** E built on B and D, with the basis stored on every review and displayed, plus a hold-for-review rule for fraud signals. The design stores the *basis* so any option can be adopted without migration of meaning.
- **Blocks.** S6.

### DR-BZ-16 — Review moderation model
- **Question.** Pre- or post-publication moderation; fraud-hold triggers; how reviews are reported and removed; whether the business may respond (and whether responses are moderated); author display (display name, initials, pseudonym); edit and withdraw rules and whether edit history is retained; the minimum number of reviews before an average rating is shown; appeals by authors and by businesses.
- **Recommendation.** Publish after automated checks; hold when a fraud signal fires; post-moderation via reports; one moderated business response per review; business may report but never remove or hide a review; average shown only after a minimum count set by the owner; authors may edit or withdraw (withdrawal removes the text per DR-BZ-18).
- **Blocks.** S6.

### DR-BZ-17 — Where review and business moderation lives
- **Question.** Extend the existing Moderation service to handle business subjects, or give Business its own reviewer queue? Also: legal takedown and defamation handling.
- **Context.** Moderation already implements reviewer assignment grants, MFA gating, separation of duties, idempotent decisions with receipts and appeals — but its `Report`, `ModerationAction` and `Appeal` models are keyed on `video_id` and decisions are applied to Content.
- **Options.** (A) Generalize Moderation with a `subject_type` and a decision-application port to Business (reuse; touches a working R1 service). (B) Business-local queue duplicating the reviewer workflow (a second reviewer system). (C) Hybrid: Business-local for verification cases (private evidence, narrow reviewer set) and Moderation for user reports.
- **Recommendation.** C: verification stays in Business (evidence must not spread), report-driven review and appeal handling reuse Moderation after an additive, separately approved change to it. No migration is made in Phase 6A.
- **Blocks.** S6.

## F. Privacy and abuse

### DR-BZ-18 — Personal-data retention, deletion and residency
- **Question.** Retention period and deletion semantics for: verification evidence, verification cases, profile revisions, inquiries, review text, review reports, business and customer audit events, logs; behaviour on account deletion (delete, anonymize, retain with pseudonym); legal-hold rules; data residency.
- **Context.** ADR-020, OD-05 and OD-08 are open platform-wide. Identity's `PrivacyRequest` is a receipt only; no export or erasure processing exists anywhere. The [privacy document](../../privacy/business-data-privacy-and-retention-PROPOSED.md) lists categories and a deletion mechanism but **proposes no periods**.
- **Recommendation.** Decide per category after legal input (DR-BZ-23). Until then the implementation ships deletion *mechanisms* without automatic purge schedules, as Identity did for accounts and privacy requests.
- **Blocks.** S3 (evidence), S5, S6.

### DR-BZ-19 — Verification evidence handling
- **Question.** Whether identity documents are collected at all (data minimization), where evidence is stored, who may view it, how long it is kept after a decision, and how it is destroyed.
- **Recommendation.** Prefer evidence types that need no personal ID document (contact-channel proof, business licence); store evidence only in a private bucket with reviewer-only short-lived signed reads, each read audited; keep it only as long as DR-BZ-18 allows.
- **Blocks.** S3.

### DR-BZ-22 — Abuse-control parameters
- **Question.** Approve the numeric limits (registrations per account per day, inquiry and review rates, report rates, search and contact-reveal rates, account-age gates, fraud-hold thresholds). The design names the controls and gives starting points to tune; the numbers are not policy until approved.
- **Recommendation.** Start conservative, record them as configuration, and review after pilot data. Follow DEC-003's approach for engagement parameters (restricted-pilot values approved separately).
- **Blocks.** S2 (registration), S5, S6.

## Summary table

| ID | Topic | Blocks | Status |
| --- | --- | --- | --- |
| DR-BZ-01 | Authorize R2 Business module; amend DEC-001 interpretation | S0 | Open |
| DR-BZ-02 | Separate Business service | S1 | Open |
| DR-BZ-03 | Who may register | S2 | Open |
| DR-BZ-04 | Verification policy | S3 | Open |
| DR-BZ-05 | Public visibility of unverified | S4 | Open |
| DR-BZ-06 | Seeded listings and claims | S8 | Open |
| DR-BZ-07 | Reviewers and SoD | S3 | Open |
| DR-BZ-08 | Staff, owners, transfer | S8 | Open |
| DR-BZ-09 | Public data fields | S2 | Open |
| DR-BZ-10 | Taxonomy and regions | S2 | Open |
| DR-BZ-11 | Profile change moderation | S2 | Open |
| DR-BZ-12 | Anonymous discovery, contact reveal | S4 | Open |
| DR-BZ-13 | Search features and ranking | S4 | Open |
| DR-BZ-14 | Inquiry rules | S5 | Open |
| DR-BZ-15 | Review authenticity | S6 | Open |
| DR-BZ-16 | Review moderation model | S6 | Open |
| DR-BZ-17 | Moderation placement | S6 | Open |
| DR-BZ-18 | Retention, deletion, residency | S3/S5/S6 | Open |
| DR-BZ-19 | Evidence handling | S3 | Open |
| DR-BZ-20 | Images | S7 | Open |
| DR-BZ-21 | Client surfaces for owners | S2/S4 | Open |
| DR-BZ-22 | Abuse parameters | S2/S5/S6 | Open |
| DR-BZ-23 | Legal review | S3/S6 | Open |
| DR-BZ-24 | Sequencing and staging capacity | after S1 | Open |
| DR-BZ-25 | Suspension and closure | S3/S6 | Open |
| DR-BZ-26 | Ownership disputes | S3/S8 | Open |

## Decision record template (use when the owner decides)

- Decision ID and title:
- Exact document revision decided against (commit or PR):
- Option chosen (or "none, deferred"), conditions:
- Owner evidence link and actual decision date:
- Requirements, ADR, matrix, contract and backlog items to update:
