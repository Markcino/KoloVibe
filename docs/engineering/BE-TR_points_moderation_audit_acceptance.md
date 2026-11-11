# BE-TR points, moderation and audit acceptance — 11 November 2026

Baseline: main `f1623740741ca3a7cfeff394a335a5997433c757` (merged BE-EN). Local verification only; no deployment or release acceptance is implied.

## Gaps found before changes

- Points already had an append-only ledger, idempotent qualified-view inbox consumption and a UTC daily cap. Its balance exposed only the net ledger total. Cap-blocked events were discarded after inbox acceptance, no durable received-but-unposted state existed, and entries lacked status/video fields, status filtering and owner detail.
- Moderation already had reports, independent removal appeals, attributable reviewer IDs, recoverable Content decisions and owner report/appeal reads. Open report duplicates had a generic 409; no video notice/standing composition or persisted decision reason codes existed. Gateway identity validation already rejected password-only privileged sessions, but moderation itself trusted a signed role without an explicit verified-MFA assertion; gateway did not explicitly enforce reviewer role before forwarding.
- Audit accepted only identity kinds and had immutable central events. Identity already supplied the transactional SecurityEvent/AuditDelivery producer pattern. Moderation had no audit producer/outbox/delivery command. Central events lacked producer/subject attribution and per-producer allow-lists.
- Identity had live revocation/MFA checks but no minimal standing/session-context read. Creators ownership/public detail could not provide restricted/suspended status with current publishing eligibility.

## Implemented endpoints and derivations

| Surface | Result |
| --- | --- |
| GET `/api/v1/creators/me/points` | Retains creator_id, balance, currency and as_of; adds confirmed/pending/withheld/reversed from retained records, never estimated counters. Verified email and owned creator profile required. Restrictions do not prevent reading one's ledger. |
| GET `/api/v1/creators/me/points/entries?status=all\|confirmed\|pending\|adjustments&cursor=<uuid>` | Adds status and nullable video_id; up to 20 records ordered by creation/receipt time then UUID descending. all includes pending/withheld receipts and ledger rows; confirmed is posted AWARD rows; pending is unposted receipts; adjustments is REVERSAL/ADJUSTMENT rows. Bad/foreign/status-incompatible cursor is 400. Concurrent status changes may invalidate cursors. |
| GET `/api/v1/creators/me/points/entries/{entry_id}` | Owner-only retained ledger entry or pending/withheld receipt; foreign/missing ID → 404. New pending receipt IDs remain stable when posted; legacy ledger IDs remain unchanged. All client POST/PUT/PATCH/DELETE methods on all three points routes return 405. No client award/adjustment route exists. |
| POST `/api/v1/reports` | New idempotency key for an already-open same-account/video report → 409 `code: already_reported`, including concurrent unique-constraint conflicts. Original key + identical payload still replays 200. Other key conflicts retain generic 409. New reports require public/published Content; existing own duplicates can be identified without revealing new Content data. |
| GET `/api/v1/creators/me/videos/{video_id}/notice` | Owner creator, including restricted/suspended owners. Current Content ownership/non-deletion is checked; foreign/deleted video → 404. Latest applied video decision, reason_code, decided_at, actual appeal eligibility and only the creator's own appeal. none/rejected/removed/restricted/restored are mapped from real applied actions; pending/conflicted decisions do not appear as applied. |
| GET `/api/v1/me/standing` | Authenticated account's live identity status, creator status, publishing permission and up to 20 recent latest video notices. Identity/creators/moderation are signed reads; Content rechecks notice ownership/non-deletion. No scope overrides. Missing creator → null status/false publishing/no notices. Publishing requires active session, verified email, existing permitted viewer/creator role and current approved creator eligibility. |
| Reviewer queues/decisions | Gateway explicitly requires moderator/administrator plus live MFA context bound to the same actor. Moderation also requires the signed gateway assertion `mfa_verified is True`; numeric/string substitutes fail. Existing session expiry/revocation/TOTP-factor checks remain enforced by identity. Decisions persist reviewer ID, reason text, reason_code and transactional audit evidence. |
| POST Audit `/internal/security-events` | Private direct service endpoint, never a public gateway route. Identity/moderation/creators/content/points have distinct configured caller keys and separate kind allow-lists. Optional paired subject_type/subject_id; strict schema, no arbitrary metadata/secrets. Existing four-field identity payload/digest/replay behavior stays compatible. Producer is derived from signature, never a client body field. |

Points meanings:

- **balance**: signed sum of all retained ledger deltas, including awards, reversals and adjustments.
- **confirmed**: gross positive posted AWARD deltas, including awards later reversed; no artificial confirmation window. Reversal amounts are reported separately.
- **pending**: one point per validated qualification received by Points whose durable QualificationReceipt remains pending posting. It is not a guess about unreceived broker backlog.
- **withheld**: one point per receipt explicitly blocked by the DEC-003 daily cap, with reason_code DAILY_CAP. No blocked award is posted to the ledger. The current two-field event flow has no creator-restriction input, so restriction blocks are not invented.
- **reversed**: absolute sum of negative REVERSAL deltas. ADJUSTMENT deltas affect balance but none of the four category totals.

