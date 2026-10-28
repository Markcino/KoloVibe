> Source: DOC-203_Full_STRIDE_Threat_Model_DRAFT_v1_0.docx (text export; formatting and embedded images are not included). Original status is retained.

<PARSED TEXT FOR PAGE: 1 / 13>
                                         DOC-203
           FULL STRIDE THREAT MODEL
                   Stage 2 | Version 1.0 | 28 October 2026 | FULL REVIEW DRAFT

Architecture baseline: DOC-201 and DOC-202 approved. This document is submitted for review;
security controls are not yet implemented or verified.



Purpose, scope and status
This is the complete design-stage threat model for Release 1, based on approved DOC-201 and
DOC-202. It specifies risks and security acceptance tests, not claims of deployed or tested controls.
R2–R4 threats are retained as future gates. No risk owner, probability or residual rating is accepted
until the security review.



System assumptions and dependencies
Client: Flutter Android/iOS and Django-template web. Edge: Cloudflare. Reverse proxy: dedicated
Nginx VM outside Swarm. App: Django/DRF microservices inside Docker Swarm; private API
gateway/BFF. Data: PostgreSQL with logical service ownership; Redis/Celery. Video: managed
processing/streaming provider. Cloudflare-to-origin authentication, upstream TLS, Swarm topology,
database hosting and exact retention rules remain architecture decisions to confirm.



Security objectives and crown jewels
Protect account/session integrity, original content ownership, unpublished media, qualified
engagement evidence, non-cash points ledger integrity, moderation case confidentiality, audit
nonrepudiation, deployment control plane, secrets, backups and future financial boundaries. R1
must never exchange points for money or reward Google ad views/clicks.



Actors and entry points
Actors include anonymous users, viewers, creators, moderators, administrators, support personnel,
service workloads, third-party video/ads providers, CI/CD operators, compromised hosts, colluding
accounts and external attackers. Entry points include public HTTPS APIs, login, direct-to-provider
upload, playback tokens, provider webhooks, internal service APIs, Swarm control plane, Nginx SSH,
DB connections and pipeline deploy credentials.



Trust boundaries
TB-01 Internet→Cloudflare; TB-02 Cloudflare→dedicated Nginx VM; TB-03 Nginx VM →private Swarm
gateway; TB-04 public API gateway→service workloads; TB-05 service →service; TB-06
service→owned PostgreSQL database; TB-07 service→Redis/Celery; TB-08 content →video provider;
TB-09 provider→signed webhook handler; TB-10 operator→Swarm manager/CI; TB-11
service→central logs/backups; TB-12 engagement→points ledger; TB-13 advertising metrics →separate
reporting. Never assume internal overlay traffic is intrinsically trusted.
<PARSED TEXT FOR PAGE: 2 / 13>
Methodology and rating
Apply STRIDE per asset, process, data store and data flow. Inherent severity is preliminary and
impact-weighted; Critical means cluster/identity takeover, widespread confidentiality compromise
or systemic points fraud; High means material service/data abuse; Medium means bounded abuse.
Assess likelihood 1–5 and impact 1–5 at review; compute risk score and document compensating
controls. Residual ratings are explicitly TBD until evidence exists. No open Critical risk permitted at
pilot; High requires mitigation and signed exception if residual.



Abuse cases and cross-boundary chains
AC-01 bypass Cloudflare→Nginx→published Swarm port; AC-02 forged proxy headers →auth/CSRF
confusion; AC-03 stolen service token→points writes; AC-04 repeated view evidence →double point
posting; AC-05 fake video completion→published unsafe content; AC-06 moderator misuse →audit
deletion; AC-07 compromised pipeline→malicious stack; AC-08 worker poison message →cross-
service effect; AC-09 private media replay→unpublished disclosure; AC-10 ad callback →attempted
points credit. Every chain requires both prevention and detection.



Required control design
Perimeter: source allowlisting, origin authentication, rate limits, secure headers, separate Nginx
hardening. Workloads: least-privilege service identity, short-lived scoped tokens, segmentation,
digest-pinned images, Swarm secrets and restricted manager access. App: object authorization, CSRF
for cookie web sessions, input validation, idempotency, transaction constraints and provider
webhook signatures. Data: DB role separation, encryption in transit/at rest, backup restore and audit
immutability. Operations: CI protections, centralized monitoring, incident runbooks and SLOs.



