# Advertising — STRIDE threat model (proposed)

**Status: PROPOSED — not approved.** 25 November 2026. Covers the `ads` service, Gateway routes, Flutter surfaces and console pages; extends DOC-203 (TM-030 ad event triggers points; TM-031 unreconciled revenue). Each threat has a control and a named test required before its capability is accepted. The last column maps to the Phase 8 security list.

## 1. Assets and boundaries

| Asset | Why it matters |
| --- | --- |
| Budget counters, billable events, invoices | Money-adjacent truth; overspend and double billing are direct harm |
| Decisions and events | The only basis for billing and reporting |
| Creative versions and review state | What viewers see; fraud and harm channel |
| Advertiser identity and Business link | Trust and impersonation |
| Consent records and viewer account ids | Privacy |
| Points and Engagement | Must remain untouched by ads |

Boundaries: B1 app ⇄ Gateway; B2 Gateway ⇄ Ads; B3 Ads ⇄ Business (read-only check); B4 Ads ⇄ Audit; B5 console ⇄ Gateway; B6 app ⇄ destination (external URL, disabled by default).

## 2. Threats and controls

| ID | STRIDE | Threat | Control | Test |
| --- | --- | --- | --- | --- |
| T-AD-01 | E | A non-member, or a member of advertiser B, reads or changes advertiser A's campaigns, creatives, results or invoices | Object chain to active membership; 404 | **Unauthorized advertiser access** |
| T-AD-02 | E | Changing a campaign, creative, decision or invoice id reaches another advertiser's object | Registry-driven join; random ids; uniform 404 | **Cross-campaign IDOR** |
| T-AD-03 | E | An analyst writes; a manager raises budget, changes team or reads invoices | Role per operation | Role-matrix test |
| T-AD-04 | E | A client sets `state`, `advertiser_id`, price or spend in a body | Allowlist validators; server-owned fields | Mass-assignment test |
| T-AD-05 | S | A fake client posts impressions for decisions it never received | Only server-created decision ids; MAC; account-bound; expiry | **Fake impression injection** |
| T-AD-06 | S | An attacker uses another user's decision id or MAC | Decision bound to account and session; 404 | Cross-account decision test |
| T-AD-07 | T | Click replay inflates clicks or spend | Unique `(decision_id, kind)`; replay returns the same destination, no new event | **Click replay** |
| T-AD-08 | T | A click without a prior valid impression, or instantly | Dependency and dwell check | Click-ordering test |
| T-AD-09 | T | Concurrent decisions overspend a budget | Atomic conditional reservation; `CHECK` | **Budget bypass** (N concurrent against a small budget; also budget lowered below spend; edited campaign dates) |
| T-AD-10 | T | Concurrent or repeated finalizer runs duplicate billable events | Unique `(decision_id, kind)`; idempotent finalizer; advisory lock | **Duplicate billing records** |
| T-AD-11 | T | Invoice generation counts a billable event twice or after a correction | Link table unique per event; invoices derived and recomputable | Invoice-reconciliation test |
| T-AD-12 | T | A correction rewrites history or is self-approved | Append-only; requester ≠ approver; threshold | Correction-authority test |
| T-AD-13 | T | A creative changes after approval, or a destination is swapped | Immutable versions; delivery reads the approved version id; destination resolved server-side | Version-immutability test |
| T-AD-14 | T | A fraudulent creative (impersonation, prohibited content, misleading claim) is approved or slips through | Mandatory review; reason codes; report-this-ad; periodic checks; suspension | **Fraudulent creatives** (reviewer rejection fixtures; a report-to-suspension path) |
| T-AD-15 | T | An unsafe destination: `javascript:`, `data:`, `file:`, `http:`, userinfo (`https://a@evil`), IP literals, localhost, private ranges, shorteners, open redirectors, homograph/punycode, over-long, control characters | Strict validator; typed in-app destinations; no redirects; normalised host recorded; external flag closed | **Unsafe URL destinations** (a table of hostile inputs, plus a mutation check) |
| T-AD-16 | E | A reviewer bypasses review: approves own advertiser's campaign, or an advertiser member holds a grant | Grants exclude members; SoD checks; claim then decide | **Privileged review bypass** |
| T-AD-17 | E | A campaign becomes `active` without approval, an unverified advertiser delivers, or a suspended campaign resumes | Server-only state machine; eligibility predicate re-evaluated at every decision | State-machine and eligibility tests |
| T-AD-18 | I | Advertiser results reveal individuals (small cells, drill-down, differencing across date ranges) | Suppression below 20, coarse bins, post-hold delay, bounded range and granularity, no account fields | **Sensitive analytics leakage** (differencing test) |
| T-AD-19 | I | Console analytics or exports expose viewer identifiers | Aggregates only; scoped by grant; reads audited | Console-scope test |
| T-AD-20 | I | Logs or audit contain MACs, consent details, creative URLs, free text | Redaction by design; id-only audit | Log and audit content test |
| T-AD-21 | I | Existence disclosure of campaigns or decisions through errors or timing | Uniform 404; constant-shape impression and click answers | Existence-disclosure test |
| T-AD-22 | T | **Ad events reach Points or Engagement** (TM-030) | No import, table, queue or key in common; Points consumer allowlist; ad kinds rejected | **No-Points test** (static scan both ways plus runtime zero-entry test) |
| T-AD-23 | I | Ads delivered or measured without consent, or after withdrawal | Gateway envelope plus service check; flags refuse start without consent source | Consent-enforcement test |
| T-AD-24 | I | Tracking creeps in: advertising ID, device fingerprint, location, behavioural targeting | No such columns or inputs; targeting allowlist | No-PII schema and no-SDK dependency test |
| T-AD-25 | S | A sponsored item is made to look organic (no label, hidden label, video-card style) | Server `sponsored` field; label mandatory in the client; layout test; creative text cannot imitate labels | Label and layout tests; reviewer rule |
| T-AD-26 | T | Click-farm or bot rings (self-interaction, concentration, metronomic timing) | IVT rules; hold; fraud queue | IVT rule tests with synthetic traffic |
| T-AD-27 | T | Advertiser team members click their own ads | Self-interaction exclusion | Self-interaction test |
| T-AD-28 | D | Decision flooding exhausts budget or the service ("budget bombing") | Per-account decision rate limit; reservations expire; unreported decisions released; hoarding rule | Flood test |
| T-AD-29 | D | Event ingestion floods the database | Per-account and per-session bounds; constant-time reject; duplicates in counters, not rows | Ingestion-bound test |
| T-AD-30 | D | Ad outage slows or blocks the feed | Client timeout then omit; organic never waits | Fallback test |
| T-AD-31 | E | A real charge or payment path appears | Guard test on routes and imports | **Billing guard** |
| T-AD-32 | E | A network SDK or adapter is activated | Dependency and registry guard with approval constant | SDK guard |
| T-AD-33 | R | An approver denies a decision | Append-only decisions and audit in the transaction | Audit-per-state-change test |
| T-AD-34 | T | Clock tricks to bypass schedule, hold window or expiry | Server time only | Clock-independence test |
| T-AD-35 | E | Console routes reachable without MFA or the right grant | Route-security matrix | Console route test |
| T-AD-36 | S | A claimed Business association is false | Signed Business check; reviewer verification | Association test |

## 3. Residual risks

| Risk | Treatment |
| --- | --- |
| Modified client fabricates plausible events | Server decisions, timing, volume, statistics, hold window; attestation later; stated in policy §3.5 |
| Real provider and network behaviour unknown | No network in Phase 8; provider constraints list unknowns |
| Reviewer error or collusion | Grants, SoD, audit, report path; cannot be removed by code |
| Consent law unconfirmed | Default fail-closed; legal blocker |
| Capacity and database role model unproven | DR-AD-05 |
| Differencing attacks on aggregates | Suppression, coarse bins, delay; reviewed in analytics tests |
