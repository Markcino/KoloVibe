# Phase 2 entry report: architecture, contracts and decisions

| Item | Value |
| --- | --- |
| Phase | 2, Architecture, contracts and decisions ([milestone 7](https://github.com/Markcino/KoloVibe/milestone/7)) |
| Entry authorization | Owner, 27 November 2026, 12:13 UTC: read-only and repository-side work once Phase 1 is PASS; stop before any staging write |
| Phase 1 verdict | **PASS** ([report](PHASE-01_Full_Product_Reconciliation_Report.md)). The owner approved the requirement sets at 12:26 UTC (#328, #329). CI on `main` at `e4f4593` passed 16 checks, skipped 4 manual-only jobs by design and failed none. The PASS was recorded in #330 (`d8e8caa`) |
| Staging authorization | Owner, 12:38 UTC: conditional approval of plans A, B, C, E and G. Plan D is **not** approved. Plan F runs only inside an authorized deployment. The work is executed by the staging infrastructure session on the owner's Mac, not from this repository session |
| This report's scope | Entry only. No staging, Swarm, RabbitMQ, Nginx, database or VM change was made from this session |
| Gate verdict | **NOT EVALUATED**: Phase 2 has started and its exit criteria (tracker section 2) are open |

## 1. Staging remediation sequence

The plans come from the [staging inspection](PHASE-02-ENTRY_Staging_Infrastructure_Inspection_2026-11-27.md), section 8. The order below follows from their dependencies, checked against the repository at `d8e8caa`. The owner's eight preconditions apply before **every** operation: Phase 1 PASS, verify current state, compare plan with reality, confirm backups and rollback, execute only the approved operation, verify health and invariants, record evidence on GitHub, and stop on anything unexpected.

| Step | Plan | Approval state (12:38 UTC) | Depends on | Repository-side finding at `d8e8caa` |
| --- | --- | --- | --- | --- |
| 1 | **B. Historical migration jobs**: save each finished job's name, completion state and `docker service inspect`, then remove only the verified finished jobs | Approved, conditional | Nothing | The owner also asks that `release-readback` stop classifying historical job objects as running application services. That is a reviewed code change to the deployment tool, made by PR before the removal is evidenced |
| 2 | **C. Legacy broker user `kolovibe_celery`**: prove there are no connections, consumers, publishers, configured references, automation or recovery dependency; export its permissions securely; then remove it | Approved, conditional | Nothing | Searched at `d8e8caa`: the name appears only in the two governance reports, not in any stack file, script, configuration or runbook. Runtime checks (connections, consumers, definitions) remain for the staging session |
| 3 | **E. Nginx edge controls**: back up the live file, install `infra/nginx/vm1-kolovibe-staging.conf`, run `nginx -t`, reload, then probe | Approved, conditional | The Nginx part does **not** depend on D. The candidate trusts `CF-Connecting-IP` only from `127.0.0.1` (the local Cloudflare tunnel), keys its limits on that address (10 r/s, bursts 40 and 20), and overwrites the forwarded headers | The **Gateway's** use of the caller's address needs `KOLOVIBE_TRUSTED_CLIENT_IP_HEADER`, which ships only with plan D. E's verification can therefore prove edge limits and header stripping now. The Gateway client-address check stays open until D. The 10 r/s figure is still a first value to confirm (#325) |
| 4 | **G. Audit caller keys**: fresh, unique per-caller keys (the owner's choice) in one combined Audit caller-map update | Approved, conditional | Points can go now. Content and Creators audit delivery (#292, D13-002) is merged but **not deployed** on v0.542.1, so their keys can only be used once the code that sends them is released (plan D) | Recommend: rotate Points now (D13-001, #271). Prepare the combined caller map with Content and Creators entries. Activate the Content and Creators entries with D, unless the staging session shows that v0.542.1 already signs with them |
| 5 | **A. CPU reservations** | Approved, conditional on the 24-hour measurement | Measurement ends about **11:58 UTC on 28 November**; then review | Reservations follow measured p95 plus headroom. No resize or new cost without a separate cost approval |
| 6 | **D. Release of `main`** | **NOT APPROVED** | A (so migration jobs can schedule) | Prepare and present before asking: the reviewed `update-plan`, the image digest comparison, migration compatibility (Identity `0017`, `0018`), database preflight, capacity check and rollback plan |
| 7 | **F. Rollback drill** | Planned; executes only inside D's authorized window | D | — |

### Operations that need separate approval

1. **Plan D**: the release from `main`, including its migrations, the Gateway client-address setting and the activation of the Content and Creators audit keys.
2. **Plan F**: runs only inside D's window.
3. **Any VM resize or cost increase** under plan A.
4. **Dead-letter exchanges and erasure users** (rest of plan C): they need #311's code and the D13-003 plan first.
5. **Any change outside A to G.**

## 2. Phase 2 architecture and contracts work (repository-side)

Work items, in the order the exit criteria need them. Each is its own pull request against its issue.

| Order | Item | Issue | Output |
| --- | --- | --- | --- |
| 1 | Service boundary ADRs for Finance, Events and Advertising (GD-01, GD-02) and the Identity notification module (GD-03) | #304 | ADRs PROPOSED, then owner review |
| 2 | One canonical API and event contract, including the new routes and events of FP-NT, FP-PAY, FP-GA, FP-CM and the Moderation `target_type` extension | #305 | Contract update plus contract tests |
| 3 | Image pipeline in Content (GD-05) and consent store in Identity (GD-06) designs | #308 | ADR addenda |
| 4 | Figma frames for the new screen ranges (M-109 to M-469) | #306 | Frames for owner approval. Writing to Figma needs the owner's file and access |
| 5 | Stage 1 and 2 sign-offs | #133, #134, #140, #141 | Owner sign-off records |

## 3. Next step

Stop here as instructed. The staging session carries out steps 1 to 5 under the owner's conditions. Repository work starts with item 1 of section 2.
