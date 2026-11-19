# AWS web staging rollout and acceptance

**State:** Candidate only. The live `kolovibe.cabetechs.shop` Nginx server still returns the intentional 503 placeholder. Do not mark the web client ready until the CI, database, proxy, and browser checks below pass.

## Observed VM1 baseline (19 November 2026)

- Nginx is active on VM1 (`ip-172-31-30-236`). `http://127.0.0.1/health/live` with mobile API Host returns 200 JSON.
- VM1 reported 1,310 MiB available memory and 15 GiB available disk at the check. These are observations, not guaranteed reservations.
- Both `kolovibe_services` and `kolovibe_data` are attachable internal overlays. The web workload belongs on VM2, the Swarm worker. VM1 runs only host Nginx and the existing HAProxy edge bridge; the bridge mounts `/srv/kolovibe-edge/run` and joins `kolovibe_services`.
- The existing Gateway has no published port. VM1 Nginx reaches it through the HAProxy bridge's `gateway.sock`. Add a distinct web socket and backend to the bridge after checking the live bridge configuration and TLS verification. Do not publish the Django web container on VM1 or open a public web port on VM2.
- The web virtual host is the first default server in `/etc/nginx/sites-enabled/kolovibe-staging.conf`; its unconditional `return 503` is the immediate cause of the public web outage. Preserve the API virtual hosts and their method allow-list.

## Release gates

1. Merge the reviewed web change only after Python journeys, the dedicated web image build, high-severity scan, SBOM, and all existing CI gates pass. Publication on main produces a separate `published-web-image-<revision>` artifact with the web digest and revision; do not substitute the shared services image. The web image binds port 8001 inside its container and refuses production settings.
2. The DBA provisions a **separate** `kolovibe_web_app` login with its own password and a `web` schema in `kolovibe_staging`. It may create only its own tables (`django_session`, `web_credential`, `django_migrations`). Validate that the PostgreSQL HBA allows precisely this login from the web overlay and denies it access to every other service schema. Run web migrations with this role before starting web traffic. Database TLS must use `verify-full` for `kolovibe-postgres`.
3. On VM1, install independent, owner-only 0400 files for the web Django key, Fernet key, and web database password, all owned by UID 10001. Mount the PostgreSQL and internal gateway CA files read-only. The Fernet key is `base64.urlsafe_b64encode(os.urandom(32))`; do not reuse a service signing key or put a secret in shell arguments, Docker labels, Git, CI artifacts, or Nginx.
4. Create a **Swarm web service on VM2** with the published digest, placement constraint for the worker, user `10001:10001`, read-only root, a bounded `/tmp` tmpfs, dropped capabilities, `no-new-privileges`, CPU and memory limits, and the `kolovibe_services` and `kolovibe_data` overlays. Mount web-specific Swarm secrets with owner-only permissions. Do not publish a Swarm port. Set `KOLOVIBE_ENV=staging`, `KOLOVIBE_GATEWAY_URL=https://gateway:8000`, and the five fixed secret-path variables required by `web/settings.py`. Verify the internal gateway certificate against its CA and the database certificate with `verify-full`.
5. Verify the live HAProxy bridge TLS policy, then add a separate web socket/backend to the VM1 bridge, keeping the Gateway route intact. Confirm web `/health/live` through the new socket before touching Nginx. Serve static assets from the VM2 web service through the bridge, not from a VM1 copy. Take a byte-for-byte backup of the live Nginx file. Replace **only** the exact placeholder server block with the reviewed web vhost; test `nginx -t`, reload, then test exact Host and wrong Host locally. Roll back the backup immediately if the expected web responses do not appear.
6. Verify public HTTPS responses from a separate client: `/health/live` 200 JSON, `/` 200 HTML, `/static/css/site.css` 200 CSS, and a wrong Host rejected locally. Test registration, email verification, sign-in, account, 30-minute idle and 8-hour absolute expiry, one refresh, selected-session revocation, password reset, CSRF denial, sign-out, and an identity outage. Check that the browser has only a secure, HttpOnly, host-only `__Host-kolovibe_session` cookie and no bearer or refresh token cookies. Observe web logs without exposing tokens.

## Limits and rollback

The current web UI intentionally gates creator publishing and video playback. Successful deployment permits discovery and ordinary-account web acceptance, **not full R1 web acceptance**. Full creator and media web journeys require separate implementation and device/browser evidence.

If the web process fails, restore the exact Nginx backup, run `nginx -t`, reload Nginx, revert the web bridge change, and scale the VM2 web service to zero. Preserve the database and secret files for investigation. Web migrations and encrypted session rows are forward-only; restoring the Nginx 503 does not reverse them. Keep the old published image and the independent keys until a reviewed rollback decision.
