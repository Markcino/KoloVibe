# R1 AWS staging runtime completion: implementation dependency matrix — 13 November 2026

**Status: planning record. Nothing is deployed, approved or changed on AWS.** Source: [AWS staging deployment plan](AWS_Staging_Deployment_Plan_R1_2026-11-13.md) section 3 and the repository at `origin/main` `d5fc895`. Dependencies for work packages C to H come from the plan and a read of the deploy tool, stack file and staging middleware; each is re-verified against code when that package starts.

## 1. Work packages

| ID | Package | Depends on | Blocks | Reviewable change | Needs from the owner |
| --- | --- | --- | --- | --- | --- |
| A | Release candidate and image strategy | none | B, and every deployment | Tool refuses any digest not named explicitly and cross-checked against CI publication evidence (PR 1). **Publish job repair (PR 2): see section 6** | A designated release commit whose `main` CI run passed and published |
| B | Explicit image update and rollback planning | A | Any move of running services off the 1 November image | `scripts/ops/kolovibe_cluster.py`: `update-plan`, `update`, `rollback` | Named operator; an approved restore point |
| C | Staging capability gates for approved R1 routes | none in code; deploys through B | Acceptance phases E to I | `staging_runtime` middleware, settings flags, stack environment | Which flags to enable first, per service |
| D | Sandboxed media worker (FFmpeg, R2) | B for rollout; E for queue wiring (to confirm) | Acceptance phase F | New worker image target and stack service | R2 account, bucket and key secrets provisioned |
| E | RabbitMQ consumers, schedulers, audit delivery | B for rollout | Acceptance phases G, H, I | Worker services and schedulers in `infra/swarm/staging.yml`; messaging secrets | Approved broker URLs, retry cadence, lag alerts |
| F | Deployment validation, health checks, logs, resource limits | C, D, E define what to validate | Capacity sign-off | `validate_staging_stack.py` and stack limits | Approved memory limits for the two ~956 MiB VMs |
| G | Migration validation and restore requirements | none in code | Any migration run on staging | PostgreSQL migration check, rollback classification, restore runbook | Approved restore point and a tested restore (FND-16) |
| H | CI and staging-config regression tests | A to G | Final readiness claim | Test and workflow wiring | none |

## 2. Dependency graph

```
A ──► B ──► (rollout of C, D, E)
C ─────────────────────────────┐
E ──► D (queue wiring, to confirm)├──► F ──► H
G ─────────────────────────────┘
```

C, E and G have no code dependency on each other, so they are independent PRs. D follows E if the media worker consumes from the broker. Everything reaches AWS only through B.

## 3. PR sequence and why B goes first

1. **PR 1 (this one): B, with the tool half of A.** Highest priority: the plan names the create-only deploy tool and the stale pin as the first blocker, and no later package can reach staging without a safe way to move a running service to a new digest and back. It is also the smallest package that is fully testable offline.
2. **PR 2: A, publish job repair** (section 6). Small, independent, and nothing can be deployed until a digest is published with evidence.
3. **PR 3: C.** Largest functional unblocker (phases E to I cannot start while the middleware returns 403 for uploads, likes, follows, watch sessions, points, reports, moderation and newer account routes).
4. **PR 4: E.** Celery consumers, supervision and the three schedulers.
5. **PR 5: D.** Media worker image with FFmpeg and optional media dependencies, no shared-image changes.
6. **PR 6: G, then F.** Migrations and restore requirements first, then the validators that check the finished stack.
7. **PR 7: H.** Regression wiring and the final remaining-work report.

Each PR stops for review; none deploys anything.

## 4. Cross-cutting rules every package keeps

No credential in Git, logs, evidence or specs; caller authentication, HTTPS, MFA and audit paths unchanged; least-privilege database logins; deferred capabilities stay off; the Gateway and production are never modified implicitly; a failed image scan is never bypassed.

## 5. State of the known gaps

| Known gap | State after PR 1 |
| --- | --- |
| Old pinned digest, create-only deploy | Tool no longer pins an image. New services and updates both need an explicit digest; `deploy` still only creates, `update` moves named services |
| Image scan failure (`sqlite-libs`) | Fixed on `main` by the PostgreSQL-only release target (PR #54): "Build and scan shared service image" and all eight smoke jobs pass on `d5fc895`. No deployable digest exists yet, see section 6 |
| Restricted middleware blocks R1 routes | Open (PR 3) |
| No media worker | Open (PR 5) |
| No Celery consumers, RabbitMQ processing, schedulers | Open (PR 4) |
| Secrets and service identities not provisioned | Open; names listed in plan section 4; operator task, plus validation in PR 6 |
| Migration distance | Open (PR 6) |
| Backup-and-restore acceptance | Open (FND-16); PR 1 only requires a named restore point and records it |

## 6. New finding: the publish job fails, so no approved digest exists

[Run 43460563793](https://github.com/Markcino/KoloVibe/actions/runs/43460563793) on `main` `d5fc895`: every gate passes (tests, security, osv, image scan, eight-service smoke) and "Publish verified shared image" then fails in "Authenticate and publish" with `Published image digest belongs to an unexpected repository`. The push itself succeeded (tag `d5fc895…-3284ce8f…`, digest `sha256:3284ce8f…`, copied from the job log), but the job failed before it recorded `published-digest.txt` and uploaded the publication evidence artifact. That digest therefore has no evidence record and **must not be used**; `update --release-dir` cannot accept it.

Likely cause, not confirmed from the log (the offending value is not printed): the job reads `RepoDigests[0]` and requires it to begin with `ghcr.io/<repo>/services@`. Repair in PR 2: select the matching entry by iteration, cross-check it against the digest the push printed, and print the digest list on failure so a further failure is diagnosable.
