# ADR-BIZ-001 — Business bounded context, service boundary and authorization model

**Status: PROPOSED — needs owner approval. Not an approved ADR.** Phase 6A, 24 November 2026.

**Identifier.** `ADR-BIZ-001` is provisional. The DOC-207 register already uses ADR-001 to ADR-022, so a register number is assigned only if the owner approves ([docs/adr/README.md](README.md): approved ADRs are recorded individually and drafts are not silently approved). This file lives here so reviewers find it with the other ADRs; it does not alter the register.

**Decision-makers.** Mark Allen Gbalazeh (@Markcino). **Related.** ADR-001 (microservices), ADR-010 (release sequencing), ADR-013 (identity), ADR-011/012 (gateway and service identity, proposed), ADR-020 (privacy retention, open), DEC-001, [requirements](../requirements/DOC-020_Business_Requirements_and_Scope_PROPOSED.md), [decision register](../architecture/business/BIZ-Owner_Decision_Register_PROPOSED.md).

## Context

R2 introduces business registration, verified ownership, profiles, public discovery, customer inquiries and reviews. DEC-001 keeps all of this out of R1, so no business code exists in `services`, `apps/web_django` or `apps/mobile`. The platform already provides Identity (accounts, sessions, MFA), a Gateway with default-closed capability flags, Creators (an owner-scoped profile with public discovery), Moderation (reviewer grants, decisions, appeals), Audit (id-only ingest) and Content (private R2 uploads). Constraints: one developer, a two-VM staging stack, an open PostgreSQL role-ownership finding (R-01), no payments, and a requirement not to create a second identity system.

The Business data differs from existing data in four ways that matter for architecture:

1. **Different ownership model.** Authority is *per business* (owner, staff), not a single global role on an account.
2. **Different personal data.** Public contact details of sole traders, private verification evidence, customer messages and review text.
3. **Different threat profile.** A public, scrapeable directory with a trust badge, a reputation system that attracts fraud, and a verification step that attackers will try to subvert.
4. **Different lifecycle.** Deferred to R2, so it must be deployable-dark and removable without touching R1.

## Decision 1 — Bounded context and service boundary

Create the **Business bounded context** and implement it as a **new `business` Django/DRF service** with its own PostgreSQL schema and role, behind the Gateway, using the shared HMAC service identity.

**Alternatives considered**

| Option | For | Against | Verdict |
| --- | --- | --- | --- |
| A. New `business` service | Own schema and blast radius; public-search load isolated from sign-in and video paths; PII and evidence in one owner; ships dark; matches ADR-001 | Ninth service: image, secrets, nonce table, verifier copy, deploy and monitoring cost; staging capacity unproven | **Recommended** |
| B. Module in Creators | No new deployable | Creators owns *creator* data and `CreatorProfile` is keyed to `user_id`; mixes a public directory, customer messages and evidence with creator eligibility; R2 code would ship inside an R1 service and cannot stay dark | Rejected |
| C. Module in Content | Has R2 storage code | Content is video-specific (models, media worker); would couple directory availability to the media pipeline | Rejected |
| D. Logic in the Gateway | No new service | The Gateway holds no business data and must stay a thin, replaceable edge; violates service-owned data | Rejected |

**Is a separate service “necessary”?** Honestly: not strictly at pilot scale. Option B would work technically. It is *recommended* because (a) ADR-001 already makes ownership-by-service the project's rule, (b) the module must remain disabled until approved and cannot be half-shipped inside an R1 service, (c) it holds a distinct class of personal data and a distinct public attack surface, and (d) object-level authorization differs fundamentally from Creators. The cost is real, so the decision carries **exit criteria**: if, after S1 (foundation), the staging stack cannot carry a ninth service within budget (DR-BZ-24), fall back to deploying the same code as a *separately imaged module* inside an existing deployable only by owner decision; the schema, API and authorization design are unchanged by that fallback.

**What stays out of the Business service:** credentials, passwords, MFA, sessions, email delivery (Identity), video and media (Content), moderation of non-business content (Moderation), money (none).

## Decision 2 — Authorization model: membership, not a new Identity role

Business ownership and staff authority are **`BusinessMembership` rows owned by the Business service**, keyed by `(business_id, account_id)`. Identity gains **no** new role, no business field and no credential store.

**Why.** `Account.role` is one global value (viewer, creator, moderator, administrator) and the gateway currently requires exactly one role per session; “owner of business X” is a relationship that varies per object and per time. Modelling it as an Identity role would grant a global authority, cannot express two businesses, and would couple every business change to Identity migrations and the MFA/invitation machinery.

