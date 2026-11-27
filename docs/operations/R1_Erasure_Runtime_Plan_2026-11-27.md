# Erasure runtime wiring plan (D13-003, #273), 27 November 2026

**Status: PROPOSED, NOT EXECUTED.** The repository change below deploys nothing. The staging steps create RabbitMQ accounts, change two existing broker grants, create Swarm secrets and start processes on shared staging. They need the owner's written go-ahead and room on VM2 (see "Capacity"). No secret value appears here, and none may be printed at any step.

## The pipeline, and what was missing (re-verified on `main` after #293)

The flow is:

1. Identity's dispatcher sends `privacy.erasure_requested` to the exchange of each participating service: Engagement, Creators, Moderation, Content (its media queue) and Business.
2. Each service's consumer erases its own data. Its dispatcher then sends `privacy.erasure_confirmed` to Identity's exchange.
3. Identity's consumer marks each job confirmed, and completes the request when every job has confirmed with no retained category.

What already runs on staging:
- Engagement's consumer and dispatcher;
- Content's media worker, which erases.

Missing until this change:
- the runtime roles and stack processes for the Identity consumer and dispatcher, the Creators and Moderation consumers and dispatchers, and the Content dispatcher;
- the broker accounts for Identity, Creators and Moderation;
- Identity-exchange write rights for Content and Engagement;
- the capability the Creators and Moderation workers need.

## Repository change (this PR)

- **`staging_runtime/roles.py`: seven roles.**
  - `identity` / `creators` / `moderation`: a `consumer` (Celery, each on its own queue) and a `dispatch-events` job.
  - `content`: a `dispatch-events` job.
  - Each needs the capability its Celery app already checks: `account_management`, or `media` for Content.
- **`staging_runtime/capabilities.py`:** Creators and Moderation may carry `account_management`. It opens **no route** on either service; the route-coverage test lists both as having no routes.
  - It is in `ERASURE_ONLY`, so the Gateway-derived R1 slice, and therefore the R1 rows of the live Creators and Moderation APIs, stay as they are.
  - `kolovibe_cluster.erasure_flag_table` is the reviewed erasure row: the R1 row plus `account_management` on those two services only. `update` never applies it to an API.
- **`infra/swarm/staging-aws.yml`: seven processes, at 0 replicas,** joined to the messaging network.
  - Each mounts its API service's secrets.
  - Identity, Creators and Moderation each also mount their own new broker URI, `kolovibe_<service>_rabbitmq_url_20261127_v1`, plus the broker CA.
  - Content's dispatcher uses Content's existing broker secret.
- **`scripts/validate_staging_stack.py`:**
  - The erasure row is allowed only on the erasure processes.
  - Each process must mount exactly its own broker account.
  - Outside Content, Engagement and Points, only erasure processes may read a broker URI.
  - There are 11 new rejection tests, and a test ties the accounts to `generate_r1_secrets.PROPOSED_BROKER_ACCOUNTS`.

### Not included: Business

Business is not deployed on staging. It has no API service, database role or schema there (#169; Phase 6B). Identity completes a request only when **every** participating service confirms, Business included.

So on staging an approved erasure will reach every other service and then wait on "Business". The privacy queue will show it as waiting, which is the honest result. It will not complete until Business is deployed. Making the participating set configurable was considered and rejected: a misconfiguration could complete a request while one service still holds the person's data.

## Evidence so far

`scripts/verify_erasure_pipeline_broker.py` was run locally on 27 November against a disposable PostgreSQL and a real RabbitMQ over TLS, as an unprivileged user. Both tests passed:

- an approved deletion is erased and confirmed across the real broker, covering Engagement, Creators, Moderation, Content (with a file-backed bucket) and Business;
- the proposed grants are least-privilege.

This is local evidence on disposable infrastructure, not staging. The duplicate, outage and reapply cases are covered by each service's own erasure tests and by `reapply_erasures`. They are NOT RUN on staging.

## Capacity (blocks deployment)

The full stack now has 18 processes. At today's reservations (100m each) it needs 1.95 CPU on its own, so it cannot schedule.

**CPU,** under the proposed budget of #274 (25m per job or consumer, 100m for the media worker):

| Item | Reservation |
| --- | --- |
| The stack (17 × 25m + 100m) | 525m |
| Eight APIs | 400m |
| PostgreSQL and RabbitMQ | 500m |
| Business API (later) | 50m |
| **Total** | **1475m**, leaving 525m free, just above the 500m margin |

**Memory is the tighter limit.**
- Reservations are 80 MiB per process, so the seven new processes add 560 MiB.
- With the two audit jobs of #272 and the six running processes, the stack reserves 1648 MiB.
- On 26 November, 2.3 of 3.8 GiB was reserved with only six of these processes running.
- The existing memory preflight must pass. If it fails, this is a capacity request (instance size and monthly cost) for the owner, not something to squeeze.

## Staging steps (each read back before the next)

0. **Preconditions:**
   - The CPU budget of #274 is applied.
   - `kolovibe_cluster.py capacity --profile aws-staging` and the memory preflight pass.
   - The owner has approved this plan.
1. **Readback before:**
   - `rabbitmqctl list_users` and `list_permissions -p /kolovibe` (names and patterns only).
   - The queues present.
   - `select status, count(*) from identity.service_privacyrequest group by 1;`
2. **Broker accounts.** For each of `kolovibe_identity`, `kolovibe_creators` and `kolovibe_moderation`:
   - Generate a password (`openssl rand`) and build the `amqps://` URI to the existing host, port 5671 and vhost `/kolovibe`.
   - `docker secret create kolovibe_<service>_rabbitmq_url_20261127_v1 -` from stdin.
   - `rabbitmqctl add_user` with the same password, read from the secret's source and never echoed.
   - `set_permissions` with exactly the `PROPOSED_BROKER_PERMISSIONS` patterns.
3. **Widen two existing grants:** Content and Engagement get exactly their `PROPOSED_BROKER_PERMISSIONS` row, which adds write on `kolovibe.identity` and nothing else.
   - Readback: `list_permissions` equals the table for all six accounts.
4. **Start the processes one at a time:**
   - Deploy the reviewed stack file, then scale to 1 in this order: `identity-consumer` (it declares `kolovibe.identity`), then `creators-consumer` and `moderation-consumer` (each declares its own queue), then the four dispatchers.
   - Readback after each: 1/1 running; no restart loop; `KOLOVIBE_SIGNAL` lines where emitted.
5. **Disposable account test:**
   - Register a disposable staging account, give it a like, a follow and a report, request deletion, and approve it in the console.
   - Expected: every service except Business confirms; the request shows "Waiting on business"; no erased row remains in the confirming services.
   - Then run `reapply_erasures --all` twice. Both runs must change nothing.
6. **Record:** counts, states and times go on #273 and in a dated operations record, with no personal data.

## Rollback

- Scale the seven processes to 0. Outbox rows stay and resend later, so nothing is lost.
- Restore the Content and Engagement grants to their `BROKER_PERMISSIONS` rows.
- Leave the new accounts disabled with `clear_permissions`. Delete nothing until a separately approved clean-up.

## Owner decisions

- Approve this plan, including the broker change.
- Decide whether to deploy Business to staging. Until it is deployed, no erasure there can complete.
- A capacity request, if the memory preflight fails.
