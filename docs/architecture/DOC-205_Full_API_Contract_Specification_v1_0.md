# DOC-205 — Full OpenAPI and API Contract Specification
Version 1.0 | 28 October 2026 | FULL REVIEW DRAFT
Baseline: DOC-201, DOC-202, DOC-203, DOC-204 approved.

## Document control and scope
DOC-205 v1.0 is a full design-stage draft for Release 1. It is based on approved DOC-201–DOC-204. The OpenAPI 3.1 YAML is the normative machine-readable draft; this handbook explains architecture rules, security contracts and implementation acceptance. API hostnames, issuer, rate limits and some schemas are placeholders pending decisions.

## API ownership and routing
Internet → Cloudflare → dedicated Nginx VM (outside Docker Swarm) → restricted Swarm gateway/BFF → identity/content/engagement/points/moderation services. Nginx never connects directly to PostgreSQL. Only explicitly published routes are public. /internal paths must not be exposed by Nginx or any public ingress. Internal endpoints require service identity and least-privilege scopes.

## Versioning and compatibility
Use /v1 for public routes. Additive optional fields may be introduced compatibly; breaking changes require /v2 and a published migration window. Each endpoint has stable operationId and request/response schemas. Deprecations use Sunset/Deprecation headers where appropriate. Never change the meaning of a points rule silently; record rule_version.

## Authentication and sessions
User-facing API uses bearer access tokens; Django template web may use secure HttpOnly SameSite cookies and CSRF protection at the BFF. Refresh token rotation, token revocation, MFA for privileged accounts, login throttling, password breach checks and secure mobile token storage are required. Final JWT issuer, key rotation and token lifetime are pending identity ADR. Token validation must enforce iss, aud, exp, nbf, algorithm allowlist and key rotation.

## Authorization and object ownership
Enforce deny-by-default RBAC and object-level checks at each service, not solely at gateway. A creator may edit only owned videos. Moderators access only authorized cases. Support has no automatic access to secrets or raw fraud signals. No public write API to points ledger. Internal workload identity cannot be substituted with a user JWT.

## Request/response conventions
JSON UTF-8; ISO 8601 UTC timestamps; UUID identifiers; application/problem+json for errors with stable code and request_id; strict content types; explicit maximum request sizes; cursor pagination for collections; ETag/If-Match recommended for concurrent edits. Do not leak existence of private resources through error differences. Document 401/403/404 decisions in test cases.

## Idempotency and concurrency
Require Idempotency-Key on unsafe creation or posting operations, scoped to actor + route + canonical request hash. Same key and same payload returns original result; changed payload returns 409. Server stores key result within defined TTL. Unique constraints, transactional outbox/inbox, and append-only points ledger protect against retries and at-least-once delivery. For watch telemetry, event_id and session_id are not sufficient evidence of qualified activity.

## Engagement and points trust contract
Client watch-events are untrusted telemetry and return 202 Accepted. Engagement service validates server-side evidence and abuse rules, emits qualified events with rule_version and evidence_ref. Points service accepts only authenticated internal qualified events, checks uniqueness, and posts append-only awards/reversals. Never expose client-settable points, awards or ledger adjustment. Advertising impressions/clicks cannot create points. R1 points are non-cash, non-transferable, and not redeemable.

## Content upload and playback
Creator creates video metadata, requests short-lived one-time upload intent, sends bytes directly to managed video provider, and receives status only after provider-authenticated callback and authoritative verification. Publish requires processed media and moderation gates. Playback token must enforce visibility, short expiration and revocation behavior. Rate-limit upload intents; check size, MIME and content state.

## Moderation and audit
Reports are authenticated and idempotent. Moderator actions require role, case-level authorization, mandatory reason and immutable audit record. Bulk or sensitive actions may require dual review. Every privileged mutation records actor, target, previous/new state, request_id, timestamp and decision reason.

## Service-to-service security
Swarm overlay membership is not authentication. Require workload JWT with audience and scopes and/or mutual TLS; validate caller service identity on every internal API. Segregate networks and databases. Rotate secrets; no credentials in images, URLs or logs. Use timeouts, bounded retries, circuit breakers and backpressure. Never retry non-idempotent operations without idempotency key.

## Webhooks and external providers
Provider callbacks must verify raw-body signature, timestamp, replay window, event_id uniqueness, provider identity and authoritative state. Place provider-specific routes behind explicit Nginx routing, not /internal service-to-service endpoints. Fail closed on invalid signatures; acknowledge duplicates safely; retry asynchronous processing with dead-letter handling.

