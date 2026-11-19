# AWS web staging rollout and acceptance

**State:** Candidate only. The live `kolovibe.cabetechs.shop` Nginx server still returns the intentional 503 placeholder. Do not mark the web client ready until the CI, database, proxy, and browser checks below pass.

## Observed VM1 baseline (19 November 2026)

- Nginx is active on VM1 (`ip-172-31-30-236`). `http://127.0.0.1/health/live` with mobile API Host returns 200 JSON.
- VM1 reported 1,310 MiB available memory and 15 GiB available disk at the check. These are observations, not guaranteed reservations.
- `kolovibe_data` is an attachable internal overlay. Confirm `kolovibe_services` is also attachable before creating the standalone web container.
- The web virtual host is the first default server in `/etc/nginx/sites-enabled/kolovibe-staging.conf`; its unconditional `return 503` is the immediate cause of the public web outage. Preserve the API virtual hosts and their method allow-list.

## Release gates

1. Merge the reviewed web change only after Python journeys, the dedicated web image build, high-severity scan, SBOM, and all existing CI gates pass. Publication on main produces a separate `published-web-image-<revision>` artifact with the web digest and revision; do not substitute the shared services image. The web image binds port 8001 inside its container and refuses production settings.
2. The DBA provisions a **separate** `kolovibe_web_app` login with its own password and a `web` schema in `kolovibe_staging`. It may create only its own tables (`django_session`, `web_credential`, `django_migrations`). Validate that the PostgreSQL HBA allows precisely this login from the web overlay and denies it access to every other service schema. Run web migrations with this role before starting web traffic. Database TLS must use `verify-full` for `kolovibe-postgres`.
3. On VM1, install independent, owner-only 0400 files for the web Django key, Fernet key, and web database password, all owned by UID 10001. Mount the PostgreSQL and internal gateway CA files read-only. The Fernet key is `base64.urlsafe_b64encode(os.urandom(32))`; do not reuse a service signing key or put a secret in shell arguments, Docker labels, Git, CI artifacts, or Nginx.
4. Create the web container with the **published digest**, user `10001:10001`, read-only root, a bounded `/tmp` tmpfs, dropped capabilities, `no-new-privileges`, CPU and memory limits, and networks `kolovibe_services` and `kolovibe_data`. Publish port **only** as `127.0.0.1:8001:8001` on VM1. Set `KOLOVIBE_ENV=staging`, `KOLOVIBE_GATEWAY_URL=https://gateway:8000`, and the five fixed secret-path variables required by `web/settings.py`. Verify the internal gateway certificate against its CA and the database certificate with `verify-full`. Confirm the container's `/health/live` through VM1 loopback before touching Nginx.
5. Copy only the image's `static/` assets to `/srv/kolovibe-web/static` as root-owned readable files. Take a byte-for-byte backup of the live Nginx file. Replace **only** the exact placeholder server block with `infra/nginx/kolovibe-web-staging.conf`; test `nginx -t`, reload, then test exact Host and wrong Host locally. Roll back the backup immediately if the expected web responses do not appear.
6. Verify public HTTPS responses from a separate client: `/health/live` 200 JSON, `/` 200 HTML, `/static/css/site.css` 200 CSS, and a wrong Host rejected locally. Test registration, email verification, sign-in, account, 30-minute idle and 8-hour absolute expiry, one refresh, selected-session revocation, password reset, CSRF denial, sign-out, and an identity outage. Check that the browser has only a secure, HttpOnly, host-only `__Host-kolovibe_session` cookie and no bearer or refresh token cookies. Observe web logs without exposing tokens.

## Limits and rollback

The current web UI intentionally gates creator publishing and video playback. Successful deployment permits discovery and ordinary-account web acceptance, **not full R1 web acceptance**. Full creator and media web journeys require separate implementation and device/browser evidence.

If the web process fails, restore the exact Nginx backup, run `nginx -t`, reload Nginx, and stop the web container. Preserve the database and secret files for investigation. Web migrations and encrypted session rows are forward-only; restoring the Nginx 503 does not reverse them. Keep the old published image and the independent keys until a reviewed rollback decision.
