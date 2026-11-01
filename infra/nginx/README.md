# VM1 host Nginx — restricted staging candidate

Nginx runs outside Swarm on **VM1**, alongside the single manager, per the accepted
[ADR-003 amendment](../../docs/architecture/ADR-003_007_Implementation_Reconciliation_2026-11-01.md).
VM2 is the worker; no third dedicated ingress VM is assumed.

[staging.conf.template](staging.conf.template) allows only health, the protected
`/ops/verify` probe and approved-public metadata on `api.cabetechs.shop`. It blocks
accounts and all other routes, verifies upstream TLS/SNI, discards supplied proxy
headers and disables access logs to avoid logging credential-bearing queries.
Gunicorn trusts its direct TLS connection, not forwarded scheme headers.

Render only these named inputs: `ORIGIN_CERT_FILE`, `ORIGIN_KEY_FILE`,
`GATEWAY_PRIVATE_ENDPOINT` (private address and port), `GATEWAY_TLS_NAME` (approved
certificate DNS SAN/Host) and `INTERNAL_CA_FILE`. Do not expand Nginx's own variables
or render credential contents. The gateway Host must be in its exact host allowlist.
Install files with least-privilege ownership and validate with `nginx -t` before
any owner-approved reload. Nginx is unavailable locally, so actual parsing/listener
acceptance is pending, not established by static tests.

Cloudflare Tunnel must verify the origin HTTPS certificate and its approved
server name. Restrict origin network access; a matching public certificate alone
does not prevent direct-origin access. The host-to-private-Swarm route, CA/key
ownership, TLS versus mTLS decision, header/origin-bypass probes and account-wave
ingress changes remain activation gates in the [API roadmap](../../docs/engineering/API_Test_Deployment_Roadmap.md).
No DNS, tunnel, firewall, host configuration or live deployment was changed.
