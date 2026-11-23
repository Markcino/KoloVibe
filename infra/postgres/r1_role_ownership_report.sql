-- R1: read-only report of role ownership, membership and effective privileges on the service schemas.
-- Answers the 23 Nov 2026 finding (runtime `_app` roles own service tables and sequences) WITHOUT changing anything:
-- it states who owns what, who can reach what through role inheritance, and whether a runtime login can disable or
-- bypass the append-only guards. Run it, review the output with the owner and DBA, and plan any correction separately.
--   psql -X -v ON_ERROR_STOP=1 -f r1_role_ownership_report.sql <connection>
-- Run over TLS as any login that can read the system catalogs (every login can). Output is role, schema, table and
-- trigger names, counts and booleans only: no row data, no password hash (pg_authid is never read), no secret.
\set QUIET on
\pset format aligned
\pset border 1
BEGIN READ ONLY;
SET LOCAL statement_timeout = '10s';
SET LOCAL lock_timeout = '1s';

\echo '== 1. session (read-only must be on)'
SELECT current_setting('server_version') AS server_version,
       current_setting('transaction_read_only') AS transaction_read_only,
       (SELECT ssl FROM pg_stat_ssl WHERE pid = pg_backend_pid()) AS tls,
       current_user AS login;

\echo '== 2. roles (login, superuser, create-role/db, bypass row security, inherits privileges)'
SELECT rolname, rolcanlogin AS login, rolsuper AS superuser, rolcreaterole AS createrole, rolcreatedb AS createdb,
       rolbypassrls AS bypassrls, rolinherit AS inherits
FROM pg_roles WHERE rolname !~ '^pg_' ORDER BY rolcanlogin DESC, rolname;

\echo '== 3. role membership (member gets the role''s privileges when inherit is true; set = may SET ROLE to it)'
SELECT m.rolname AS member, r.rolname AS member_of, a.admin_option AS admin,
       to_jsonb(a) ->> 'inherit_option' AS inherit, to_jsonb(a) ->> 'set_option' AS "set"
FROM pg_auth_members a JOIN pg_roles m ON m.oid = a.member JOIN pg_roles r ON r.oid = a.roleid
WHERE m.rolname !~ '^pg_' AND r.rolname !~ '^pg_' ORDER BY 1, 2;

\echo '== 4. who owns the service objects (schema, owner, kind, count); owners that are LOGIN roles are the finding'
SELECT n.nspname AS schema, pg_get_userbyid(c.relowner) AS owner,
       CASE c.relkind WHEN 'r' THEN 'table' WHEN 'p' THEN 'partitioned table' WHEN 'S' THEN 'sequence'
                      WHEN 'v' THEN 'view' WHEN 'm' THEN 'materialized view' ELSE c.relkind::text END AS kind,
       count(*) AS objects,
       (SELECT rolcanlogin FROM pg_roles WHERE oid = c.relowner) AS owner_can_login
FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname IN ('gateway','identity','creators','content','engagement','points','moderation','audit')
  AND c.relkind IN ('r','p','S','v','m')
GROUP BY 1, 2, 3, c.relowner ORDER BY 1, 2, 3;

\echo '== 5. schema owners and where a LOGIN role can use or create (effective, including inherited membership)'
SELECT n.nspname AS schema, pg_get_userbyid(n.nspowner) AS schema_owner, r.rolname AS login,
       has_schema_privilege(r.oid, n.oid, 'USAGE') AS usage, has_schema_privilege(r.oid, n.oid, 'CREATE') AS "create",
       pg_has_role(r.oid, n.nspowner, 'USAGE') AS acts_as_schema_owner
FROM pg_namespace n CROSS JOIN pg_roles r
WHERE n.nspname IN ('gateway','identity','creators','content','engagement','points','moderation','audit')
  AND r.rolcanlogin AND NOT r.rolsuper
  AND (has_schema_privilege(r.oid, n.oid, 'USAGE') OR has_schema_privilege(r.oid, n.oid, 'CREATE'))
ORDER BY 1, 3;

\echo '== 6. guarded (trigger-protected) tables: can a LOGIN role control or bypass the guard?'
\echo '   controls_table = owns it or inherits its owner: may DROP/DISABLE the trigger or truncate; truncate/update/delete = effective grant'
SELECT n.nspname AS schema, c.relname AS "table", t.tgname AS "trigger", pg_get_userbyid(c.relowner) AS owner,
       r.rolname AS login, pg_has_role(r.oid, c.relowner, 'USAGE') AS controls_table,
       has_table_privilege(r.oid, c.oid, 'TRUNCATE') AS "truncate",
       has_table_privilege(r.oid, c.oid, 'UPDATE') AS "update", has_table_privilege(r.oid, c.oid, 'DELETE') AS "delete"
FROM pg_trigger t JOIN pg_class c ON c.oid = t.tgrelid JOIN pg_namespace n ON n.oid = c.relnamespace
CROSS JOIN pg_roles r
WHERE NOT t.tgisinternal AND c.relkind IN ('r','p')
  AND n.nspname IN ('gateway','identity','creators','content','engagement','points','moderation','audit')
  AND r.rolcanlogin AND NOT r.rolsuper
  AND (pg_has_role(r.oid, c.relowner, 'USAGE') OR has_table_privilege(r.oid, c.oid, 'TRUNCATE')
       OR has_table_privilege(r.oid, c.oid, 'UPDATE') OR has_table_privilege(r.oid, c.oid, 'DELETE'))
ORDER BY 1, 2, 3, 5;

\echo '== 7. default privileges that will apply to future objects'
SELECT pg_get_userbyid(d.defaclrole) AS for_objects_created_by, coalesce(n.nspname, '(any schema)') AS schema,
       d.defaclobjtype AS object_type, d.defaclacl::text AS grants
FROM pg_default_acl d LEFT JOIN pg_namespace n ON n.oid = d.defaclnamespace ORDER BY 1, 2, 3;

\echo '== 8. database and public-schema exposure'
SELECT (SELECT datacl::text FROM pg_database WHERE datname = current_database()) AS database_acl,
       (SELECT nspacl::text FROM pg_namespace WHERE nspname = 'public') AS public_schema_acl,
       (SELECT count(*) FROM pg_roles r WHERE r.rolcanlogin AND NOT r.rolsuper
          AND has_database_privilege(r.oid, current_database(), 'CREATE')) AS logins_that_can_create_schemas;

ROLLBACK;
