# Release reconciliation for v0.542.1 (D13-005), 27 November 2026

**Status: TOOL READY, READBACK NOT RUN.** This session has no operator access to the staging VMs. The readback below is read-only, but it has to be run on VM1 by the operator.

## The publication (from CI, not from staging)

`main` CI run 542 ([45850836406](https://github.com/Markcino/KoloVibe/actions/runs/45850836406)), source `38d038056cf77df4d4193e0aecef472dc7226aea`. The digests below were read from that run's publish job log (job 140019256339):

| Image | Digest |
|---|---|
| Shared services (8 APIs and the jobs) | `ghcr.io/markcino/kolovibe/services@sha256:ab9c0e0d6172d747b29d6d1b4a3f3bae61428d5cdbab99e394b6d937f6844caf` |
| Media worker | `ghcr.io/markcino/kolovibe/media-worker@sha256:247b7dfbd5a537b272eb0ff236c0f2f2bd486dd5d763676ef6495a547b634e21` |
| Web console | `ghcr.io/markcino/kolovibe/web@sha256:d94fd230f1e198d1f06b6bde2b32ec47feb2728258e40fbdaefd0ea7d61abae4` |

The `published-image-<sha>` artifacts hold the same values. This session could not download them, because the network blocks the artifact host.

## What D13-005 found (26 November)

v0.531.1 was rolled out outside the reviewed tool. The services kept the v0.341.1 `kolovibe.source-revision` and pin-proof labels, and the jobs stack label still named v0.205.1. So the tool could not prove the live state. v0.542.1 was then deployed in two ways (#169, 26 November 17:55 UTC):

- the 8 APIs through the tool, which writes the labels;
- the jobs, the media worker and the web console by pinned digest.

Whether the second group carries v0.542.1 labels has **not been read back**.

## The readback (read-only, on VM1, as root)

```sh
python3 kolovibe_cluster.py release-readback --profile aws-staging \
  --image ghcr.io/markcino/kolovibe/services@sha256:ab9c0e0d6172d747b29d6d1b4a3f3bae61428d5cdbab99e394b6d937f6844caf \
  --media-image ghcr.io/markcino/kolovibe/media-worker@sha256:247b7dfbd5a537b272eb0ff236c0f2f2bd486dd5d763676ef6495a547b634e21 \
  --web-image ghcr.io/markcino/kolovibe/web@sha256:d94fd230f1e198d1f06b6bde2b32ec47feb2728258e40fbdaefd0ea7d61abae4 \
  --revision 38d038056cf77df4d4193e0aecef472dc7226aea
```

For every service built from one of the three project images, the readback checks two things:

- the digest is exactly the published one;
- the `kolovibe.source-revision` label equals the release commit.

PostgreSQL, RabbitMQ and the R2 proxy are listed and skipped. The command exits 2 on any FAIL. Nothing is changed: it uses GET only, behind the same manager checks as every other mode.

## Closing D13-005

1. The operator runs the readback and attaches the JSON to #169 and to this record. It holds names, digests and labels only.
2. **If every check passes:** the deployed state is proven by the reviewed tool, and D13-005 can be closed.
3. **If a job, media or web service FAILs only on its label:** correct the label with `docker service update --label-add kolovibe.source-revision=38d0380… <service>`, one service at a time, then run the readback again.
   - This changes service metadata on staging, so it needs the owner's go-ahead.
   - It restarts no task in Swarm, since a label-only update does not change the task template.
   - Rollback: `--label-add` back to the previous value, recorded from the readback.
4. **If a digest FAILs:** stop. That service does not run v0.542.1 and needs its own reviewed rollout.

## Process change

From now on, every rollout, including the jobs, media and web, ends with `release-readback` for the release it deployed. The rollout counts as recorded only once that readback has passed.
