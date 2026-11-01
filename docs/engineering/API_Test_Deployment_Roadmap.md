# API test deployment roadmap

**Status: planning and local verification only (1 November 2026).** No staging or production deployment is claimed. The intended future public host is `kolovibe.cabetechs.shop`; use a separate, access-controlled staging hostname for API testing after the owner confirms DNS and access policy. Do not expose the root `.env` or use `KOLOVIBE_ENV=local` on either VM.

## Target and current boundary

The accepted pilot layout is Cloudflare edge and Tunnel → host Nginx on Oracle VM1 → private Swarm gateway → private services on the VM1 manager/VM2 worker network. RabbitMQ is the Celery broker; PostgreSQL owns business records. VM1 is a single manager and ingress host, so loss of VM1 interrupts service. See the [VM audit runbook](Oracle_VM_Infrastructure_Verification_Runbook.md) and [architecture amendment](../architecture/ADR-003_007_Implementation_Reconciliation_2026-11-01.md).

Current code supports local account APIs, approved-public video and creator metadata, and a non-cash append-only points ledger scaffold. Video playback, provider uploads, eligibility, award calculation, reports/appeals, profile settings and production authentication are not ready for external testing. All service settings currently reject any environment other than `local`; runserver is development-only. An older CI run recorded a secret-discovery failure; verify the latest exact commit's check status before promoting any image.

## Ordered delivery and acceptance gates

| Gate | Work to complete | Evidence before advancing |
| --- | --- | --- |
| 0. Clean source | Review current diff, run all eight Django suites and migrations, web and Flutter tests, structure/design/contract checks, secret scan, SAST and dependency audit. Resolve any failing GitHub Actions check for the exact candidate commit. | Green checks and recorded commit/image digest; no candidate secret findings. |
| 1. Read-only infrastructure audit | Run the VM1/VM2 metadata-only checks in the VM audit runbook. Confirm actual Tunnel connector, Nginx listener, Swarm nodes/services, RabbitMQ location, PostgreSQL topology, disk and recovery access. | Redacted inventory and INF-01–INF-06 findings; no guessed hostnames, ports or credentials. |
| 2. Staging identity and transport decisions | Record ADR-013 token/key ownership, MFA boundary and rotation; approve Nginx→gateway TLS or mTLS and workload identity, trusted proxy headers and origin policy. Keep privileged APIs disabled until MFA and audit pass. | Approved ADRs and negative tests for wrong audience, replay, expired tokens, forged headers and direct-origin access. |
| 3. Staging settings and contracts | Add explicit staging settings per service and web client: `DEBUG=False`, exact hosts, HTTPS, trusted proxies, cookie/CSRF policy, bounded request bodies, WSGI runtime, redacted logs, and `/api/v1` contract tests. Preserve current local-only settings as a separate profile. | `manage.py check --deploy`, contract tests and a staging build that refuses missing secrets or unsafe hosts. |
| 4. Data and broker | Provision one PostgreSQL owner/login per service with verified TLS and no cross-service privileges. Apply migrations using each owner; configure encrypted backup and perform isolated restore. Configure private RabbitMQ vhosts/users, durable queues, publisher confirms, bounded retries and dead letters. | Cross-service SELECT/DELETE denied, restore timing recorded, duplicate/replay and broker-outage tests pass. |
| 5. Immutable images and Swarm | Build and scan each image in Actions. Publish only the exact checked digest; inject per-service secrets with Swarm secrets, not a committed or copied `.env`. Place gateway on a private ingress network, services and data on isolated networks, and constrain placement to verified VM capacity. Define health checks, resource limits and rolling rollback. | Image/SBOM provenance, secret-mount checks, network isolation, worker failure and rollback results. |
| 6. Edge route | Configure VM1 host Nginx for the staging hostname and only the gateway upstream. Verify Cloudflare Tunnel service URL and origin certificate with TLS verification enabled; restrict OCI and host firewall rules so Docker, PostgreSQL and RabbitMQ are not public. | External staging request works; direct-origin, wrong Host, invalid certificate and header-spoof probes fail. |
| 7. Restricted API test wave | Permit a small tester cohort. Start with `GET /api/v1/videos` and `GET /api/v1/creators/{id}`; empty and 404 are valid without approved records. Enable account registration/login only after SMTP, session ADR, rate limits and secure transport pass. Enable each remaining R1 endpoint only after its owner-approved rules and audit evidence. | Endpoint matrix records success, empty, 401/403/404/429/503, replay and cross-account cases; no seeded password or demo account. |
| 8. Operational acceptance | Add request correlation, redacted logs, alerts, backup monitoring, capacity/load measurements, incident procedure, and a rollback and restore drill. Recheck mobile Android/iOS against the staging HTTPS hostname. | INF-07–INF-10 evidence, signed security/product acceptance and pilot go/no-go record. |

## Immediate API test contract

The first externally reachable staging cut should be read-only. It may return an empty video list and 404 for unknown creators. Do not turn an empty database into sample content. Account testing requires a configured SMTP sender and newly registered tester accounts; the application contains no test credential. The current mobile debug build can use a configured loopback gateway; device/staging builds must use a verified HTTPS gateway URL ending in `/api/v1`.

Do not label the API fully deployed while the current application gaps remain in [R1 application tracker](R1_Application_Tracker.md). `kolovibe.cabetechs.shop` remains reserved for a later production release; DNS ownership and final hostname routing need explicit verification.

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
