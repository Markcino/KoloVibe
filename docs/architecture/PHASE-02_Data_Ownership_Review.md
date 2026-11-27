# Phase 2 data ownership and technical walkthrough record

Desk review against main `41d662c6bd5d6592c56027f9dc51e2aaecf5a54c`, 27 November 2026. This is an agent technical preparation, **not** the sponsor/architecture/security sign-off or independent accounting review (#141). Django migrations remain authoritative for built services; no migrations were authored or executed.

| Domain | Owned records / planned extension | Isolation and invariants | Evidence / acceptance still needed |
| --- | --- | --- | --- |
| Gateway | No domain tables | Authentication forwarding, capability gates and signed peer requests only | Path/method/auth/non-exposure tests; no new service routes built |
| Identity | Accounts, sessions, legal acceptance, privacy workflow; planned consent, device, notification and channel attempt tables | Account FK stays inside Identity; dispatcher restricted view; unique event/recipient/template key; no credentials in dispatcher grants | ADR-NT-001; role isolation/runtime tests #309/#146 |
| Creators | Profiles, applications, measures and eligibility | Account ids are opaque external UUIDs, no cross-service FK | Existing migrations; Decision F; snapshot interfaces need review |
| Content | Videos, processing, upload intents, revisions; planned image assets and derivatives | Private R2; processing state authorizes derivatives; immutable asset purpose/subject/owner binding | GD-05; image limits and scanning selection #308/#149 |
| Engagement | Likes, follows, shares, watch/qualified views; planned comments, revisions, blocks/settings | Author/video ids external; visibility and standing checked through owner interfaces; one-level replies; idempotency; no ad qualification input | FP-CM; future runtime and privacy tests #135 |
| Points | Non-cash append-only entries; planned finalized eligible snapshots | Snapshot weights only, immutable period/rule/hash; no redemption or debit from Finance | Decision J; general-release policy #137; no new snapshot code |
| Moderation | Reports, decisions, assignments, appeals | Planned comment target, immutable policy/outcome, independent appeals | Existing report API requires target-type extension; contract completeness #305 |
| Audit | Signed security-event ingestion and protected read grants | HTTP outbox delivery is separate from RabbitMQ; allowlisted kinds | 149 kinds catalogued; delivery/runtime #271/#272; risk sign-off #140 |
| Business | Profiles, memberships, verification, listing, inquiries and reviews | Own schema, no money; data reuse by API only | Existing approved Business design and migrations; visual/state approval #306 |
| Finance (planned) | Book, currency policy, account, journal/line, source inbox, intent, provider inbox, refund/dispute, reconciliation, period, allocation, hold, payout/destination, policy/grants, statement, outbox | Unique source+digest; integer minor units; balanced journal per currency/book; serialized hash chain; immutable posting and closed periods; contra-journals; SoD; no raw payment details | ADR-FIN-001 + FIN ERD; independent accountant must review posting/rounding/SoD and PostgreSQL constraints before #141 closure |
| Events (planned) | Organizer/member, venue, event/revision/listing, ticket type, reservation/item, order/pricing, ticket/credential, check-in, refund request, inbox/outbox | Lock event then sorted types; stock nonnegative; one issue/admission per ticket; Finance ids only, no monetary ledger/provider clients | ADR-EVT-001 supersedes historical financial_event ERD; late-success/cancellation saga tests #319/#320 |
| Advertising (planned) | Advertiser/member, campaign/budget, creative/version, review, placement, decision, measurement/dedupe, billable fact/invoice, inbox/outbox | Immutable reviewed creative; MAC-bound decision; consent+age fail closed; operational counters only; Finance owns payment state | ADR-AD-001 supersedes `ads` service name; no mobile external payment link; sales-channel decision #305/#322 |

No cross-domain SQL join, FK, trigger or write is permitted. Same-service FKs use restrictive deletion for immutable evidence; ownership is always derived server-side. Target ERDs do not prove built schema parity. Deployed staging remains the separate session's evidence and is not silently promoted to this target.

## Walkthrough findings and resolution

1. Historical DOC-208 described a dedicated proxy, HA Swarm, Redis and managed video. The canonical target now shows host Nginx, RabbitMQ, R2/FFmpeg and all twelve services. It is a target, not an assertion that three new services run on staging.
2. DOC-204 had a misleading cross-service account→creator relationship. The diagram now avoids cross-service FKs and links this ownership review; detailed built schema authority remains migrations.
3. Events' old ERD/ADR ledger and payment adapter conflict with J/FP-PAY. Current ADR header supersedes them. Finance success drives ticket issuance; refund cancellation is a saga, never an atomic distributed transaction.
4. Finance's old basis excludes Points; Decision J requires a finalized eligible-Points snapshot. Current ADR corrects that without converting Points into money.
5. API drafts disagree on `/orders`, `/events/{id}/orders`, refund naming, advertiser scope and public callbacks. The contract reconciliation notes in packages/contracts identify canonical choices and unresolved provider/store details. No guessed provider schema is approved.
6. Formal Stage 2 closure also requires G-03/G-04/G-05/G-08/G-10 decisions and named signatures. Open runtime/security evidence remains unverified; schema validation cannot sign it off.
