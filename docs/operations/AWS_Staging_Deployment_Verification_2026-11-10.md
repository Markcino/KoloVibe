# AWS staging deployment verification · 10 November 2026

The owner-provided deployment transcripts show that the AWS Swarm stack converged to 10 of 10 services at 1/1 replicas. The separate [Oracle Cloud record](Deployment_Verification_2026-11-03.md) covers a different deployment. This AWS snapshot establishes staging availability for the paths below. Production and pilot acceptance remain open.

## Runtime and rollout

| Area | Recorded evidence |
| --- | --- |
| Placement | AWS VM1 was the Swarm manager and leader in Drain. VM2 was the active workload worker. The owner reported host Nginx on VM1 and removal of the worker’s Tunnel connectors and temporary port exposure. |
| Application | Eight migration jobs completed. Gateway, identity, creators, content, engagement, points, moderation and audit converged from startup to 1/1 each. The owner reported eight passing Django service probes. |
| PostgreSQL | The PostgreSQL DHI service reached 1/1. The initial privilege-audit query failed for all eight services while resolving cross-schema names. The owner subsequently reported an 8/8 pass with the catalog-OID audit. Backup and restore evidence remains open. |
| RabbitMQ | The RabbitMQ DHI service reached 1/1. The broker inspection showed a healthy node, no alarms, a TLS AMQP listener and the application vhost. The queue listing was empty. Celery delivery, retries, dead letters and crash recovery still need evidence. |

The eight Django services used `ghcr.io/markcino/kolovibe/services@sha256:8d6a16e450e6a7825c7d501069cd54fa3a75776afc2819e5664499bcef85ea14`. The [published-image record](Deployment_Verification_2026-11-03.md#verified-source-and-image) identifies its source commit as `be03dbcc`. The mobile startup fix in PR #30 is a Flutter source change. The 10 November [main workflow run](https://github.com/Markcino/KoloVibe/actions/runs/42830288613) skipped shared-image publication after CI failures.

## Edge and acceptance

| Endpoint or surface | Observed result |
| --- | --- |
| Protected backend, `api.cabetechs.shop` | The owner reported HTTP 401 without authorization and HTTP 200 with authorized verification. Nginx-to-gateway TLS verification was reported active. |
| Mobile staging API, `mobile-api.cabetechs.shop/api/v1` | The staging API suite passed 15/15 across this host and the protected backend. Gateway discovery returned 200, an invalid cursor returned 400, and an unknown creator returned 404. |
| Web, `kolovibe.cabetechs.shop` | The owner reported the HTTP 503 placeholder. Web rollout remains open. |
| iPhone and account API | The tester reported 9/9 account steps passed. Two verified accounts received their own profile, signed out, and received 401 with their former access token. Refresh-token revocation after logout remains unverified. The merged startup restore fix awaits a physical iPhone retest. |

The [R1 application tracker](../engineering/R1_Application_Tracker.md#aws-staging-acceptance-on-10-november-2026) owns application and device acceptance, including Android UAT, refresh/replay behavior, secure storage and rate-limit evidence. Operational acceptance still needs audit monitoring, restore and rollback drills, and resilience evidence.
