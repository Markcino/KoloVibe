# Phase 12 unblock evidence (25 November 2026)

Evidence for the rows recorded in `../results/unblock.json`. Runs used commit `c11f1a6` in a cloud session: a disposable stack (PostgreSQL 16, RabbitMQ 3.12), a single-node Docker Swarm and `playwright run-server` 1.63.0 for Firefox and WebKit. Nothing touched staging.

| File | What it shows |
| --- | --- |
| `ci_media_image_high_critical.txt` | The 11 High/Critical Grype findings on `ffmpeg 9.0.2-r0` from CI run 45619859049 (T10_92, D12-002) |
| `swarm_drill.txt` | Limits, reservations, restart policy, OOM and kill drills on the local Swarm (T10_96, T10_97) |
| `swarm_prepare.py`, `swarm_twin.py` | How the rendered `staging-aws.yml` was adapted for one local node (image, replicas 1, placement) and the twin stack for the OOM and kill drills |
| `g9_firefox.json`, `g9_webkit.json` | Full group 9 console runs (T9_90, T9_91) |
| `g9_T9_11_*_after_fix.json` | T9_11 after it was changed to wait for the response, in all three engines |

The local Swarm image was built from the `local` Dockerfile stage with `apk upgrade` skipped, because the Alpine mirror was not reachable from the session. The soak test itself is `scripts/phase11/test_g3_soak.py`; its result is in `../results/unblock.json`.
