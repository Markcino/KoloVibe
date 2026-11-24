# DOC-020 (proposed content) — Business module requirements and scope

**Status: PROPOSED — Draft for owner review. Not approved.** Phase 6A, 24 November 2026. Accountable owner: Mark Allen Gbalazeh (@Markcino).

[DOC-020](platform_documentation_register_and_DEC001.md) is registered as *Deferred — outside R1; no standalone specification found*. This document is proposed content for it. It does not change the register, DEC-001, the PRD or the SRS. Promotion from Proposed to Approved needs a change request under [DOC-023](DOC-023_Change_Control_Proposed.md) and decision [DR-BZ-01](../architecture/business/BIZ-Owner_Decision_Register_PROPOSED.md).

## 1. What is approved, what is proposed

| Statement | State | Evidence |
| --- | --- | --- |
| Release 1 excludes business discovery, ticketing and monetary payouts. | **Approved** | DEC-001, 28 October 2026 |
| Verified business services and reviews are planned for R2 (PRD-F12). | **Draft** (PRD body is a working draft; scope only is approved) | PRD v0.2 §5, §7; document control #133 |
| The platform uses independently deployable Django/DRF services with a gateway. | **Approved (inherited)** | ADR-001 |
| Client authentication, sessions and privileged MFA are Django-native in Identity. | **Design approved**; implementation and verification open | ADR-013 v1.0 |
| Release sequencing keeps business verification in R2. | **Accepted — inherited** | ADR-010 |
| Everything else in this document and its companions. | **Proposed** | this package |

“Policy-pending” below means the requirement's *mechanism* is proposed but a policy it depends on is an open owner decision (DR-BZ-nn). Those policies are **not invented here**.

## 2. Purpose and scope

KoloVibe R2 adds a directory of Liberian businesses that can be found, contacted and reviewed, with ownership checked before a business is presented as verified. The Business module lets an account holder register a business, prove ownership, publish a profile, receive customer inquiries and receive reviews, with moderators controlling abuse.

**In scope (design only in Phase 6A):** business registration and verified ownership; profiles, categories, contact information and operating hours; listings, discovery, search and filters; customer inquiries; reviews and review moderation; business owner, business staff, customer, moderator and administrator permissions; privacy, retention and abuse prevention; audit.

**Out of scope, per the Phase 6A instruction and DEC-001:** live streaming; payments, checkout, deposits, bookings with payment; event ticketing and QR; advertising, sponsorship and paid placement; cash or monetary payouts; real-money rewards; automatic settlement; any customer-to-business money movement. Nothing in this module may take, hold or display a price that implies a transaction on the platform.

**Excluded by owner decision DR-BZ-21 (24 November 2026):** any public website, business web portal, customer web app or other browser-facing Business page. All non-privileged Business actors use the Flutter app; only moderators and administrators use the protected Django console (see [client architecture](../architecture/business/BIZ-Client_Architecture_DR-BZ-21.md)).

**Not designed because they are not requested or approved:** in-app messaging beyond inquiry threads; follower or "save business" features; business analytics; multi-language content; business-to-business features; push or email delivery of inquiry notifications (see DR-BZ-14).

## 3. Actors

| Actor | Definition | Identity source | Client surface (DR-BZ-21) |
| --- | --- | --- | --- |
| Visitor | Unauthenticated caller of public endpoints. | none | Flutter app |
| Customer | A signed-in Identity account (viewer or creator role) with a verified email. A creator is a customer too. | Identity `Account` | Flutter app |
| Business owner | An account with an *active owner membership* for a specific business. A relationship, not an Identity role. | Business `BusinessMembership` | Flutter app |
| Business staff | An account with an *active staff membership* for a specific business, with fewer capabilities than an owner. | Business `BusinessMembership` | Flutter app |
| Moderator | Identity role `moderator`, MFA session, acting only within explicit assignment grants. | Identity role + Moderation/Business grants | Protected Django console |
| Administrator | Identity role `administrator`, MFA session. | Identity role | Protected Django console |
| Internal service | A signed service caller (gateway, moderation, audit). | existing HMAC service identity | none |

A person has **one** account. The Business module introduces **no second identity system, credential or role field in Identity** (BZ-R-037).

## 4. Existing capabilities reused

