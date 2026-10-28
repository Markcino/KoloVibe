> Source: DOC-204_Full_Database_Architecture_DRAFT_v1_0.docx (text export; formatting and embedded images are not included). Original status is retained.

<PARSED TEXT FOR PAGE: 1 / 5>
DOC-204 | FULL DATABASE
ARCHITECTURE
Stage 2 · Version 1.0 · Full review draft · 28 October 2026

Approved baseline: DOC-201, DOC-202, DOC-203. This document requires sponsor and technical
review before final approval.



Document control and decisions
DOC-204 v1.0 — FULL REVIEW DRAFT, 28 October 2026. Baselines: DOC-201 microservices, DOC-202
data flows, DOC-203 STRIDE. Sponsor approval pending. PostgreSQL is proposed as a private logical
cluster with one database and role per service initially; physical isolation may be introduced later.
No production infrastructure is assumed deployed.



Scope and release boundaries
Release 1: identities and profiles, video metadata and moderation, qualified views/likes, append-only
non-cash points ledger, event delivery and audit. R2 business reviews, R3 ticketing, R4 real-money
payouts are deliberately excluded from active R1 schema. Monetary balances must never be stored
in the points ledger.



Architecture and ownership
Identity owns user identity, credentials and sessions. Content owns video metadata, upload intent
and publish state. Engagement owns raw evidence references, qualification decisions and
deduplication. Points owns immutable points journal and derived balances. Moderation owns
reports and case actions. Audit owns immutable security events. Each service uses separate DB login
and migration principal; no cross-service SQL joins, foreign keys or writes. Cross-service identifiers
are UUID references validated through APIs/events.



Physical and logical topology
Nginx is on a dedicated VM outside Docker Swarm. Swarm microservices reach PostgreSQL over
private routed networks and authenticated TLS; PostgreSQL must not publish port 5432 to the
Internet. Prefer managed PostgreSQL with PITR if budget allows; otherwise hardened dedicated
database VM with encrypted WAL archiving and backups. Redis is not the source of truth. Database
ownership is logical, not one server per service.



Identifiers, clocks and naming
Use UUIDv7 or UUIDv4 consistently; examples use gen_random_uuid() UUIDv4. Timestamps are
TIMESTAMPTZ UTC. Monetary fields are prohibited in R1 points schema. Use snake_case identifiers,
explicit CHECK constraints, unique keys and indexes. Store provider identifiers as opaque strings.
Avoid embedding sensitive data in identifiers.
<PARSED TEXT FOR PAGE: 2 / 5>
Identity domain
accounts: user_id, status, created_at, deleted_at. creator_profiles: user_id, display_name,
verification_status, timestamps. sessions: hashed refresh token family reference, revocation and
expiry; do not store plaintext tokens. PII separated into protected identity tables where practical.
Django auth model design must be finalized before first migration.



Content domain
videos: creator_user_id UUID external reference, title, visibility, moderation_state, provider_asset_id,
duration_ms, created/published timestamps. upload_intents: one-time intent token hash, creator
UUID, provider upload identifier, expiry and consumed timestamp. Provider webhooks verified
before state transition; deleting video should use soft-delete/tombstone with provider cleanup
workflow.



Engagement domain
engagement_events store event_id, video_id, viewer_user_id (nullable for allowed anonymous
evidence), kind, evidence digest, server_received_at and idempotency_key. qualification_decisions
store rule_version, qualified boolean, reason, decision timestamp and event ID. Unique constraints
must enforce one decision per event and eligibility window where specified. Client-submitted
timestamps and counters are untrusted.



Points domain
points_entries is an append-only journal of signed integer deltas (not money), creator UUID, source
qualification UUID, rule version, entry type AWARD/REVERSAL/ADJUSTMENT, reversal_of entry ID,
and created_at. Only Points service writes; uniqueness prevents duplicate awards; reversals are
compensating entries, never updates/deletes. Balance is SUM(delta) by creator or a transactionally
maintained projection reconciled against journal. No direct relation to advertising callbacks.



Moderation and audit domains
moderation_reports capture reporter UUID, video UUID, reason, state, and case ownership;
moderation_actions capture actor, reason, old/new state and case ID. Audit records append-only
actor/service identity, action, target reference, correlation ID, timestamp, tamper-evident export.
Audit and moderation storage access restricted; retention and privacy periods require approval.



Cross-service consistency
Use transactional outbox in each owning database, with event_id UUID, aggregate reference, type,
schema_version, payload, occurred_at, published_at and retry count. A publisher sends at least once;
consumers maintain inbox/processed_event keys and idempotent handlers. No distributed database
transaction or synchronous cross-service FK. Example: Engagement commits qualification + outbox
event; Points consumes, validates service identity/rule, posts journal entry once;
acknowledgement/retry cannot duplicate points.
<PARSED TEXT FOR PAGE: 3 / 5>
Transaction and concurrency design
Use atomic DB transactions around qualification decision/outbox and points journal posting/inbox.
Enforce uniqueness at database level, not only Django validation. Use SELECT FOR UPDATE where
aggregate projections require serialization; avoid long locks. Use optimistic state transitions for
video publishing/moderation. On failure, retry with exponential backoff, dead-letter queue and
reconciliation; never silently drop events.



Data classification and privacy
Classify credential/session material and raw anti-fraud signals as restricted; PII as confidential;
published content as public; moderation reports as restricted. Encrypt connections, backups and
disks; enforce least-privilege roles; redact logs. Data retention periods, lawful basis, data residency,
user deletion exceptions and fraud evidence holds require legal/privacy review before pilot.



