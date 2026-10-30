# FND-01 — Repository governance

Status: PARTIAL — repository configuration prepared; server-side enforcement and independent review remain pending.

## Repository changes

- `.github/CODEOWNERS` assigns the existing owner to all files, including CI and governance configuration. It does not yet include an independent reviewer.
- `.github/PULL_REQUEST_TEMPLATE.md` records validation, review and rollout requirements.
- `.github/branch-protection/main.json` is the proposed GitHub REST payload for protecting `main`. Committing this file does not apply protection.
- This runbook records activation steps and acceptance evidence.

The policy requires one code-owner approval, fresh approval after code changes, approval of the latest reviewable push, resolved conversations, up-to-date CI, and enforcement for administrators. Force pushes and branch deletion are disabled. The 12 required check names and GitHub Actions app ID 15368 were verified against main commit `514bfa160c7108cf4975a44477822eacd4a946fd`.

## Observed blockers — 30 October 2026

| Item | Observed state | Intervention |
| --- | --- | --- |
| Private repository feature eligibility | GitHub rulesets API returned 403 with a requirement to upgrade to GitHub Pro or make the repository public. | Account owner arranges an eligible private-repository plan. |
| Independent reviewer | Only `@Markcino` is named in CODEOWNERS. | Owner selects a trusted reviewer, grants write access, and supplies the exact username. |
| Server-side protection | The branch API reports `protected: false`. | Administrator applies the reviewed configuration after the prerequisites below. |
| Administration tooling | The connected GitHub tools expose content changes and protection reads, but no branch-protection write operation. | Administrator uses repository settings or authenticated GitHub CLI. |
| Acceptance | No protected-PR exercise has been completed. | Independent reviewer and owner complete the acceptance exercise below. |

No collaborator invitation or billing change has been made.

## Activation order

1. Enable an eligible plan for the personal account owning this private repository. The observed API response specifically identified GitHub Pro as an option.
2. Add the selected independent reviewer with write access.
3. Through a reviewed PR, add that person's real GitHub username alongside `@Markcino` on every applicable CODEOWNERS line. The `/services/`, `/.github/` and `/infra/` entries override the wildcard entry. Do not commit a placeholder username.
4. Merge that ownership change and this governance PR before activation. A pull request uses CODEOWNERS from its base branch.
5. Review any existing classic protection rules or rulesets. The PUT below replaces classic protection settings for `main`; reconcile it with any settings added since this record.
6. Apply the reviewed policy using the UI or CLI below.
7. Read the effective settings and perform the acceptance exercise.

GitHub does not permit a PR author to approve their own PR. Enabling required code-owner approval while the author is the only code owner will block that author's PRs. A second account controlled by the author does not supply independent review.

## Apply through GitHub settings

Open [KoloVibe branch settings](https://github.com/Markcino/KoloVibe/settings/branches), create a classic branch protection rule for `main`, and mirror the JSON policy:

- Require a pull request, one approval, code-owner review, dismissal of stale approvals, and approval of the latest reviewable push.
- Require all 12 status checks listed in the JSON, with GitHub Actions as their source, and require the branch to be up to date.
- Require resolved conversations and apply protection to administrators.
- Keep force pushes and deletions disabled.

Leave branch locking disabled so reviewed changes can still merge.

## Apply through GitHub CLI

Run from the repository root using GitHub CLI authenticated as an authorized administrator. Use the existing credential store; do not put tokens in commands, files or commits.

First inspect authentication and current protection:

```sh
gh auth status --hostname github.com
gh api --hostname github.com repos/Markcino/KoloVibe/branches/main
gh api --hostname github.com repos/Markcino/KoloVibe/branches/main/protection
```

A 403 indicates unresolved plan/permission requirements. A 404 may mean no protection exists or the caller cannot read it; confirm permissions before applying.

Only after the plan, reviewer and CODEOWNERS prerequisites are satisfied:

```sh
gh api --hostname github.com --method PUT repos/Markcino/KoloVibe/branches/main/protection --input .github/branch-protection/main.json
```

Then read back:

```sh
gh api --hostname github.com repos/Markcino/KoloVibe/branches/main/protection
```

Confirm the response includes:

- `enforce_admins.enabled: true`.
- `required_status_checks.strict: true` and all 12 `checks` with app ID 15368.
- One required approving review, code-owner reviews, stale-review dismissal and latest-push approval.
- `required_conversation_resolution.enabled: true`.
- `allow_force_pushes.enabled: false` and `allow_deletions.enabled: false`.

Do not enable production or environment deployment requirements as part of FND-01; those remain separate acceptance work.

## Acceptance evidence

Use a small, reversible documentation change on a separate branch:

- [ ] Confirm code-owner review is requested on a ready-for-review PR.
- [ ] Confirm merging is blocked before independent approval.
- [ ] Confirm all 12 required CI checks are reported for the PR and complete successfully.
- [ ] Obtain independent approval, then change the PR content and confirm approval must be renewed.
- [ ] Confirm conversations must be resolved before merging.
- [ ] Retain a settings screenshot, effective configuration readback and the reviewed PR URL.

Verify force-push and deletion restrictions from the effective configuration; do not attempt a destructive test against `main`.

Mark FND-01 complete only after effective protection and the acceptance evidence are reviewed. Until then the tracker remains partial.

## References

- [GitHub branch protection REST API](https://docs.github.com/en/rest/branches/branch-protection)
- [Managing a branch protection rule](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/managing-a-branch-protection-rule)
- [CODEOWNERS](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-code-owners)
- [Required reviews](https://docs.github.com/en/pull-requests/how-tos/review-pull-requests/approving-a-pull-request-with-required-reviews)
