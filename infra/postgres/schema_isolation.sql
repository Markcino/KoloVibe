-- PostgreSQL schema and message ledgers; execute with DBA privileges against
-- the KoloVibe database, never as a service login. Application credentials are
-- provisioned outside Git.
--
-- Ownership model (D11-002 / R-01). Per service there are TWO NOLOGIN roles:
--   kolovibe_<svc>      OWNS the schema, its tables, sequences and triggers. Only the migration login may use it.
--   kolovibe_<svc>_rt   runtime role: USAGE on the schema and SELECT/INSERT/UPDATE/DELETE on its tables, USAGE/SELECT/
--                       UPDATE on its sequences. No ownership, no CREATE, no TRUNCATE, no REFERENCES/TRIGGER.
-- The service's RUNTIME login is granted kolovibe_<svc>_rt ONLY. A separate MIGRATION login (used by the migration job,
-- never by the running service) is granted kolovibe_<svc> and connects with KOLOVIBE_DB_MIGRATION_ROLE=kolovibe_<svc>
-- so every object it creates is owned by the owner role. A runtime login that can act as the owner could disable the
-- append-only triggers of the ledger and audit stores, so it must never be a member of kolovibe_<svc>.
REVOKE ALL ON SCHEMA public FROM PUBLIC;
DO $do$
DECLARE svc text; rolename text; runtime text;
BEGIN
  FOREACH svc IN ARRAY ARRAY['gateway','identity','creators','content','engagement','points','moderation','audit','business'] LOOP
    rolename := 'kolovibe_' || svc;
    runtime := rolename || '_rt';
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = rolename) THEN
      EXECUTE format('CREATE ROLE %I NOLOGIN', rolename);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = runtime) THEN
      EXECUTE format('CREATE ROLE %I NOLOGIN', runtime);
    END IF;
    EXECUTE format('CREATE SCHEMA IF NOT EXISTS %I AUTHORIZATION %I', svc, rolename);
    EXECUTE format('REVOKE ALL ON SCHEMA %I FROM PUBLIC', svc);
    EXECUTE format('REVOKE ALL ON ALL TABLES IN SCHEMA %I FROM PUBLIC', svc);
    EXECUTE format('REVOKE ALL ON ALL SEQUENCES IN SCHEMA %I FROM PUBLIC', svc);
    EXECUTE format('CREATE TABLE IF NOT EXISTS %I.internal_request_nonce (caller text NOT NULL, nonce text NOT NULL, received_at timestamptz NOT NULL DEFAULT now(), PRIMARY KEY (caller,nonce))', svc);
    EXECUTE format('CREATE TABLE IF NOT EXISTS %I.event_outbox (id uuid PRIMARY KEY, event_type text NOT NULL, payload jsonb NOT NULL, created_at timestamptz NOT NULL DEFAULT now(), published_at timestamptz, attempts integer NOT NULL DEFAULT 0)', svc);
    EXECUTE format('CREATE TABLE IF NOT EXISTS %I.event_inbox (id uuid PRIMARY KEY, event_type text NOT NULL, received_at timestamptz NOT NULL DEFAULT now())', svc);
    EXECUTE format('ALTER TABLE %I.internal_request_nonce OWNER TO %I', svc, rolename);
    EXECUTE format('ALTER TABLE %I.event_outbox OWNER TO %I', svc, rolename);
    EXECUTE format('ALTER TABLE %I.event_inbox OWNER TO %I', svc, rolename);
    -- Runtime privileges: data access only. Re-running this file also repairs grants on tables that already exist.
    EXECUTE format('GRANT USAGE ON SCHEMA %I TO %I', svc, runtime);
    EXECUTE format('GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA %I TO %I', svc, runtime);
    EXECUTE format('GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA %I TO %I', svc, runtime);
    EXECUTE format('ALTER DEFAULT PRIVILEGES FOR ROLE %I IN SCHEMA %I GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO %I', rolename, svc, runtime);
    EXECUTE format('ALTER DEFAULT PRIVILEGES FOR ROLE %I IN SCHEMA %I GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO %I', rolename, svc, runtime);
  END LOOP;
END $do$;
-- DBA must provision distinct LOGIN roles: one RUNTIME login per service granted exactly
-- kolovibe_<service>_rt, and one MIGRATION login per service granted exactly kolovibe_<service>.
-- Revoke database CREATE and cross-service privileges from PUBLIC/other principals before
-- production use. For a database whose tables are already owned by a login, see
-- r01_ownership_remediation.sql (reviewed, not executed by any automation).
