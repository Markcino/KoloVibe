# Environment security verification

KoloVibe runs its authorized remote checks exclusively through the **GitHub Environment**
`staging-security-review`. The workflow is manually dispatched, has read-only repository
permissions, and must be protected by required reviewers and an allowed deployment branch.

## Environment configuration

In GitHub: **Settings → Environments → staging-security-review**. Create it and configure:

| Type | Name | Purpose |
| --- | --- | --- |
| Environment variable | `KOLOVIBE_STAGING_URL` | Approved HTTPS origin; no paths or redirects |
| Environment variable | `KOLOVIBE_STAGING_HOST` | Same approved DNS hostname |
| Environment variable | `KOLOVIBE_STAGING_CHECK_PATH` | Explicit, read-only, authenticated health route such as `/ops/verify` |
| **Environment secret** | `KOLOVIBE_STAGING_CHECK_TOKEN` | Dedicated least-privilege bearer token accepted by that route |

The health endpoint and its token verification must be implemented in the deployed
application before this workflow will succeed. It must respond `200` with
`{"status":"ok"}` only to a valid authorized token. Keep the token limited to verification,
rotate it, and never grant publishing, administration or database permissions.

Do **not** create these credentials as repository secrets, put them in Git, write them
into workflow artifacts or echo them to logs. GitHub protects stored secret values,
but an approved workflow can read them, so restrict branch selection, reviewers
and workflow-edit permissions. Use environment-specific identity/federation instead
of long-lived deployment SSH keys where possible.

## Execution

1. Confirm DNS, TLS and the destination are authorized for testing.
2. Restrict environment deployments to reviewed `main` and require independent reviewers
   in GitHub environment protection settings (if supported by your plan).
3. Under **Actions → ci_cd → Run workflow**, select reviewed `main` and operation
   **staging-security**. Other refs are rejected; normal CI never receives the probe secret.
4. Review the output and retain separate evidence for TLS termination, trusted proxy
   headers, origin bypass, private service networking, database access isolation,
   mTLS/service identity, restore, rollback, secrets rotation and audit logging.

The workflow refuses to run with any missing environment variable or environment secret.
Its secret-bearing request does not follow HTTP redirects, preventing forwarding to
another host. Negative public-route checks do not include the token.

**Limitations:** No live environment, protected environment configuration, approved
endpoint, or token is currently verified here. The workflow is not evidence that
deployment security controls have been accepted.
