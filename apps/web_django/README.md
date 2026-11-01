# Django web client — local R1 shell

The user expanded R1 to include a Django server-rendered web client. This directory contains a local-only shell with public video and creator reads plus account forms against the gateway. Creator publishing, points and playback remain gated.

Run local tests from the repository root with `.venv/bin/python scripts/run_local_web.py test tests`. The root `.env` supplies the unique web secret and loopback gateway URL; no credential is bundled in the client. Staging/production settings and deployment remain pending.

Discovery follows gateway cursor pages and rejects malformed records before rendering. Account refresh preserves rotated cookies during dependency outages; logout clears browser credentials while reporting any unconfirmed server revocation. For reproducible tests with isolated PostgreSQL, a real gateway and private test-mail capture, follow the [local acceptance procedure](../../docs/engineering/API_Test_Deployment_Roadmap.md#reproducible-isolated-local-acceptance).
