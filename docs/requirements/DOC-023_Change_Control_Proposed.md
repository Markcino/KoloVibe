# DOC-023 — Source-document change control

**Status: In review — routine method approved by the owner on 2026-11-22.** [Owner decision](https://github.com/Markcino/KoloVibe/issues/133#issuecomment-7076320307); individual document approvals remain separate. Accountable owner: Mark Allen Gbalazeh (@Markcino). This records the owner-approved routine for the governance already described in the [register](platform_documentation_register_and_DEC001.md); it grants no approval itself.

## Recommended routine

1. Open one issue/change request with its question, current authority, proposed source revision and scope. For this package use `CR-133`; do not reuse DEC-002 or an approved decision ID.
2. Search and inspect the affected sources only. Identify requirements, ADRs, controls, tests, privacy/legal obligations, client/screen expectations, and tracker rows affected. Link evidence instead of copying sensitive material.
3. Record options, the recommended option, security/privacy/cost/operations/open-source implications and risk if wrong. Distinguish corrections to records from new policy or scope decisions.
4. Prepare a draft PR on the issue branch. Keep proposals **Draft**; moving to **In review** records review activity, not acceptance. Run required focused and repository checks; record actual results and unavailable evidence.
5. Obtain the owner's explicit decision against an exact source revision. Record its link, actual date, accepted/deferred/rejected sections, conditions, and accountable owner. Only then apply the authorized **Approved** or **Superseded** transition; retain the previous revision and replacement reference.
6. Update the source register, relevant CSV/ADR status, readiness index and issue together. A partial decision cannot tick a whole tracker item. A baseline approval does not mean deployment, independent assurance, or Stage 1 closure.

No workflow/ruleset/AWS change is part of this routine. Existing self-review does not become independent security/legal review. Plain Markdown, CSV and Git are portable; no new vendor is required.

## Change record template

- Change ID and issue:
- Source files, document IDs, current revision and approval scope:
- Proposed replacement revision and exact fields:
- Question/options/recommendation/risk if wrong:
- Security and authorization/control impact:
- Privacy, retention/residency and legal review impact:
- Cost/capacity/operational and open-source implications (estimates must be labelled):
- Requirements, contracts, migrations, client/screen and evidence links affected:
- Checks run, results, limitations and unresolved issues:
- Owner decision and evidence link:
- Actual decision date and conditions:
- Supersedes/replaced-by reference (only when authorized):
- Register/CSV/readiness/tracker changes verified:

## CR-133 — current proposed change

Scope: document IDs, inventory, approval interpretation, detail-review manifest and research/control proposals only. Source baseline is the commit named in `document_register.csv`; the PR diff identifies this package's exact revision. Approved DEC-001/003/004/005 and OD-07 remain unchanged; DEC-002/006/007 remain open. #134–#137 deliverables, runtime code, deferred features, GitHub rulesets and AWS are not modified.

Impact: preserves source links/history; corrects unsupported approval attribution; exposes missing files/evidence and owner decisions. No implementation pass, legal acceptance or new requirement approval is inferred. Rollback is a reviewed document revert while retaining the issue/decision history.

- Routine owner decision: Approved by Mark Allen Gbalazeh — method only
- Decision reference: https://github.com/Markcino/KoloVibe/issues/133#issuecomment-7076320307
- Actual decision date: 2026-11-22
