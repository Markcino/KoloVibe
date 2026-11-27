# Main branch ruleset: solo-developer workflow plan (#142), 27 November 2026

**Status: PROPOSED, NOT APPLIED.** Applying it changes a repository ruleset, so it waits for the owner's written go-ahead. This file is the plan, the payload, the readback and the rollback.

## Current state (readback, 27 Nov 2026 06:10 UTC)

`gh api repos/Markcino/KoloVibe/rulesets` returns one active ruleset, `KoloVibe Rules` (id 26202507). It targets `~DEFAULT_BRANCH` with no bypass actors. It has only two rules:

- `deletion`
- `non_fast_forward`

Classic branch protection on `main` is not set (`branches/main/protection` answers 404). So today a direct push to `main` is allowed, and so is a merge with failing or missing checks.

## Proposed rules

These are added to the same ruleset. The two existing rules are kept.

| Rule | Setting | Why |
|---|---|---|
| `pull_request` | `required_approving_review_count: 0`, `dismiss_stale_reviews_on_push: false`, `require_code_owner_review: false`, `require_last_push_approval: false`, `required_review_thread_resolution: false` | Every change goes through a PR. No second approver is required, because there is one everyday developer. |
| `required_status_checks` | `strict_required_status_checks_policy: false`; the 15 checks below, each with `integration_id: 15368` (GitHub Actions) | A merge with failing or missing checks is blocked. "Strict" (branch up to date) is left off so a solo flow is not forced to re-run CI after every merge. |
| `deletion`, `non_fast_forward` | unchanged | |

The 15 required checks are the jobs that run on every pull request in `.github/workflows/ci_cd.yml`. The job names were confirmed on PR #268, head `1053b33`.

- Django services and reproducibility
- Security scans and SBOM
- Flutter static and widget tests
- Python and Flutter dependency advisories / osv-scan
- Build and scan shared service image
- Build and scan media worker image
- Build and scan staging web image
- Image build and security / gateway
- Image build and security / identity
- Image build and security / creators
- Image build and security / content
- Image build and security / engagement
- Image build and security / points
- Image build and security / moderation
- Image build and security / audit

Not required: the dispatch-only jobs (skipped on PRs), `Publish verified shared and media worker images` (main only), and GitGuardian (a third-party app).

No bypass actor is added. An emergency change then needs the rule set to `evaluate`, recorded on #142, and set back to active afterwards.

## Apply (owner-approved only)

```sh
gh api -X PUT repos/Markcino/KoloVibe/rulesets/26202507 --input docs/operations/R1_Main_Ruleset_2026-11-27.json
```

## Readback

```sh
gh api repos/Markcino/KoloVibe/rulesets/26202507 --jq '{enforcement, bypass_actors, rules}'
gh api repos/Markcino/KoloVibe/rules/branches/main
```

The readback passes when:

- the ruleset is `active` with no bypass actors;
- the four rules are present;
- the 15 contexts match the JSON exactly.

## Proof that merging is blocked

1. Open a throwaway draft PR that changes only a comment. While its CI is still running, call `gh api -X PUT repos/Markcino/KoloVibe/pulls/<n>/merge`. It must answer 405 with a message saying the required status checks are expected. That is the missing-checks case.
2. For the failing-checks case, use the same PR with one scripts test changed to fail. After CI reports the failure, the merge call must still answer 405.
3. Try a direct `git push origin HEAD:main`. It must be rejected by the `pull_request` rule.
4. Close the PR and delete its branch.

Record the three answers on #142.

## Rollback

Restore the two original rules:

```sh
gh api -X PUT repos/Markcino/KoloVibe/rulesets/26202507 --input docs/operations/R1_Main_Ruleset_Rollback_2026-11-27.json
```

Then repeat the readback.

## Operational notes

- When a CI job is renamed, update the list of required checks in the same PR. Otherwise every PR waits on a check that never reports.
- The OpenSSL exception expiry (#143) fails the scan jobs from 28 November unless it is remediated. With this ruleset active, that blocks every merge until remediation or a recorded renewal decision. That is the intended fail-closed behaviour.
