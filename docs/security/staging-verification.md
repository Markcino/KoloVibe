# Environment security verification

This repository provides a controlled verification script for an explicitly approved environment. It cannot attest to security without an actual deployed environment, route configuration, network ACL evidence, and authorized review.

## Runbook
1. Configure the isolated deployment, DNS, TLS, service gateway, and security policies under approved architecture decisions.
2. Obtain authorization for the exact test hostname and record it.
3. Set `KOLOVIBE_STAGING_URL=https://<approved-host>` and `KOLOVIBE_STAGING_HOST=<approved-host>` locally or within a protected GitHub environment.
4. Execute `python scripts/verify_staging.py`. This checks HTTPS/TLS, a public health endpoint if approved, and that reserved internal paths reject anonymous access. These HTTP probes alone do not prove host-level network isolation or prevent origin bypass.
5. Attach results, reverse proxy configuration, firewall tests, authenticated service-access negative tests, database isolation checks, secret rotation, backup restoration, and rollback evidence.
6. A security reviewer must sign off on the findings before accepting staging controls.

**Never use a production hostname for this runbook.** This probe is intentionally non-destructive and does not attempt penetration testing or unauthorized scanning.

## Blockers
No deployed environment endpoint, certificate, security-group configuration, access credentials, or SSH permission is currently supplied to the repository. Until they are provided, real network-isolation, mTLS/transport, host hardening, backups, and origin-bypass tests are **not executed**.