## Availability and performance
Set endpoint-specific budgets for p95 latency, request body size, rate limits and concurrency during Stage 3 load planning. Liveness must not depend on external systems; readiness checks required dependencies without leaking details. Define per-service timeout and SLO, protect Redis and PostgreSQL pools, and propagate trace IDs across synchronous calls and Celery jobs.

## Privacy and observability
Do not log passwords, tokens, raw upload URLs, full device fingerprints or private report details. Log request_id, service, route template, status, latency, caller class and trace_id. Apply retention limits and role-restricted access. Sensitive anti-fraud evidence requires purpose limitation and privacy review before pilot.

## Security test matrix
Test missing/expired/wrong-audience tokens, object ID swaps, user JWT on internal endpoint, workload token without scope, idempotency key replay, race conditions, forged provider webhooks, private video playback, self-view points abuse, ad event reward attempts, overlong payloads, CSRF on cookie endpoints, enumeration, rate limits and response redaction. Map test cases to DOC-203 risks and DOC-206 controls.

## Out of scope and future gates
R2 business verification and reviews, R3 ticketing/payments, R4 cash payouts and monetary ledger are explicitly excluded from R1 OpenAPI. Do not introduce payment or withdrawal endpoints before separately approved specifications and threat models.

## Open decisions and review conditions
OD-205-01 token issuer and web cookie-vs-BFF policy; OD-205-02 precise request limits/rate limits; OD-205-03 watch evidence schema and points rule thresholds; OD-205-04 video provider callback contract; OD-205-05 pagination response schema for points/moderation; OD-205-06 public endpoint error semantics; OD-205-07 service identity issuance and rotation; OD-205-08 audit retention. Final acceptance requires resolving or explicitly tracking each, linting OpenAPI, contract tests and security review. This is design approval only, not an implemented API.

## Endpoint inventory
| Method | Path | Owner | Summary |
|---|---|---|---|
| POST | `/auth/register` | Identity | Register user |
| POST | `/auth/login` | Identity | Authenticate user |
| POST | `/auth/refresh` | Identity | Rotate refresh token |
| POST | `/auth/logout` | Identity | Revoke current session |
| GET | `/me` | Identity | Get current account |
| GET | `/creators/{creator_id}` | Creators | Get public creator profile |
| PATCH | `/creators/me` | Creators | Edit own creator profile |
| POST | `/videos` | Content | Create draft video metadata |
| GET | `/videos` | Content | List published videos |
| GET | `/videos/{video_id}` | Content | Get video details |
| PATCH | `/videos/{video_id}` | Content | Edit own draft video |
| POST | `/videos/{video_id}/upload-intents` | Content | Issue one-time direct upload intent |
| POST | `/videos/{video_id}/publish` | Content | Request publication after processing/moderation |
| POST | `/videos/{video_id}/unpublish` | Content | Unpublish owned video |
| GET | `/videos/{video_id}/playback` | Content | Obtain authorized short-lived playback token |
| POST | `/engagement/watch-events` | Engagement | Submit untrusted watch telemetry for server validation |
| PUT | `/videos/{video_id}/like` | Engagement | Like video once per user |
| DELETE | `/videos/{video_id}/like` | Engagement | Remove like |
| GET | `/creators/me/points` | Points | Read own non-cash points balance |
| GET | `/creators/me/points/entries` | Points | Read own points history |
| POST | `/reports` | Moderation | Report content |
| GET | `/moderation/reports` | Moderation | List moderation cases |
| POST | `/moderation/reports/{report_id}/decisions` | Moderation | Make audited moderation decision |
| GET | `/health/live` | Operations | Process liveness |
| GET | `/health/ready` | Operations | Dependency readiness |
| POST | `/internal/points/qualified-events` | Internal Events | Record qualified award via service identity only |

## Schema inventory
Problem, User, RegisterRequest, LoginRequest, TokenResponse, Creator, CreatorUpdate, Video, VideoCreate, UploadIntent, Playback, WatchEvent, Like, PointsBalance, PointsEntry, ReportCreate, Report, ModerationDecision, InternalQualifiedEvent, PageVideos

**Normative source:** `DOC-205_OpenAPI_3_1_DRAFT.yaml`. Open decisions are intentionally not represented as finalized operational facts.