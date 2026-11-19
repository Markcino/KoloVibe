# R1 cluster tool: Gateway prior-release guard — 19 November 2026

**Status record. This change deploys nothing, changes no flag, secret or service, and grants no approval.** Evidence is operator-reported, read-only output from 19 November 2026.

## What blocked the rollout

After PR #86 the `aws-staging` plan passed the Gateway flag check and stopped at the next Gateway guard:

`BLOCKED: Gateway differs from the working pinned baseline`

The guard accepts the Gateway only if its image is the 1 November baseline or the exact target being planned. The live Gateway runs the v0.187.2 release, `…services@sha256:0b3bba46…`, which is neither. A read-only read-back confirmed that the image was the only mismatch: the database login, host and name, service name and environment all matched.

The Gateway carries **no service labels**. The tool stamps `kolovibe.source-revision` whenever it applies an update, so the 17 November move to v0.187.2 was not applied by this tool. The tool had no way to plan a second release at all.

## What changed

- `aws-staging` gains `reviewed_releases`: the exact digest of v0.187.2 (CI run 44150174814, source commit `5603230f`). The Gateway guard now accepts the baseline, the exact target, or a digest in that list.
- A review-time check rejects anything that is not an exact `ghcr.io/markcino/kolovibe/services@sha256:<64 hex>` digest, a duplicate, or the baseline. Tags, wildcards and other repositories cannot be listed.
- **Not relaxed:** an unlisted digest of this repository still stops every plan, as do another repository or a tag. The database login, host, environment, hardening, placement, networks and flag checks are unchanged. The Oracle profile lists no earlier release.
- Each future release is added by a reviewed change, so the Gateway cannot drift to an unknown image unnoticed.

## Not changed

No service was updated. The seven other services already accept any digest of the project's repository, so only the Gateway needed this. The R1 rollout, the media-worker image and the VM2 patch window remain separate, separately approved steps.
