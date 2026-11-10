# API test deployment roadmap

**AWS staging was deployed and exercised on 10 November 2026.** The [AWS rollout record](../operations/AWS_Staging_Deployment_Verification_2026-11-10.md) covers service convergence, deployed image provenance and distinct public mobile, protected backend and web outcomes. The [R1 tracker](R1_Application_Tracker.md#aws-staging-acceptance-on-10-november-2026) owns application UAT.

**Oracle Cloud baseline · 3 November 2026.** Public acceptance was blocked in that environment.
Owner-supplied live output confirms that `kvtest-gateway` on VM2 passes HTTPS
liveness, certificate verification and PostgreSQL `verify-full` with its
least-privilege schema. The existing database routing, fixed hostname mapping,
firewall and HBA configuration remain unchanged at the owner's request. Independent
public endpoint checks returned HTTP 503 on all 19 cases. The other seven APIs,
RabbitMQ, ingress routing and full deployed acceptance remain pending.

The [3 November deployment record](../operations/Deployment_Verification_2026-11-03.md)
contains the verified commit/image/Actions evidence, endpoint report, capacity-gated
Cloud Shell deployment runner and explicit limits. It supersedes older statements
below that Actions readback or image publication were unverified; historical
local-fixture evidence remains scoped to its original environment.

## Oracle Cloud target and rollout gates

The accepted pilot layout is Cloudflare edge and Tunnel → host Nginx on Oracle VM1 → private Swarm gateway → private services on the VM1 manager/VM2 worker network. RabbitMQ is the Celery broker; PostgreSQL owns business records. VM1 is a single manager and ingress host, so loss of VM1 interrupts service. See the [VM audit runbook](Oracle_VM_Infrastructure_Verification_Runbook.md) and [architecture amendment](../architecture/ADR-003_007_Implementation_Reconciliation_2026-11-01.md).

Current code supports local account APIs, approved-public video and creator metadata, and a non-cash append-only points ledger scaffold. Video playback, provider uploads, eligibility, award calculation, reports/appeals, profile settings and production authentication are not ready for external testing. All eight services now support a fail-closed restricted `staging` profile alongside unchanged local behavior, while continuing to reject `production`. Images use Gunicorn; local runserver remains development-only. The 3 November readback verifies successful CI and publication for commit `be03dbcced01f1a4f71c643dbc179da2810ffa61`; preserve the matching immutable image identified in the deployment record.

## Ordered delivery and acceptance gates

| Gate | Work to complete | Evidence before advancing |
| --- | --- | --- |
| 0. Clean source | Review current diff, run all eight Django suites and migrations, web and Flutter tests, structure/design/contract checks, secret scan, SAST and dependency audit. Resolve any failing GitHub Actions check for the exact candidate commit. | Green checks and recorded commit/image digest; no candidate secret findings. |
| 1. Read-only infrastructure audit | Run the VM1/VM2 metadata-only checks in the VM audit runbook. Confirm actual Tunnel connector, Nginx listener, Swarm nodes/services, RabbitMQ location, PostgreSQL topology, disk and recovery access. | Redacted inventory and INF-01–INF-06 findings; no guessed hostnames, ports or credentials. |
| 2. Staging identity and transport decisions | Implement and verify the owner-approved [ADR-013 client identity and session design](../architecture/ADR-013_Client_Authentication_and_Session_Security_v1.0_APPROVED.md), including lifetimes, refresh/revocation, web sessions/CSRF, MFA, recovery and key rotation. Separately approve ADR-012 workload identity and Nginx→gateway TLS or mTLS, trusted proxy headers and origin policy. Keep privileged APIs disabled until MFA and audit pass. | Full approved session/MFA and transport contracts; negative tests for wrong audience, replay, expiry, forged headers and direct-origin access. |
| 3. Staging settings and contracts | Add explicit staging settings per service and web client: `DEBUG=False`, exact hosts, HTTPS, trusted proxies, cookie/CSRF policy, bounded request bodies, WSGI runtime, redacted logs, and `/api/v1` contract tests. Preserve current local-only settings as a separate profile. | `manage.py check --deploy`, contract tests and a staging build that refuses missing secrets or unsafe hosts. |
| 4. Data and broker | Provision one PostgreSQL owner/login per service with verified TLS and no cross-service privileges. Apply migrations using each owner; configure encrypted backup and perform isolated restore. Configure private RabbitMQ vhosts/users, durable queues, publisher confirms, bounded retries and dead letters. | Cross-service SELECT/DELETE denied, restore timing recorded, duplicate/replay and broker-outage tests pass. |
| 5. Immutable images and Swarm | Build/scan the shared API image once in Actions; test all eight selected services, then publish only that exact checked digest. The single deployment YAML also defines the separately pinned RabbitMQ DHI image. Inject per-service Swarm secrets, not `.env`; use private service/data/messaging zones and reviewed capacity before enabling any zero-replica candidate. | Image/SBOM provenance, secret-mount checks, network isolation, worker failure and rollback results. |
| 6. Edge route | Verify `api.cabetechs.shop` maps through the existing Cloudflare Tunnel to the intended VM1 Nginx virtual host; prepare an access-controlled API test route and only the gateway upstream. Verify the `kolovibe.cabetechs.shop` application route separately. Verify Cloudflare Tunnel service URL and origin certificate with TLS verification enabled; restrict OCI and host firewall rules so Docker, PostgreSQL and RabbitMQ are not public. | External staging request works; direct-origin, wrong Host, invalid certificate and header-spoof probes fail. |
| 7. Restricted API test wave | Permit a small tester cohort. Start with `GET /api/v1/videos` and `GET /api/v1/creators/{id}`; empty and 404 are valid without approved records. Django-native identity selection alone does not enable accounts: registration/login require real SMTP, verified ADR-013 session/MFA implementation, rate limits and secure transport. Enable remaining R1 endpoints only after their owner-approved rules and audit evidence. | Endpoint matrix records success, empty, 401/403/404/429/503, replay and cross-account cases; no seeded password or demo account. |
| 8. Operational acceptance | Add request correlation, redacted logs, alerts, backup monitoring, capacity/load measurements, incident procedure, and a rollback and restore drill. Recheck mobile Android/iOS against the staging HTTPS hostname. | INF-07–INF-10 evidence, signed security/product acceptance and pilot go/no-go record. |

## Immediate API test contract

The first externally reachable staging cut should be read-only. It may return an empty video list and 404 for unknown creators. Do not turn an empty database into sample content. Account testing requires a configured SMTP sender and newly registered tester accounts; the application contains no test credential. The current mobile debug build can use a configured loopback gateway; device/staging builds must use a verified HTTPS gateway URL ending in `/api/v1`.

Do not label the API fully deployed while the current application gaps remain in [R1 application tracker](R1_Application_Tracker.md). `api.cabetechs.shop` and `kolovibe.cabetechs.shop` are owner-reported Cloudflare Tunnel hostnames. Their exact DNS records, ingress mapping, HTTPS behavior, Nginx virtual hosts and deployed gateway routing still require live verification. An externally reachable DNS name does not authorize deployment.

## Restricted staging preparation and evidence

The preparation and fixture results below describe the repository’s Oracle candidate and local test harness. See the dated AWS rollout record above for actual AWS staging results.

Shared infrastructure configuration lives in `services/staging_runtime`; the
eight service settings retain their own apps/models/schema paths. For native
staging commands, include the absolute `services` directory in `PYTHONPATH` while
running from the owning service directory. The shared image copies all service
source into `/app/services` and selects one application at container startup;
see [container verification](container-verification.md#running-separate-services).
Do not set `KOLOVIBE_ENV=local` on a VM to evade these checks.

Required settings are documented by the [Swarm candidate](../../infra/swarm/README.md);
each service needs exact hosts, matching service identity, DEBUG=0, a private
`DJANGO_SECRET_KEY_FILE`, verified-TLS PostgreSQL, server TLS cert/key, internal CA,
caller-key JSON and a separate private probe token file. No SQLite, wildcard
host, plaintext peer or local environment-key fallback is accepted. Runtime DB
logins must not own migration/schema/database CREATE privileges.

Staging APIs do not authenticate through browser cookies: public accounts use
explicit bearer/refresh credentials; private calls use HMAC plus verified TLS.
Therefore `security.W003` is explicitly scoped out of the API deployment check;
the separate web app retains CSRF and cookie controls and is not part of this
staging stack. `security.W005`/`W021` are also scoped out because domain-wide HSTS
and preload are not approved for this restricted pilot. Per-host HTTPS/HSTS and
secure cookie defaults remain enforced. These three documented exceptions are
not production acceptance or permission to silence other check failures.

Accounts default disabled at gateway **and identity**. Preparation supports an
approved account wave through `KOLOVIBE_STAGING_ACCOUNTS=1` and
`KOLOVIBE_ACCOUNT_APPROVAL_FILE`, a JSON object with nonempty reviewed-reference
strings for `identity`, `smtp`, `credentials`, `transport`. Identity additionally
requires SMTP host/port/from address and private SMTP user/password files. References
must correspond to actual owner approvals; parsing the file does not verify their
authenticity. Identity is defined in the single stack, but this wave still needs
reviewed activation, provisioning of the defined SMTP secret mounts and ingress rules. The stack defaults
all eight APIs and RabbitMQ to zero replicas; accounts stay disabled and the
Nginx template blocks them.
All points and other unapproved routes remain blocked regardless of account flags.

Run from the repository root with native PostgreSQL tools and OpenSSL on PATH:

```bash
PYTHONPATH=scripts .venv/bin/python -m verify_staging_runtime
```

This passed against disposable TLS PostgreSQL: eight `check --deploy --fail-level
WARNING` profiles (three explicit policy exceptions above), eight real Gunicorn
HTTPS processes, production/incomplete configuration rejection, least-privilege
schema access, protected probes/readiness, exact Host/TLS checks, public metadata,
default-disabled account routes, real loopback STARTTLS/authenticated SMTP capture,
complete offline protected secret validation, TOTP/recovery login, concurrent
one-use MFA challenges, signed HTTPS audit ingestion and outage/retry recovery,
PostgreSQL security-event UPDATE/DELETE/TRUNCATE rejection, concurrent
refresh reuse/revocation, signing-key rotation, restricted-record 404s, forged
proxy-scheme rejection, pending-migration propagation and dependency-outage 503.
No external mail or existing
database was accessed. Temporary logins, records, certificates and processes are
removed with the fixture.

Additional current results: **115 service tests** and all migration drift checks
passed; **14 web tests**, **74 script regressions**, six local gateway/web journeys
and all PostgreSQL foundation checks passed. `pip check` and the hash-locked
dependency audit pass with no known advisories; cryptography is pinned to 50.0.2.
The stale identity-proposal test now validates the canonical ADR/DOC-205 contract,
without recreating removed duplicate proposal documents or implying approval.

Privileged MFA defaults disabled at both account services and requires separate
MFA/audit approval references in addition to the four account references.
Password login returns 202 without session credentials; `/auth/mfa/verify`
consumes a TOTP/recovery challenge before issuing a fifteen-minute role-bound
privileged session. Ordinary local account behavior remains unchanged. Existing
creator/privileged sessions must reauthenticate after migration. The
[identity runbook](../../infra/swarm/README.md#identity-and-privileged-account-activation)
owns enrollment, private key/secret handling, bounded audit retry and monitored
scheduling requirements; [protected secret validation](../security/staging-verification.md#identity-secrets-offline-validation-only)
owns environment setup. No external mail was sent or real secrets installed.
Privileged client UI, recovery/rotation, retention, actual periodic delivery runner
and remote activation evidence remain open; production is still rejected.
`actionlint -shellcheck='' .github/workflows/ci_cd.yml` passed using the
checksum-verified 1.7.7 tool. Full repository Bandit enforcement passed with zero
medium/high findings; the new runtime/validation source secret scan passed.
The existing PostgreSQL foundation and six local contract journeys were rerun
and passed without changing live data.
The CI trigger regression now matches main-only pushes and manual lock generation.
Docker/image execution, GHCR provenance, actual Nginx syntax/routing, private
network isolation, certificate/workload rotation, backup/restore, alerts and live
account acceptance remain pending. The prepared manifests are not applied; all
changes remain uncommitted for review. Production is still **NO-GO**.

## Reproducible isolated local acceptance

Use Python 3.12 with the existing hash-locked development and CI requirements. Native `initdb`, `pg_ctl` and `openssl` must be on PATH. From the repository root:

```bash
PYTHONPATH=scripts .venv/bin/python -m verify_local_journeys
PYTHONPATH=scripts .venv/bin/python -m test_postgres_foundations
```

The first command creates a fresh TLS PostgreSQL cluster and service-owned logins, migrates only those temporary databases, starts loopback identity/content/creators/gateway/web processes, and captures verification mail privately. It tests real account forms and signed API calls against the existing OpenAPI schema, concurrent refresh reuse, and 21-record pagination. Synthetic records exist only in the disposable fixture. No root `.env`, existing database or external SMTP service is used; task-owned processes and data are removed at exit. The second command checks service isolation, nonce storage, ledger and transactional event foundations. Its publisher remains a double, not live RabbitMQ evidence.

For manual local service use, the existing launcher accepts service-prefixed PostgreSQL settings: `KOLOVIBE_<SERVICE>_DB_NAME`, `DB_USER`, `DB_HOST`, `DB_PORT`, `DB_PASSWORD_FILE` and `DB_SSLROOTCERT` (each suffix uses the same prefix). Supplying any requires the complete set except optional port. The selected service alone receives the corresponding generic settings; inherited service credentials are removed. Engagement/points workers use their own `KOLOVIBE_<SERVICE>_RABBITMQ_URL`. Passwords remain in private local files; persistent CI/deployment values come from Actions/Swarm secrets. SQLite remains a unit-test/local fallback only when no PostgreSQL configuration is supplied.

### Current continuation evidence

| Check | Result |
| --- | --- |
| `python scripts/run_local_service.py SERVICE test tests` for all eight services; corresponding `makemigrations --check --dry-run` | Passed: 101 tests; no migration drift |
| `python scripts/run_local_web.py test tests` | Passed: 14 tests |
| `python -m unittest discover -s scripts -p 'test_*.py'` | Passed: 35 tests |
| `PYTHONPATH=scripts .venv/bin/python -m verify_local_journeys` | Passed: six real PostgreSQL/HTTP/mail/web/contract journeys |
| Disposable PostgreSQL foundation fixture | Passed: 24 tests; plaintext and wrong-host TLS rejected |
| `flutter analyze`; `flutter test` in `apps/mobile` | Passed: clean analysis; 143 tests |
| `flutter build ios --simulator --debug` | Passed: unsigned simulator application; not an App Store or Android release build |
| Structure/design and dependency-lock checks; OpenAPI validation; actionlint on the then-separate API workflow | Passed; current consolidated workflow evidence is in [container verification](container-verification.md#validation-and-remaining-evidence) |
| `bandit -r services scripts apps/web_django` with repository enforcement | Passed gate: 23 low findings, zero medium/high |
| `pip-audit -r requirements-dev.txt --no-deps --disable-pip`; non-ignored source secret scan | Passed: no known dependency advisories or unreviewed secret findings |

An isolated iOS simulator could not finish system-app boot within the bounded wait. It was shut down and deleted; app launch and hot reload are **not verified**. No physical device was modified. Native RabbitMQ/Erlang and Docker were unavailable. The RabbitMQ package attempt was stopped when it required unrelated shared-system dependency upgrades; no existing broker was used. Live broker retry/DLQ/crash tests and container publication remain blocked, not skipped-as-passed. These workflow edits have not been pushed or run in Actions.

**Credential action required:** a credential-like SMTP value was removed from `.env.example`. Treat it as exposed and revoke/rotate it with the provider; clearing the current file does not remove prior Git history. Do not reuse it for local or Actions configuration. No credential value is reproduced in documentation.

## Vendor references

- [Django deployment checklist](https://docs.djangoproject.com/en/5.2/howto/deployment/)
- [Docker Swarm rolling updates and rollback](https://docs.docker.com/engine/swarm/)
- [Docker Swarm secrets](https://docs.docker.com/engine/swarm/secrets/)
- [Cloudflare Tunnel HTTPS origin verification](https://developers.cloudflare.com/tunnel/troubleshooting/https-origins/)
- [OCI network security controls](https://docs.oracle.com/en-us/iaas/Content/Security/Reference/networking_security.htm)

