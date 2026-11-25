# Advertising and sponsorship — requirements (proposed)

**Status: PROPOSED — not approved.** 25 November 2026. Proposed content for PRD-F11 (direct-sold part), FR-016 and FR-020. Development-only, sandbox billing, closed flags, production NO-GO ([DR-AD-01](../architecture/advertising/AD-Owner_Decisions_Required_PHASE8A.md)). Priority: **M** must, **P** needs a value or decision, **B** blocked.

## 1. Scope

**In:** advertiser accounts and verification; campaigns, budgets, schedules; versioned creatives and review; feed and Explore sponsored placements; consent enforcement; validated impressions and clicks; invalid-traffic controls; bounded advertiser reporting; console review, fraud, suspension, scoped analytics, audit; sandbox billing preparation.

**Out:** real charging or any payment provider; advertiser web portal; public website or ad-serving web endpoint; AdMob/AdSense or any network SDK; behavioural or demographic targeting; Points, cash or any reward for ad interaction (FR-016); pre-roll, mid-roll, interstitial or full-screen ads; programmatic bidding; payouts of advertising revenue (R4); image/video creatives before the shared media pipeline.

## 2. Actors

Advertiser owner, manager, analyst (Flutter); viewer (Flutter, sees sponsored items); reviewers with `advertiser_review`, `ad_review`, `ad_fraud`, `ad_billing` grants and administrators (console, MFA); platform services (Gateway, Identity, Audit, Business).

## 3. Functional requirements

### A1 Advertiser accounts

| ID | Requirement | Pri |
| --- | --- | --- |
| AD-R-001 | Registration only with grant or invitation; owner assigned by the server | M/P |
| AD-R-002 | States `pending_verification`, `verified`, `rejected`, `restricted`, `suspended`, `closed`; server-only | M |
| AD-R-003 | Verification case with reviewer decision, reason code, resubmission limit, validity period; no files until media pipeline | M/P |
| AD-R-004 | Optional association to a verified Business proved by a signed read-only Business check | M/P |
| AD-R-005 | Roles `owner`, `manager`, `analyst`; invitation single use; moderators, administrators and reviewers cannot be members | M |
| AD-R-006 | Team change, closure and budget increase need step-up (fail closed until it exists) | M/B |
| AD-R-007 | An unverified, restricted or suspended advertiser cannot have a campaign approved or delivered | M |

### A2 Campaigns

| ID | Requirement | Pri |
| --- | --- | --- |
| AD-R-010 | Campaign: name, placement(s) from the approved list, total and daily budget, start and end, targeting (placement, county, content category only), creative reference | M |
| AD-R-011 | States `draft`, `in_review`, `changes_requested`, `approved`, `scheduled`, `active`, `paused`, `suspended`, `completed`, `rejected`, `cancelled`; the client sends *requests* only | M |
| AD-R-012 | Server validation: schedule rules, budget bounds, placement approved, creative version approved before `active` | M |
| AD-R-013 | Advertiser may pause an `active` campaign and resume it unless `suspended`, `completed` or past its end | M |
| AD-R-014 | Budget changes follow DR-AD-22; lowering below spent plus reserved is refused | M |
| AD-R-015 | Every state-changing operation takes an idempotency key; replay returns the stored result; key reuse with another body is refused | M |
| AD-R-016 | Campaign lists and results visible only to members of the owning advertiser | M |

### A3 Creatives

| ID | Requirement | Pri |
| --- | --- | --- |
| AD-R-020 | Creative versions are immutable; edit creates a new version | M |
| AD-R-021 | Phase 8 formats: text-only native card with bounded fields; destination typed (in-app, or external https disabled by flag) | M |
| AD-R-022 | Image/video upload with size, type, dimension and duration limits, re-encoding and screening | B (DR-AD-06) |
| AD-R-023 | Review by `ad_review` reviewer; bounded reason codes; appeal; reviewer ≠ advertiser member; submitter ≠ decider | M |
| AD-R-024 | Destination validation: https only, no userinfo, no IP literal, no shortener, no redirect, normalised host recorded, length bounded; re-checked on schedule | M |
| AD-R-025 | Safe delivery: clients render only server fields as plain text; destination resolved server-side at click | M |
| AD-R-026 | A suspended or rejected creative stops delivery on the next decision | M |

### A4 Delivery

