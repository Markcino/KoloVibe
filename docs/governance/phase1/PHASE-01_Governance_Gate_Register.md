# Phase 1 governance gate register (Task 5)

**Established 27 November 2026 at `1c706ce`.** It reconciles every approval gate on record into seven categories, so nothing already approved is asked again and nothing unapproved is assumed. Source registers stay authoritative for detail: [Decisions A to J](../../planning/Owner_Decisions_A-J_2026-11-25.md), [DOC-209 consolidated open decisions](../../architecture/DOC-209_Consolidated_Open_Decisions.csv), [DOC-207 ADR register](../../architecture/DOC-207_ADR_Register.csv), the [Business](../../architecture/business/BIZ-Owner_Decision_Register_PROPOSED.md), [Events](../../architecture/events/EVT-Owner_Decisions_Required_PHASE7A.md), [Advertising](../../architecture/advertising/AD-Owner_Decisions_Required_PHASE8A.md) and [Finance](../../architecture/finance/FIN-Owner_Decisions_Required_PHASE9A.md) decision documents.

## 1. Already approved for development (not asked again)

| Approval | Record |
| --- | --- |
| Full-product scope: the 18 capability areas, Flutter for every non-privileged role, privileged console only | Mandate, 27 November |
| Decisions A (edit re-review), B (legal acceptance), C (privacy mechanism), D (backup and alerting mechanism), E (copyright), F (creator measures), G (step-up), H (Events scope), I (Advertising scope), J (Finance owns the one ledger; points non-cash; sandbox only) | Owner decisions A to J, 25 November |
| Public web: static policies, account-deletion page and app-link association files only | Rulings of 25 and 26 November; mandate section 3 |
| SIM-02 sharing through app links with store fallback | 26 November |
| Business design package (#218) and its recorded answers | Business approval record, 24 November |
| ADR-013 v1.0 client authentication and sessions | ADR-013 |
| Architecture constraints (Django, Flutter, PostgreSQL, RabbitMQ not Redis, R2 and FFmpeg, Swarm, host Nginx, Cloudflare ingress) | Mandate section 3 |

## 2. Decisions Phase 2 needs (mandatory exit criterion of Phase 1)

> **Owner ruling, 27 November 2026, 11:31 UTC.** Mark Gbalazeh (@Markcino) chose **"Approve all as recommended"** on the decision card "Approve the Phase 2 decisions GD-01 to GD-08 as recommended?". GD-01 to GD-08 are **APPROVED** with the recommended option in each entry below: GD-01 (a), GD-02 (a), GD-03 (a), GD-04 as stated, GD-05 (a), GD-06 (a), GD-07 (a), GD-08. This approves the structure for development. It sets no money, legal, provider or retention value, and authorizes no deployment or live activation.


These are structural. Phase 2 cannot produce approved ADRs and contracts without them. Each recommendation reuses the existing PROPOSED design package; none invents a value.

### GD-01 Finance bounded context and ledger (DR-FIN-02, DR-FIN-03, DR-FIN-07)

- **Blocking requirement:** FP-FN-01 (FN-R-001 to FN-R-012); #304, #313.
- **Why:** every money-touching area (Events, Advertising, payouts) posts to it.
- **Options:** (a) new `finance` service, own schema and role, double-entry append-only hash-chained journals in integer minor units, `sandbox` and `live` books with live refused by a constant; (b) ledger tables inside an existing service.
- **Recommended:** (a). It is Decision J's single-ledger rule made concrete and keeps money out of other services' databases.
- **Security:** a separate role and schema limit blast radius; live book blocked in code. **Financial:** no money moves; sandbox only. **Operational:** a 10th deployable needs capacity (#274). **If delayed:** Events, Advertising and payouts cannot be designed.
- **Approval wording:** "I approve GD-01 option (a): a new Finance service with its own schema, double-entry append-only ledger, sandbox book only."

### GD-02 Events and Advertising bounded contexts (DR-EV-02, DR-AD-02)

- **Blocking requirement:** FP-EV-01, FP-AD-01; #304, #318, #321.
- **Options:** (a) two new services, `events` and `advertising`, each with its own schema, posting money only to Finance; (b) fold Events into Business; (c) fold Advertising into Content or Engagement.
- **Recommended:** (a), matching the mandate's twelve-service list. **Security:** organizer and advertiser authority stay isolated. **Financial:** neither keeps a ledger (Decision J). **Operational:** two more deployables (#274). **If delayed:** Phases 6 and 7 cannot start.
- **Approval wording:** "I approve GD-02 option (a): separate Events and Advertising services, posting all money to Finance."

### GD-03 Notifications placement

- **Blocking requirement:** FP-NT-01; #304, #309.
- **Options:** (a) an Identity-owned notification module with its own dispatcher process and database role, consuming events from every service; (b) a new `notifications` service (a 13th deployable); (c) each service sends its own messages.
- **Recommended:** (a). Identity already owns contact addresses, `NotificationPreferences` and the mail sender, so no address data is copied; a separate role limits Identity's exposure; the mandate asks for no new service without justification. (c) duplicates delivery logic.
- **Security:** push tokens stay with account data; dispatcher role cannot read credentials. **Financial:** provider costs for push and email at volume. **Operational:** one more process, not a service. **If delayed:** events, finance statements and moderation outcomes have no way to reach people.
- **Approval wording:** "I approve GD-03 option (a): notifications as an Identity-owned module with its own dispatcher."

### GD-04 Authority model for organizers and advertisers (DR-EV-04, DR-AD-04, DR-FIN-06, DR-FIN-05)

- **Recommended:** membership-based authority in each context (the Business pattern), Finance grants with maker-checker-releaser separation, all sensitive actions behind the Decision G step-up. **Approval wording:** "I approve GD-04: membership authority for organizers and advertisers and maker-checker-releaser Finance grants."

### GD-05 Image pipeline for event images and ad creatives (DR-EV-17, DR-AD-06)

- **Options:** (a) extend Content's media pipeline with an image path (R2 plus a hardened image processor); (b) a pipeline owned by each new service. **Recommended:** (a), one hardened media path (DRY, one scanning surface). **Approval wording:** "I approve GD-05 option (a)."

### GD-06 Consent store (DR-AD-07, DR-AD-40 mechanism)

- **Options:** (a) Identity owns a purpose-based consent record (extending marketing consent); (b) Advertising owns it. **Recommended:** (a); consent is account data and Decision B already keeps it there. Purposes and wording stay legal decisions. **Approval wording:** "I approve GD-06 option (a)."

### GD-07 Comments (#135)

- **Options:** (a) build comments with reporting, moderation and creator controls (turn off, delete, block); (b) keep comments out of the full product.
- **Recommended:** (a). "Social engagement" is a mandate area and comments are its main missing piece; they reuse the Moderation report and decision workflow. They add moderation load and abuse risk, so they ship with rate limits, report-to-hide thresholds as owner values, and Figma frames first. No code until decided.
- **Approval wording:** "I approve GD-07 option (a): comments with moderation and creator controls." or "I choose GD-07 option (b): no comments."

### GD-08 Phase plan

- **Recommended:** approve the eleven-phase plan in the [tracker](../PHASE_EXECUTION_TRACKER.md#3-phase-plan). **Approval wording:** "I approve the Phase 1 to 11 plan."

## 3. Missing business rules (needed before the phase that builds them; configurable with no default until then)

| Area | Decisions | Needed by |
| --- | --- | --- |
| Points general release | ADR-019, DEC-003 (#137) | Phase 3 |
| Privacy | Retention values (ADR-020, RV2-04, #136), export retrieval window, withheld export categories, deletion-completion email (GD-12) | Phase 3 |
| Business | DR-BZ-08 ownership transfer, DR-BZ-25 data after closure, DR-BZ-28; evidence checklist, categories, review minimum | Phase 4 |
| Finance | DR-FIN-10 to DR-FIN-22 (currencies, source classes, recognition, periods, pool, basis, eligibility, holds, payout rules, onboarding, clawbacks, disputes, statements); revenue-share percentage | Phase 5 |
| Events | DR-EV-10 to DR-EV-31, DR-EV-40, DR-EV-41 | Phase 6 |
| Advertising | DR-AD-10 to DR-AD-35 | Phase 7 |
| Dead letters | RV2-03 values (GD-13: retry ceiling 10, 14 days, bounded length, proposed) | Phase 3 |

## 4. Legal and regulatory approval

Terms, privacy notice, copyright policy and contact, creator enforcement policy (#165); retention and legal holds (#136); advertising consent purposes and minors (DR-AD-40); payment and payout regulatory position in Liberia (DR-FIN-04 independent accounting approver, DR-EV-22 KYC); store data-safety and privacy declarations (FP-DST). **Recommendation:** engage qualified counsel before Phase 5; until then texts stay marked "pending legal review".

## 5. Infrastructure approval

CPU and memory for new deployables (#274, #283; spending authorization is the owner's); broker plan for erasure queues (#273); Points key correction (#271, #281); branch protection ruleset (#142, #279); mTLS versus per-caller keys (#138); observability platform and alert channel (OD-08, #145); backup hosting, RTO and RPO (ADR-016, #144); OpenSSL scan exception **expires 5 December** (#143).

## 6. External provider approval

Payment provider (GD-20; DR-EV-22, DR-FIN-30); payout provider (DR-FIN-31); Google AdMob account and products (DR-AD-36), after checking current Google policy; push providers (Firebase Cloud Messaging, Apple Push Notification service); Apple Developer and Google Play accounts and signing ownership (#166); static policy page hosting.

## 7. Staging activation and production activation

- **Staging activation:** every change since v0.542.1 (64 commits), Business, the 18 zero-replica worker services and any new service each need an approved operations plan. Nothing in Phase 1 changes staging.
- **Production activation:** NO-GO. Needs Phase 10 and 11 to pass, legal sign-off, provider approvals and an explicit owner go decision (#168). Live money, live ads and payouts each need their own separate approval (Decisions H, I, J).

## 8. Requirement-set approval (#307, added 27 November 2026 after the 12:13 UTC instruction)

Phase 1 passes when the owner approves these five sets. Approval of a set approves its requirements for development and its recommended options for the choices below. It does not approve a provider, an account, a value marked `[OWNER VALUE]`, live payments, live ads or store submission.

| Set | Open choices (recommendation in **bold**) |
| --- | --- |
| [FP-NT](../../requirements/FP-NT_Notifications_Requirements_PROPOSED.md) | NT-D1 Firebase project: **organization-owned**; NT-D2 marketing notifications: **none in first release**; NT-D3 recommended development values |
| [FP-PAY](../../requirements/FP-PAY_Payments_and_Payouts_Requirements_PROPOSED.md) | PAY-D1 provider: **sandbox adapter only until the owner names one** (GD-20); PAY-D2 business ad purchases: **outside the mobile apps only, confirm with both stores in writing** (Apple 3.1.3(g) names in-app boosts as IAP); PAY-D3 tickets: **provider payment sheet in the app, subject to written App Review confirmation**; PAY-D4 payouts: **written store confirmation before submission**; PAY-D5 values from the owner |
| [FP-GA](../../requirements/FP-GA_Google_Mobile_Ads_Requirements_PROPOSED.md) | GA-D1 **Google UMP**; GA-D2 **organization-owned AdMob account**; GA-D3 **no ads to minors or unknown-age accounts**; GA-D4 **banner and native in feed only**; GA-D5 **test units until separately authorized** |
| [FP-DST](../../requirements/FP-DST_Store_Distribution_Requirements_PROPOSED.md) | DST-D1 **organization developer accounts**; DST-D2 **host the existing static policy site on the KoloVibe domain** (operations approval); DST-D3 age rating from owner and legal review; DST-D4 **Crashlytics after disclosures**; DST-D5 **written store payment confirmations before Phase 10 submission** |
| [FP-CM](../../requirements/FP-CM_Comments_Requirements_PROPOSED.md) | CM-D1 **recommended development values**; CM-D2 anonymous reads **off**; CM-D3 creator removal of comments on their own video **not appealable** (platform removals stay appealable) |