| Need | Reused as it exists today | Gap this module must fill |
| --- | --- | --- |
| Accounts, sessions, email verification, MFA for privileged roles | Identity (`Account`, `LoginSession`, `TotpFactor`, session validation returning the live role and MFA state to the gateway) | A purpose-bound step-up proof other services can consume (P6B-04) |
| Public edge, route gating, contract defaults | Gateway capability flags (closed by default), per-domain route modules, response allowlist validators, route-contract and role-matrix tests | New capability names; contract merged into DOC-205 |
| Service-to-service trust | Shared HMAC service identity with per-caller keys, nonce table, drift test | One more copy of the verifier in the new service |
| Ownership resolved on the server, never named by the client | Creators and Content (`/creators/me`, cross-creator 404) | Business-scoped membership instead of account-global role |
| Public discovery pattern | Creators search: allowlisted public fields, bounded query, cursor pages, only reviewed-active profiles discoverable | Ranking, filters, keyset cursor |
| Invitation and approval pattern | Creator invitation and application review; moderator invitations (mailbox-bound, single-use, idempotent) | Staff invitation delivery channel (DR-BZ-08) |
| Reviewer authorization | Moderation `ModeratorAssignment` grants, MFA gating, distinct-reviewer rule, idempotent decisions with receipts, appeals | Generalization beyond `video_id` (DR-BZ-17) |
| Audit | Audit ingest with producer and kind allowlists, id-only payloads, MFA-gated read | A `business` producer, kinds and subject types |
| Private object storage and safe uploads | Content: private R2, size-bound create-only grants, exact-object completion; D-10 creator-photo rules | Image pipeline does not exist (DR-BZ-20) |
| Privacy requests | Identity `PrivacyRequest` receipts | Processing and propagation do not exist anywhere (DR-BZ-18) |
| Mobile client: HTTP, session, secure token storage, design system, system states | Flutter `ApiClient`, `LiveAccountRepository`, `CredentialStore`, shared widgets and system-state screens | Business screens, repositories and a route-space extension (DR-BZ-27); no second client or session |
| Retention of expired security rows | Identity `retention.py` pattern (bounded batches, grace periods, policy rows never touched) | Policy periods (DR-BZ-18) |

## 5. Functional and security requirements

Status column: **P** = proposed; **PP (DR-BZ-nn)** = proposed mechanism, policy pending that decision.

### 5.1 Registration and verified ownership

| ID | Requirement | Status |
| --- | --- | --- |
| BZ-R-001 | A signed-in account with a verified email MAY create a draft Business. Creation atomically creates the creator-of-record as the first active owner. The client never supplies an owner or account id. | PP (DR-BZ-03) |
| BZ-R-002 | A business always has at least one active owner. The last owner cannot be removed or leave except by closing the business. | PP (DR-BZ-08) |
| BZ-R-003 | At submission, the service detects duplicate and look-alike businesses (normalized name, contacts) and flags them for the reviewer; a flag never auto-rejects. | PP (DR-BZ-04) |
| BZ-R-004 | Ownership verification is a case with states `submitted`, `under_review`, `needs_info`, `verified`, `rejected`, `withdrawn`, `revoked`. The reviewer decides with a reason code. | PP (DR-BZ-04, DR-BZ-19) |
| BZ-R-005 | Only an authorized reviewer, with a live MFA session and an explicit grant, may decide a case. A reviewer cannot decide a case they submitted or are affiliated with. Decisions are idempotent and audited. | PP (DR-BZ-07) |
| BZ-R-006 | “Verified” is a property of a business, separate from whether it is publicly listed. It can be revoked. Every change is audited. | PP (DR-BZ-05) |
| BZ-R-007 | Edits to *material* fields follow the policy for re-review or holding. | PP (DR-BZ-11) |
| BZ-R-008 | Ownership transfer and ownership disputes follow a defined, audited workflow; a disputed listing can be frozen. | PP (DR-BZ-08, DR-BZ-26) |
| BZ-R-009 | Moderators or administrators can suspend or delist a business with a reason code; the owner is notified and can appeal. | PP (DR-BZ-25) |

### 5.2 Profiles, categories, contacts and hours

| ID | Requirement | Status |
| --- | --- | --- |
| BZ-R-010 | A profile is stored as revisions. Visitors see the last *approved* revision. A new revision never changes what is public until approved where the policy requires approval. | PP (DR-BZ-11) |
| BZ-R-011 | Categories come from an administrator-managed controlled vocabulary with stable slugs. Owners cannot create categories. | PP (DR-BZ-10) |
| BZ-R-012 | Contact channels (phone, email, website, social) have a type, a validated format and a per-channel public flag. Websites accept `https` only. | PP (DR-BZ-09) |
| BZ-R-013 | Operating hours are a weekly schedule of non-overlapping intervals plus dated exceptions, in a declared IANA time zone (default `Africa/Monrovia`). “Open now” is computed on the server. | P |
| BZ-R-014 | Location is stored at the granularity the policy allows. Exact coordinates are optional and never public unless the owner opted in. | PP (DR-BZ-09, DR-BZ-13) |
| BZ-R-015 | All text is length-bounded, normalized, free of control characters and treated as plain text (no HTML). Clients must render it as text. | P |

