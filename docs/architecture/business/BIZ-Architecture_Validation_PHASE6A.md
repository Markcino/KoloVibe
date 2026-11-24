# Business architecture — validation against the repository and infrastructure (Phase 6A)

**Status: validation record, 24 November 2026.** It checks the approved Business design (ADR-BIZ-001, [service architecture](BIZ-ARCH_Service_Architecture_PROPOSED.md), [ERD](BIZ-ERD_PROPOSED.md), [authorization matrix](../../security/phase6/BIZ-RBAC_and_Object_Authorization_Matrix_PROPOSED.md)) against what exists at `main` `5e7eda7`: the Phase 6B backend (merged in PR #219, behind closed flags, **not deployed**), the contracts, the existing services and the infrastructure files. It is a review, not a change: no code, migration, AWS or staging action was taken, and nothing here approves a deviation.

**Method.** Read the design documents; read the Business service models, state tables, limits, settings and caller policy; read the Gateway Business routes and Audit producer list; read `infra/postgres/schema_isolation.sql`, `infra/swarm/*.yml`, `infra/rabbitmq/README.md` and `scripts/ops/kolovibe_cluster.py`; compared the 50-operation OpenAPI proposal with the 57 Business operations in DOC-205 programmatically; read the Phase 6B result documents. **Re-run in Phase 6A on `main`:** Business 162 tests (1 skipped), Audit 49 (1 skipped), Gateway 210 (18 skipped), and the repository script suite (446) all pass on SQLite. **Quoted from 6B and not re-run:** the PostgreSQL 16 results (`test_business_postgres.py` 11 tests, foundations suite), because Phase 6A is documentation-only.

## 1. Verdicts

| Area | Verdict | One-line reason |
| --- | --- | --- |
| Bounded context and service boundary (ADR-BIZ-001 Decision 1) | **Confirmed** | Business owns its data and shares nothing; exit criteria still apply |
| "No new microservice for symmetry" | **Confirmed**: nothing further is proposed | Section 3 |
| PostgreSQL schema ownership | **Confirmed for isolation; not met for owner/runtime separation** | Section 4 |
| Gateway contracts | **Confirmed with deviation** | 57 operations in DOC-205; response validation weaker than designed (Section 5) |
| Identity integration | **Confirmed; one open prerequisite** | Step-up proof does not exist (P6B-04) |
| Audit integration | **Confirmed** | Producer, kinds, migration, drift test, delivery command exist; scheduling is operations |
| Moderation integration | **Deviation** | Business-local queue instead of the recommended hybrid (Section 6) |
| RabbitMQ requirements | **Confirmed: none needed** for the built slices | Section 7 |
| Existing infrastructure limits | **Not evidenced** | No Business stack entry, no sizing, instance size unrecorded (Section 8) |
| Client architecture | **Confirmed** against DR-BZ-21 | [Client architecture](BIZ-Client_Architecture_DR-BZ-21.md); no web surface exists in code |

## 2. Service boundary and ADR-BIZ-001

| Claim in the ADR | Check at `main` | Result |
| --- | --- | --- |
| New `business` service behind the Gateway with the shared HMAC identity | `services/business` exists; `CALLER_PATHS = {"gateway": ('/internal/probe', '/internal/business/')}`; shared verifier copy covered by the drift test (nine services) | Confirmed |
| Membership, not a new Identity role | `BusinessMembership`; Identity contains no Business code (searched) | Confirmed |
| Business has no dependency on Creators, Engagement or Points | No imports or calls found | Confirmed |
| Moderation → Business decision port | Not built; Business accepts the gateway only | **Deviation** (Section 6) |
| Public reads come from a `business_listing` projection | `BusinessListing` model with a pinned column set and a `reconcile_listings` command | Confirmed |
| PostgreSQL full-text and trigram search | Substring match with two relevance tiers | **Deviation** (D-2) |
| Evidence and images via private R2 | No file handling in Business at all (text evidence only) | Deferred as designed |

The ADR says honestly that a separate service is "not strictly necessary at pilot scale" and attaches exit criteria: if the staging stack cannot carry a ninth service within budget, the same code may ship inside an existing deployable by owner decision. **No evidence has been produced that the criteria are triggered or satisfied** (Section 8), so the decision stands and the exit stays available.

## 3. Why no further services

The review looked for services the design might have added "for symmetry". None is justified:

| Candidate | Verdict | Reason |
| --- | --- | --- |
| Separate search service or search engine | No | Search is a query over one table inside the Business schema; PostgreSQL covers it; a second copy of personal data would be needed |
| Separate inquiry, review or verification services | No | They share membership, throttles, idempotency, audit outbox and the eligibility predicate; splitting would duplicate `authz.py` and cut transactional consistency (aggregates, listing refresh) |
| Notification service | No | No notification channel is approved (DR-BZ-14); Identity owns email |
| Business-specific moderation service | No | Would be a second reviewer system, which DR-BZ-17 exists to avoid |
| Separate image or evidence service | Not now | No files exist; when they do, extend the shared image pipeline (DR-BZ-20) |
| Web service for owners | No | Excluded by DR-BZ-21 |

Net: R2 adds exactly one API service and one audit-delivery job (the pattern the three existing audit jobs use).

## 4. PostgreSQL schema ownership

| Property | Evidence | Result |
| --- | --- | --- |
| One schema and one role per service | `schema_isolation.sql` loops over nine services including `business`: schema, `NOLOGIN` role, nonce, outbox and inbox tables | Confirmed |
| No cross-service SQL, no cross-service foreign keys | 6B: a disposable TLS PostgreSQL run denies cross-schema access for the Business login; `BZ-R-047` | Confirmed (disposable database only) |
| Least-privilege runtime login | 6B: migrations and tests run as a login holding only the Business role | Confirmed on a disposable cluster |
| **Migration owner separate from the runtime login** | The script makes the service role own the schema and every table, and the login is *granted that role*; `test_postgres_foundations.py` creates a login, `GRANT`s it the service role and runs `migrate` as that login | **Not met.** It is the same pattern that produced R-01 (26 runtime-owned tables on staging). The architecture document called Business "an opportunity to create the new service with migration-owner separation from the start"; the code does not do that. P6B-06 is still open |

Consequence: the first staging rollout of Business should not use the existing script unchanged. The recommended fix (DR-BZ-32 option B) is a Business-only change to the provisioning SQL and the test: a migration-owner role that owns the objects and a runtime login with DML privileges only. It is **not** made in Phase 6A, and **no staging database change** is proposed without an approved operations plan.

## 5. Gateway contracts

| Check | Result |
| --- | --- |
| Operations in DOC-205 | **57** (proposal: 50). Every route is declared before use; the route-contract (6 tests) and role-matrix (5 tests) pass per 6B and the repository script suite passes (446) |
| Flags | Five, all closed by default: `business_owner` 19, `business_review_admin` 13, `business_inquiries` 12, `business_reviews` 10, `business_discovery` 3 |
| Anonymous list | 4: categories, search, detail, public reviews (the proposal's BZ-AZ-01…04) |
| Privileged routes | 13, all MFA; 10 moderator-or-administrator under grants, 3 administrator-only |
| **Response validation** | The design (AC-CON-002, authorization matrix section 6) says the Gateway re-validates every Business response against exact allowlists and returns 503 on any extra field. **As built the Gateway forwards bounded JSON objects and bounded refusals**; exact shapes are tested in the Business service (6B, "deviation recorded") | **Deviation (D-4).** The anonymous reads, the most exposed, have no second allowlist at the edge |

Operations in the proposal that DOC-205 does not contain (eleven): suspension, restoration, appeal of a suspension or rejection, appeal of a review removal, closure, ownership transfer, evidence read grant, grant revocation by DELETE, category create and patch (merged into one PUT), and staff invitation at `/members` (replaced by `/members/invitations`). Operations in DOC-205 that the proposal did not contain (eighteen): staff-invitation issue, redemption, leave, invitation revocation, profile and listing reads, profile-revision review (three), report read, claim, inquiry confirm (two), review invitations (two), verification evidence, registration grants and the PUT category. The first set is the unbuilt backlog; the second is accepted growth that the owner approved by merging #219.

## 6. Identity, Audit and Moderation integration

**Identity.** Sessions are validated per request through the Gateway (no positive cache); roles and MFA state come from Identity; privileged accounts cannot own, staff or review. Open: (a) the **purpose-bound step-up proof** (P6B-04, DR-BZ-33): Identity's re-authentication proof is consumable only inside Identity, so contact change on a live profile, staff removal, closure and ownership transfer **refuse for every caller**; (b) the Gateway does not carry account age, so no account-age gate exists (BZ-R-021, 026). Neither can be fixed inside Business.

**Audit.** `business` is a producer in Audit with its own kind list; Audit migration `0006_business_producer` exists (additive); Business keeps `AuditEvent` and `AuditDelivery` rows and a `deliver_audit_events` command; a test guards the two kind lists against drift. Delivery is **not scheduled** by the repository, the same as the existing audit jobs.

**Moderation (DR-BZ-17).** The approved recommendation was a hybrid: verification stays in Business; user reports and appeals reuse Moderation after a separately approved, additive generalization from `video_id`. As built, **Moderation was not changed** (it contains no Business code) and Business has a **local report queue** built on the same grant, MFA, conflict and idempotency patterns. Consequences: duplicated reviewer logic; no restoration of wrongly removed content by a different reviewer; no appeals; no listing reports (no suspension action). This is a sound interim given that Moderation is in R1 acceptance, but it is a deviation the owner has not accepted (**DR-BZ-29**).

## 7. RabbitMQ

| Question | Finding |
| --- | --- |
| Does Business publish or consume messages? | No. `services/business` contains no broker, Celery or Kombu import. The per-schema `event_outbox` and `event_inbox` tables from the isolation script exist but are unused |
| Does any built slice need a queue, exchange or permission? | No. Audit delivery is a signed internal HTTP call from Business to Audit (`/internal/security-events`, a path Audit allows only for the `business` caller), not the broker |
| What would? | File evidence and image processing (a worker on a Celery queue), only after DR-BZ-19 and DR-BZ-20 |
| Broker state | The Swarm candidate is **not active** and has not been accepted; no broker permissions, dead-letter queue or sizing exist. The verified Points exchange routing is untouched and must stay so |

So: **no RabbitMQ change is required, requested or made** for Business. A future media worker needs its own approved queue, a scoped account and a sizing check; nothing may widen existing permissions.

## 8. Existing infrastructure resource limits

| Fact | Evidence |
| --- | --- |
| Business is in no stack file and is unknown to the cluster tooling | `infra/swarm/staging.yml` and `staging-aws.yml` do not mention it; `scripts/ops/kolovibe_cluster.py` lists eight services (`SERVICES`, `UPDATE_ORDER`); `schema_isolation.sql`, `check_structure.py` and the local runner do list nine |
| AWS instance size | Recorded nowhere in the repository (the AWS stack file says so) |
| Budgets are reviewed figures, not measurements | The seven AWS background processes carry limits of 512, 192, 160, 192, 160, 160 and 160 MiB (**1,536 MiB total**), all at zero replicas |
| API limit | Required variable with no default in the Oracle stack; the cluster tool applies 256 MiB (limit) and 128 MiB (reservation) to an API it creates and checks `256 MiB per new service + broker limit + 384 MiB` against available memory |
| Business increment | One more API (planning figure 256 MiB limit) and one audit-delivery job (the existing audit jobs use 160 MiB): **about 416 MiB of limits**, unmeasured |
| Oracle VMs | About 956 MiB of RAM each with existing workloads (broker README) |

Conclusion: the ninth service is **not shown to fit**. This matches the approved sequencing (DR-BZ-24: local and CI only, then rollout after R-01 remediation and R1 pilot acceptance). It also means the ADR's exit criteria cannot be evaluated until the owner records the AWS instance size and a read-only capacity check.

## 9. Deviation register (as built versus approved design)

| # | Deviation | Impact | Needs |
| --- | --- | --- | --- |
| D-1 | Owner/runtime separation not met (same pattern as R1) | Repeats the R-01 finding for a new schema | DR-BZ-32 |
| D-2 | Substring search with two tiers instead of full-text and trigram indexes | Fine at pilot size; unbounded scans are capped (500 rows when a post-filter applies) | DR-BZ-30 |
| D-3 | Moderation not generalised; Business-local report queue; no restoration or appeals | Duplicated reviewer logic; gaps in the removal workflow | DR-BZ-29, DR-BZ-25 |
| D-4 | Gateway forwards bounded JSON instead of re-validating exact Business response shapes | The public reads have a single allowlist, in the Business service | DR-BZ-31 |
| D-5 | Business accepts the Gateway only; no Moderation caller path | Consistent with D-3 | with DR-BZ-29 |
| D-6 | Eleven proposed operations unbuilt; eighteen unplanned operations added | Backlog items and contract growth | owner awareness (this record) |
| D-7 | Verification case has no `withdrawn` state; rejected business returns to `submitted` (the design said `draft`); `suspended` and `closed` exist as states but nothing transitions into them | An owner cannot withdraw a case; suspension and closure are unreachable | DR-BZ-25, DR-BZ-33 |
| D-8 | Text evidence only; no files, no images | By design until DR-BZ-19, 20 | owner inputs |
| D-9 | Review `pending` state is not stored: a review is created `published` or `held` | Simpler; equivalent for fraud holds | none |
| D-10 | Deployment tooling still lists eight services | Cannot deploy Business with the cluster tool | approved rollout (DR-BZ-24) |
| D-11 | Governance registers (DOC-020 row, DOC-207) still say "Deferred" | Records disagree with the approval record | change request BZ-B-000 |

## 10. What this validation does not show

It does not show the backend works in any deployed environment, that the PostgreSQL privileges on staging are correct, that the ninth service fits, that the controls resist an independent attacker, or that any policy the owner still owes is right. The Business suites were authored with the code and are not independent assurance. Phase 11 acceptance is unchanged.
