> Source: DOC-205_Full_API_Specification_DRAFT_v1_0.docx (text export; formatting and embedded images are not included). Original status is retained.

<PARSED TEXT FOR PAGE: 1 / 8>
                                          DOC-205
              FULL OPENAPI & API CONTRACT
                                  SPECIFICATION
                    Stage 2 · Version 1.0 · 28 October 2026 · FULL REVIEW DRAFT

Approved baseline: DOC-201–DOC-204. This is a design-stage draft; no production API or test success
is claimed.



Document control and scope
DOC-205 v1.0 is a full design-stage draft for Release 1. It is based on approved DOC-201–DOC-204. The
OpenAPI 3.1 YAML is the normative machine-readable draft; this handbook explains architecture
rules, security contracts and implementation acceptance. API hostnames, issuer, rate limits and
some schemas are placeholders pending decisions.



API ownership and routing
Internet → Cloudflare → dedicated Nginx VM (outside Docker Swarm) → restricted Swarm
gateway/BFF → identity/content/engagement/points/moderation services. Nginx never connects
directly to PostgreSQL. Only explicitly published routes are public. /internal paths must not be
exposed by Nginx or any public ingress. Internal endpoints require service identity and least-
privilege scopes.



Versioning and compatibility
Use /v1 for public routes. Additive optional fields may be introduced compatibly; breaking changes
require /v2 and a published migration window. Each endpoint has stable operationId and
request/response schemas. Deprecations use Sunset/Deprecation headers where appropriate. Never
change the meaning of a points rule silently; record rule_version.



Authentication and sessions
User-facing API uses bearer access tokens; Django template web may use secure HttpOnly SameSite
cookies and CSRF protection at the BFF. Refresh token rotation, token revocation, MFA for privileged
accounts, login throttling, password breach checks and secure mobile token storage are required.
Final JWT issuer, key rotation and token lifetime are pending identity ADR. Token validation must
enforce iss, aud, exp, nbf, algorithm allowlist and key rotation.



Authorization and object ownership
Enforce deny-by-default RBAC and object-level checks at each service, not solely at gateway. A
creator may edit only owned videos. Moderators access only authorized cases. Support has no
automatic access to secrets or raw fraud signals. No public write API to points ledger. Internal
workload identity cannot be substituted with a user JWT.
<PARSED TEXT FOR PAGE: 2 / 8>
Request/response conventions
JSON UTF-8; ISO 8601 UTC timestamps; UUID identifiers; application/problem+json for errors with
stable code and request_id; strict content types; explicit maximum request sizes; cursor pagination
for collections; ETag/If-Match recommended for concurrent edits. Do not leak existence of private
resources through error differences. Document 401/403/404 decisions in test cases.



Idempotency and concurrency
Require Idempotency-Key on unsafe creation or posting operations, scoped to actor + route +
canonical request hash. Same key and same payload returns original result; changed payload
returns 409. Server stores key result within defined TTL. Unique constraints, transactional
outbox/inbox, and append-only points ledger protect against retries and at-least-once delivery. For
watch telemetry, event_id and session_id are not sufficient evidence of qualified activity.



Engagement and points trust contract
Client watch-events are untrusted telemetry and return 202 Accepted. Engagement service validates
server-side evidence and abuse rules, emits qualified events with rule_version and evidence_ref.
Points service accepts only authenticated internal qualified events, checks uniqueness, and posts
append-only awards/reversals. Never expose client-settable points, awards or ledger adjustment.
Advertising impressions/clicks cannot create points. R1 points are non-cash, non-transferable, and
not redeemable.



Content upload and playback
Creator creates video metadata, requests short-lived one-time upload intent, sends bytes directly to
managed video provider, and receives status only after provider-authenticated callback and
authoritative verification. Publish requires processed media and moderation gates. Playback token
must enforce visibility, short expiration and revocation behavior. Rate-limit upload intents; check
size, MIME and content state.



Moderation and audit
Reports are authenticated and idempotent. Moderator actions require role, case-level authorization,
mandatory reason and immutable audit record. Bulk or sensitive actions may require dual review.
Every privileged mutation records actor, target, previous/new state, request_id, timestamp and
decision reason.