| ID | Requirement | Pri |
| --- | --- | --- |
| AD-R-030 | Placement is server configuration; unapproved placement refused | M |
| AD-R-031 | Sponsored items delivered in a **separate response and field**; client shows "Sponsored", advertiser name and a distinct card style | M |
| AD-R-032 | No like, share, comment or follow on sponsored cards; no Engagement interaction | M |
| AD-R-033 | Eligibility, density and frequency rules per policy §2 | M/P |
| AD-R-034 | Consent required for decision; absent consent returns `consent_required` | M/B (DR-AD-07) |
| AD-R-035 | Unavailable-ad fallback omits the slot; organic content never waits | M |
| AD-R-036 | Deterministic, auditable selection with no paid priority and no personal data | M |
| AD-R-037 | "Why this ad" and "Report this ad" on every sponsored card | M |

### A5 Measurement

| ID | Requirement | Pri |
| --- | --- | --- |
| AD-R-040 | Every decision is server-created, account-bound, expiring and single-purpose | M |
| AD-R-041 | Impression and click are valid only per policy §3; client reports alone are never billable | M |
| AD-R-042 | Deduplication by unique `(decision_id, kind)`; replays are no-ops | M |
| AD-R-043 | Invalid-traffic rules per policy §4; outcomes `valid`, `invalid`, `held`; no automatic penalty on accounts | M/P |
| AD-R-044 | Billable events only by the finalizer after the hold window | M |
| AD-R-045 | Ad events never reach Points or Engagement; static and runtime tests | M |
| AD-R-046 | Advertiser reporting is aggregate, bounded, suppressed for small cells, delayed by the hold window | M |
| AD-R-047 | Raw events and decisions are purged on the retention schedule once approved | P |

### A6 Console

| ID | Requirement | Pri |
| --- | --- | --- |
| AD-R-050 | Pages: advertiser verification; campaign review; creative moderation; fraud alerts; campaign suspension; scoped analytics; advertising audit; billing corrections | M |
| AD-R-051 | MFA on every page; grant-scoped queues; claim, confirm, decision forms safe against double submit; step-up where required | M |
| AD-R-052 | Suspension takes effect on the next decision; restorer ≠ suspender; reason code and notice | M |
| AD-R-053 | Every privileged read and every decision is audited with ids only | M |

### A7 Billing preparation (sandbox only)

| ID | Requirement | Pri |
| --- | --- | --- |
| AD-R-060 | Budget reservations at decision time; spend plus reservations never exceed budget | M |
| AD-R-061 | Billable events append-only and unique per decision and kind; no duplicate billing records under concurrency or replay | M |
| AD-R-062 | Invoice data derived and recomputable from billable events; unique number; states `draft`, `issued`, `reconciled`, `void`; no payment status | M |
| AD-R-063 | Corrections append-only, two-person above threshold, with reason code | M/P |
| AD-R-064 | Reconciliation interface with a sandbox source; differences recorded, never auto-corrected | M |
| AD-R-065 | No charge, payment or collection operation exists; guard test | M |
| AD-R-066 | Real money and invoice tax and entity data | B (DR-AD-21, 51) |

### Cross-cutting

| ID | Requirement | Pri |
| --- | --- | --- |
| AD-R-070 | Every operation: closed Gateway flag, service identity, role check, per-object authorization with 404, allowlist validation, throttle | M |
| AD-R-071 | Every state change writes an id-only audit event in the deciding transaction, delivered by outbox | M |
| AD-R-072 | Ads stores `account_id` only; no contacts, device ids, precise location or viewing history | M |
| AD-R-073 | No tokens, MACs, consent details, creative URLs or free text in logs or audit | M |
| AD-R-074 | Service owns its schema; no cross-service tables or foreign keys | M |
| AD-R-075 | No network SDK dependency without an approval constant | M |

## 4. Non-functional

| ID | Requirement |
| --- | --- |
| AD-N-01 | Feed decision must never delay organic content: client timeout, then omit the slot (target p95 under 300 ms, measured in Phase 11) |
| AD-N-02 | Event ingestion bounded per account and session; ingestion cannot starve the service |
| AD-N-03 | Money integers only; micro-minor units for per-impression cost; rounding once per invoice line |
| AD-N-04 | Reporting queries bounded by date range and page size |
| AD-N-05 | Flutter screens follow existing design tokens, accessibility and large-text layout audit |
| AD-N-06 | With all flags closed no Ads route is served |

## 5. Traceability

Requirement → [API operation](../architecture/advertising/AD-API_Contract_PROPOSED.md) → [authorization row](../security/phase8/AD-Authorization_Model_and_Matrix_PROPOSED.md) → [threat](../security/phase8/AD-STRIDE_Threat_Model_PROPOSED.md) → [acceptance test](../engineering/phase8/AD-Acceptance_and_Delivery_Plan_PROPOSED.md).
