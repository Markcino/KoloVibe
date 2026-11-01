# Django web client — local R1 shell

The user expanded R1 to include a Django server-rendered web client. This directory contains a local-only shell with public video and creator reads plus account forms against the gateway. Creator publishing, points and playback remain gated.

Run local tests from the repository root with `.venv/bin/python scripts/run_local_web.py test tests`. The root `.env` supplies the unique web secret and loopback gateway URL; no credential is bundled in the client. Staging/production settings and deployment remain pending.
