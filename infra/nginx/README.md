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
certificate DNS SAN/Host), `INTERNAL_CA_FILE` and `TUNNEL_CONNECTOR_ADDRESS` (the address or
CIDR the Cloudflare Tunnel connector reaches this listener from, read back on VM1, never a
public range). Do not expand Nginx's own variables
or render credential contents. The gateway Host must be in its exact host allowlist.
Install files with least-privilege ownership and validate with `nginx -t` before
any owner-approved reload. Nginx is unavailable locally, so actual parsing/listener
acceptance is pending, not established by static tests.

**Rate limiting and client address (T10_81, T10_87, D12-001).** Both vhosts limit each client to
10 requests per second (API burst 20, web burst 40) and 20 concurrent connections, answering `429`.
The client is the address in `CF-Connecting-IP`, believed only from the connector
(`set_real_ip_from`; the web vhost listens on loopback only, so its connector is `127.0.0.1`).
Nginx then overwrites `CF-Connecting-IP` with that address and clears `X-Forwarded-For`,
`X-Real-IP` and `True-Client-IP`, so the Gateway, which trusts `CF-Connecting-IP` only
(`KOLOVIBE_TRUSTED_CLIENT_IP_HEADER`), always sees an edge-derived address. A direct-origin caller is
limited and reported by its own address. `scripts/test_edge_client_origin.py` runs the rendered
template on a real Nginx when one is installed. The limits are a first figure for the owner to
confirm; a test through the real Tunnel is still required before the origin budgets count.

Cloudflare Tunnel must verify the origin HTTPS certificate and its approved
server name. Restrict origin network access; a matching public certificate alone
does not prevent direct-origin access. The host-to-private-Swarm route, CA/key
ownership, TLS versus mTLS decision, header/origin-bypass probes and account-wave
ingress changes remain activation gates in the [API roadmap](../../docs/engineering/API_Test_Deployment_Roadmap.md).
No DNS, tunnel, firewall, host configuration or live deployment was changed.
