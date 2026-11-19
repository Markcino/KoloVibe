# R1 staging status reconciliation — 17 November 2026

**Restricted staging is deployed on v0.187.2. Full R1 and production acceptance remain incomplete.**

This status-only reconciliation uses the owner's Application Implementation Audit results from 17 November and GitHub publication evidence. It adds no infrastructure configuration, credentials, internal addresses, server paths or raw operational logs. No deployment or acceptance test was run as part of this documentation change.

## Evidence and limits

| Item | Status | Evidence boundary |
| --- | --- | --- |
| Release publication | Verified in GitHub | [CI run 44150174814, attempt 2](https://github.com/Markcino/KoloVibe/actions/runs/44150174814/attempts/2) succeeded for source commit 5603230f0c27a4fe426dcab43afed731c6ec6bb1; shared and media images were published as v0.187.2 |
| Eight backend APIs | Deployment completed, operator-reported | The audit's 21:41 UTC output reported all eight at their desired replica count |
| Media worker | Startup completed, operator-reported | The same audit reported a running worker and one media-queue consumer; this does not establish real video processing |
| Integrated assessment | **26 passed / 0 failed / 19 pending** | Recorded in the audit at 21:44 UTC; preserve these totals until a new assessment is recorded |
| Authentication routing | Passed for submitted probes | At 21:48 UTC, local and public POST requests returned JSON: login 401, register 400, refresh 401; public certificate verification succeeded |
| Successful authentication on v0.187.2 | Pending evidence | Invalid-input routing responses do not establish successful login, profile access or valid refresh |
| Full functional/security acceptance | Pending | CI fixtures, service startup and idle queues do not establish live end-to-end journeys |

The subsequent assistant recap claiming current-release login/profile results of 200/200/401 is not substantiated by the retrieved user output in **Application Implementation Audit**, and is not used to close a gate. The separate Authentication Routing Test conversation is not used as evidence for this reconciliation. Keep the successful [10 November account UAT](../engineering/R1_Application_Tracker.md#aws-staging-acceptance-on-10-november-2026) as historical evidence for its tested release.

## Continuation

Finish documentation reconciliation, then continue the unfinished acceptance work:

- Authenticated login and own-profile access on the recorded release.
- C-01 valid refresh; C-02 rotation/replay; C-03 logout/revocation.
- C-04 expired/tampered credentials; C-05 cross-account authorization.
- C-06 mobile persistence; C-07 throttling/abuse protection.
- Creator onboarding and eligibility.
- Real video upload, processing, moderation/publication, playback and ownership.
- Engagement, non-cash points, duplicate/recovery behavior, moderation and audit delivery.
- Physical-device journeys and separate background-job acceptance.

These are work groups, not a reconstruction of the report's 19 individual pending rows. Do not recalculate the original totals from this list. Preserve completed deployment/routing results and repeat checks only when the target changes or new evidence requires it.

## Document reconciliation

The [application tracker](../engineering/R1_Application_Tracker.md) owns delivery status and the [API roadmap](../engineering/API_Test_Deployment_Roadmap.md) owns continuation. This dated record supersedes earlier statements that image publication, eight-service deployment or media-worker startup have not happened. Earlier failure logs and candidate plans remain historical records, not instructions to repeat provisioning or rollout.

Stage 3 remains owner-declared complete; Stages 4 and 5 remain in progress. Existing owner decisions and restricted-staging waivers remain unchanged; neither a waiver nor deployment convergence is a passed acceptance control. Approved MVP scope remains unchanged. This update grants no new deployment, migration, policy or production approval.
