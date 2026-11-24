# Phase 6B · B5 — customer inquiries and reviews: results

Date: 24 November 2026. Local, disposable environments only. Builds on B1 to B4. Not independent assurance.

## Implemented

**Inquiries** (flag `business_inquiries`): a verified-email customer opens one conversation with a *listed* business; the business sees a pseudonymous label (`Customer N`), never an account id; unlisted, unknown, own-business, staff and **blocked** callers all receive the same 404 (a block is never disclosed). Thread ids are bound to the path business, staff can work the inbox but only owners can block, a conversation has a message cap, per-customer and per-business throttles count only real eligible attempts (so probing unlisted ids cannot spend a business's budget), and both sides can **confirm completion** once both have written, which is one route to review eligibility.

**Reviews** (flag `business_reviews`): the eligibility **basis** is derived from the proof supplied and stored on every review: `interaction_confirmed` (a thread both sides confirmed, bound to the author and business), `invited` (a business-issued single-use code, shown once, only a keyed digest stored) or `open` (unconfirmed, labelled). Owners, staff and the creator account are refused with the same 404 as an unlisted business. One review per author per business **ever** (withdrawal does not allow a second). Fraud signals hold a review instead of publishing it: a burst of reviews for one business, a burst by one author, or identical text anywhere on the platform. A held review is not public, not counted, and appears in the reviewer queue as a system fraud hold. Edits re-enter the checks. Withdrawal blanks the text at once and deletes the business response. The aggregate (count and sum) is recomputed from published reviews inside the same transaction as every change; the average stays hidden until the owner sets a minimum count. Authors are shown as `Reviewer N`.

**Owner response and abuse reports:** one response per published review, owner only; a business has **no** operation that hides, edits or removes a review. Any verified account can report a review, a response or an inquiry message, but only content it can see (published and listed, or a conversation it takes part in), not its own, once per subject. Reviewers (MFA, `review_queue` grant, not the reporter, not affiliated with the business) read the case (audited), then **remove** or **keep** (keep releases a fraud hold); decisions are idempotent and a decided report cannot be decided again.

## Verification run

| Check | Result |
| --- | --- |
| Business tests (SQLite) | 162 passed, 1 skipped (existing) — B5 adds 45 |
| Negative tests | eligibility one-answer 404; mass-assignment and bound table (15 invalid review payloads, 5 invalid decisions); proof tests (unconfirmed, foreign and cross-business threads indistinguishable; used, revoked, expired, other-business and unknown invitation codes indistinguishable; both proofs together rejected); holds for each signal; response/owner isolation across businesses; report visibility rules; reviewer role/MFA/grant matrix (a verification grant is not a review-queue grant); conflicted reviewer blocked; aggregate always equals recomputation |
| DOC-205 (+22 operations, rating added to the public detail) | valid OpenAPI 3.1; route-contract (6) and role-matrix (5) tests pass; anonymous list deliberately extended by `GET /businesses/{id}/reviews`; Gateway Business tests (14) pass |
| Disposable TLS PostgreSQL 16 | foundations suite passes for 9 services; `test_business_postgres.py`: 11 passed, adding: four concurrent reviews by one author produce exactly one (others 409) and one aggregate row; five concurrent reviews leave the aggregate equal to the published ratings; one invitation code is used once under a four-way race |
| Whole repository | all nine service suites pass; `makemigrations --check` clean for all; 446 `scripts/` tests pass; Bandit 0 medium/high; secret scan passes (it caught one test string that looked like credentials; rewritten) |

## Migration plan

`business/0006_inquiries` (three tables, partial-unique open thread per customer and business, state and author-kind checks) and `business/0007_reviews` (reviews, responses, invitations, aggregate, reports; unique review per author per business; rating 1 to 5; one open report per reporter and subject). Additive; applied only to disposable databases.

## Open items and deviations

1. **Moderation reuse (DR-BZ-17 option C) is not done.** Generalising the Moderation service from videos to business subjects is a change to a service in R1 acceptance that the owner said needs its own approval. B5 therefore uses a **Business-local report queue** built on the same grant, MFA, separation-of-duties and idempotency patterns. Migration to Moderation, restoration of wrongly removed content (needs a *different* reviewer than the remover), and **author/business appeals are not built**.
2. **Listing reports** are not accepted (no suspension action exists, DR-BZ-25).
3. **Policy values not supplied by the owner:** minimum review count for showing an average (hidden until set), edit window, author display form (pseudonymous labels used), account-age gate (the Gateway does not carry account age), hold thresholds (starting values in `limits.py`).
4. **No notification** is sent for inquiries, replies, reports or holds (DR-BZ-14).
5. **Retention:** nothing is purged automatically (DR-BZ-18); withdrawal blanks text immediately as the author's own deletion, but removed reviews and decided reports are retained until periods are approved. No export or erase operation exists yet (no privacy orchestration path).
6. Duplicate-text detection compares exact normalised text; it is not a similarity engine.
