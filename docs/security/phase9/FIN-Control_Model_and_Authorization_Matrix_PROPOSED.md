# Finance — control model and authorization matrix (proposed)

**Status: PROPOSED — not approved.** 25 November 2026. This is the control model DR-FIN-05 asks the owner to approve. Until it is approved, no financial write path may be enabled, and the instruction applies in its strictest form: **no person may create, approve and release the same financial transaction.** Counts of approvers below are *control design*, not financial values; they follow the approved baseline in DOC-004 ("two distinct approvers for payout release; cannot self-approve") and the planning handbook ("dual approval").

## 1. Principles

1. **Authority is Finance-owned grants**, not Identity roles. A grant can be held only by an administrator account with MFA. An ordinary administrator holds **no** finance grant by default.
2. **Maker, checker, releaser.** Preparing, approving and releasing are three different capabilities held by three different accounts for any one transaction.
3. **Mutually exclusive grants.** Per account: `fin_preparer`, `fin_approver`, `fin_releaser` are pairwise exclusive; `fin_policy_author` and `fin_policy_approver` are exclusive; `fin_auditor` excludes every other finance grant; `fin_reconciler` excludes `fin_approver` and `fin_releaser`. Enforced when granting **and** re-checked at every action.
4. **Per-transaction distinctness.** On one transaction, the set {preparer, approver 1, approver 2, releaser, payee} must contain distinct accounts; enforced by database constraints on the approval rows and re-checked in the transaction.
5. **Payees hold no finance grant.** An account that is a payee (creator or business owner) cannot hold any grant, and a grant holder cannot be a payee (conflict of interest). A conflict is refused and reported.
6. **Grant management needs two administrators** (requester ≠ approver, step-up), is audited, and an administrator cannot grant themselves.
7. **Freeze is asymmetric.** Any `fin_approver`, `fin_fraud` holder or administrator can freeze payouts (safe direction) alone; lifting a freeze needs two distinct approvers.
8. **Every approval is per transaction and per version.** An approval references the exact content hash of what it approves; if the object changes, the approval is void.
9. **Server-side only.** Roles, grants and object ownership are resolved on the server per request; the client never supplies actor, payee, amount basis or role. Payee endpoints are `/me/...` with no id parameter, so there is no payee identifier to tamper with.
10. **No break-glass.** There is no override or emergency path that bypasses these controls.

## 2. Grants

| Grant | May | May not |
| --- | --- | --- |
| `fin_policy_author` | Draft and submit policy versions | Approve any policy; hold any other grant |
| `fin_policy_approver` | Approve or reject a submitted policy version (needs independent accountant evidence reference) | Author; approve a policy they edited |
| `fin_preparer` | Record revenue manually (statement lines without an API), prepare adjustments, trigger a period close request, prepare payout batches, prepare exception resolutions | Approve or release anything; see payout destinations in full |
| `fin_approver` | Approve allocation runs, adjustments (as approver 1 or 2), payout requests (approver 1 or 2), holds release, exception resolutions | Prepare or release the same transaction; approve their own prepared item |
| `fin_releaser` | Release an approved payout batch to the sandbox (or live, if ever authorized) provider adapter | Prepare or approve |
| `fin_reconciler` | Run and review reconciliations, open exceptions | Post adjustments or approve |
| `fin_fraud` | Place and review fraud holds; freeze | Release holds alone; approve payouts |
| `fin_auditor` | Read-only access to ledger, statements, audit reports, policy history | Any write; any other grant |

## 3. Transaction control matrix

`P` prepares/initiates · `A1`, `A2` distinct approvers · `R` releases · `S` system (deterministic job, no human discretion) · `—` not involved. "Distinct" means different accounts.

| Transaction | Initiated by | Approvals | Release / execution | Notes |
| --- | --- | --- | --- | --- |
| Policy version | `fin_policy_author` | `fin_policy_approver` + independent accountant evidence | Effective on `effective_from` (S) | Author ≠ approver |
| Manual revenue record | `fin_preparer` | `fin_approver` (one) | S posts T1 | Preparer ≠ approver; unique provider reference |
| Source statement import | S (sandbox/adapter) | Reconciliation by `fin_reconciler` | S | No human enters amounts |
| Business event posting (T3, T4, invoice facts) | S from signed events | — (verified by source authority and idempotency) | S | Only allowlisted sources and kinds |
| Reconciliation exception resolution | `fin_preparer` | `fin_approver` | S posts adjustment or waiver | Reconciler cannot approve |
| Period close | `fin_preparer` requests | `fin_approver` | S closes | No reopen |
| Allocation run | S computes at close | `fin_approver` (one, ≠ the person who requested the close) | S posts T5 | Deterministic; reviewer sees input hashes and outputs |
| Hold placement | `fin_fraud` or S rule | — | S | Safe direction |
| Hold release | `fin_fraud` or `fin_preparer` requests | `fin_approver` | S posts T6 | Requester ≠ approver |
| Adjustment | `fin_preparer` | `fin_approver` **A1** and **A2** (two distinct) | S posts T10 | Preparer ≠ A1 ≠ A2; payee excluded; no amount threshold in design |
| Payout request | payee (self only), subject to system eligibility | `fin_approver` **A1** and **A2** | `fin_releaser` releases (distinct from A1, A2 and any preparer) | Payee ≠ any actor |
| Payout cancellation before release | payee or `fin_approver` | — | S | After release only the provider path applies |
| Failed or returned payout | S from verified provider event | `fin_approver` to re-queue or write off | S posts T9 | A retry is a new approval cycle |
| Freeze | any `fin_approver`, `fin_fraud`, administrator | — | S | Asymmetric |
| Lift freeze | `fin_approver` | second `fin_approver` | S | Distinct |
| Grant or revoke finance grant | administrator | second administrator (step-up) | S | Not self; exclusivity checked |
| Statement read (staff) | `fin_auditor`, `fin_approver` (scoped) | — | — | Reads audited |

## 4. Object-level authorization for payees

| Operation | Payee (creator or business owner) | Staff | Others |
| --- | --- | --- | --- |
| Earnings overview, revenue history, allocations, statements | **own only** (resolved from the session; no id supplied) | auditor and scoped approvers via console | 404 / no route |
| Payout destination add, change, remove | own, **step-up**, verification in sandbox | masked view for preparers; full view for no one in the console | — |
| Payout request, cancel | own, subject to eligibility; one open request per payee unless policy allows more | approval path | — |
| Dispute open | own allocation or statement only | finance reviewer decides | — |

## 5. Separation-of-duties conflicts the system must refuse (each is a test)

| Conflict | Refused at |
| --- | --- |
| Same account prepares and approves | approval write |
| Same account is A1 and A2 | approval write (unique per transaction) |
| Releaser also approved or prepared | release |
| Approver is the payee | approval write; also grant assignment |
| Grant holder becomes a payee | payee onboarding |
| Account holds two exclusive grants | grant write and every action |
| Administrator grants themselves | grant write |
| Policy author approves the version | policy approval |
| Approval reused after the object changed | approval check against content hash |
| Replay of a decision with a new key on a decided object | state machine |
| Operation by an account with MFA lapsed or step-up missing | envelope check |

## 6. Console access

All finance pages require MFA, a specific grant per page, and answer 404 to an authenticated administrator without that grant (so grant existence is not revealed). Forms use the Business claim, confirm, decision pattern (a double submit records once). The console never shows a full payout destination or a creator's identity beyond what the page's task requires; statements are viewable only by `fin_auditor` or scoped approvers and every view is audited.
