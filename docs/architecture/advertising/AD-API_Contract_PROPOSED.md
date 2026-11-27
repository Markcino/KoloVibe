# Advertising API contract (proposed)

> Phase 2 reconciliation, 27 November 2026: this is historical proposal detail. [DOC-205](../DOC-205_OpenAPI_3_1_DRAFT.yaml) is the sole API authority and [the event catalogue](../../../packages/contracts/events/catalogue.yaml) the sole messaging authority. Current ADR-AD-001 governs ownership. Grouped paths, ledger/provider ownership and `ads` naming below are superseded where they conflict; they are not a second contract. Contract approval remains pending #305/#141.

**Status: PROPOSED — not approved; not yet in DOC-205.** 25 November 2026. On approval the operations become OpenAPI 3.1 in `packages/contracts/openapi`, and the contract-reconciliation test used for Business is extended (contract ⇄ Gateway routes ⇄ service registry ⇄ console ⇄ Dart models). Paths under `/api/v1`. The client never sends an owner, account, state, price, spend, destination URL for a click, or role.

## Conventions

| Item | Rule |
| --- | --- |
| Flags (closed by default) | `ad_advertiser` (A1), `ad_campaigns` (A2, A3, reporting), `ad_delivery` (decision, impression, click, report), `ad_admin` (console). `ad_delivery` additionally **refuses to start unless the consent source exists** (DR-AD-07) |
| Flags in tables | **MFA**, **VE** (verified email), **ID** (`Idempotency-Key`; replay returns stored answer; key reuse with another body → 409), **SU** (step-up, fails closed until DR-AD-05) |
| Non-entitled caller | 404 on objects; 403 only from the Gateway role check |
| Pagination | Keyset, bounded size, no total counts |
| Errors | `{detail, code}`, bounded, no echo |
| Consent | The Gateway puts the consent state in the signed envelope; delivery operations refuse with `consent_required` |

## A1 — Advertiser accounts (`ad_advertiser`)

| Operation | Method and path | Caller | Flags | Notes |
| --- | --- | --- | --- | --- |
| `advertiser_register` | POST `/advertisers` | account with grant | VE, ID | Owner = caller; `grant_required` otherwise |
| `advertiser_mine` / `get` / `update` | GET `/advertisers/mine`, GET/PATCH `/advertisers/{a}` | member (update: owner, manager) | — | Allowlisted fields |
| `advertiser_business_link` | POST `/advertisers/{a}/business-link` | owner | ID | Server asks Business; client sends only a business id |
| `verification_submit` / `get` / `respond` | POST/GET `/advertisers/{a}/verification`, POST `…/respond` | owner | ID | |
| `team_list` / `invite` / `revoke_invitation` / `redeem` | GET/POST `/advertisers/{a}/members`, `/invitations`, POST `/advertisers/invitations/redeem` | owner (redeem: any VE account) | ID | Code single use |
| `team_role_change` / `team_remove` | PATCH/DELETE `/advertisers/{a}/members/{m}` | owner | **SU** | Not the last owner |
| `advertiser_close` | POST `/advertisers/{a}/close` | owner | **SU**, ID | No active campaign |

## A2 — Campaigns (`ad_campaigns`)

| Operation | Method and path | Caller | Flags | Notes |
| --- | --- | --- | --- | --- |
| `placements_list` | GET `/ad-placements` | member | — | Approved placements only, with format limits |
| `campaign_create` | POST `/advertisers/{a}/campaigns` | owner, manager | ID | Draft; server validates schedule and budget bounds |
| `campaign_list` / `get` | GET `/advertisers/{a}/campaigns[/{c}]` | member | — | |
| `campaign_update` | PATCH `/advertisers/{a}/campaigns/{c}` | owner, manager | — | Draft and `changes_requested` only; optimistic `version` |
| `campaign_budget_change` | POST `…/{c}/budget` | owner | ID, **SU** to raise | Floor: spent plus reserved |
| `campaign_submit` | POST `…/{c}/submit` | owner, manager | ID | Requires a submitted creative version |
| `campaign_pause` / `resume` | POST `…/{c}/pause`, `…/resume` | owner, manager | ID | `resume` refused if `suspended`, `completed`, or past end |
| `campaign_cancel` | POST `…/{c}/cancel` | owner | ID | Draft or approved only |
| `campaign_results` | GET `…/{c}/results?from=&to=&by=` | member incl. analyst | — | Aggregates, suppressed small cells, post-hold only |
| `advertiser_results` | GET `/advertisers/{a}/results` | member | — | Roll-up |
| `invoices_list` / `get` | GET `/advertisers/{a}/invoices[/{i}]` | owner | — | Sandbox, labelled; no payment status |

## A3 — Creatives (`ad_campaigns`)

| Operation | Method and path | Caller | Flags | Notes |
| --- | --- | --- | --- | --- |
| `creative_create` | POST `/advertisers/{a}/campaigns/{c}/creatives` | owner, manager | ID | Creates v1 as draft |
| `creative_version_create` | POST `…/creatives/{k}/versions` | owner, manager | ID | New immutable version |
| `creative_get` / `versions_list` | GET `…/creatives/{k}[/versions]` | member | — | Review status and reason codes |
| `creative_submit` | POST `…/versions/{v}/submit` | owner, manager | ID | |
| `creative_media_upload_intent` | POST `…/versions/{v}/media` | owner, manager | ID | **Blocked by DR-AD-06**; not routed in Phase 8 until approved |
| `creative_appeal` | POST `…/versions/{v}/appeal` | owner | ID | One appeal |

