# Staging VM2 CPU budget proposal (D13-004, #274), 27 November 2026

**Status: PROPOSED, NOT APPLIED.** Changing reservations changes services on shared staging, so it needs a written go-ahead after the measurement below. No capacity purchase is proposed: the 26 November reading shows the workload fits once the reservations match use.

## What is known (26 November, read-only, `R1_AWS_Staging_Verification_2026-11-26.md`)

- **The node:** VM2 has 2 vCPU (2000m) and 3.8 GiB of memory.
- **What is reserved:** **2000m of 2000m** CPU and 2.3 GiB of memory, across:
  - 8 APIs and 7 workers at 100m each;
  - PostgreSQL and RabbitMQ at 250m each.
- **What is used:** CPU use was "near 0%". **That is one observation, not a measurement over time.**
- **The effect:** a one-shot migration job reserving 100m stayed Pending. The v0.531.1 rollout scaled every service to zero to run migrations.

Reservations are only scheduling budgets. Each service keeps its own CPU **limit** (0.5 to 1.0 CPU), so lowering a reservation does not cap a service at idle. It only stops idle services from blocking the scheduler.

## Step 1: measure (read-only, needs operator access to VM1 and VM2)

1. **Reservations:** on VM1, run `sudo python3 kolovibe_cluster.py capacity --profile aws-staging` (added in this PR). It prints reserved and allocatable CPU and memory per service, and FAILs while a 100m job cannot fit.
2. **Use:** on VM2, sample every 60 s for at least 24 hours, including one normal working period. The command is `docker stats --no-stream --format '{{.Name}} {{.CPUPerc}} {{.MemUsage}}'`, appended to a root-only file.
3. **Record:** p50, p95 and max CPU per service go in a dated operations record and on #274. These are names and numbers only.

## Step 2: proposed budget, to confirm against the measured p95

| Class | Today | Proposed reservation | Limit (unchanged) |
|---|---|---|---|
| 8 API services | 100m each (800m) | 50m each (400m) | 1.0 CPU |
| Idle jobs and consumers: requeue, dispatch, audit delivery, purge, queue consumers (6 running) | 100m each (600m) | 25m each (150m) | 0.5 CPU |
| Media worker (bursty FFmpeg) | 100m | 100m | 1.0 CPU |
| PostgreSQL | 250m | 250m | unchanged |
| RabbitMQ | 250m | 250m | unchanged |
| **Total running today** | **2000m** | **1150m** | |
| Approved, not yet deployed: Business API, plus 4 erasure workers (Creators, Moderation, Business, Identity confirmations) | (cannot schedule) | 50m + 4 × 25m = 150m | 1.0 / 0.5 CPU |
| Proposed 27 Nov (D13-002, #272): Content and Creators audit delivery jobs | (cannot schedule) | 2 × 25m = 50m | 0.5 CPU |
| Proposed 27 Nov (D13-003, #273): erasure consumers and dispatchers for Identity, Creators and Moderation, plus Content's dispatcher (the earlier "4 erasure workers" row counted consumers only) | (cannot schedule) | 7 × 25m = 175m, of which 75m is already in the row above | 0.5 CPU |
| **Total with planned additions** | | **1450m** (1475m once Business adds its dispatcher) | |
| **Free** | **0m** | **550m (27%)**, just above the 500m margin | |

**Margin:** at least 500m stays free after the planned additions. That leaves room for:

- one 100m migration or maintenance job;
- a `stop-first` rolling update, which never runs two copies;
- a spike in any single service, which is bounded by its limit.

**Rule:** if any service's measured p95 is above its proposed reservation, its reservation becomes that p95, rounded up to 25m. If that leaves less than 500m free, the result is a capacity request (an instance size and its monthly cost) for the owner to approve with a spending ceiling. It is not applied before that approval.

Memory is unchanged: 2.3 of 3.8 GiB is reserved, and the existing memory preflight already gates new services. *Update, 27 November:* the 12 processes not yet running (audit jobs and erasure processes) reserve 80 MiB each, about 960 MiB in all, so memory, not CPU, is the likely limit. If the preflight fails, the result is a capacity request (see `R1_Erasure_Runtime_Plan_2026-11-27.md`).

## Step 3: apply (owner-approved only)

1. **The nine stack processes:** change `reservations.cpus` in `infra/swarm/staging-aws.yml` through a reviewed PR, then `docker stack deploy` the stack file.
2. **The eight APIs:** they copy the live Gateway's spec. Run `docker service update --reserve-cpu 0.05 <service>` one service at a time, with readback after each.
3. **Readback:**
   - every service is 1/1;
   - `capacity` PASSes;
   - a 100m one-shot job (`docker service create --mode replicated-job --reserve-cpu 0.1 --constraint node.hostname==ip-172-31-16-154 alpine:3.24.1@sha256:… true`) completes with the full stack running.
4. **Rollback:** `docker service update --reserve-cpu 0.1 <service>` for each API, and redeploy the previous stack file. Reservations change nothing else, so this is immediate.

## Owner decisions

- Approve step 1, the measurement (read-only).
- After the measurement: approve the budget, or a capacity request if it does not fit.
