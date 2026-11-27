# Points to Audit signing-key correction plan (D13-001, #271), 27 November 2026

**Status: PROPOSED, NOT EXECUTED.** This plan changes Swarm secrets and services on shared staging, so it needs the owner's written go-ahead before step 1. No secret value appears here, and none may be printed at any step. Keys are compared only by keyed fingerprint (see "Fingerprints").

## The intended pairing

`scripts/ops/generate_r1_secrets.py` is the reviewed source of the design. `build()` makes one fresh Points key and writes it twice:

- as `kolovibe_points_outbound_key_r1_v1`, which Points mounts as `outbound_key`;
- as the `points` entry of Audit's caller map.

`validate()` refuses a caller map whose `points` entry is not exactly that key. It also refuses any two callers that share a key.

Audit enforces the same rule at runtime. `services/audit/service/service_auth.py` `_accepted_keys` returns no keys, which means 403, when two entries share a key. A caller entry may be a list of up to `MAX_KEYS_PER_CALLER` keys, which allows overlap during a rotation.

So the intended state is: the key Points signs with equals Audit's `points` entry, and it differs from every other caller's key. This follows the per-peer key rule (#146).

## What is wrong today

This is from the read-only check of 26 November (`R1_AWS_Staging_Verification_2026-11-26.md`, D13-001):

- **Points mounts the old key:** `kolovibe_points_outbound_key_r1_v1`, through the shared `points-secrets` anchor in `infra/swarm/staging-aws.yml`. That anchor covers `points-consumer` and `points-audit`, and the Points API mounts the same key through the cluster tool's R1 table.
- **Audit holds a different key:** Audit mounts `kolovibe_audit_callers_auditread_20261122_v1`, from the 22 November audit-read rotation. Its `points` entry has a different fingerprint, most likely from a second generator run.
- **A v2 secret has unknown origin:** `kolovibe_points_outbound_key_r1_v2` exists (about 16 November). It is mounted by nothing, so it is **not** used here.

## Recommended correction: a fresh, distinct Points key

Neither existing key is reused:

- the v1 key has been in use for a week without a working pair;
- the v2 key's origin is unknown;
- Audit's current `points` entry would need extracting from a map that also holds the other callers' keys.

A new key also avoids an accidental collision with another caller, which would lock out every caller of Audit.

New secret names, following the dated pattern used on 22 November:

- `kolovibe_points_outbound_key_20261127_v1`: the new Points key, at least 48 random bytes, base64.
- `kolovibe_audit_callers_points_20261127_v1`: the current Audit map with **only** its `points` entry replaced by the new key. Identity, Moderation and Gateway stay byte-for-byte the same.

### Step 0: repository change, reviewed and merged first

- `scripts/ops/kolovibe_cluster.py` `_aws_allowed_secrets()`:
  - allow `kolovibe_points_outbound_key_20261127_v1` for `points`;
  - allow `kolovibe_audit_callers_points_20261127_v1` for `audit`;
  - keep the old names allowed, for rollback.
- `infra/swarm/staging-aws.yml`: the `points-secrets` anchor mounts `kolovibe_points_outbound_key_20261127_v1` as `outbound_key`, and the top-level `secrets:` list gains it.
- Tests: the existing cluster-tool and stack tests extended to cover the new names.

### Steps on VM1, the manager. Each is read back before the next

1. **Readback before:**
   - `docker secret ls --format '{{.Name}}' | grep -E 'points_outbound|audit_callers'`;
   - the fingerprints of the Points mount and of every Audit map entry (see "Fingerprints").
   - Record the backlog: `select count(*) from points.service_auditdelivery where delivered_at is null;` (11 on 26 Nov).
2. **Create the Points key:**
   `openssl rand -base64 48 | tr -d '\n' | docker secret create kolovibe_points_outbound_key_20261127_v1 -`
   Nothing is echoed.
3. **Create the Audit map:**
   - Read the current map from a running Audit task with `docker exec <audit task> cat /run/secrets/caller_keys`.
   - Pipe it through `jq --rawfile k <(…new key…) '.points = $k'` straight into `docker secret create kolovibe_audit_callers_points_20261127_v1 -`. The new key can be read back the same way from a short-lived container that mounts it.
   - Nothing goes to disk or the terminal.
   - Readback: the new map's fingerprints equal the old map's for every caller except `points`; all of its fingerprints are distinct; and `points` equals the new Points key's fingerprint.
4. **Roll Audit first:**
   `kolovibe_cluster.py update-plan --profile aws-staging --services audit --secret-override audit:caller_keys=kolovibe_audit_callers_points_20261127_v1`
   Review the plan, then `update` with the same arguments.
   - **Why first:** Points already fails, so nothing new breaks. Identity, Moderation and Gateway keep their keys.
   - **Readback:**
     - Audit 1/1 healthy.
     - Identity and Moderation delivery keep draining.
     - `signed_tests` for gateway to audit still pass.
5. **Roll Points:**
   - The API: `update-plan` and then `update` with `--services points --secret-override points:outbound_key=kolovibe_points_outbound_key_20261127_v1`.
   - Then `points-consumer` and `points-audit`, from the step-0 stack file, one at a time. Each stays at 1 replica.
6. **Readback after:**
   - From the `points-audit` container, the diagnostic signed POST of `{}` to Audit `/internal/security-events` answers **400**, not 403.
   - Within a few delivery intervals of 30 s, `points.service_auditdelivery` has 0 undelivered rows.
   - `audit.service_securityevent` has the 11 events with producer `points`.
   - Run cluster `signed_tests` for the points to audit pair.
7. **Record:** the fingerprints (keyed, 8 hex), times and counts go on #271 and in a dated operations record. Values never do.

### Rollback, at any step

- **Audit:** `--secret-override audit:caller_keys=kolovibe_audit_callers_auditread_20261122_v1`.
- **Points:** `--secret-override points:outbound_key=kolovibe_points_outbound_key_r1_v1`. Then redeploy `points-consumer` and `points-audit` from the pre-change stack file.

This returns to today's state: Points undelivered, evidence kept, nothing lost. No secret is deleted during the change. The superseded secrets are removed only after a later, separately approved clean-up.

## Fingerprints

Use one random salt per session, which is never stored:

```sh
python3 -c 'import hmac,hashlib,sys,os; s=os.environ["FP_SALT"].encode(); print(hmac.new(s, sys.stdin.buffer.read().strip(), hashlib.sha256).hexdigest()[:8])'
```

Each key is piped from its mount. Only the 8-hex output is ever shown.

## Owner decisions

- Approve this plan, steps 0 to 7.
- Later and separately: remove the superseded secrets (`r1_v1`, `r1_v2`, `auditread_20261122_v1`).
