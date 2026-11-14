-- R1 staging: read-only pre-migration checks for psql (no writes, no DDL, no locks beyond reads).
-- Run as a login that can read all service schemas, over TLS, against the staging database:
--   psql -X -v ON_ERROR_STOP=1 -f r1_readonly_preflight.sql <connection>
-- Output is names and counts only: creator handles are never selected. Compare section 2 with
--   python3 scripts/ops/r1_db_preflight.py --print-expected
-- (or use that tool directly where a Python path to the database exists).
\set QUIET on
\pset format aligned
\pset border 1
BEGIN READ ONLY;
SET LOCAL statement_timeout = '5s';
SET LOCAL lock_timeout = '1s';

\echo '== 1. server (read-only must be on; version 16 is the planned one)'
SELECT current_setting('server_version') AS server_version,
       current_setting('transaction_read_only') AS transaction_read_only,
       (SELECT ssl FROM pg_stat_ssl WHERE pid = pg_backend_pid()) AS tls,
       current_user AS login;

\echo '== 2. applied migrations per service schema (compare with the expected list for the release commit)'
SELECT 'identity' AS schema, name FROM identity.django_migrations WHERE app = 'service'
UNION ALL SELECT 'creators', name FROM creators.django_migrations WHERE app = 'service'
UNION ALL SELECT 'content', name FROM content.django_migrations WHERE app = 'service'
UNION ALL SELECT 'points', name FROM points.django_migrations WHERE app = 'service'
UNION ALL SELECT 'audit', name FROM audit.django_migrations WHERE app = 'service'
ORDER BY 1, 2;

\echo '== 2b. schemas for the services whose migrations are new in this release (no rows = every migration pending)'
SELECT nspname AS schema,
       (SELECT count(*) FROM information_schema.tables t WHERE t.table_schema = nspname) AS tables
FROM pg_namespace WHERE nspname IN ('engagement', 'moderation', 'gateway') ORDER BY 1;

\echo '== 3. creators 0004: handles that differ only by case (counts only; nothing is renamed)'
SELECT count(*) AS creator_profiles,
       (SELECT count(*) FROM (SELECT lower(handle) FROM creators.service_creatorprofile
                              GROUP BY lower(handle) HAVING count(*) > 1) g) AS colliding_groups,
       (SELECT coalesce(sum(n), 0) FROM (SELECT count(*) AS n FROM creators.service_creatorprofile
                                         GROUP BY lower(handle) HAVING count(*) > 1) g) AS rows_in_collisions
FROM creators.service_creatorprofile;

\echo '== 3b. is the case-insensitive constraint already present'
SELECT count(*) AS constraint_or_index_present FROM (
  SELECT 1 FROM pg_constraint WHERE conname = 'creator_handle_case_insensitive'
  UNION ALL SELECT 1 FROM pg_indexes WHERE schemaname = 'creators' AND indexname = 'creator_handle_case_insensitive') x;

\echo '== 4. content: does stream_upload_id exist (0003 adds it, 0005 drops it)'
SELECT count(*) AS column_present FROM information_schema.columns
WHERE table_schema = 'content' AND table_name = 'service_video' AND column_name = 'stream_upload_id';

\echo '== 5. login roles (names only)'
SELECT rolname FROM pg_roles WHERE rolname LIKE 'kolovibe\_%' OR rolname LIKE 'kv\_%' ORDER BY 1;

ROLLBACK;
