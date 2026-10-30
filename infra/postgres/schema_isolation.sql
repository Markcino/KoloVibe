-- PostgreSQL schema and message ledgers; execute with DBA privileges against
-- the KoloVibe database, never as a service login. Application credentials are
-- provisioned outside Git and each login receives only ONE matching role.
REVOKE ALL ON SCHEMA public FROM PUBLIC;
DO $do$
DECLARE svc text; rolename text;
BEGIN
  FOREACH svc IN ARRAY ARRAY['gateway','identity','creators','content','engagement','points','moderation','audit'] LOOP
    rolename := 'kolovibe_' || svc;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = rolename) THEN
      EXECUTE format('CREATE ROLE %I NOLOGIN', rolename);
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
  END LOOP;
END $do$;
-- DBA must provision distinct LOGIN roles and grant exactly one matching
-- kolovibe_<service> role per login. Revoke database CREATE and cross-service
-- privileges from PUBLIC/other principals before production use.
