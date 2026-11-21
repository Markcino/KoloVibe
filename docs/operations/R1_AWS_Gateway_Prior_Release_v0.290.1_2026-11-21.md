# AWS staging — register the already-running v0.290.1 Gateway image (21 November 2026)

**Status: deployment guard maintenance only.** No service update, migration, broker permission change, secret rotation, network change, DNS or public-web activation is performed by this change.

## Operator-observed evidence and blocker

On AWS manager `ip-172-31-30-236`, the operator's read-only `docker service ls` output reports all eight APIs (including `kolovibe-gateway`) at

`ghcr.io/markcino/kolovibe/services@sha256:03dcdb201d4c2e0e2891dc20b4bdc6836f765ba70a671dcf8af4c17153762333`.

The source commit reported for that release is `1be1236624623c223e944bb8c281ce8cee5e4fe7`. GitHub `main` Actions run [44888581033](https://github.com/Markcino/KoloVibe/actions/runs/44888581033) completed successfully, including the image-publish job, and recorded a `published-image-1be1236624623c223e944bb8c281ce8cee5e4fe7` artifact.

A fresh AWS `worker-preflight` was valid. The manager's `update-plan` for new release `78b28cf584c34fb563c45a9074b525e5a810360d` stopped before any write with:

`BLOCKED: Gateway differs from the working pinned baseline`.

The updater's `base_gateway` accepts only the historical baseline image, the target image, or one explicitly named digest in `AWS_STAGING.reviewed_releases`. The v0.290.1 observed live digest was not listed, so this guard alone explains the stop. The combined error does **not** establish that other aspects of the Gateway specification already match; the next live read-only plan must still verify those.

## Scope of this proposed change

- Add exactly one immutable services digest (the observed v0.290.1 image) to `AWS_STAGING.reviewed_releases`.
- Add regression coverage proving that this earlier digest is accepted for read-only forward planning while unknown digests, tags, other repositories and environment drift remain rejected.
- Keep unchanged the Gateway identity, database host/login, capability states, non-root/read-only mode, secret ownership, encrypted overlays, placement and private port restrictions.
- Leave the Oracle profile and all running AWS services untouched. This is not a waiver of any other guard.

## Required review and execution gates

1. CI passes on this PR; reviewer confirms the previous image digest and its published-image evidence before merge.
2. On VM1, use the reviewed `kolovibe_cluster.py` from **this** PR's merged commit (not the older v0.295.1 script). Verify the Git blob SHA before use.
3. Generate **new** worker evidence on VM2; securely transfer it to VM1, and run `update-plan` within five minutes. Do not synthesize worker evidence.
4. Inspect the entire plan for permitted image-only changes, expected flags/secret mounts, no `BLOCKED` and correct service order. A fresh failure requires diagnosis, not a bypass.
5. Only then run an explicitly confirmed update under the existing approved restricted R1 staging operating rules, verify each service and prepare independent rollback. Do not roll web public or scale the second media worker.
