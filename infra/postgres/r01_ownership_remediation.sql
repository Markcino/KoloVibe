-- R-01 / D11-002: move table ownership from a service's RUNTIME login to its NOLOGIN owner role, for ONE service.
-- REVIEWED, NOT EXECUTED BY ANY AUTOMATION. Run by the DBA only after a verified backup and the owner's written approval,
-- one service at a time, with the service stopped or quiesced (REASSIGN OWNED takes locks on every object it moves).
--
--   psql -X -v ON_ERROR_STOP=1 -v service=points -v runtime_login=kolovibe_points_app -f r01_ownership_remediation.sql <tls connection>
--
-- Prerequisites (DBA, outside Git): schema_isolation.sql has been re-run (it is idempotent: it creates kolovibe_<svc>_rt and
-- repairs grants), and a separate MIGRATION login exists and is a member of kolovibe_<svc> and of nothing else.
-- Effect, in one transaction: (1) every object the runtime login owns passes to kolovibe_<svc>; (2) the login stops being a
-- member of kolovibe_<svc> and becomes a member of kolovibe_<svc>_rt only; (3) the script verifies the result and aborts
-- (rolling everything back) if the login can still act as an owner or still owns anything.
-- Rollback: restore from the pre-change restore point, or reverse with REASSIGN OWNED BY kolovibe_<svc> TO <login> (not advised).
\set QUIET on
BEGIN;
SET LOCAL lock_timeout = '10s';
SELECT format('kolovibe_%s', :'service') AS owner_role, format('kolovibe_%s_rt', :'service') AS runtime_role \gset
SELECT set_config('r01.service', :'service', true), set_config('r01.login', :'runtime_login', true);

DO $r01$
DECLARE svc text := current_setting('r01.service'); login text := current_setting('r01.login');
        owner text := 'kolovibe_' || svc; rt text := 'kolovibe_' || svc || '_rt';
BEGIN
  IF svc NOT IN ('gateway','identity','creators','content','engagement','points','moderation','audit','business') THEN
    RAISE EXCEPTION 'unknown service %', svc;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = login AND rolcanlogin AND NOT rolsuper) THEN
    RAISE EXCEPTION 'runtime login % must exist, be a plain LOGIN role', login;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = rt) THEN
    RAISE EXCEPTION 'run schema_isolation.sql first: role % is missing', rt;
  END IF;
  EXECUTE format('REASSIGN OWNED BY %I TO %I', login, owner);
  EXECUTE format('REVOKE %I FROM %I', owner, login);
  EXECUTE format('GRANT %I TO %I', rt, login);
  -- verify: nothing owned, no way to act as the owner, no CREATE, DML still present
  IF EXISTS (SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
             WHERE n.nspname = svc AND pg_has_role(login, c.relowner, 'USAGE') AND c.relkind IN ('r','p','S')) THEN
    RAISE EXCEPTION 'login % can still act as the owner of objects in %', login, svc;
  END IF;
  IF has_schema_privilege(login, svc, 'CREATE') THEN
    RAISE EXCEPTION 'login % can still create objects in %', login, svc;
  END IF;
  IF NOT has_table_privilege(login, format('%I.event_outbox', svc), 'INSERT') THEN
    RAISE EXCEPTION 'login % lost its data access in %', login, svc;
  END IF;
END
$r01$;
COMMIT;
\echo 'ownership remediated for service' :service
-- Next: re-run r1_role_ownership_report.sql and expect zero login-owned objects, then start the service and check its health.