### 5.3 Listings, discovery, search and filtering

| ID | Requirement | Status |
| --- | --- | --- |
| BZ-R-016 | Public visibility is decided by a **single server-side eligibility predicate**. Public reads query only a listing projection holding public columns. No endpoint may bypass it. | PP (DR-BZ-05) |
| BZ-R-017 | Search supports keyword, category, region, open-now and verified filters, with deterministic ranking and no paid placement or sponsorship. | PP (DR-BZ-13) |
| BZ-R-018 | Queries are length- and character-bounded; pages are bounded (default 20) and use opaque, tamper-evident cursors; filters are an allowlist. | P |
| BZ-R-019 | A public representation exposes only allowlisted fields. Contact channels follow the reveal policy. | PP (DR-BZ-12) |
| BZ-R-020 | A suspended, delisted, closed or rejected business disappears from search and detail on the next request; intermediary caching, if any, has an approved maximum age. | P |

### 5.4 Customer inquiries

| ID | Requirement | Status |
| --- | --- | --- |
| BZ-R-021 | A verified-email customer may open an inquiry thread with a *listed* business, subject to throttles. | PP (DR-BZ-14, DR-BZ-22) |
| BZ-R-022 | Messages are bounded plain text, with no attachments. The customer and the business can add messages to a thread that is open. | PP (DR-BZ-14) |
| BZ-R-023 | A business sees only inquiries addressed to it, and sees the customer's display label only. The business never receives the customer's account id or email. | P |
| BZ-R-024 | A business may block a customer from messaging it; a customer may close a thread; per-customer and per-business throttles apply. | PP (DR-BZ-22) |
| BZ-R-025 | An inquiry thread or message can be reported to moderation. | PP (DR-BZ-17) |

### 5.5 Reviews and review moderation

| ID | Requirement | Status |
| --- | --- | --- |
| BZ-R-026 | A review is accepted only when the author meets the eligibility policy. The eligibility *basis* is stored on the review and may be displayed. | PP (DR-BZ-15) |
| BZ-R-027 | One active review per author per business. Owners, staff and affiliated accounts cannot review their own business. | PP (DR-BZ-15) |
| BZ-R-028 | Reviews follow a moderated lifecycle (`pending`, `published`, `held`, `removed`, `withdrawn`). Fraud signals can hold a review for human review. | PP (DR-BZ-16) |
| BZ-R-029 | A business owner may post one public response per review. A business can report a review but cannot hide, edit or remove it. | PP (DR-BZ-16) |
| BZ-R-030 | Aggregate rating and count are computed server-side from published reviews only, never accepted from a client or from the business. | PP (DR-BZ-16) |
| BZ-R-031 | An author may edit or withdraw their review under a defined window; history is kept only as the retention policy allows. | PP (DR-BZ-16, DR-BZ-18) |
| BZ-R-032 | Any signed-in user can report a review, listing or inquiry; moderators handle reports with MFA, assignment, distinct-reviewer rules, idempotent decisions and appeals. | PP (DR-BZ-17) |

### 5.6 Authorization

| ID | Requirement | Status |
| --- | --- | --- |
| BZ-R-033 | Deny by default. The gateway authenticates and gates the route; the Business service authorizes every object operation. | P |
| BZ-R-034 | A caller who is not entitled to an object gets **404**, not 403, so object existence is not disclosed. | P |
| BZ-R-035 | Membership and role changes take effect on the next request; there is no cached grant. | P |
| BZ-R-036 | Privileged business actions require the existing MFA session context; sensitive owner actions (contact change, ownership transfer, staff removal) need step-up authentication. | PP (needs P6B-04) |
| BZ-R-037 | No new Identity role, credential or password store is introduced. Business ownership is a membership relationship. | P |

### 5.7 Privacy, retention and abuse

| ID | Requirement | Status |
| --- | --- | --- |
| BZ-R-038 | Collect and expose the minimum data each purpose needs, classified per the [privacy document](../privacy/business-data-privacy-and-retention-PROPOSED.md). | P |
| BZ-R-039 | Every personal-data category has a deletion mechanism (soft delete, purge job, legal hold). Retention *periods* are not set until approved. | PP (DR-BZ-18) |
| BZ-R-040 | The module supports export and erasure requests for the data it holds when a privacy orchestration path exists. | PP (DR-BZ-18) |
| BZ-R-041 | Logs and audit events carry identifiers and decisions only: never message text, review text, contact values, evidence, tokens or file names. | P |
| BZ-R-042 | Rate limits and velocity controls cover registration, verification submission, profile edits, inquiries, reviews, reports, search and contact reveal. | PP (DR-BZ-22) |
| BZ-R-043 | Every request is validated against an allowlist of fields, types and sizes before use; body size is capped before it is read. | P |
| BZ-R-044 | Every state change and every privileged read (a reviewer reading verification evidence, a moderator reading inquiry or review content, reviewer queues) writes an audit event. Routine reads by a business of its own inquiries are not audited per read. | P |
| BZ-R-045 | When images or evidence are enabled: private bucket, size-bound create-only upload grants, decode and re-encode, metadata stripped, malware and bomb defences, short-lived signed reads, no public object URLs, no listing. | PP (DR-BZ-19, DR-BZ-20) |