Engagement and points security invariants
INV-01 Only server-validated qualified activity may create points. INV-02 No ad impression/click
event may directly or indirectly create a points posting. INV-03 Each qualified activity has at most
one effective award per applicable rule window. INV-04 Every points entry is attributable to rule
version and evidence reference. INV-05 Reversal is append-only, not destructive mutation. INV-06
Creator cannot directly credit their own points. INV-07 R1 points cannot be withdrawn, transferred
or redeemed for cash. INV-08 Client timestamps and playback counters are untrusted.



Privacy and retention
Collect minimum necessary fraud signals; restrict access to raw IP/device identifiers; do not log
tokens, provider secrets or health data; use documented retention schedules and subject
access/deletion procedures subject to legal and fraud-evidence holds. Exact retention periods,
consent notices and Liberia-specific legal review are pending and must be signed before pilot.



Security verification strategy
For every risk: owner produces architecture evidence, configuration evidence, automated negative
test, staging integration result and a remediation ticket where needed. Verify Nginx origin bypass,
Swarm port isolation, unauthorized service calls, database privilege separation, replay/idempotency,
<PARSED TEXT FOR PAGE: 3 / 13>
media authorization, fraud simulation, moderation audit, log redaction, restore drill and failover.
Track results as Pass/Fail/Blocked/Not Run; none are claimed as passed in this draft.



Incident response and observability
Alert on privileged logins, failed service identity checks, Swarm manager membership changes,
anomalous qualified-view rates, points reversals, unusual content takedowns, provider webhook
signature failures and backup errors. Preserve correlation IDs across Nginx, gateway, services,
worker and ledger. Define on-call owner, containment steps, evidence retention, recovery validation
and user communication thresholds.



Third-party and supply-chain review
Document Cloudflare/video-provider contracts, data residency and processor roles; restrict webhook
secrets; rotate credentials; pin dependency versions; scan images and dependencies; generate
SBOMs; verify license and security updates; ensure no ad platform integration creates incentives
prohibited by publisher policies.



Future release gates
R2 verified businesses requires business verification abuse and review authenticity controls. R3
tickets requires payment settlement authority, signed PSP callbacks, unique QR redemption and
double-scan resistance. R4 payouts requires independently reconciled eligible collected revenue,
monetary double-entry ledger, maker-checker approvals, sanctions/fraud checks as applicable, and
separate security sign-off. These are not R1 implementations.



Open decisions and blockers
OD-01 Nginx/Swarm private connectivity and mTLS/tunnel; OD-02 Swarm managers/workers count
and quorum; OD-03 PostgreSQL topology and backup RPO/RTO; OD-04 identity/session and workload
credentials; OD-05 qualified-view thresholds and points formula; OD-06 fraud-signal
privacy/retention; OD-07 provider webhook specifics; OD-08 audit storage/retention; OD-09
monitoring stack and on-call; OD-10 edge-to-origin authentication. Each decision needs an owner,
due date and approval record.



Formal acceptance criteria
Complete review of all TM IDs; confirm threat likelihood/impact and accountable owner; map each
High/Critical risk to tested control and evidence; verify no unmitigated Critical risk; approve
exceptions for any residual High risk; approve privacy and fraud retention; cross-reference
DOC-201/202/204/205/206/208; obtain security lead and project sponsor sign-off. Until then DOC-203
is a full review draft, not approved or security certified.



Detailed threat register
The accompanying CSV is the editable master register. Entries below provide the full
threat/control/test mapping.
<PARSED TEXT FOR PAGE: 4 / 13>
TM-001 — Forged Cloudflare origin requests [High]
Boundary: Perimeter and proxy | STRIDE: S | Release: R1 | Owner: Platform/SRE

Attack scenario: Attacker reaches Nginx directly and bypasses WAF

Required controls: Authenticated origin pull or mTLS; firewall Cloudflare source allowlist; reject
missing origin authentication

Verification: External origin-bypass probe; firewall audit

Residual risk: TBD after implementation and testing. Status: proposed; not tested.

TM-002 — Forged forwarded headers [High]
Boundary: Perimeter and proxy | STRIDE: T | Release: R1 | Owner: Platform

