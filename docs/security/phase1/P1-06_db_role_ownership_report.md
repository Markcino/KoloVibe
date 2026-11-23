# P1-06 — Read-only database role, ownership and privilege report

**Type:** operator tooling and tests (no database change). **Baseline reference:** Phase 0 risk R-01 (High), backlog B-07. **Staging:** not touched; the owner runs the script.

## Problem
The 23 November 2026 catalog audit found 26 tables and 8 sequences on staging owned by runtime `_app` roles. Aggregate counts do not show whether those roles can disable the append-only triggers on the points ledger and audit tables (an owner can `DROP`/`DISABLE` a trigger and `TRUNCATE`), which services' logins can reach which schemas, or which role memberships are inherited. The reconciliation requires that evidence before any `ALTER OWNER`.

## What was added
`infra/postgres/r1_role_ownership_report.sql`: one `BEGIN READ ONLY … ROLLBACK` script, catalog reads only, eight sections: session (read-only, TLS), roles, memberships (with `inherit`/`set` options where the server has them), object ownership per service schema with `owner_can_login`, schema reach per login role including inherited rights, **guarded (trigger-protected) tables with whether each login role controls or can truncate/update/delete them**, default privileges, database and `public` schema exposure.

Output is role, schema, table and trigger names, counts and booleans. `pg_authid` is never read, so no password hash can appear.

## Tests (`scripts/verify_r1_db_preflight.py`, `RoleOwnershipReportTests`, disposable TLS PostgreSQL, already a CI step)
- all eight sections print and the session is read-only;
- the fixture reproduces the finding: `ci_identity` (a LOGIN role) owns tables, reported with `owner_can_login = t`;
- the points ledger guard appears with `ci_points` as a role that controls the table;
- membership `ci_points → kolovibe_points` and schema reach are shown; no service login reaches another service's schema; no `PASSWORD`, `rolpassword` or `SCRAM` text in output;
- static check: no `INSERT/UPDATE/DELETE/DROP/ALTER/CREATE/TRUNCATE/GRANT/REVOKE/COPY` statement, no `pg_authid`, no `SET ROLE`, begins read-only and ends with `ROLLBACK`.
- `run_psql_file()` was extracted from `SqlScriptTests` so both operator scripts share one TLS-verified psql runner.

Local run: whole `verify_r1_db_preflight.py` module, 16 tests OK, against PostgreSQL 14.15.

## How the owner uses it
```
psql -X -v ON_ERROR_STOP=1 -f infra/postgres/r1_role_ownership_report.sql "<TLS connection string>" > role-report.txt
```
Review sections 4 and 6 first. Do **not** run `ALTER OWNER`, `REVOKE` or any DDL from this output without a separate, owner-approved plan with a recovery path and maintenance window (Phase 0 backlog B-09).

## Limits
- Tested on PostgreSQL 14; staging runs 17.11. The membership section uses `to_jsonb(row)->>'inherit_option'`, which yields the column on 16+ and NULL on older servers; CI runs the server version provided by the runner.
- It reports; it does not remediate. Remediation (a non-login migration-owner role, objects re-owned, runtime logins granted DML only) is intentionally not part of this change.
