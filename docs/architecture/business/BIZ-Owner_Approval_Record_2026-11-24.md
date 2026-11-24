# Business module — owner approval record (Phase 6A decisions)

**Recorded 24 November 2026 from the owner's answer in the Phase 6B session.** Decision-maker: Mark Allen Gbalazeh (@Markcino), the accountable owner.

## What was decided

Asked how to proceed because [PR #218](https://github.com/Markcino/KoloVibe/pull/218) (Phase 6A) was still an open draft with all 26 decisions open, the owner chose **"Approve all 26 as recommended"**: every recommendation in the [decision register](BIZ-Owner_Decision_Register_PROPOSED.md) becomes policy. Evidence is the owner's answer to that question in the session. **The owner then reviewed and merged PR #218 (the Phase 6A documents, head `1dc425c`) at 2026-11-24T10:08:56Z**, which is the GitHub record for the design itself. This record, the registration-grant defaults and everything in Phase 6B were added afterwards and are in a separate pull request.

This record replaces the "Open" status of DR-BZ-01 to DR-BZ-26 with **Approved as recommended** and does not change their wording. It makes ADR-BIZ-001 and the requirements baseline approved *as written*.

## What the approval does not supply

The register asked the owner to supply some content that "approve as recommended" cannot contain. Phase 6B therefore ships **mechanisms** and reports these as blockers rather than inventing values:

| Item | Needed from the owner | Affects |
| --- | --- | --- |
| Verification evidence checklist and accepted methods (DR-BZ-04, 19) | The written checklist, document types, validity period, review target | B2 |
| Category taxonomy and county/city lists (DR-BZ-10) | The initial lists | B3 |
| Public-field warning and notice copy (DR-BZ-09, privacy document section 8) | Wording | B3, B5 |
| Retention periods and legal-hold rules (DR-BZ-18) | Periods per category | B2, B5 purge jobs |
| Legal review outcome (DR-BZ-23) | Reviewer and result | B2, B5 |
| Review-eligibility details (DR-BZ-15): minimum account age, minimum review count to show an average | Numbers | B5 |
| Purpose-bound step-up proof in Identity (P6B-04) | Design approval of an Identity change | Owner contact change, closure, ownership transfer, staff removal |
| Numeric abuse limits (DR-BZ-22) | Confirmation of the starting values in `services/business/service/limits.py` | all |

## Starting values recorded as configuration (DR-BZ-22, DR-BZ-03)

Registration is invitation-only for the pilot cohort; 3 open businesses per account; 10 active staff and 10 pending invitations per business; staff invitation codes valid 72 hours; registration 5 attempts per day, staff invitations 20 per day, code redemption 10 attempts per hour per account. These are conservative initial values for the owner to confirm or change in one file.

## Unchanged restrictions

Production remains NO-GO. No capability is enabled on staging or production; no AWS or staging change was made; no payments, ticketing, live streaming or advertising. Phase 6C must not begin without separate approval.

## Addendum — DR-BZ-21 formal decision (Phase 6A reconciliation, 24 November 2026)

The owner restated the client decision more strictly in the Phase 6A instruction and asked that it be recorded formally: **all business owners, customers and business staff use Flutter mobile; only administrators and moderators use the protected Django web dashboard; there is no public website and no business web portal.** This tightens the earlier "approved as recommended" entry for DR-BZ-21 (option A) and rejects options B and C. The record is in the [decision register](BIZ-Owner_Decision_Register_PROPOSED.md#dr-bz-21--where-business-owners-work) and the consequences are in the [client architecture](BIZ-Client_Architecture_DR-BZ-21.md). It adds no other approval; DR-BZ-27 and DR-BZ-28 are new and **open**.