Pending/withheld entry amounts describe potential awards, not posted balance changes. A receipt commits before processing; inbox acceptance, cap counter, posted award/withheld outcome and terminal receipt state commit together. Database failures preserve pending receipts for broker retry; terminal outcomes prevent repeat awards. Old consumed events without a retained award are marked legacy/unknown, not falsely pending or withheld. Previously discarded cap outcomes cannot be reconstructed. Existing DEC-003 qualified-view payload remains exactly creator_user_id + qualified_at, so video_id is honestly null for these awards; it is never inferred from client input.

## Models, migrations and files

- **Points `0004_pointsentry_video_id_qualificationreceipt.py`**: nullable PointsEntry.video_id; QualificationReceipt (event ID, creator account, actual qualification/receipt times, state, one-point amount, withholding code), owner/state index and amount constraint. Preserves ledger append-only guards across SQLite upgrade/rollback table rebuilds. Primary files: service/models.py, pilot_points.py, tests/test_completion.py.
- **Moderation `0003_auditevent_moderationaction_creator_id_and_more.py`**: nullable historical decision reason_code/creator_id and owner-lookup completion flag; immutable AuditEvent plus mutable AuditDelivery with attempts/delivery/next-attempt time. Database UPDATE/DELETE (and PostgreSQL TRUNCATE) guards protect producer evidence. Primary files: models.py, workflow.py, security_audit.py, internal_client.py, management commands and completion/workflow tests.
- **Audit `0004_securityevent_producer_securityevent_subject_id_and_more.py`**: producer defaults to identity for existing records; nullable subject type/UUID. Restores SQLite central audit guards after table rebuilds and during rollback. Primary files: models.py, events.py, service_auth.py, tests/test_producers.py.
- **Gateway**: pilot_points.py, moderation.py, new standing.py, routes/points.py, routes/moderation.py and tests. New routes retain points/moderation capability gates.
- **DOC-205**: PointsBalance/PointsEntry derivations and filters/detail, report conflict, notice/standing schemas/paths, reviewer MFA/reason-code requirements and direct private audit ingest with caller-kind allow-lists, subject schema and HMAC headers; implemented paths marked local.

Decision codes are optional on existing reviewer request shapes for compatibility. New decisions without an explicit code record REVIEWED_<ACTION>, an honest technical review code rather than a fabricated policy finding. Historical absent codes remain null. Existing applied restrict actions can render restricted notices; no new restriction decision route is introduced. Existing DEC-005 appeals remain limited to current removals with matching revision and no prior appeal; rejected content is not silently made appealable.

## Audit delivery and configuration

