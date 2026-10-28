# Container verification

Each Django service is built independently from the same version-controlled Dockerfile. Images contain only that service and hash-locked Python packages, run as UID/GID 10001, and are not pushed by the container-quality workflow.

CI validates the image configuration, local-only Django process startup, `GET /health/live`, rejection of `POST /health/live`, and scans the image for high/critical known vulnerabilities using Grype.

**Boundary:** The image currently uses Django's local development server and local-only settings. A successful CI image run does **not** qualify the image for production deployment. Before deploying to staging or production, implement and validate a hardened production WSGI/ASGI server, authenticated readiness checks, real PostgreSQL service isolation, runtime secrets, private routing, container digest promotion, and backup/recovery controls.

The workflow does not require a GitHub Secret. Runtime keys are generated ephemerally inside the GitHub-hosted runner, never stored in the image. If a future job connects to a deployed environment, store access credentials in a reviewer-protected GitHub Environment and limit its permissions and trigger to manual approval.
