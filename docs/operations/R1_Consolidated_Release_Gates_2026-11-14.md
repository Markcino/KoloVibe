# KoloVibe R1 consolidated release-candidate gates — 2026-11-14

Status: **PREPARATION / NO-GO**. This document does not authorize infrastructure changes, PR merges, image publication or deployment.

## Source baseline
- Base `main`: `de8737a8d4eb63732c3610e8deeca26027b74908`.
- Repository file inspected: `scripts/ops/kolovibe_cluster.py`.
- The current `Profile.gateway_flags` and `base_gateway()` check only gateway flags. `api_spec()` clones the gateway spec, including its environment, before service-specific updates. A per-service guard requires code and tests.
- The local `ebe3068` implementation reported by the operator is **not present on a remotely accessible branch**. Do not claim it is integrated or tested.

## Mandatory repository-side gates
- [ ] Integrate and review per-service staging flag table for all eight services, with gateway/identity account agreement and no flag leakage to other services.
- [ ] Confirm update-plan/update fail closed on mismatched per-service flags without logging environment values.
- [ ] Correct AWS worker-label, existing encrypted-backup and GHCR publication documentation from primary evidence.
- [ ] Verify all eight backend services, API contracts, R2/FFmpeg on-demand video pipeline, RabbitMQ consumers and mobile integrations against actual source.
- [ ] Run complete applicable Django, Flutter, security, infrastructure, dependency and image CI tests on the release branch.
- [ ] Open a draft PR and review exact diff. Do not merge without owner approval.

## Mandatory operational gates (separate approvals)
- [ ] Verify PostgreSQL and RabbitMQ health and end-to-end messaging.
- [ ] Verify selected immutable GHCR digest and registry access without exposing credentials.
- [ ] Rehearse OPA on a disposable environment; document results and manager authorization plan.
- [ ] Approve, create and restore-test an encrypted PostgreSQL backup; record rollback and recovery objectives.
- [ ] Verify AWS capacity, Swarm placement, permissions and service health.
- [ ] Approve exact deployment digest, service changes, migration order, maintenance impact and rollback point.
- [ ] Explicit owner authorization before any AWS mutation.

## Physical-device UAT after approved deployment
- [ ] Install staging Flutter build on physical iPhone.
- [ ] Register, verify, sign in, close/reopen app and confirm persistent authenticated session.
- [ ] Verify token refresh, logout, expired-session handling and account access controls.
- [ ] Complete creator onboarding and profile changes.
- [ ] Upload video, process via FFmpeg, publish and play back from R2 delivery path.
- [ ] Validate server-verified views/likes, non-cash points, moderation and audit trail.
- [ ] Record device/build, API release digest, expected/actual outcomes and evidence for each journey.

**Deployment decision: NO-GO until all mandatory gates pass and the owner approves the exact deployment plan.**