Attack scenario: Client-supplied X-Forwarded-* changes IP, scheme or host interpretation

Required controls: Nginx overwrites proxy headers; Django ALLOWED_HOSTS,
SECURE_PROXY_SSL_HEADER only for trusted proxy; strict CSRF origins

Verification: Spoof Host/X-Forwarded-For/Proto tests

Residual risk: TBD after implementation and testing. Status: proposed; not tested.

TM-003 — Proxy-to-Swarm interception [High]
Boundary: Perimeter and proxy | STRIDE: I | Release: R1 | Owner: Platform

Attack scenario: Traffic from separate Nginx VM is observed or altered

Required controls: Private routed network plus verified upstream TLS/mTLS or WireGuard; rotate
keys

Verification: MITM attempt and certificate mismatch test

Residual risk: TBD after implementation and testing. Status: proposed; not tested.

TM-004 — Nginx VM failure [High]
Boundary: Perimeter and proxy | STRIDE: D | Release: R1 | Owner: SRE

Attack scenario: Single reverse proxy causes total outage

Required controls: Document RTO/RPO; backup config; tested rebuild; second proxy and LB for HA

Verification: Kill proxy VM and time recovery

Residual risk: TBD after implementation and testing. Status: proposed; not tested.

TM-005 — Nginx host compromise [Critical]
Boundary: Perimeter and proxy | STRIDE: E | Release: R1 | Owner: SRE/Security

Attack scenario: Exposed VM yields routing control and secret theft
<PARSED TEXT FOR PAGE: 5 / 13>
Required controls: Harden OS, no app credentials, restricted SSH, patching, file integrity and
centralized logs

Verification: Host hardening and secret exposure review

Residual risk: TBD after implementation and testing. Status: proposed; not tested.

TM-006 — Oversized requests and connection flood [High]
Boundary: Perimeter and proxy | STRIDE: D | Release: R1 | Owner: SRE

Attack scenario: Upload and API floods exhaust gateway or app capacity

Required controls: Edge and Nginx limits, per-route rate limits, upload directly to video provider

Verification: Load and burst test

Residual risk: TBD after implementation and testing. Status: proposed; not tested.

TM-007 — Credential stuffing [High]
Boundary: Identity | STRIDE: S | Release: R1 | Owner: Identity

Attack scenario: Reused passwords compromise accounts

Required controls: Rate limits, breached-password screening, MFA for privileged roles, anomaly
detection

Verification: Automated login abuse simulation

Residual risk: TBD after implementation and testing. Status: proposed; not tested.

TM-008 — Token theft or replay [High]
Boundary: Identity | STRIDE: S | Release: R1 | Owner: Identity

Attack scenario: Stolen access/refresh token accesses another account

Required controls: Short access TTL, rotating refresh tokens, revocation, secure storage,
device/session audit

Verification: Replay revoked and rotated tokens

Residual risk: TBD after implementation and testing. Status: proposed; not tested.

TM-009 — Role escalation / IDOR [Critical]
Boundary: Identity | STRIDE: E | Release: R1 | Owner: Identity/All services

Attack scenario: Viewer accesses creator or moderator resources by changing IDs

Required controls: Object-level authorization in each service; default deny; scoped service tokens

Verification: Cross-tenant API matrix negative tests

Residual risk: TBD after implementation and testing. Status: proposed; not tested.
<PARSED TEXT FOR PAGE: 6 / 13>
TM-010 — Privileged action without attribution [High]
Boundary: Identity | STRIDE: R | Release: R1 | Owner: Security

Attack scenario: Moderator action lacks immutable audit context

Required controls: Append-only audit trail with actor, target, reason, request ID and timestamp

Verification: Remove logs locally and verify central copy

Residual risk: TBD after implementation and testing. Status: proposed; not tested.

TM-011 — Account enumeration [Medium]
Boundary: Identity | STRIDE: I | Release: R1 | Owner: Identity

Attack scenario: Reset/login responses reveal registered users

Required controls: Generic responses and uniform timing; per-IP/account rate limiting

Verification: Enumeration comparison

Residual risk: TBD after implementation and testing. Status: proposed; not tested.

TM-012 — Forged service identity [Critical]
Boundary: Service mesh and Swarm | STRIDE: S | Release: R1 | Owner: Platform/Points

