# Phase 5 — administration web console: results

**Date:** 23 November 2026. **Base:** `main` at `c572cee`. Repository changes only. No staging access, no deployment, no merge, no live infrastructure change. The console stays the protected administrator and moderator console: no public pages were added.

## Gap analysis
The console already implements nearly every capability on the list (sign-in with privileged MFA, server-validated sessions, dashboard, creator find/invite/review, moderator invitations, assignment management, video, report and appeal review with decisions, points review, audit browsing, own account, logout). Two real gaps and one testing gap remained, and one capability needs a decision.

## Pull requests (none merged)
| PR | What | Type |
| --- | --- | --- |
| [#213](https://github.com/Markcino/KoloVibe/pull/213) | **Route security matrix.** Walks the URL table, so an unclassified route fails. For every privileged route: anonymous (all methods), non-privileged account, password-only/MFA-pending, MFA flag not true, idle and over-age sessions; all 12 state-changing routes without and with a foreign CSRF token; safe-method purity; administrator-only pages. The gateway is a recorder, so every refusal also proves no business request was made. | test |
| [#214](https://github.com/Markcino/KoloVibe/pull/214) | **Fraud review page.** The dashboard showed only the first five holds and never used the cursor or linked to the video. `/admin/fraud/` lists all active holds in the caller's gateway-scoped list, 20 per page, linked to video review; read-only; validated query and response. | feature |
| [#215](https://github.com/Markcino/KoloVibe/pull/215) | **Layout and accessibility checks** on rendered pages and the stylesheet (landmarks, skip link, names, labels, table captions and scope, data-label reflow, keyboard-reachable scroll regions, CSRF on forms, breakpoints, visible focus, 48 px targets, reduced motion, contrast, forced colours). | test |

Tests: web suite 101 before; 112 with #213 and #215, 109 with #214 (each branch is separate). Mutation checks for each: unguarding a route, removing both MFA-flag layers, removing the creators role check, removing response validation, and removing labels, scope, scroll-region names and touch targets each fail the matching tests.

## Findings
1. **Administrator-only pages use two patterns.** `creators` and the assignment views refuse a moderator in the console itself (403, no gateway call) as well as in the owning service; `team` delegates entirely to the gateway and Identity and the console surfaces their refusal. Both are now pinned. (My first description of #213 called all five delegated; that was wrong and is corrected in the PR and its write-up.)
2. **MFA is checked in two independent layers** (the view guard and the server-session validator). A test that mutates one layer alone passes by design; the matrix mutates both.
3. **Decision replay, cross-account access, assignments and audit** were already covered by existing tests (intent bound to actor, session, target and expiry; stable idempotency keys; cross-resource gateway denials; assignment grants and revocations; audit filters and pagination); I added no duplicates.

## Not done, and why
- **Creator invitation management (list outstanding invitations, revoke).** There is no approved contract. Listing is a small additive read, but revocation needs a new application state (a migration) and audit semantics; the console must not invent either. Proposal for the owner: approve "list invited accounts" (read-only) and decide whether revocation is wanted.
- **Fraud hold clearing or creation**, **points award or reversal execution**, **audit retention and export**: no approved rule or backend operation; the pages stay read-only.
- **Accessibility acceptance.** Only static checks ran. No screen-reader pass, browser check at real widths or keyboard walk-through was performed.
- **Staging acceptance.** Nothing was run against the deployed console.

## Process correction
Two earlier pull requests (#205 Phase 2 results and #210 Phase 3 results) were stacked on other docs branches and were merged into those branches after the base had already merged, so **their results documents and tracker sections never reached `main`**. They are restored in this documentation pull request, together with the Phase 4 and Phase 5 tracker sections. Documentation pull requests from now on target `main`.

## Owner actions
1. Review #213–#215; none is merged.
2. Decide creator invitation listing and revocation, fraud hold clearing, and the points and audit items above.
3. Run the console negative-path checks on staging and an accessibility pass when you choose, and tell me the results to record.
4. Earlier items remain open: approve #197, run the #198 database report, send the v0.373.1 commit.
