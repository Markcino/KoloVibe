# Content and Creators audit delivery plan (D13-002, #272), 27 November 2026

**Status: PROPOSED, NOT EXECUTED.** The repository change below is code only and deploys nothing. The staging steps create Swarm secrets and start two jobs on shared staging, so they need the owner's written go-ahead. They also need room on VM2: the CPU budget of #274 (`R1_Staging_CPU_Budget_Proposal_2026-11-27.md`) must be applied first. No secret value appears here, and none may be printed at any step.

## What was wrong (re-verified on `main` after #291)

The read-only check of 26 November (`R1_AWS_Staging_Verification_2026-11-26.md`, D13-002) found six undelivered rows in `content.service_auditdelivery` and nothing that delivers them. The repository confirms the cause:

- `deliver_audit_events` exists in both services (#235).
- Audit already accepts both producers. Its `CALLER_PATHS` allows `content` and `creators` on `/internal/security-events`, `events.PRODUCER_KINDS` names exactly their vocabularies, and the staging runtime accepts them in Audit's caller map, as long as every key is distinct.
- Missing:
  - no `(content, deliver-audit)` or `(creators, deliver-audit)` runtime role;
  - no stack job;
  - no signing key or Audit peer file for either service;
  - no Audit map entry for either service.

## Repository change (this PR)

- `services/staging_runtime/roles.py`: two job roles, `(content, deliver-audit)` and `(creators, deliver-audit)`. Both run `deliver_audit_events` and need the `media` capability, which is already in both services' reviewed flag rows.
- `infra/swarm/staging-aws.yml`: two jobs, `content-audit` and `creators-audit`.
  - Both start at **0 replicas**.
  - Both run with interval 30 s and batch 100, the same as `points-audit`.
  - Each mounts its API service's secrets plus two new, dated secrets:
    - `kolovibe_content_audit_outbound_20261127_v1` / `kolovibe_creators_audit_outbound_20261127_v1`, the job's own signing key;
    - `kolovibe_content_audit_peers_20261127_v1` / `kolovibe_creators_audit_peers_20261127_v1`, the peer file `{"audit": "<Audit origin>"}`.
  - The Content and Creators APIs, the media worker and `content-requeue` never mount these secrets.
- `scripts/validate_staging_stack.py`: the validator now covers the two jobs.
  - It requires exactly those extra mounts, on those two jobs only, plus the outbound-key and peer-file paths.
  - It refuses another caller's key, a missing key, the key on any other process, a creators job without its onboarding flag row, and a creators job on the broker network.
- `scripts/ops/kolovibe_cluster.py`: Audit may mount the proposed map `kolovibe_audit_callers_20261127_v1`. The 22 November map stays allowed for rollback.
- **Tests:**
  - `scripts/test_staging_roles.py`: the role table.
  - `scripts/test_aws_stack.py`: the jobs and nine rejection cases.
  - `scripts/test_cluster_audit_read_state.py`: only Audit may mount the new map.
  - The signed-call behaviour for each new pair is already covered by `services/audit/tests/test_service_identity.py`, which is identical in every service. It accepts each allowed caller only with its own key, and denies cross-peer impersonation, keys shared by two callers and replay.

## One Audit map for #271 and #272 (recommended)

The Points correction (#281) and this change both replace Audit's caller map. Doing them in one Audit roll means one restart and one readback instead of two. The combined map `kolovibe_audit_callers_20261127_v1` holds:

- `identity`, `moderation` and `gateway`: byte-for-byte unchanged from `kolovibe_audit_callers_auditread_20261122_v1`;
- `points`: the fresh key of #281;
- `content` and `creators`: the two new keys above.

Each new key is at least 48 random bytes, base64. All six entries must have distinct fingerprints, because Audit refuses the whole map otherwise. This takes the place of #281's `kolovibe_audit_callers_points_20261127_v1`. If the owner wants the two changes separate, #281 runs as written, and this plan builds its map from the map in use at that time.

## Staging steps (VM1, the manager). Each is read back before the next

0. **Before you start:**
   - The CPU budget of #274 is applied, and `kolovibe_cluster.py capacity --profile aws-staging` passes.
   - The release read-back (#287) names the live Content and Creators secret names. If a live name differs from the stack file (for example a `_2` rotation), stop and correct the stack file first.
1. **Readback before:**
   - The fingerprints of every Audit map entry.
   - `select count(*) from content.service_auditdelivery where delivered_at is null;` (6 on 26 Nov). Run the same count for `creators`.
2. **Create the keys and peer files.** Nothing is echoed.
   - `openssl rand -base64 48 | tr -d '\n' | docker secret create kolovibe_content_audit_outbound_20261127_v1 -`
   - The same for `kolovibe_creators_audit_outbound_20261127_v1`.
   - Each peer file is `{"audit": "<origin>"}`. The origin is the non-secret Audit origin already used in `kolovibe_points_audit_peers_r1_v1`.
3. **Create the combined Audit map** as in #281 step 3. Read the current map from a running Audit task, set `points`, `content` and `creators` with `jq --rawfile`, and pipe the result straight into `docker secret create`.
   - Readback: the unchanged entries keep their fingerprints; the new ones equal the new keys' fingerprints; all six are distinct.
4. **Roll Audit first:**
   - `update-plan`, then `update`, with `--services audit --secret-override audit:caller_keys=kolovibe_audit_callers_20261127_v1`.
   - Readback: Audit is 1/1 healthy, and Identity and Moderation delivery keep draining.
5. **Start the jobs one at a time:**
   - `docker stack deploy` the reviewed stack file, then `docker service scale <stack>_content-audit=1`.
   - Wait for one clean cycle, then do the same for `creators-audit`.
6. **Readback after:**
   - A signed diagnostic POST of `{}` from each job to Audit `/internal/security-events` answers **400**, not 403.
   - Within a few 30 s intervals, both delivery tables show 0 undelivered rows older than 5 minutes.
   - `audit.service_securityevent` holds those events with producers `content` and `creators`.
   - The console Audit page lists them.
7. **Record:** the keyed fingerprints (8 hex), times and counts go on #272 and in a dated operations record. Values never do.

## Rollback, at any step

- **Jobs:** `docker service scale <stack>_content-audit=0` and `<stack>_creators-audit=0`. Undelivered rows stay and retry later, so nothing is lost.
- **Audit:** `--secret-override audit:caller_keys=kolovibe_audit_callers_auditread_20261122_v1`.

No secret is deleted. Superseded secrets are removed only after a later, separately approved clean-up.

## Owner decisions

- Approve this plan, and choose either one combined Audit roll with #281 (recommended) or two separate rolls.
- The schedule (30 s, batch 100) copies the reviewed `points-audit` values. It is a proposal, not a measured requirement.
