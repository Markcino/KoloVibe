# FND-01 — Repository governance

Status: COMPLETE — owner-declared on 1 November 2026, at Mark's direction.

This records the owner's completion declaration, not a new independent verification of GitHub settings. The 30 October observations below are historical. No current protection readback or acceptance exercise was performed during this change.

## Ownership and review model

Mark Allen Gbalazeh (`@Markcino`) is KoloVibe's sole developer and repository owner. Engineering, database, security and operations roles in the tracker describe his responsibilities, not additional team members.

Development changes go through pull requests with documented owner self-review, mandatory CI and resolved conversations. Required approving reviews are zero; code-owner approval, latest-push approval and stale-approval dismissal are disabled. CODEOWNERS remains an ownership record. No additional developer or reviewer appointment is a prerequisite for FND-01.

Self-review and AI assistance do not provide independent security assurance. This adjustment covers the development PR workflow; it does not waive the security evidence or acceptance gates in the approved architecture and Stage 3 plan.

## Prepared controls

- `.github/CODEOWNERS`: existing ownership retained under `@Markcino`.
- `.github/PULL_REQUEST_TEMPLATE.md`: owner self-review, validation and rollout checklist.
- `.github/branch-protection/main.json`: proposed REST payload requiring pull requests, all 12 existing GitHub Actions checks, up-to-date branches, resolved conversations and administrator enforcement. Force pushes and branch deletion are disabled.
- No approval or bypass account is invented. Branch locking stays disabled so changes can merge after required checks.

The committed JSON is configuration to apply; it does not activate protection on GitHub.

## Historical observations — 30 October 2026

| Item | Observed state | Intervention |
| --- | --- | --- |
| Private repository feature eligibility | GitHub rulesets API returns 403 requiring an eligible plan. | Mark arranges an eligible plan for this private repository. |
| Server-side protection | Branch API reports `protected: false`. | Mark applies the policy through administrator settings or GitHub CLI. |
| Administration tooling | Connected tools support repository content changes but no protection-setting writes. | An authenticated administrator performs activation. |
| Acceptance | Effective protection and a protected-PR exercise have not been verified. | Mark records the readback and PR exercise below. |

No reviewer invitation, billing change or protection activation has been performed.

## Activation order

1. Enable an eligible plan for the personal account owning the private repository.
2. Merge the solo-developer governance correction before activation.
3. Review existing rulesets and classic rules. The PUT below replaces classic protection for `main`; reconcile any settings added after this record.
4. Apply the policy through settings or CLI.
5. Read back the effective settings and run the acceptance exercise.

There is no independent-reviewer setup step.

## Apply through GitHub settings

Open [KoloVibe branch settings](https://github.com/Markcino/KoloVibe/settings/branches), create or edit a classic rule targeting `main`, and mirror the JSON:

- Enable **Require a pull request before merging**.
- Leave **Require approvals**, **Require review from Code Owners**, **Require approval of the most recent reviewable push**, and **Dismiss stale pull request approvals** disabled.
- Require all 12 CI checks listed in the JSON, selecting GitHub Actions as their source, and require the branch to be up to date.
- Require resolved conversations and enforce protection for administrators.
- Disable force pushes and deletions. Keep branch locking disabled.

## Apply through GitHub CLI

Run from the repository root using GitHub CLI authenticated as an administrator. Use the existing credential store; do not put tokens into commands, files or commits.

Inspect current access and protection:

```sh
gh auth status --hostname github.com
gh api --hostname github.com repos/Markcino/KoloVibe/branches/main
gh api --hostname github.com repos/Markcino/KoloVibe/branches/main/protection
```

A 403 requires resolving plan/permission access. A 404 may mean no protection exists or the caller cannot read it; confirm administrator access.

After the prerequisites are satisfied:

```sh
gh api --hostname github.com --method PUT repos/Markcino/KoloVibe/branches/main/protection --input .github/branch-protection/main.json
gh api --hostname github.com repos/Markcino/KoloVibe/branches/main/protection
```

Check the effective response:

| Field | Expected |
| --- | --- |
| `enforce_admins.enabled` | `true` |
| `required_status_checks.strict` | `true` |
| `required_status_checks.checks` | All 12 configured names with GitHub Actions app ID 15368 |
| `required_pull_request_reviews.required_approving_review_count` | `0` |
| `required_pull_request_reviews.require_code_owner_reviews` | `false` |
| `required_pull_request_reviews.require_last_push_approval` | `false` |
| `required_pull_request_reviews.dismiss_stale_reviews` | `false` |
| `required_conversation_resolution.enabled` | `true` |
| `allow_force_pushes.enabled` | `false` |
| `allow_deletions.enabled` | `false` |

Do not set `required_pull_request_reviews` to `null`: the object with zero required approvals retains the pull-request requirement.

## Acceptance evidence

Use a small, reversible documentation change on a separate branch:

- [ ] Confirm the owner can open and self-review a PR without being required to approve it.
- [ ] Confirm all 12 required CI checks are attached to the PR.
- [ ] Confirm pending or failed required checks block merging.
- [ ] Push another documentation change and confirm checks apply to the latest commit.
- [ ] Confirm unresolved conversations block merging.
- [ ] Confirm merge becomes available after successful current checks and resolved conversations, with zero required approvals.
- [ ] Retain the settings screenshot, effective configuration readback and PR URL.

Verify force-push and deletion restrictions from the effective settings; do not attempt destructive tests against `main`. Retain future verification evidence separately from the owner's completion declaration.

## References

- [GitHub branch protection REST API](https://docs.github.com/en/rest/branches/branch-protection)
- [Managing branch protection](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/managing-a-branch-protection-rule)
- [Stage 3 current status](Stage3_Current_Status.md)
