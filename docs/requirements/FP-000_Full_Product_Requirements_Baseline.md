# FP-000 Full-product requirements baseline (PRD and SRS index)

**Status: ACTIVE INDEX, established in Phase 1 on 27 November 2026 at `1c706ce`.** It defines which requirement sets make up the full product and the state of approval of each. It links to the detailed requirements and does not copy them. The [full application mandate](../governance/Full_Application_Mandate_2026-11-27.md) is the authority for scope; this file is the authority for **which requirement document governs each area**.

Approval of a requirement set and authorization to build or activate it are separate. Owner decisions A to J ([record](../planning/Owner_Decisions_A-J_2026-11-25.md)) approve development scope for Business, Events, Advertising and Finance. They do not approve live money movement, live advertising, provider credentials or production publication.

## 1. How requirement IDs work

- The detailed requirement sets keep their own IDs (`PRD-F`, `FR`, `NFR`, `FN-R`, `EV-R`, `AD-R`, the Business reconciliation rows).
- Each feature in the [Phase 1 traceability matrix](../governance/phase1/PHASE-01_Feature_Traceability_Matrix.csv) has a full-product ID `FP-<area>-nn` that links to one or more of those detailed IDs.
- An area with no detailed requirement set has a new `FP-` set (section 3) that must be written and approved before its build phase (#307).

## 2. Requirement sets by area

| Area (mandate section 2) | Governing requirement set | Approval state | FP rows |
| --- | --- | --- | --- |
| Identity and account management | [PRD v0.2](platform_PRD_v0_2_scope_approved.md) PRD-F01, F02, F09; [SRS v0.2](platform_SRS_v0_2_scope_approved.md) FR-001 to FR-003, FR-017, FR-018, FR-021, FR-030; [ADR-013](../architecture/ADR-013_Client_Authentication_and_Session_Security_v1.0_APPROVED.md); Decisions B and G | Scope approved (DEC-001); detail is draft (#133); ADR-013 approved | FP-ID-01 to FP-ID-09 |
| Creator management | PRD-F03; FR-004; DEC-004; Decision F | Scope approved; detail draft | FP-CR-01 to FP-CR-03 |
| Video creation, upload, processing and playback | PRD-F04; FR-005 to FR-007; Decisions A and E | Scope approved; detail draft | FP-CT-01 to FP-CT-07 |
| Content discovery and social engagement | PRD-F05; FR-008 to FR-010 | Scope approved; detail draft. Comments have no requirement (#135) | FP-EN-01 to FP-EN-05 |
| Non-cash points and qualified views | PRD-F06, F07; FR-011, FR-012; [DOC-006](DOC-006_Engagement_Points_Rules_DRAFT.md); ADR-019 | Pilot parameters approved (DEC-003); general-release rules open (#137) | FP-EN-03, FP-PT-01, FP-PT-02 |
| Moderation, reporting and appeals | PRD-F08; FR-013, FR-014, FR-023 to FR-026; Decision E | Scope approved; detail draft | FP-MD-01, FP-MD-02, FP-CT-05 |
| Audit and accountability | PRD-F10; FR-015, FR-028; Decision D | Scope approved; detail draft | FP-AU-01, FP-AU-02 |
| Business discovery and management | [BIZ reconciliation](BIZ-Requirements_Reconciliation_PHASE6A.md) and [DOC-020](DOC-020_Business_Requirements_and_Scope_PROPOSED.md); [Business approval record](../architecture/business/BIZ-Owner_Approval_Record_2026-11-24.md) | Design approved (#218); extensions wait on DR-BZ decisions | FP-BZ-01 to FP-BZ-06 |
| Events and ticketing | [EVT requirements](EVT-Requirements_PRD_SRS_PROPOSED.md) EV-R-001 to EV-R-096 | Scope approved (Decision H); detail PROPOSED | FP-EV-01 to FP-EV-05 |
| Advertising and direct sponsorship | [AD requirements](AD-Requirements_PRD_SRS_PROPOSED.md) AD-R-001 to AD-R-075 | Scope approved (Decision I); detail PROPOSED | FP-AD-01 to FP-AD-04 |
| Google mobile advertising | PRD-F11 (test placements only); DR-AD-36; **FP-GA (to write)** | Scope approved (Decision I); requirements missing | FP-GA-01 |
| Finance and creator monetization | [FIN requirements](FIN-Requirements_PRD_SRS_PROPOSED.md) FN-R-001 to FN-R-084; Decision J | Scope approved (Decision J, sandbox only); detail PROPOSED | FP-FN-01 to FP-FN-05, FP-FN-07 |
| Payment processing, reconciliation and payouts | FIN F5; EV-R E5; **FP-PAY (to write)** | Sandbox development approved; provider and live activation not approved | FP-FN-05, FP-FN-06 |
| Notifications | **FP-NT (to write)**; referenced by DR-EV-18 and DR-FIN-42 | Capability named in the mandate; requirements missing | FP-NT-01 |
| Privacy and legal compliance | PRD-F09; FR-017; Decision C; ADR-020; owner rulings on policy and deletion pages | Mechanism approved; retention values and legal texts open (#136, #165) | FP-PV-01 to FP-PV-05, FP-ID-06 |
| Flutter Android and iOS applications | Standing directive; [mobile design coverage](../mobile-design-coverage.md); **FP-DST (to write)** for distribution | 108 R1 frames approved; no frames for new areas (#306) | FP-MB-01, FP-MB-02 |
| Administrator and moderator console | FR-030; standing directive | Scope approved | FP-WB-01 |
| Monitoring, security and disaster recovery | NFR set in SRS v0.2; Decision D; ADR-016, ADR-017, ADR-018 | Mechanism approved; values open | FP-OP-01 to FP-OP-07 |
| Excluded | Live streaming; any public website or portal beyond the static policy, deletion and app-link resources | Excluded by the standing directive and owner rulings | FP-X-01, FP-X-02 |

## 3. Requirement sets still to write (tracked in #307)

| Set | Covers | Must not invent |
| --- | --- | --- |
| FP-NT | In-app inbox, push (FCM, APNs), transactional email, preferences, quiet hours, delivery retries, per-event templates | Provider accounts, wording that needs legal review |
| FP-PAY | Provider interface, sandbox adapter, webhooks, reconciliation, refunds, chargebacks | Provider choice, fees, currencies, KYC thresholds |
| FP-GA | Google Mobile Ads placements, consent, test units, mediation stance | Ad unit ids, revenue terms; current Google policy must be checked first |
| FP-DST | Release signing, store listings, data safety and privacy labels, privacy manifest, staged rollout, kill switch | Store accounts, legal entity details |

## 4. What this replaces

DEC-001 (Release 1 scope) and the R1-only statements in the PRD and SRS v0.2 remain the historical record of the Release 1 boundary. Where they say Business, ticketing, advertising or payouts are deferred or out of scope, this baseline and the mandate apply instead. See the [archive register](../archive/ARCHIVE_REGISTER.md).