- Report creation, appeal creation, decision reservation and applied/conflicted outcomes atomically write producer evidence + AuditDelivery. Replays do not duplicate evidence. Audit failures roll back their owning business transaction; Content decision retries retain the existing idempotent receipt behavior.
- `python3 manage.py deliver_audit_events --limit 100` sends only due events, one attempt per selected event/invocation, two-second transport timeout, maximum batch 1000 and exponential retry delay capped at one hour. Acknowledgment must be exact; failed/malformed/unavailable delivery retains immutable evidence and remains retryable across invocations. No event is dropped after an attempt threshold. Schedule this command under deployment supervision; this change does not install a scheduler.
- Moderation adds the audit peer to its existing signed client. Audit uses verified HTTPS even locally (Content's existing loopback-only local exception is retained). Configure KOLOVIBE_AUDIT_URL and the existing moderation outbound signing key; central audit's caller file must assign the distinct matching producer key.
- Local launcher adds audit-only KOLOVIBE_AUDIT_CALLER_KEYS_FILE → KOLOVIBE_CALLER_KEYS_FILE, and moderation-only KOLOVIBE_AUDIT_URL / KOLOVIBE_INTERNAL_CA_FILE pass-through. Shared staging configuration now rejects duplicate audit producer keys and unapproved producer names. Audit service middleware independently validates that configured key map on each request, so rotation is not cached. No secret values or deployment manifests were added.

## Exact verification commands and results

Executed from repository root with Python 3.12.14, Django 5.2.18 and openapi-spec-validator 0.9.0, using the existing local dependency directories:

```bash
export KOLOVIBE_ENV=local
export DJANGO_SECRET_KEY=local-be-tr-test-key-at-least-32-characters
export PYTHONPATH=/workspace/scratch/7d4e52b069cd/kolovibe-dec003/deps:/workspace/scratch/7d4e52b069cd/kolovibe-stream.hKze2v/deps:/workspace/scratch/7d4e52b069cd/kolovibe-r2.MHla4M/media-deps:/workspace/scratch/100b9f85b85d/kolovibe-be-tr/services
```

| Exact command | Result |
| --- | --- |
| `(cd services/points && python3 manage.py test tests --verbosity 1)` | 21 passed |
| `(cd services/moderation && python3 manage.py test tests --verbosity 1)` | 18 passed |
| `(cd services/audit && python3 manage.py test tests --verbosity 1)` | 12 passed |
| `(cd services/gateway && python3 manage.py test tests --verbosity 1)` | 119 passed |
| `(cd services/identity && python3 manage.py test tests --verbosity 1)` | 58 passed |
| `(cd services/creators && python3 manage.py test tests --verbosity 1)` | 19 passed |
| `python3 -m unittest discover -s scripts -p test_run_local_service.py -v` | 10 passed |
| `python3 -m unittest discover -s scripts -p 'test_*runtime.py' -v` | 13 passed |
| `(cd services/points && python3 manage.py makemigrations --check --dry-run)` | Passed; no changes |
| `(cd services/moderation && python3 manage.py makemigrations --check --dry-run)` | Passed; no changes |
| `(cd services/audit && python3 manage.py makemigrations --check --dry-run)` | Passed; no changes |
| `(cd services/gateway && python3 manage.py makemigrations --check --dry-run)` | Passed; no changes |
| `(cd services/identity && python3 manage.py makemigrations --check --dry-run)` | Passed; no changes |
| `(cd services/creators && python3 manage.py makemigrations --check --dry-run)` | Passed; no changes |
| `python3 scripts/check_be_tr_migrations.py points` | Upgrade/rollback/re-upgrade preserved legacy facts and append-only guards |
| `python3 scripts/check_be_tr_migrations.py moderation` | Same; no invented historical codes/owners |
| `python3 scripts/check_be_tr_migrations.py audit` | Same; identity producer and payload digest retained |
| `python3 -c "import yaml; from openapi_spec_validator import validate_spec; validate_spec(yaml.safe_load(open('docs/architecture/DOC-205_OpenAPI_3_1_DRAFT.yaml'))); print('DOC-205 OpenAPI 3.1: PASS')"` | Passed; strict duplicate-key and changed JSON-schema checks also passed |
| `python3 scripts/check_structure.py` | Passed; eight services and approved layout |
| `git diff --check` | Passed |

**270 tests passed**, plus three migration round-trip checks. Coverage includes pending failure recovery, real cap withholding, reversal/adjustment derivation, mixed receipt/ledger pagination, stable receipt IDs, owner-only detail/notices, rejected client awards, reviewer role/MFA boundaries, session revocation/expired MFA, attributable reasons, report conflict codes, independent appeals, transactional audit rollback, producer allow-lists/keys, immutable database guards and bounded delivery backoff.

## Cross-ownership edits and remaining limits

- Identity: new gateway-only `/internal/auth/standing` live session context in accounts.py + urls.py, and tests; no identity model/migration changes. Returns only account ID/status, email verification and MFA verification, using existing revocation/session_allowed checks.
- Creators: minimal gateway-only `standing` operation in existing onboarding endpoint and tests; no creator model/migration changes. Supplies actual status/ownership and the existing approved-attestation eligibility rule, including restricted/suspended profiles.
- Shared: staging_runtime/__init__.py audit-key validation, local launcher/test, disposable migration-check script and DOC-205. **No Content, Engagement or outbox/AMQPS transport source edits.** Existing signed Content inspect/apply endpoints are reused.
- Apply Points 0004, Moderation 0003 and Audit 0004 before these handlers; coordinate Gateway/service response contracts and the new signed reviewer MFA assertion. Rollback destroys added qualification/audit evidence if those tables are dropped: preserve/export new data and pending delivery state under a reviewed rollback plan first. The disposable SQLite round-trip checks establish guard/schema behavior, not a production rollback authorization.
- Run bounded `python3 manage.py backfill_action_owners --limit 100` batches against authoritative Content for legacy moderation actions before serving large legacy standing histories. Each checked record is marked complete, including genuinely unavailable/deleted content without inventing an owner. Standing fails 503 on more than 20 unresolved legacy latest notices or its eight-second checked budget, rather than guessing ownership or emitting incomplete cross-owner results. Existing Content calls have two-second timeouts; the checked budget can finish after a final in-flight call. Slow/large histories may therefore need backfill or operational tuning.
- Confirmed is gross posted awards, not an available cash balance; withheld reflects retained cap outcomes only. Unreceived broker backlog, old discarded cap outcomes, absent video IDs and old reason codes are not reconstructed. A restriction-withholding policy/input is not added by this change.
- Central ingest accepts the five producers, but only moderation's new outbox/delivery is added here; identity's existing producer stays unchanged. It does not claim creators/content/points now publish audit events automatically.
- Live PostgreSQL concurrency/trigger behavior, signed service traffic, verified TLS, AMQPS delivery, production load, audit-command scheduling, deployment and CI acceptance were not exercised. Tests use SQLite and mocked peers. Existing staging capability approvals are not expanded and production remains gated.