Service-to-service security
Swarm overlay membership is not authentication. Require workload JWT with audience and scopes
and/or mutual TLS; validate caller service identity on every internal API. Segregate networks and
databases. Rotate secrets; no credentials in images, URLs or logs. Use timeouts, bounded retries,
circuit breakers and backpressure. Never retry non-idempotent operations without idempotency
key.
<PARSED TEXT FOR PAGE: 3 / 8>
Webhooks and external providers
Provider callbacks must verify raw-body signature, timestamp, replay window, event_id uniqueness,
provider identity and authoritative state. Place provider-specific routes behind explicit Nginx
routing, not /internal service-to-service endpoints. Fail closed on invalid signatures; acknowledge
duplicates safely; retry asynchronous processing with dead-letter handling.



Availability and performance
Set endpoint-specific budgets for p95 latency, request body size, rate limits and concurrency during
Stage 3 load planning. Liveness must not depend on external systems; readiness checks required
dependencies without leaking details. Define per-service timeout and SLO, protect Redis and
PostgreSQL pools, and propagate trace IDs across synchronous calls and Celery jobs.



Privacy and observability
Do not log passwords, tokens, raw upload URLs, full device fingerprints or private report details. Log
request_id, service, route template, status, latency, caller class and trace_id. Apply retention limits
and role-restricted access. Sensitive anti-fraud evidence requires purpose limitation and privacy
review before pilot.



Security test matrix
Test missing/expired/wrong-audience tokens, object ID swaps, user JWT on internal endpoint,
workload token without scope, idempotency key replay, race conditions, forged provider webhooks,
private video playback, self-view points abuse, ad event reward attempts, overlong payloads, CSRF
on cookie endpoints, enumeration, rate limits and response redaction. Map test cases to DOC-203
risks and DOC-206 controls.



Out of scope and future gates
R2 business verification and reviews, R3 ticketing/payments, R4 cash payouts and monetary ledger
are explicitly excluded from R1 OpenAPI. Do not introduce payment or withdrawal endpoints before
separately approved specifications and threat models.



Open decisions and review conditions
OD-205-01 token issuer and web cookie-vs-BFF policy; OD-205-02 precise request limits/rate limits;
OD-205-03 watch evidence schema and points rule thresholds; OD-205-04 video provider callback
contract; OD-205-05 pagination response schema for points/moderation; OD-205-06 public endpoint
error semantics; OD-205-07 service identity issuance and rotation; OD-205-08 audit retention. Final
acceptance requires resolving or explicitly tracking each, linting OpenAPI, contract tests and
security review. This is design approval only, not an implemented API.



Endpoint catalog

POST /auth/register
Register user | Owner: Identity | Auth: Public
<PARSED TEXT FOR PAGE: 4 / 8>
POST /auth/login
Authenticate user | Owner: Identity | Auth: Public

POST /auth/refresh
Rotate refresh token | Owner: Identity | Auth: Public

Refresh token is transported in secure HttpOnly cookie for web; mobile storage uses OS secure store.
Exact strategy subject to ADR.

POST /auth/logout
Revoke current session | Owner: Identity | Auth: User

GET /me
Get current account | Owner: Identity | Auth: User

GET /creators/{creator_id}
Get public creator profile | Owner: Creators | Auth: Public

PATCH /creators/me
Edit own creator profile | Owner: Creators | Auth: User

Roles: creator

POST /videos
Create draft video metadata | Owner: Content | Auth: User

Roles: creator

GET /videos
List published videos | Owner: Content | Auth: Public

GET /videos/{video_id}
Get video details | Owner: Content | Auth: Public

Unpublished content visible only to owner or authorized moderators.

PATCH /videos/{video_id}
Edit own draft video | Owner: Content | Auth: User

Roles: creator

POST /videos/{video_id}/upload-intents
Issue one-time direct upload intent | Owner: Content | Auth: User

Roles: creator

Video bytes upload to provider; backend verifies provider completion via authenticated webhook
and provider status check.
<PARSED TEXT FOR PAGE: 5 / 8>
POST /videos/{video_id}/publish
Request publication after processing/moderation | Owner: Content | Auth: User