**Flow.** The Gateway authenticates the bearer token against Identity's live session (no positive cache) and forwards a signed envelope containing the authenticated `actor_id` and role. The Business service resolves the membership for the specific `business_id` on every request and answers **404** to a caller with no entitlement. The client never supplies an owner or account id. This extends the existing pattern: the Creators service resolves ownership from the session, and the Gateway role-matrix test proves privileged routes refuse lower roles before forwarding.

**Privileged accounts.** Moderators and administrators cannot hold memberships (conflict of interest, separation of duties); their authority comes from their Identity role plus explicit grants (Decision 3).

**Alternatives.** New Identity roles `business_owner` / `business_staff` (rejected: global scope, single-role gateway assumption, Identity migrations, MFA coupling); a separate business login (rejected: second identity system, forbidden); membership claims embedded in the access token (rejected: stale authority; revocation must apply on the next request).

**Prerequisite.** Sensitive owner actions need a step-up proof. Identity's reauthentication token is bound to the account and session and can be consumed only inside Identity. A purpose-bound consume capability for other services is therefore an **Identity change** (P6B-04) to design and approve separately.

## Decision 3 — Moderation and verification placement

- **Verification cases** (private evidence, narrow reviewer set) live in the Business service, decided by reviewers who hold a Business verification grant under DR-BZ-07, MFA-gated through the existing Identity session context.
- **User reports and appeals about reviews, listings and inquiries** reuse the Moderation service's reviewer workflow after an additive, separately approved generalization from `video_id` to a subject type and a decision-application port to Business (mirroring Moderation → Content). **No change to Moderation is made in Phase 6A.**
- If the owner rejects touching Moderation (DR-BZ-17), Business keeps a local queue limited to the same state machine, accepting duplicated reviewer logic and a second place to test separation of duties.

## Decision 4 — Listing projection and search

Public reads are served from a **`business_listing` projection** holding only public columns, written transactionally when the eligibility predicate changes. Search uses **PostgreSQL full-text search** (`tsvector` with GIN index and a trigram index for tolerance) inside the Business schema, with a keyset cursor over `(rank, id)`. No search engine or cache is introduced. The eligibility predicate is a single function used by every public query.

**Why.** It mirrors Creators' “only reviewed active profiles are discoverable” rule, keeps private columns out of public query paths structurally (not by remembering to select the right fields), avoids a new datastore on a two-VM budget, and keeps ranking deterministic and free of paid placement.

**Alternatives.** Query the source tables with filters (rejected: one forgotten condition leaks private data); dedicated search engine (rejected for now: cost and a second copy of PII); `ILIKE` only (rejected: no ranking, slow at scale).

## Decision 5 — Deferral of uploads and images

The first slices accept **no file uploads**. Verification evidence (S3) and images (S7) use private R2 with the existing size-bound, create-only grant pattern and the creator-photo rules; the image decode-and-re-encode pipeline is built **once** (for D-10 creator photos) and extended, not duplicated (DR-BZ-20).

## Consequences

**Positive:** independent failure and release; private columns structurally separated from public queries; no second identity system; every R2 control can be tested at the gateway and service; dark by default.

**Negative and risks:** a ninth service increases operational load and the number of shared-verifier copies that must stay identical; membership logic is duplicated in each business-scoped service call path unless centralised inside Business; Moderation reuse needs an additive change to a service that is in R1 acceptance; verification and review policies remain unapproved, so the highest-value controls depend on owner decisions.

**Mitigations.** Add the service to the shared-identity drift test and the structure check in S1; keep the membership predicate in one module with a dedicated authorization test matrix; gate Moderation changes behind their own approval; keep every R2 route behind flags closed by default; keep the exit criteria in Decision 1.

## Compliance with the Phase 6A rules

| Rule | How the design complies |
| --- | --- |
| No second identity system | Decision 2: membership only |
| No cross-service table access | UUID references, no foreign keys, internal HTTP and outbox events only ([ERD](../architecture/business/BIZ-ERD_PROPOSED.md)) |
| Reuse existing audit, contract, validation | Audit producer addition; DOC-205 route-contract tests; allowlist validators |
| Least privilege, explicit ownership | Membership predicate; assignment grants; 404 on non-entitlement |
| No deferred features | No payments, tickets, live, ads, cash |
| No migrations, no AWS change | Documentation only |

## Approval record

Not approved. Owner decision, exact revision, date and conditions: _to be recorded per DOC-023 when decided._