Attack scenario: Compromised container calls internal points endpoint as engagement service

Required controls: Workload identity, short-lived service credentials, mTLS or signed service JWT
with audience and scopes

Verification: Call points endpoint with wrong service identity

Residual risk: TBD after implementation and testing. Status: proposed; not tested.

TM-013 — Lateral movement via overlay [High]
Boundary: Service mesh and Swarm | STRIDE: E | Release: R1 | Owner: Platform

Attack scenario: One service accesses unrelated private services

Required controls: Segment overlay networks, per-service network membership, egress policies
where supported

Verification: Compromised-container reachability map

Residual risk: TBD after implementation and testing. Status: proposed; not tested.

TM-014 — Swarm manager takeover [Critical]
Boundary: Service mesh and Swarm | STRIDE: E | Release: R1 | Owner: SRE

Attack scenario: Exposed control plane yields full cluster control

Required controls: Dedicated managers, restricted 2377, mutual node auth, hardened hosts, RBAC
via operational access
<PARSED TEXT FOR PAGE: 7 / 13>
Verification: Management port scan and admin access review

Residual risk: TBD after implementation and testing. Status: proposed; not tested.

TM-015 — Leaked Swarm secrets [Critical]
Boundary: Service mesh and Swarm | STRIDE: I | Release: R1 | Owner: SRE

Attack scenario: Secrets exposed through env, logs or backups

Required controls: Swarm secrets or external manager; avoid env; rotation; encrypted backups; no
secrets in images

Verification: Image/config/log secret scan

Residual risk: TBD after implementation and testing. Status: proposed; not tested.

TM-016 — Untrusted image deployment [High]
Boundary: Service mesh and Swarm | STRIDE: T | Release: R1 | Owner: DevSecOps

Attack scenario: Malicious dependency or image enters release

Required controls: Pinned image digests, SBOM, SCA, signed provenance, approval gates

Verification: Deploy unsigned image in staging; block

Residual risk: TBD after implementation and testing. Status: proposed; not tested.

TM-017 — Node loss and quorum loss [High]
Boundary: Service mesh and Swarm | STRIDE: D | Release: R1 | Owner: SRE

Attack scenario: Manager quorum or worker capacity unavailable

Required controls: 3 managers for HA if budget permits; placement constraints; backup/restore;
capacity alerting

Verification: Simulate manager/worker loss

Residual risk: TBD after implementation and testing. Status: proposed; not tested.

TM-018 — Missing distributed trace [Medium]
Boundary: Service mesh and Swarm | STRIDE: R | Release: R1 | Owner: Platform

Attack scenario: Cannot attribute cross-service modification

Required controls: Trace IDs propagated, immutable audit events, synchronized time

Verification: Trace end-to-end engagement event

Residual risk: TBD after implementation and testing. Status: proposed; not tested.

TM-019 — Forged upload completion [High]
Boundary: Content/media | STRIDE: T | Release: R1 | Owner: Content

Attack scenario: Client claims a video was uploaded without provider verification
<PARSED TEXT FOR PAGE: 8 / 13>
Required controls: Server-issued one-time upload intent; provider status lookup and signed
webhook verification

Verification: Submit fake completion event

Residual risk: TBD after implementation and testing. Status: proposed; not tested.

TM-020 — Private media leakage [High]
Boundary: Content/media | STRIDE: I | Release: R1 | Owner: Content

Attack scenario: Unauthorized user retrieves unpublished or removed video

Required controls: Signed playback tokens where applicable; strict publish state; purge invalidation

Verification: Attempt access after unpublish

Residual risk: TBD after implementation and testing. Status: proposed; not tested.

TM-021 — Malicious media payload [High]
Boundary: Content/media | STRIDE: D | Release: R1 | Owner: Content

Attack scenario: Crafted file exploits transcoder or metadata parser

Required controls: Managed provider processing, content-type/size checks, malware scanning where
feasible, sandboxed parsing

Verification: Fuzz metadata and MIME mismatch

Residual risk: TBD after implementation and testing. Status: proposed; not tested.

TM-022 — Webhook replay or forgery [High]
Boundary: Content/media | STRIDE: T | Release: R1 | Owner: Content

Attack scenario: Attacker replays provider callback to alter media status

Required controls: Verify signature, timestamp, event ID deduplication and authoritative provider
state

