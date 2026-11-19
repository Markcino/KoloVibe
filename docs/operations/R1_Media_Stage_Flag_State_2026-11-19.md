# R1 AWS staging: media-stage flag state and read-only verification — 19 November 2026

**Status record only. This change deploys nothing, changes no flag, secret, network or service, and grants no approval.** It adds no credentials, internal addresses, server paths or raw operational logs. Evidence below is operator-reported, read-only output from 19 November 2026.

## What was observed

| Item | Result | Evidence boundary |
| --- | --- | --- |
| Images | All eight APIs on one shared digest; media worker on the media-worker digest | Operator read-back (`docker service ls`) |
| Update state | All eight services last updated 17 November between 21:11 and 21:40 UTC, update status `completed` | Operator read-back |
| Flags (live) | Gateway, Creators, Content: `KOLOVIBE_STAGING_CAPABILITIES=media`. Gateway and Identity: accounts `1`, privileged `0`. All others: baseline (no capability variable). Creator onboarding is set nowhere | Operator read-back, flag variables only |
| `verify-worker` | content, creators, engagement, points, moderation, audit: 12/12 pass; RabbitMQ 4/4; identity 11/12; gateway 26/33 | Tool output, tool hash `8d86cadf…a545ca` verified against the release commit |
| Messaging and R2-proxy overlays | Both internal; both carry the `encrypted` option | Operator read-back |
| Broker | One queue, no backlog, one consumer. Only the content account is connected. Per-service accounts are narrowly scoped; one older account has full permissions on the vhost and is not connected | Operator read-back, names only |

## Why the tool stopped accepting the live state

The cluster tool recognised two flag states, `baseline` and the full `r1` row. The live `media` row is neither, so every manager mode (`plan`, `update-plan`, `update`) stopped at the Gateway check. The profile text already says a different live value "stops the tool until a reviewed change updates the profile": this record and the accompanying change are that review. The repository docs reviewed do not describe how or when the `media` row was applied.

## What changed in the tool

- `aws-staging` gains `media_flags`: an exact third state (`media` on Gateway, Creators and Content only; baseline everywhere else). `--enable-r1-capabilities` moves it to the R1 row.
- A review-time check keeps it a strict step toward R1 (baseline accounts/privileged values, no creator onboarding, only `media`, only on those three services, never a capability the R1 row lacks).
- Near misses are still refused: wider or different capability sets, `media` on any other service, onboarding or privileged without the rest of R1.
- The Oracle profile is unchanged.
- The identity probe in `verify-worker` asserted that a GET of the public login path returns 405. Identity serves only the signed `/internal/auth/*` routes, so it correctly answers 403 and the check could never pass. It now asserts 403 for Identity with a name that says why; the Gateway still asserts 405. A 2xx or 5xx is never accepted.

## What the remaining `verify-worker` failures mean

The seven Gateway failures expect the closed baseline (403 on account and video-write routes). With accounts and media open they return 400 (register, verify) and 401 (login, refresh, logout, `/me`, video write), which are the expected authentication and validation answers. These expectations are not changed here; they will pass or be rewritten with the R1 rollout, when the intended state is final. Treat them as known and explained, not as passes.

## Not changed and still open

- The R1 API rollout (privileged MFA, creator onboarding, caller-key rotation, expanded gateway peers, engagement/points/moderation capabilities) and the six worker and job processes in `staging-aws.yml` remain undeployed and need their own written approval naming exact commands.
- Owner decisions recorded on 19 November: VM2 stays at its current size; an EBS snapshot is wanted before the rollout; R1 scope approval is the owner's and is not given by this record.
- The media worker was killed for exceeding its memory limit on 18 November. Capacity under the full R1 load is not established.
- `verify-edge` targets a host behind Cloudflare Access and asserts the pre-account baseline; it is not a valid pass/fail check for the current state.
- Delivery of identity security-audit events is not running (no delivery process, no mounts); events wait in the database outbox.
