# Phase 11 test harness

Black-box and infrastructure tests against a **disposable** local stack: a task-owned TLS PostgreSQL (one role per service), all nine services and the console started through the repository's own journey entry points, a private TLS RabbitMQ with the generator's least-privilege accounts, the production Points worker, captured mail, and (for group 9) Chromium. Nothing here contacts a network host or touches a real system. Results are recorded as JSON; nothing is hidden: a broken test is reported as an error, never skipped silently.

**Needs:** Python with the locked dependencies, PostgreSQL 16 and RabbitMQ 3.12 binaries, FFmpeg, `playwright` plus a Chromium (group 9 only), and an **unprivileged user** (PostgreSQL and RabbitMQ refuse root). Port 5671 on loopback must be free when the broker is used.

```bash
cd scripts/phase11
python runner.py OUT.json test_g1_accounts                    # groups: test_g1_accounts, test_g2_content, test_g3_engagement,
python runner.py OUT.json test_g2_content test_g9_console     #         test_g4_business, test_g9_console, test_g10_infra
P11_NO_BROKER=1 python runner.py OUT.json test_g2_content     # skip the broker when a group does not need it (g1, g2, g4, g9, g10)
python runner.py OUT.json test_g3_soak                          # T3_92: load and failure injection on the broker (SOAK_VIEWS, SOAK_REPUBLISH)
P11_NO_BROKER=1 P11_BROWSER=firefox P11_WS=ws://127.0.0.1:3001/ python runner.py OUT.json test_g9_console   # group 9 in Firefox or webkit through `npx playwright run-server`
python matrix.py RESULTS_DIR docs/engineering/phase11/Phase11_Test_Matrix.md
```

`stack_up.py` keeps a stack running for exploration (`runner.py OUT.json --attach=stack.json MODULE`). Run `test_g1_accounts` on its own stack: its brute-force tests deliberately trip throttles. Group 3 needs the broker (run without `P11_NO_BROKER`). Test ids are the `T<group>_<n>` token in each test name; the registry of what could not be run, with reasons, is in `matrix.py`.

Each test asserts the **secure** behaviour a requirement implies. A FAIL is a finding to triage, not something to tune away. The retest criteria for each defect are in `docs/engineering/phase11/Phase11_Defect_Register.md`.
