# KoloVibe Oracle / Cloudflare deployment preflight

**Date:** 2026-11-01. **Decision:** NO-GO for production; allow read-only verification and reviewable repository changes. This evidence is from user-supplied VM output and the connected GitHub repository, not independently authenticated access to Oracle or Cloudflare. It is not security sign-off.

## Observed controls

| Area | Evidence | Status |
| --- | --- | --- |
| Swarm | VM1 manager Leader/Ready and VM2 worker Ready; Engine 29.3.0 | Manager-controlled operations verified; single manager is NOT HA |
| Overlays | kolovibe_services 172.28.10.0/24; kolovibe_messaging 172.28.11.0/24; kolovibe_data 172.28.12.0/24; encryption option present | Known host-subnet collision corrected; full OCI/VPN overlap and IPsec packet verification pending |
| Cross-node | worker-ok via service VIP and task IP from VM1; manager-ok from VM2 | Passed on services overlay only |
| Host firewall | Peer-scoped TCP/UDP 7946, UDP 4789 and ESP; firewall systemd units active | Runtime passed; reboot persistence and broad existing ACCEPT / OCI NSG review pending |
| Cloudflare/Nginx | api.cabetechs.shop and kolovibe.cabetechs.shop forwarded through Tunnel to VM1 Nginx intentional 503 placeholders | Hostname routing verified, but no API or private TLS upstream acceptance |
| Docker OPA on VM1 | openpolicyagent/opa-docker-authz-v2:0.9 points to missing /etc/docker/policies/authz.rego; fail-open warnings observed | CRITICAL; local OPA v1 tests are not production enforcement |
| GHCR | Eight images published for commit 8d41b99a7fb7efbb20d2c3e87571069b68ddd9d9 | Registry push verified, not a production-approved release |
| Django | Restricted staging.yml with Gunicorn, health checks and external secrets | No production deployment authorization or tested live stack |

## Security and release hold points

1. OPA: repair fail-open with offline policy tests matching the new shared registry image pattern ghcr.io/markcino/kolovibe/services@sha256:DIGEST and the approved per-container KOLOVIBE_SERVICE_NAME. The historical eight packages above are not the new release format. Validate real Docker API requests for service create/update, secrets, networks, recovery and negative tests before activating. Current lab policy denies legitimate Swarm updates; never copy it directly to live path. Require independent console recovery path.
2. Edge: verify Cloudflare origin authentication/WAF/Access and direct-origin denial. The verified tunnel target uses localhost:80 but the new Nginx staging template expects a 443 TLS listener. Reconcile without replacing working host routes. Design Nginx-host-to-private-gateway authenticated TLS, with exact Host/certificate checks and negative spoof tests. Do not expose Django ports publicly.
3. Firewalls: read back OCI VCN/security lists/NSGs and host INPUT/FORWARD. Restrict broad Swarm ports to trusted peer IPs, preserve Docker's unencrypted VXLAN guard, and check ingress 10.0.0.0/24 against complete OCI/VPN routes. Verify reboot persistence during a planned maintenance window, using Bastion/console recovery.
4. CI/release: require all same-commit quality and security gates and a verified published GHCR digest. A prior successful publication cannot approve a later commit; investigate secret-scanner findings rather than bypassing them. Do not deploy dev-mode images.
5. RabbitMQ: the broker manifest must use kolovibe_messaging and an explicitly capacity-reviewed memory limit, not 1024M on ~956 MiB RAM VMs. Require pinned DHI digest, secrets, TLS-only broker, durable node-bound storage, monitored alarms and recovery tests. The candidate is not running and is not safe to deploy without budget verification.
6. PostgreSQL and operations: decide actual DB provider/topology, TLS verify-full and per-service roles; prove backups, timed restore and RPO/RTO. Test rollback, monitoring, audit retention, alerts and manager/worker recovery.
7. Governance: preserve historical DOC-208 and DOC-209 baselines; this dated implementation diagram and network register reflect the user-confirmed VM1/VM2 and RabbitMQ amendment, NOT a new final architecture approval. Update the Stage 3 evidence and record deployment acceptance only after live verification.

## Deployment boundary

Use GitHub Actions to test, scan and publish immutable GHCR digests. Deploy from VM1 manager only after the stack, credentials, OPA enforcement and ingress are accepted; VM2 receives scheduled tasks without routine SSH. Host patching and incident recovery may still require VM2 maintenance or supported automation.

No DNS, Docker daemon, Cloudflare Tunnel, VM firewall, Swarm stack or live OPA policy is changed by these repository-only updates.

## Read-only manager preflight commands

    hostname
    sudo nginx -t
    systemctl is-active nginx cloudflared docker kolovibe-swarm-firewall || true
    docker node ls
    docker service ls
    docker network ls --filter driver=overlay
    docker info --format 'Auth plugins: {{json .Plugins.Authorization}}'
    sudo test -f /etc/docker/policies/authz.rego && echo 'OPA policy present' || echo 'OPA policy MISSING'
    sudo iptables -S INPUT | grep -E '7946|4789|2377|REJECT|DROP' || true

Never paste Docker secrets, private keys, or an unredacted service environment into tickets or chats.