Verification: Replay valid signed webhook

Residual risk: TBD after implementation and testing. Status: proposed; not tested.

TM-023 — Synthetic view farms [Critical]
Boundary: Engagement | STRIDE: S | Release: R1 | Owner: Engagement

Attack scenario: Bots or coordinated clients create fake qualified views

Required controls: Server-validated watch evidence, device/network velocity rules, anti-abuse holds,
no client point award

Verification: Bot/replay farm scenario

Residual risk: TBD after implementation and testing. Status: proposed; not tested.
<PARSED TEXT FOR PAGE: 9 / 13>
TM-024 — Event replay and race [Critical]
Boundary: Engagement | STRIDE: T | Release: R1 | Owner: Engagement/Points

Attack scenario: Duplicate watch/like events award repeated points

Required controls: Idempotency keys, unique constraints, atomic transaction and dedupe windows

Verification: Parallel 100x replay test

Residual risk: TBD after implementation and testing. Status: proposed; not tested.

TM-025 — Self-engagement manipulation [High]
Boundary: Engagement | STRIDE: T | Release: R1 | Owner: Engagement

Attack scenario: Creator boosts own content with controlled accounts

Required controls: Self-view exclusion, collusion/velocity heuristics, review and reversals

Verification: Creator self-view and sockpuppet tests

Residual risk: TBD after implementation and testing. Status: proposed; not tested.

TM-026 — Unexplainable qualification decision [High]
Boundary: Engagement | STRIDE: R | Release: R1 | Owner: Engagement

Attack scenario: Cannot explain why points were awarded or withheld

Required controls: Versioned qualification rules, evidence reference, decision reason, trace ID

Verification: Reconstruct point entry from event

Residual risk: TBD after implementation and testing. Status: proposed; not tested.

TM-027 — Direct ledger write [Critical]
Boundary: Engagement | STRIDE: E | Release: R1 | Owner: Points

Attack scenario: Client or unrelated service calls points write endpoint

Required controls: Points ledger private network and service-auth; no public mutation route;
allowlisted callers

Verification: Unauthenticated and cross-service write attempts

Residual risk: TBD after implementation and testing. Status: proposed; not tested.

TM-028 — Negative balance / ledger tampering [High]
Boundary: Engagement | STRIDE: T | Release: R1 | Owner: Points

Attack scenario: Reversals and concurrent updates corrupt points balance

Required controls: Append-only entries, idempotent postings, transactional constraints, derived
balance and reconciliation

Verification: Concurrent posting and reversal test
<PARSED TEXT FOR PAGE: 10 / 13>
Residual risk: TBD after implementation and testing. Status: proposed; not tested.

TM-029 — Sensitive anti-fraud signals exposure [Medium]
Boundary: Engagement | STRIDE: I | Release: R1 | Owner: Security/Engagement

Attack scenario: API leaks device/IP fingerprints or detection thresholds

Required controls: Minimize retention, restrict analyst access, redact APIs and logs

Verification: PII access and export tests

Residual risk: TBD after implementation and testing. Status: proposed; not tested.

TM-030 — Ad event triggers points [Critical]
Boundary: Advertising | STRIDE: T | Release: R1 | Owner: Revenue/Points

Attack scenario: Ad impression or click callback creates creator reward

Required controls: Hard separation of ad telemetry and eligibility; no ad event ledger writer;
architecture test

Verification: Send ad callback; assert zero points

Residual risk: TBD after implementation and testing. Status: proposed; not tested.

TM-031 — Unreconciled ad revenue [High]
Boundary: Advertising | STRIDE: R | Release: R1 | Owner: Finance

Attack scenario: Future payouts use unverified estimated earnings

Required controls: No payouts in R1; later use collected eligible settled revenue, dual approval and
reconciliation

Verification: Negative payout boundary test

Residual risk: TBD after implementation and testing. Status: proposed; not tested.

TM-032 — Moderator mass-action abuse [High]
Boundary: Moderation | STRIDE: E | Release: R1 | Owner: Moderation

Attack scenario: Insider deletes or suppresses content beyond scope

Required controls: Least privilege, dual review for sensitive bulk actions, reason codes, audit

Verification: Privilege and bulk-action tests

Residual risk: TBD after implementation and testing. Status: proposed; not tested.

