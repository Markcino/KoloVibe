-- DOC-204 illustrative PostgreSQL 16+ schema blueprint. Review before applying.
-- Separate logical databases / migration roles are required per service.
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE TABLE accounts (
 user_id uuid PRIMARY KEY DEFAULT gen_random_uuid(), status text NOT NULL CHECK(status IN ('ACTIVE','SUSPENDED','DELETED')),
 created_at timestamptz NOT NULL DEFAULT now(), deleted_at timestamptz
);
CREATE TABLE creator_profiles (
 user_id uuid PRIMARY KEY REFERENCES accounts(user_id), display_name varchar(120) NOT NULL,
 verification_status text NOT NULL DEFAULT 'UNVERIFIED' CHECK(verification_status IN ('UNVERIFIED','PENDING','VERIFIED','REJECTED')),
 created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE sessions (
 session_id uuid PRIMARY KEY DEFAULT gen_random_uuid(), user_id uuid NOT NULL REFERENCES accounts(user_id),
 refresh_token_hash bytea NOT NULL UNIQUE, expires_at timestamptz NOT NULL, revoked_at timestamptz
);
-- CONTENT SERVICE DATABASE (execute separately)
CREATE TABLE videos (
 video_id uuid PRIMARY KEY DEFAULT gen_random_uuid(), creator_user_id uuid NOT NULL,
 title varchar(240) NOT NULL, provider_asset_id text UNIQUE,
 visibility text NOT NULL DEFAULT 'PRIVATE' CHECK(visibility IN ('PRIVATE','PUBLIC','UNLISTED')),
 state text NOT NULL DEFAULT 'DRAFT' CHECK(state IN ('DRAFT','UPLOADING','PROCESSING','READY','PUBLISHED','BLOCKED','DELETED')),
 created_at timestamptz NOT NULL DEFAULT now(), published_at timestamptz,
 deleted_at timestamptz
);
CREATE INDEX videos_creator_created_idx ON videos(creator_user_id, created_at DESC);
CREATE TABLE upload_intents (
 intent_id uuid PRIMARY KEY DEFAULT gen_random_uuid(), video_id uuid NOT NULL REFERENCES videos(video_id),
 token_hash bytea NOT NULL UNIQUE, provider_upload_id text UNIQUE,
 expires_at timestamptz NOT NULL, consumed_at timestamptz
);
-- ENGAGEMENT SERVICE DATABASE (execute separately)
CREATE TABLE engagement_events (
 event_id uuid PRIMARY KEY DEFAULT gen_random_uuid(), video_id uuid NOT NULL,
 viewer_user_id uuid, kind text NOT NULL CHECK(kind IN ('VIEW','LIKE')),
 evidence_digest bytea NOT NULL, idempotency_key text NOT NULL UNIQUE,
 server_received_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX engagement_video_time_idx ON engagement_events(video_id,server_received_at DESC);
CREATE TABLE qualification_decisions (
 decision_id uuid PRIMARY KEY DEFAULT gen_random_uuid(), event_id uuid NOT NULL UNIQUE REFERENCES engagement_events(event_id),
 qualified boolean NOT NULL, reason_code text NOT NULL, rule_version varchar(32) NOT NULL,
 decided_at timestamptz NOT NULL DEFAULT now()
);
-- POINTS SERVICE DATABASE (execute separately)
CREATE TABLE points_entries (
 entry_id uuid PRIMARY KEY DEFAULT gen_random_uuid(), creator_user_id uuid NOT NULL,
 source_decision_id uuid UNIQUE, delta bigint NOT NULL CHECK(delta <> 0),
 entry_type text NOT NULL CHECK(entry_type IN ('AWARD','REVERSAL','ADJUSTMENT')),
 rule_version varchar(32) NOT NULL, reversal_of uuid REFERENCES points_entries(entry_id),
 reason_code text NOT NULL, created_at timestamptz NOT NULL DEFAULT now(),
 CHECK ((entry_type = 'AWARD' AND delta > 0 AND source_decision_id IS NOT NULL AND reversal_of IS NULL)
     OR (entry_type = 'REVERSAL' AND delta < 0 AND reversal_of IS NOT NULL)
     OR (entry_type = 'ADJUSTMENT' AND reversal_of IS NULL))
);
CREATE UNIQUE INDEX points_one_reversal_per_entry ON points_entries(reversal_of) WHERE reversal_of IS NOT NULL;
CREATE INDEX points_creator_created_idx ON points_entries(creator_user_id,created_at DESC);
-- Add trigger and permissions preventing UPDATE/DELETE on points_entries; enforce service-only inserts.
CREATE TABLE inbox_events (source_event_id uuid PRIMARY KEY, consumed_at timestamptz NOT NULL DEFAULT now());
-- MODERATION SERVICE DATABASE (execute separately)
CREATE TABLE reports (
 report_id uuid PRIMARY KEY DEFAULT gen_random_uuid(), video_id uuid NOT NULL, reporter_user_id uuid NOT NULL,
 reason_code text NOT NULL, status text NOT NULL DEFAULT 'OPEN' CHECK(status IN ('OPEN','REVIEWING','RESOLVED','DISMISSED')),
 created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE moderation_actions (
 action_id uuid PRIMARY KEY DEFAULT gen_random_uuid(), report_id uuid NOT NULL REFERENCES reports(report_id),
 moderator_user_id uuid NOT NULL, action_code text NOT NULL, reason text NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now()
);
-- AUDIT SERVICE DATABASE (execute separately)
CREATE TABLE audit_events (
 audit_id uuid PRIMARY KEY DEFAULT gen_random_uuid(), actor_id uuid, service_name text NOT NULL,
 event_type text NOT NULL, target_ref text, correlation_id uuid NOT NULL,
 occurred_at timestamptz NOT NULL DEFAULT now()
);
-- Generic outbox template: instantiate separately in each producing service database.
CREATE TABLE outbox_events (
 event_id uuid PRIMARY KEY DEFAULT gen_random_uuid(), aggregate_id uuid NOT NULL,
 event_type text NOT NULL, schema_version integer NOT NULL DEFAULT 1,
 payload jsonb NOT NULL, occurred_at timestamptz NOT NULL DEFAULT now(),
 published_at timestamptz, retry_count integer NOT NULL DEFAULT 0
);
CREATE INDEX outbox_unpublished_idx ON outbox_events(occurred_at) WHERE published_at IS NULL;