Roles: creator

POST /videos/{video_id}/unpublish
Unpublish owned video | Owner: Content | Auth: User

Roles: creator

GET /videos/{video_id}/playback
Obtain authorized short-lived playback token | Owner: Content | Auth: User

POST /engagement/watch-events
Submit untrusted watch telemetry for server validation | Owner: Engagement | Auth: User

202 Accepted. Telemetry alone never grants points; server checks signed sessions, playback evidence
and abuse signals.

PUT /videos/{video_id}/like
Like video once per user | Owner: Engagement | Auth: User

DELETE /videos/{video_id}/like
Remove like | Owner: Engagement | Auth: User

GET /creators/me/points
Read own non-cash points balance | Owner: Points | Auth: User

Roles: creator

GET /creators/me/points/entries
Read own points history | Owner: Points | Auth: User

Roles: creator

Actual response should be paginated; schema refinement before implementation.

POST /reports
Report content | Owner: Moderation | Auth: User

GET /moderation/reports
List moderation cases | Owner: Moderation | Auth: User

Roles: moderator, admin

Paginated response refinement required.

POST /moderation/reports/{report_id}/decisions
Make audited moderation decision | Owner: Moderation | Auth: User

Roles: moderator, admin
<PARSED TEXT FOR PAGE: 6 / 8>
GET /health/live
Process liveness | Owner: Operations | Auth: Public

GET /health/ready
Dependency readiness | Owner: Operations | Auth: Public

Not exposed publicly through Nginx; only cluster health checks.

POST /internal/points/qualified-events
Record qualified award via service identity only | Owner: Internal Events | Auth: Service

Never exposed through public Nginx. mTLS/workload JWT with points:write scope, audience checks,
and outbox/inbox deduplication.



Schema catalog

Problem
Required: type, title, status, code, request_id

Properties: type, title, status, detail, code, request_id

User
Required: id, display_name, roles

Properties: id, email, display_name, roles, created_at

RegisterRequest
Required: email, password, display_name

Properties: email, password, display_name

LoginRequest
Required: email, password

Properties: email, password

TokenResponse
Required: access_token, expires_in, token_type

Properties: access_token, expires_in, token_type, refresh_token

Creator
Required: id, user_id, handle, status

Properties: id, user_id, handle, bio, status

CreatorUpdate
Required: None

Properties: bio, display_name
<PARSED TEXT FOR PAGE: 7 / 8>
Video
Required: id, creator_id, title, state

Properties: id, creator_id, title, description, state, duration_seconds, created_at

VideoCreate
Required: title

Properties: title, description, visibility

UploadIntent
Required: upload_id, video_id, upload_url, expires_at

Properties: upload_id, video_id, upload_url, expires_at, max_bytes

Playback
Required: playback_url, expires_at

Properties: playback_url, expires_at

WatchEvent
Required: video_id, session_id, event_id, position_seconds

Properties: video_id, session_id, event_id, position_seconds, observed_at

Like
Required: video_id, liked

Properties: video_id, liked, updated_at

PointsBalance
Required: creator_id, balance, pending, currency

Properties: creator_id, balance, pending, currency, as_of

PointsEntry
Required: id, creator_id, amount, kind, rule_version, created_at

Properties: id, creator_id, amount, kind, rule_version, evidence_ref, created_at

ReportCreate
Required: video_id, reason

Properties: video_id, reason, details

Report
Required: id, video_id, status

Properties: id, video_id, status, created_at
<PARSED TEXT FOR PAGE: 8 / 8>
ModerationDecision
Required: action, reason

Properties: action, reason

InternalQualifiedEvent
Required: event_id, creator_id, video_id, rule_version, evidence_ref, points

Properties: event_id, creator_id, video_id, rule_version, evidence_ref, points

PageVideos
Required: items

Properties: items, next_cursor



Approval and evidence
Sponsor: __________________ Date: __________ Security reviewer: __________________ Date: __________

Unresolved items: See OD-205-01 through OD-205-08. Approval of this design does not mean all
implementation parameters are fixed.