TM-033 — Reports expose victim data [High]
Boundary: Moderation | STRIDE: I | Release: R1 | Owner: Moderation

Attack scenario: Reporter/target personal data disclosed to other users

Required controls: Case-level access, redaction, purpose limitation, retention policy
<PARSED TEXT FOR PAGE: 11 / 13>
Verification: Cross-case report read test

Residual risk: TBD after implementation and testing. Status: proposed; not tested.

TM-034 — PostgreSQL exposure [Critical]
Boundary: Data/backup | STRIDE: I | Release: R1 | Owner: DBA/SRE

Attack scenario: Database accepts public connections or weak credentials

Required controls: Private DB network, per-service DB roles, TLS, least privilege, no public port

Verification: External connectivity and privilege audit

Residual risk: TBD after implementation and testing. Status: proposed; not tested.

TM-035 — Cross-service database writes [High]
Boundary: Data/backup | STRIDE: T | Release: R1 | Owner: DBA

Attack scenario: Content service modifies points tables directly

Required controls: Separate logical databases/schemas and roles; API-only ownership; migration
ownership

Verification: Try cross-service SQL writes

Residual risk: TBD after implementation and testing. Status: proposed; not tested.

TM-036 — Unencrypted backup leakage [High]
Boundary: Data/backup | STRIDE: I | Release: R1 | Owner: SRE

Attack scenario: Backup object storage exposes account or audit data

Required controls: Encrypted backups, least privilege, separate credentials, retention, restore testing

Verification: Backup access and restore drill

Residual risk: TBD after implementation and testing. Status: proposed; not tested.

TM-037 — Redis queue loss or poisoning [High]
Boundary: Data/backup | STRIDE: D | Release: R1 | Owner: Platform

Attack scenario: Jobs disappear or malicious payload executes

Required controls: Authenticated private Redis, durable queues where required, schema validation,
DLQ, retries

Verification: Worker crash/retry and invalid payload tests

Residual risk: TBD after implementation and testing. Status: proposed; not tested.

TM-038 — CI/CD credentials compromised [Critical]
Boundary: Operations | STRIDE: E | Release: R1 | Owner: DevSecOps

Attack scenario: Attacker publishes malicious image or Swarm stack
<PARSED TEXT FOR PAGE: 12 / 13>
Required controls: OIDC short-lived credentials, branch protection, two-person production approval,
secret scanning

Verification: Pipeline permission and rollback tests

Residual risk: TBD after implementation and testing. Status: proposed; not tested.

TM-039 — Logs contain PII or tokens [High]
Boundary: Operations | STRIDE: I | Release: R1 | Owner: Security/SRE

Attack scenario: Central logs leak sessions or sensitive identifiers

Required controls: Structured redaction, log access policy, retention, audit

Verification: Seed test secret; assert absent in logs

Residual risk: TBD after implementation and testing. Status: proposed; not tested.

TM-040 — Failed recovery from incident [High]
Boundary: Operations | STRIDE: D | Release: R1 | Owner: SRE

Attack scenario: Backup exists but cannot restore data and service

Required controls: Restore runbooks, periodic drills, point-in-time recovery, documented RTO/RPO

Verification: Full isolated restore drill

Residual risk: TBD after implementation and testing. Status: proposed; not tested.

TM-041 — Forged payment callback [Critical]
Boundary: Future ticketing | STRIDE: T | Release: R3/R4 | Owner: Payments

Attack scenario: Attacker marks ticket paid without settlement

Required controls: Deferred R3; signed webhooks, authoritative PSP lookup, idempotency

Verification: R3 gate: replay/forgery tests

Residual risk: TBD after implementation and testing. Status: proposed; not tested.

TM-042 — Single-user payout approval [Critical]
Boundary: Future payouts | STRIDE: E | Release: R3/R4 | Owner: Finance

Attack scenario: Insider approves own payout or changes beneficiary

Required controls: Deferred R4; segregation of duties, double-entry money ledger, dual approval

Verification: R4 gate: maker-checker tests

Residual risk: TBD after implementation and testing. Status: proposed; not tested.



Approval record
Project sponsor: __________________ Date: __________
<PARSED TEXT FOR PAGE: 13 / 13>
Security reviewer: ________________ Date: __________

Conditions / exceptions: __________________________________________