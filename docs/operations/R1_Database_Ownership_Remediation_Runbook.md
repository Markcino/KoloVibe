# R-01 database ownership remediation: operator runbook (D11-002)

**Status: procedure written 25 November 2026. NOT executed. Nothing in AWS staging or anywhere else was changed.** The repository now provisions a new database correctly and has a tested script for converting an existing one. Converting the live staging database needs the owner's written approval, a verified backup and a maintenance window; the outcome there is **unverified** until the read-back in step 6 is done.

## The model

| Role | Kind | Holds | Used by |
| --- | --- | --- | --- |
| `kolovibe_<svc>` | NOLOGIN | **Owns** the schema, tables, sequences and triggers | only the migration login, through `SET ROLE` |
| `kolovibe_<svc>_rt` | NOLOGIN | `USAGE` on the schema; `SELECT/INSERT/UPDATE/DELETE` on tables; `USAGE/SELECT/UPDATE` on sequences; the same by default on future tables created by the owner | the runtime login |
| runtime login (`kolovibe_<svc>_app` in staging) | LOGIN | member of `kolovibe_<svc>_rt` **only** | the running service |
| migration login (new, for example `kolovibe_<svc>_mig`) | LOGIN | member of `kolovibe_<svc>` **only**; the job sets `KOLOVIBE_DB_MIGRATION_ROLE=kolovibe_<svc>` | the migration job, never a running service |

Why: the runtime login used to inherit the role that owns its tables, so a stolen service credential could `ALTER TABLE ... DISABLE TRIGGER` on the Points ledger, the Audit store or the Identity security events and then rewrite history (Phase 11 finding D11-002, demonstrated on 117 of 117 tables). A table's owner is the only role that can disable its triggers, so the fix is that **no running service is, or can become, an owner**.

## For a new database

1. DBA runs `infra/postgres/schema_isolation.sql` (idempotent) as an administrator.
2. DBA creates the runtime and migration logins (passwords outside Git) and grants each exactly the one role in the table above.
3. Migrations: the migration job connects as the migration login with `KOLOVIBE_DB_MIGRATION_ROLE=kolovibe_<svc>` (`staging_runtime.database_options` accepts only that service's own owner role).

## For the existing staging database (owner approval required)

1. Verified backup and restore point recorded (ADR-016 is still open: no backup has been restored on the real system).
2. Read-only before-state: `infra/postgres/r1_role_ownership_report.sql`; keep the output.
3. Re-run `schema_isolation.sql` (creates the `_rt` roles and repairs grants; no data change).
4. Create one migration login per service, member of `kolovibe_<svc>`.
5. Per service, with that service scaled to zero: `infra/postgres/r01_ownership_remediation.sql` with `-v service=<svc> -v runtime_login=<login>`. It reassigns ownership, swaps the login's membership and **aborts and rolls back** if anything is still owned or controllable. Scale the service back up and check `/health/ready`.
6. Read-back: run `r1_role_ownership_report.sql` again. Expect no object owned by a LOGIN role, no runtime login in section 6 with `controls_table = t`, and then repeat Phase 11 tests T10_03, T10_04 and T10_94 against staging.
7. Change the migration job to use the migration login and role. Until then no migration can run (the runtime login can no longer alter the schema); this is intended.

**Rollback:** restore from the restore point. Do not hand ownership back to a login.

## Evidence in the repository

`scripts/test_postgres_foundations.py` (every service's runtime login cannot own, control, alter, truncate or create), `scripts/test_r01_remediation.py` (the conversion script on a recreated legacy schema, including refusal of bad input and re-run), `scripts/verify_r1_db_preflight.py` (the report is clean after the split and still exposes a legacy database), `scripts/test_staging_runtime.py` (the migration-role option), and Phase 11 T10_03 and T10_04 on the full local stack.
