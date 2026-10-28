> Source: DOC-006_Engagement_Points_Rules_DRAFT.docx (text export; original formatting, formulas and embedded images are not included). Original review status is retained.

<PARSED TEXT FOR PAGE: 1 / 2>
Engagement, Points and Revenue Business
Rules
DOC-006 | Proposed rule catalog; unapproved parameters clearly marked

Version 0.1 | 28 October 2026 | Status: Draft for stakeholder review. PRD and SRS v0.2 remain
approved baselines.

Rule ID                          Topic                            Requirement / decision
BR-001                           Advertising separation           Ad impressions, ad clicks and
                                                                  ad watch events never award
                                                                  points.
BR-002                           Qualified event                  Client-submitted playback
                                                                  evidence is untrusted; only
                                                                  backend decisions qualify an
                                                                  event.
BR-003                           Idempotency                      An event identifier can create
                                                                  at most one award; retries
                                                                  return the prior decision.
BR-004                           Self-engagement                  Creator self-views and
                                                                  coordinated self-interaction
                                                                  are excluded or held.
BR-005                           Abuse scoring                    Velocity, repeated
                                                                  accounts/devices and
                                                                  suspicious patterns trigger
                                                                  review or hold.
BR-006                           Versioned rules                  Qualification and points
                                                                  formula use versioned,
                                                                  auditable policy settings.
BR-007                           Points vs money                  Points are non-cash records;
                                                                  no conversion promise in the
                                                                  MVP.
BR-008                           Ledger integrity                 Append-only points entries;
                                                                  corrections are compensating
                                                                  entries, not silent edits.
BR-009                           Disputes                         Creators may appeal holds and
                                                                  reversals; decisions are
                                                                  attributable.
BR-010                           Revenue collection               Future eligible pool uses
                                                                  actual reconciled collected
                                                                  company revenue, not
                                                                  estimated ad impressions.
BR-011                           Financial segregation            Future monetary ledger
                                                                  separate from engagement
                                                                  and points ledger; double-
                                                                  entry and reconciliation.
BR-012                           Payout controls                  No cash disbursement until
                                                                  provider, legal, fraud,
                                                                  approval and independent
                                                                  security gates pass.
BR-013                           Copyright and policy             Only content with declared
                                                                  rights can be uploaded;
<PARSED TEXT FOR PAGE: 2 / 2>
                                                                     takedown and appeal
                                                                     available.
BR-014                            Privacy                            Minimize behavioral/device
                                                                     data, limit retention and
                                                                     prohibit sensitive tracking
                                                                     without lawful basis.



Decision parameters not yet approved
Parameter                         Proposed approach                  Approval status
Minimum watch threshold           Set using pilot research; avoid    Pending
                                  arbitrary fixed cash incentives
Repeat view window                Server-defined anti-replay and     Pending
                                  anti-farm limits
Points per view/like              Versioned formula and caps;        Pending
                                  no cash equivalence
Pending hold period               Risk-tiered; specify appeal        Pending
                                  window
Creator verification              Identity and rights review         Pending
                                  appropriate to risk
Revenue-share percentage          Only after collected revenue,      Deferred
                                  costs, reserves and legal
                                  review
Payout threshold/provider         Requires compliant provider        Deferred
                                  and treasury controls



Example qualification sequence
   Receive engagement event with authenticated subject, media ID, session ID and idempotency
    key.
   Check media approval, creator ownership, account status and consent/eligibility.
   Normalize telemetry and reject impossible/duplicate or prohibited events.
   Evaluate fraud signals; accept, hold or reject under a versioned ruleset.
   Create qualification decision transactionally; issue points entry once for accepted event.
   Maintain a read-only creator statement with explanation of pending and reversed entries.
   Audit any manual intervention; enforce reviewer independence and access control.



Acceptance tests
   Same event replayed 100 times yields no duplicate award.
   Self-view does not produce an eligible award.
   Ad impression and click callbacks produce zero points entries.
   Creator cannot alter points by API parameter manipulation.
   Reversal produces a new adjustment record and preserves original entry.
   Held event does not appear as settled/eligible points.