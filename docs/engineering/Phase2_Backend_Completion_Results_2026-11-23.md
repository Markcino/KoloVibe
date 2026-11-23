# Phase 2 — complete R1 backend services: results

**Date:** 23 November 2026. **Base:** `main` at `bb79e1a`. Repository changes only: no deployment, no merge, no staging or AWS access, no migration applied, no RabbitMQ permission change. Tracker: [Phase 2 section](R1_Application_Tracker.md) (this PR is stacked on #192, which holds the tracker).

## Method
The contract came first. DOC-205 declares 84 paths; every public operation is already served by the gateway, and Phase 1's contract test proves it. So no endpoint was "missing" against the approved contract. The gap analysis therefore looked for behaviour a finished backend still lacks: unbounded storage, unimplemented query capability recorded in client parity notes, and write paths with no approved rule. Nothing was invented where the approved documents are silent.

## Implemented (three pull requests, none merged)

| PR | Service(s) | Gap | Result |
| --- | --- | --- | --- |
| [#202](https://github.com/Markcino/KoloVibe/pull/202) | all eight (shared verifier) | Every internal request stored a replay-protection nonce that was never deleted | Bounded purge of nonces older than 10 minutes (the signature window is 60 s, checked first), at most 5,000 rows per minute per process, failure-tolerant. 4 shared tests × 8 services; PostgreSQL SQL verified |
| [#203](https://github.com/Markcino/KoloVibe/pull/203) | identity | `LoginThrottle` rows are created by anonymous login attempts and, like one-time codes, MFA challenges, replay markers and finished sessions, were never deleted | `retention.py` with grace periods, opportunistic and command-driven bounded purge; replay detection preserved; accounts, security events and audit rows untouched. 8 new tests, suite 147 |
| [#204](https://github.com/Markcino/KoloVibe/pull/204) | content, gateway, DOC-205 | M-040 creator library had no search (parity gap) | Additive `q` on `GET /creators/me/videos`, own non-deleted videos only, composes with `state` and `cursor`; contract updated. New tests; content 124, gateway 184 |

All three: no breaking change, no migration, no new audit event kind (a new kind needs a coordinated Audit deployment), no fake data, ownership and authorization unchanged.

## Capability review by service (evidence-based)

| Service | Assessment | What remains |
| --- | --- | --- |
| Identity | Registration, six-digit verification, login, refresh rotation and replay revocation, logout, password reset and change, sessions, preferences, profile, privileged MFA with TOTP replay protection, moderator invitations all implemented and tested (Phase 1 added regression guards and the account-level MFA lock, [#197](https://github.com/Markcino/KoloVibe/pull/197)). Retention added here. | Account deletion and data export: intake only; policy is ADR-020 (blocked by approval) |
| Creators | Onboarding, invitations, reviewer decisions, profile edit, search, upload eligibility all present | Staging activation and end-to-end journey (owner) |
| Content | Drafts, metadata, R2 upload, FFmpeg processing, publication controls, public search and now own-library search, ownership 404s, soft delete | Post-approval edit policy (R-03); live R2/FFmpeg evidence (owner) |
| Engagement | Likes, follows, shares, watch sessions, qualification, fraud holds, outbox with idempotent inbox in Points | Live RabbitMQ evidence; no change to permissions made |
| Points | Append-only ledger, balance, history, withholding by daily cap, receipts with idempotent inbox | **Reversal/adjustment execution: no approved rule, so none was built** |
| Moderation | Reports, queues, assignments, decisions, restrictions, notices, appeals, copyright notices | M-078 appeal-submit decision; SLA/routing model |
| Audit | Authenticated ingest, grant-scoped redacted reads, append-only guards | Retention, redaction and legal-hold policy (OD-08, ADR-017) |
| Gateway | All DOC-205 routes, service identity, default-deny and role matrix (Phase 1 tests) | Single contract source (B-13) |

## Verification
Suites run locally after the changes: gateway 184, identity 147, creators 76, content 124, engagement 71, points 68, moderation 71, audit 48 (the figures in each PR are the run at that branch); drift test OK; DOC-205 validates. CI results are on each pull request. Flutter was not run.

## Blocked by approval (not implemented, deliberately)
Points reversal execution; audit retention and legal hold; post-approval metadata re-review; M-078 appeal submission; account deletion and data export; unverified-account clean-up; business, event, advertising and payment modules (Phase 0 B-19). Each needs an owner decision recorded, and the money-related items also need separate provider and legal approvals; none was started.

## Owner decisions and actions
1. Review the three pull requests; #203 and #202 touch security tables and the shared verifier, so a deployment note: the runtime login needs `DELETE` on those tables (true today).
2. Decide the blocked policies above, starting with points reversal (it gates fraud review and the creator ledger's `reversed` figure) and the post-approval edit policy.
3. Phase 1 items still open: approve #197, run the #198 report, supply the v0.373.1 commit.
4. Not merged: do not merge or deploy until you decide.
