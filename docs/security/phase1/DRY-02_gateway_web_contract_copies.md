# DRY-02 — Gateway and web validator copies cannot drift

**Type:** guard test (no production change). **Baseline reference:** Phase 0 DRY analysis D-D.

## Duplication verified
`invitation_contracts.py` (56 lines) and `reviewer_contracts.py` (54 lines) are byte-identical in `services/gateway/service/` and `apps/web_django/web/`. `admin_contracts.py` shares its validators and adds four web-only ones (`valid_candidate`, `valid_creator_summary`, `valid_pending_applications`, `_uuid`).

## Decision
The web console is a separate deployable that must reject malformed gateway responses on its own; importing gateway code, or moving the validators into a shared package both images must install, would couple the deployables and widen what each image ships. The existing repository pattern for intentional copies (service identity, `test_service_identity_drift.py`) is to keep the copies and test them. This change applies it.

## Test (`scripts/test_contract_copies_in_sync.py`)
- the two whole-module copies are identical;
- functions defined in both copies of `admin_contracts.py` are identical;
- the set of web-only validators is exactly the four above, so moving one is a visible change.

Runs in the existing `unittest discover -s scripts` CI step. Mutation check: appending a comment to the web `reviewer_contracts.py` fails the test.

## Follow-up (not done)
Promoting these validators into generated code from a single contract in `packages/contracts` is Phase 0 backlog B-13, which depends on DOC-205 approval status.