Destination input: `{kind: "business_listing"|"event"|"external_https", ref}`. For `external_https`, the server validates (https only, no userinfo, no IP literal, no shortener, no redirect, length bounded, normalised host) and the route is disabled while the external-links flag is closed.

## A4/A5 — Delivery and measurement (`ad_delivery`, signed-in, consent required)

| Operation | Method and path | Caller | Flags | Notes |
| --- | --- | --- | --- | --- |
| `ad_decision` | POST `/ad-placements/{p}/decision` | viewer | VE, consent | Returns zero or one sponsored item: `{decision_id, mac, expires_at, advertiser_name, headline, body, cta, label: "Sponsored"}`; **no price, no campaign id, no destination**; omitted if ineligible |
| `ad_impression` | POST `/ad-decisions/{d}/impression` | the decision's account | consent | Body: `{mac, visible_ms}`; always answers 204; outcome is internal |
| `ad_click` | POST `/ad-decisions/{d}/click` | the decision's account | consent | Body: `{mac}`; returns `{destination}` resolved from the stored version; replay returns the same destination without a new event |
| `ad_report` | POST `/ad-decisions/{d}/report` | the decision's account | ID | Reason code; no consent needed |
| `ad_why` | GET `/ad-decisions/{d}/why` | the decision's account | — | Fixed text plus advertiser name |

Impression and click always answer in constant shape so a client cannot probe the validation rules.

## A6 — Administration (`ad_admin`, console only, MFA on every operation)

| Operation | Method and path | Caller (grant) | Flags | Notes |
| --- | --- | --- | --- | --- |
| `admin_advertiser_queue` / `case_get` / `claim` / `decide` | `/admin/advertisers/verification…` | `advertiser_review` | MFA, ID | Claim then decide |
| `admin_advertiser_restrict` / `suspend` / `restore` | POST `/admin/advertisers/{a}/…` | administrator | MFA, **SU**, ID | Restorer ≠ suspender |
| `admin_campaign_queue` / `get` / `decide` | `/admin/campaigns/review…` | `ad_review` | MFA, ID | Reviewer not a member |
| `admin_creative_queue` / `get` / `decide` | `/admin/creatives/review…` | `ad_review` | MFA, ID | Reason codes |
| `admin_creative_appeal_decide` | POST `/admin/creatives/{v}/appeal/decision` | administrator | MFA, ID | Not the original reviewer |
| `admin_campaign_suspend` / `restore` | POST `/admin/campaigns/{c}/suspend`, `/restore` | `ad_review`, `ad_fraud`, administrator | MFA, ID | Next decision honours it |
| `admin_fraud_queue` / `get` / `decide` | `/admin/ad-fraud…` | `ad_fraud` | MFA, ID | Hold, release, dismiss; no account penalty |
| `admin_ad_report_queue` / `decide` | `/admin/ad-reports…` | `ad_review` | MFA, ID | User reports of creatives |
| `admin_analytics` | GET `/admin/ad-analytics?…` | `ad_fraud`, administrator | MFA | Scoped; suppressed; read audited |
| `admin_billing_corrections` | GET, POST `/admin/ad-billing/corrections…` | `ad_billing` | MFA, **SU**, ID | Requester ≠ approver; second approver above threshold |
| `admin_recon` | GET `/admin/ad-billing/reconciliation` | `ad_billing`, administrator | MFA | Differences only |
| `admin_placements` / `grants` | `/admin/ad-placements`, `/admin/ad-grants` | administrator | MFA, **SU** | |
| `admin_audit_read` | existing Audit reader | administrator | MFA | New `ads` producer kinds |

## Internal (not client-reachable)

| Operation | Caller | Notes |
| --- | --- | --- |
| `finalize_billable` | scheduled management command | Only writer of `billable_event`; idempotent; bounded batch |
| `expire_decisions` | scheduled management command | Releases reservations; lazy expiry also runs inline so correctness never depends on the job |
| `generate_invoices` | scheduled management command | Derives invoice lines from billable events; sandbox |
| `reconcile` | scheduled management command | Uses `ReconciliationSource` |
| `business_check` | Ads → Business | Signed read-only; **a new Business endpoint needing approval** |

## Audit kinds (new producer `ads`; an Audit change needing approval)

`advertiser.registered`, `advertiser.membership_granted`, `advertiser.membership_revoked`, `advertiser.invitation_created`, `advertiser.invitation_redeemed`, `advertiser.verification_submitted`, `advertiser.verification_decided`, `advertiser.status_changed`, `advertiser.business_linked`, `campaign.created`, `campaign.submitted`, `campaign.reviewed`, `campaign.state_changed`, `campaign.budget_changed`, `creative.version_created`, `creative.submitted`, `creative.reviewed`, `creative.appealed`, `creative.suspended`, `ad.decision_refused` (aggregate), `ad.report_created`, `fraud.signal_decided`, `billing.invoice_generated`, `billing.correction_posted`, `billing.recon_difference`, `admin.queue_read`, `admin.case_read`, `admin.analytics_read`. Ids and codes only; **per-decision and per-event records are not audited individually** (they are the measurement tables, with retention).

## Open contract questions

1. The consent state in the envelope needs an Identity and Gateway change (DR-AD-07).
2. `ad_decision` is POST (it creates a record and reserves budget), not a cacheable GET.
3. About 70 operations; fixed when the OpenAPI is written. Flags: four, versus Business's five.