Indexes, capacity and partitioning
Indexes target creator timeline, publish state, provider_asset_id, event idempotency,
viewer/video/rule window, points creator chronological reads, and outbox unpublished events.
Avoid premature partitioning; consider monthly partitioning of high-volume engagement evidence
after measured growth. Benchmark write amplification and index selectivity before production.
Purge evidence only under approved retention schedule.



Migration and release discipline
Each service owns Django migrations and dedicated migration credentials, separate from runtime.
Use expand/migrate/contract compatible schema changes. Never allow two services to run
migrations against the same schema. Deploy backwards-compatible changes first; monitor
replication lag and locks; back up before destructive migration. Rollback application separately from
irreversible DB migrations.



Backup, restore and disaster recovery
Enable daily encrypted base backups plus continuous WAL archiving/PITR where supported; offsite
copies with least privilege and periodic restore tests. Provisional RPO 15 minutes and RTO 4 hours
are TARGETS FOR REVIEW, not commitments. Validate backup integrity, restore permissions,
journal reconciliation and webhook replay. Single database instance is an SPOF until HA is funded
and implemented.



Access controls and infrastructure
PostgreSQL pg_hba.conf restricts private Swarm source networks; require TLS certificate validation;
avoid shared superuser. Runtime roles get DML only on owned schema; migration roles get owned-
schema DDL. Nginx VM has no database credentials. Workers use service-specific identity and least-
privilege credentials. Swarm secrets or external secret manager; rotation procedure and no
passwords in images, Compose files or logs.
<PARSED TEXT FOR PAGE: 4 / 5>
Monitoring and verification
Track connection pool saturation, slow queries, deadlocks, WAL retention, backup success,
replication lag, outbox backlog, duplicate suppression, points journal reconciliation, unexpected
direct SQL writes and migration errors. Tests: cross-service access denied, duplicate award
prevented under parallel requests, rollback atomicity, outbox replay, reversals, point projection
rebuild, PITR restore and privacy deletion workflow.



Security mapping to DOC-203
TM-027 direct ledger write → points DB isolation and private service auth. TM-028 ledger tampering
→ append-only policy, unique source and reversal. TM-034 PostgreSQL exposure → private listener,
TLS, pg_hba. TM-035 cross-service writes → separate DB roles and no cross-service FK. TM-036
backup leakage → encrypted offsite backup. TM-037 queue loss → durable outbox/inbox. Threat IDs
should be reconciled with the authoritative DOC-203 CSV at review.



Open architecture decisions
DB-01 managed vs self-hosted PostgreSQL; DB-02 single cluster vs multiple clusters; DB-03 exact
RPO/RTO; DB-04 UUID strategy; DB-05 qualification window and anti-fraud retention; DB-06 creator
profile verification fields; DB-07 service auth and workload identity; DB-08 audit immutable storage
and retention; DB-09 anonymous engagement policy; DB-10 encryption/key custody; DB-11 backup
region; DB-12 expected load and capacity budget.



Acceptance criteria and sign-off
Review ERD and SQL DDL; demonstrate database role separation, absence of cross-service FK,
append-only points, idempotent posting, validated provider status, reversible outbox processing,
migration safety, private DB access, tested restore and signed privacy retention. Approval of this
design does not imply these implementation tests have passed. Project sponsor: ______. Security
reviewer: ______. Database reviewer: ______. Date: ______.



Entity catalog and constraints

Identity service
   accounts (user_id PK, status, created_at)
   creator_profiles (user_id PK, verification_status, display_name)
   sessions (session_id PK, user_id, token_hash, expires_at)

Content service
   videos (video_id PK, creator_user_id external, provider_asset_id UNIQUE, state)
   upload_intents (intent_id PK, video_id FK, token_hash, expires_at)
   outbox_events (event_id PK, aggregate_id, event_type, published_at)

Engagement service
   engagement_events (event_id PK, video_id external, viewer_user_id external, idempotency_key
    UNIQUE)
   qualification_decisions (decision_id PK, event_id FK UNIQUE, qualified, rule_version)
<PARSED TEXT FOR PAGE: 5 / 5>
    outbox_events (event_id PK, aggregate_id, event_type, published_at)

Points service
    points_entries (entry_id PK, creator_user_id external, source_decision_id UNIQUE nullable,
     delta, entry_type)
    inbox_events (source_event_id PK, consumed_at)
    outbox_events (event_id PK, aggregate_id, event_type, published_at)

Moderation service
    reports (report_id PK, video_id external, reporter_user_id external, status)
    actions (action_id PK, report_id FK, moderator_user_id external, reason)

Audit service
    audit_events (audit_id PK, actor_id external, event_type, correlation_id, created_at)



Canonical transaction sequence
1.   Engagement service receives event and validates authentication, rate limits and evidence.
2.   Engagement service commits decision plus outbox event in a single database transaction.
3.   Publisher delivers signed/authenticated event at least once; delivery may duplicate.
4.   Points service verifies producer identity and rule version, records inbox key and journal entry
     in one transaction.
5.   Points service responds idempotently; retries cannot create duplicate awards.
6.   Reconciliation compares qualification decisions to journal entries and flags missing or
     unexpected postings.



Illustrative schema and ERD
The companion SQL and Mermaid files contain the editable entity definitions, primary keys, checks,
indexes, and relationship model. Cross-service UUID references intentionally have no database
foreign keys.



Approval and exceptions
Project sponsor: __________________ Date: __________

Database reviewer: _________________ Date: __________

Security reviewer: _________________ Date: __________

Approved deviations and unresolved decisions: __________________________________