### 5.8 Architecture and delivery

| ID | Requirement | Status |
| --- | --- | --- |
| BZ-R-046 | Each capability is behind a gateway flag that is closed by default; production stays unauthorized. | P |
| BZ-R-047 | The service owns its schema and role. No service reads another service's tables; cross-service references are UUIDs with no foreign keys; events use the outbox. | P |
| BZ-R-048 | Contract first: every route is declared in the API contract before implementation; the route-contract and role-matrix tests are extended and must fail on an undeclared or under-protected route. | P |

### 5.9 Client surfaces (follows decided DR-BZ-21)

| ID | Requirement | Status |
| --- | --- | --- |
| BZ-R-049 | Business owners, business staff, customers and visitors use the Flutter mobile app only. No public website, business web portal, customer web app or other browser-facing Business page exists. | **Decided (DR-BZ-21)** |
| BZ-R-050 | Only moderators and administrators use a web surface, the existing protected Django console, for Business verification, profile-revision review, report decisions, reviewer and registration grants and categories. Console pages carry every existing console control (privileged role, fresh MFA, session limits, signed intent, CSRF, confirmation, route-matrix registration). | **Decided (DR-BZ-21)** |
| BZ-R-051 | The Gateway and the Business service return JSON only for Business routes: no templates, HTML, cookies or `Access-Control-*` headers. Anonymous API reads exist to serve the app and do not authorize any web page, search-engine surface, share page or embed. | **Decided (DR-BZ-21)**; verification P |
| BZ-R-052 | The Flutter client reuses the existing API client, session management, secure token storage, repositories and design components; it adds no second session, API client or design system. | P |
| BZ-R-053 | The client holds no authority: it never decides or sends ownership, role, state, verified, listed, eligibility basis, rating or "open now"; it renders all Business text as plain text and shows server reason codes without interpreting them. | P |
| BZ-R-054 | Single-use codes (staff invitation, review invitation) are shown once, never persisted on the device or logged, and expire as the server states. No link that opens outside the app exists until DR-BZ-28 is decided. | PP (DR-BZ-28) |

## 6. Non-functional expectations (proposed, not measured)

No new SLOs are approved. Proposed engineering expectations: public endpoints are read-only with bounded queries and pagination so one request cannot scan the directory; search runs inside the Business schema on PostgreSQL full-text indexes (no new data store); the module can be disabled by flag without affecting R1 services; failure of Business never blocks sign-in, video or moderation paths. Capacity numbers wait for pilot data and DR-BZ-24.

## 7. Assumptions and constraints

- R1 pilot acceptance, PostgreSQL role-ownership remediation and production approval are open ([go-live readiness](../planning/go_live_readiness.md)). Production is NO-GO.
- The single developer and the existing AWS two-VM topology are fixed constraints.
- The design assumes the Liberia time zone `Africa/Monrovia` (UTC+0, no daylight saving) as a default value only; the field is per business.
- No legal conclusions are drawn (DR-BZ-23).

## 8. Traceability

PRD-F12 → BZ-R-001…054 → [ADR-BIZ-001](../adr/ADR-BIZ-001_Business_Bounded_Context_PROPOSED.md) → [architecture](../architecture/business/BIZ-ARCH_Service_Architecture_PROPOSED.md), [ERD](../architecture/business/BIZ-ERD_PROPOSED.md), [OpenAPI proposal](../architecture/business/BIZ-OpenAPI_3_1_PROPOSAL.yaml) → [authorization matrix](../security/phase6/BIZ-RBAC_and_Object_Authorization_Matrix_PROPOSED.md), [STRIDE](../security/phase6/BIZ-STRIDE_Threat_Model_PROPOSED.md), [privacy](../privacy/business-data-privacy-and-retention-PROPOSED.md) → [acceptance criteria](../engineering/phase6/BIZ-Acceptance_Criteria_PROPOSED.md) → [backlog](../engineering/phase6/BIZ-Implementation_Backlog_PROPOSED.md). Open policies: [decision register](../architecture/business/BIZ-Owner_Decision_Register_PROPOSED.md).
