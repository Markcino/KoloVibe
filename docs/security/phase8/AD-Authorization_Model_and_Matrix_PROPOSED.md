# Advertising — campaign authorization model and matrix (proposed)

**Status: PROPOSED — not approved.** 25 November 2026. Companion to the [API contract](../../architecture/advertising/AD-API_Contract_PROPOSED.md), the Business and Events matrices. Every operation names a row; the contract-reconciliation test enforces it.

## 1. Model

1. **Identity authenticates; Ads authorizes.** The Gateway forwards a signed envelope (actor, role, MFA, verified email, consent state, idempotency key). The client never supplies an advertiser, campaign owner, role or state.
2. **Object chain.** Every object is resolved `object → campaign → advertiser → active membership of the caller`. One predicate function does this; no handler queries objects without it. A failed join answers **404**.
3. **Membership roles.** `owner` (everything, incl. team, budget raise, closure, invoices); `manager` (campaigns, creatives; not team, closure, invoices); `analyst` (read results only).
4. **Reviewer grants.** `advertiser_review`, `ad_review`, `ad_fraud`, `ad_billing`; held only by moderators or administrators; MFA; scope-limited queues; never members of any advertiser (and the reverse).
5. **Separation of duties.** Submitter ≠ decider; suspender ≠ restorer; correction requester ≠ approver; reviewer cannot review an advertiser or campaign where their account is a member or a linked-business owner.
6. **Viewer decisions.** A viewer can act only on decisions issued to their own account; decision ids are random and MAC-protected.
7. **No advertiser reads viewer data**, ever; only suppressed aggregates.
8. **Default deny, closed flags.** `ad_delivery` additionally requires the consent source.

## 2. Actors

ANON · VIEW (signed-in, verified email) · OWN, MGR, ANA (advertiser roles) · NON (signed-in, not a member) · MOD (moderator without grant) · REV(x) (grant x, MFA) · ADM (administrator, MFA) · SVC (job or service identity).

## 3. Matrix

`✔` allowed · `own` own objects only · `—` denied (404 on objects) · `SU` step-up · `G(x)` needs grant.

| Operation group | ANON | VIEW | OWN | MGR | ANA | NON | MOD | REV | ADM | SVC | Object rule |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Register advertiser | — | ✔ with grant | — | — | — | — | — | — | grants | — | Owner = caller |
| Read own advertiser | — | — | ✔ | ✔ | ✔ | — | — | — | — | — | Active membership |
| Update advertiser profile | — | — | ✔ | ✔ | — | — | — | — | — | — | Allowlisted fields |
| Business link | — | — | ✔ | — | — | — | — | — | — | ✔ check | Proof from Business only |
| Verification submit/respond | — | — | ✔ | — | — | — | — | — | — | — | |
| Verification queue/decide | — | — | — | — | — | — | — | G(advertiser_review) | — | — | Not a member; claim then decide |
| Team invite/redeem | — | redeem ✔ | ✔ | — | — | — | — | — | — | — | Code single use |
| Team role change/remove, close | — | — | ✔ SU | — | — | — | — | — | — | — | Not last owner |
| Restrict/suspend/restore advertiser | — | — | — | — | — | — | — | — | ✔ SU | — | Restorer ≠ suspender |
| Placement list | — | — | ✔ | ✔ | ✔ | — | — | — | ✔ | — | Approved only |
| Campaign create/update/submit | — | — | ✔ | ✔ | — | — | — | — | — | — | Own advertiser; state machine |
| Budget change | — | — | ✔ (raise SU) | — | — | — | — | — | — | — | Floor spent+reserved |
| Pause/resume | — | — | ✔ | ✔ | — | — | — | — | — | — | Not if suspended |
| Campaign review decision | — | — | — | — | — | — | — | G(ad_review) | — | — | Not a member |
| Campaign suspend/restore | — | — | — | — | — | — | — | G(ad_review)/G(ad_fraud) | ✔ | — | Different restorer |
| Creative create/version/submit | — | — | ✔ | ✔ | — | — | — | — | — | — | Own campaign |
| Creative review decision | — | — | — | — | — | — | — | G(ad_review) | — | — | Reviewer ≠ submitter, not a member |
| Creative appeal | — | — | ✔ | — | — | — | — | — | — | — | One |
| Appeal decision | — | — | — | — | — | — | — | — | ✔ | — | Not the original reviewer |
| Own results, invoices | — | — | ✔ | results ✔ | results ✔ | — | — | — | — | — | Suppressed aggregates; invoices owner only |
| **Ad decision** | — | ✔ consent | — | — | — | — | — | — | — | — | Account must not be a member of the campaign's advertiser |
| **Impression / click** | — | own decision | own decision | own | own | — | — | — | — | — | Decision issued to this account only |
| Report/why on decision | — | own decision | — | — | — | — | — | — | — | — | |
| Fraud queue/decide | — | — | — | — | — | — | — | G(ad_fraud) | ✔ | — | No account penalty exists |
| Ad report queue/decide | — | — | — | — | — | — | — | G(ad_review) | ✔ | — | |
| Scoped analytics (console) | — | — | — | — | — | — | — | G(ad_fraud) | ✔ | — | Suppressed; reads audited |
| Billing corrections | — | — | — | — | — | — | — | G(ad_billing) SU | — | — | Requester ≠ approver; threshold |
| Reconciliation view | — | — | — | — | — | — | — | G(ad_billing) | ✔ | — | |
| Placements, grants | — | — | — | — | — | — | — | — | ✔ SU | — | |
| Finalizer, invoice job, expiry | — | — | — | — | — | — | — | — | — | ✔ | Only writer of billable events |
| Audit history | — | — | — | — | — | — | — | — | ✔ | ingest | Id-only |

## 4. The cross-campaign IDOR test (generated from the registry)

For every operation that takes a campaign, creative, version, decision, invoice or report id, a caller who is `owner` of advertiser A must receive **404** for objects of advertiser B, **including** valid ids belonging to B, ids of the same shape that do not exist (same response, same timing class), and ids of A that sit under a different advertiser path. An `analyst` must fail every write. A viewer must fail every decision that was issued to another account. A new operation without a registry entry fails the build.
