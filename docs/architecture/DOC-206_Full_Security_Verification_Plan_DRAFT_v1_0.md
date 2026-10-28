> Source: DOC-206_Full_Security_Verification_Plan_DRAFT_v1_0.docx (text export; formatting and embedded images are not included). Original status is retained.

<PARSED TEXT FOR PAGE: 1 / 12>
                                          DOC-206
           SECURITY VERIFICATION PLAN
                  Version 1.0 | Stage 2 | FULL REVIEW DRAFT | 28 October 2026

40 Release 1 security controls + 2 future-release gates. No implementation or security test results are
claimed.



1. Document control and approval
DOC-206 v1.0 | FULL DESIGN-STAGE DRAFT | 28 October 2026. Baselines: DOC-201 to DOC-205
approved; DOC-203 STRIDE register contains 42 threats. This document defines planned controls and
proof obligations, not passing test results. Project sponsor and security reviewer approval is
required. Mapping to OWASP ASVS 5.0 and MASVS is thematic until requirement-level control IDs
are verified against authoritative standards.



2. Scope and boundaries
R1: Flutter Android/iOS, Django template web, Django/DRF
identity/content/engagement/points/moderation services, Cloudflare edge, dedicated Nginx VM
outside Docker Swarm, Swarm manager/worker hosts, PostgreSQL logical service databases,
Redis/Celery, managed video provider, CI/CD and observability. R2 business reviews, R3 ticketing
and R4 financial settlement are explicitly excluded from R1 release certification, but their future
gate controls are recorded.



3. Security assurance goals
Prove identity integrity, object-level authorization, transport confidentiality, points ledger integrity,
content authorization, trusted service identity, tamper-resistant audit trails, controlled deployments,
privacy minimization, restore capability and prevention of ad-driven rewards. Never infer security
from a private overlay network alone.



4. Test environments and isolation
Use dedicated staging with representative Nginx VM and Docker Swarm topology; separate domains,
test provider credentials and synthetic users. No production secrets or live payment details in
testing. Use disposable DB snapshots, synthetic fraud events and scoped test accounts. Document
exact environment versions, deployed image digests, firewall rules, TLS settings and network
topology for reproducibility.



5. Framework and requirement traceability
Use OWASP ASVS 5.0 Level 2 as the Django/web/API target; OWASP MASVS/MASTG for Flutter;
OWASP API Security Top 10 for API abuse; NIST SSDF for secure development. The control matrix
maps security areas to framework families, not definitive clause numbers. Security lead must
<PARSED TEXT FOR PAGE: 2 / 12>
confirm exact clause IDs and add hyperlinks in the baseline before test execution. Cross-link each
SEC-ID to DOC-203 threat IDs and DOC-205 operations in the final traceability sheet.



6. Test techniques
SAST and secret scanning on every PR; SCA and image scanning on build; unit tests for authz, token
rotation, idempotency, ledger accounting; API contract fuzzing and DAST in staging; manual
adversarial tests for cross-service trust, origin bypass, moderation abuse, bot farms and provider
webhook forgery; mobile static/runtime checks; host and Swarm configuration review;
load/chaos/restore exercises. Penetration testing requires written authorization and controlled
scope.



7. Severity and acceptance gates
Critical: exploitable cluster/admin takeover, material sensitive-data breach or systemic points
manipulation. High: material unauthorized access or disruption. Medium/Low: bounded impact. R1
pilot BLOCKED by any open Critical, any untested Critical control, or failed backup restoration. High
issues require remediation or a time-limited documented risk exception approved by security lead
and sponsor. An exception cannot override an invariant prohibiting ad-generated rewards or public
ledger writes. No test result is prefilled as passed.



8. Identity and session testing
Check registration/login, enumeration, credential stuffing, privileged MFA, refresh token rotation
and revocation, browser CSRF/cookie flags, mobile secure token storage and logout. Verify cross-
user, cross-role and cross-service authorization using a deny-by-default matrix. For each endpoint
include anonymous, viewer, creator, moderator, admin and service-token negative cases.



9. Nginx and Docker Swarm testing
Confirm Nginx is on a separate VM, not a Swarm service. Verify Cloudflare-origin restriction,
TLS/certificate chain, trusted forwarding headers, request size/rate limits, Nginx hardening and
recovery. Scan public Swarm nodes for unintended service ports; validate manager port 2377
restrictions, node joining, overlay membership, service-to-service identity, non-root containers,
secrets and image provenance. Test loss of a worker and manager quorum according to deployment
topology.



10. Engagement and points abuse testing
Generate valid, partial, replayed, concurrent, self-generated, scripted and coordinated view events.
Client watch counters and timestamps are untrusted. Require server qualification, idempotency
constraints, atomic posting, explainable rule version/evidence references, append-only reversals
and reconciliation. Inject advertising impression/click callbacks and assert no points entry. R1 points
are non-cash and cannot be withdrawn or transferred.
<PARSED TEXT FOR PAGE: 3 / 12>
11. Media and moderation testing
Use malicious metadata, fake upload-complete callbacks, stale playback tokens, unpublished video
URLs and replayed provider webhooks. Confirm authoritative provider state, signature verification
and content lifecycle checks. Exercise moderator case scoping, bulk-action permissions, reason
codes, immutable audit correlation and reporter privacy.



12. Data, backup and privacy testing
Check private PostgreSQL exposure, TLS, per-service database roles, migration ownership and no
cross-service direct writes. Test Redis authentication and poisoned jobs. Verify encrypted backup
access, point-in-time recovery and restore in isolated staging. Test retention expiration, PII
minimization, audit access controls and deletion/hold workflows. RPO/RTO values must be set by
operations and signed off.



13. CI/CD and supply-chain verification
Every change: lint/type checks, tests, SAST, secret scan and dependency scan. Every image: pinned
digest, SBOM, container scan and provenance verification. Release: signed change, two-person
approval, immutable deployment manifest, rollback plan, post-deploy smoke tests and security
regression. Store artifacts with build SHA and timestamps.



14. Evidence and defect workflow
Each control record has ID, owner, environment, command/tool, version, prerequisites,
expected/actual result, execution date, tester, screenshots/logs or machine-readable output, issue
reference and retest date. Results: NOT RUN, BLOCKED, PASS, FAIL, ACCEPTED EXCEPTION (with
signer/expiry). Never use PASS without evidence. Record reproducible findings without embedding
credentials or sensitive user data.



15. Pilot gate and sign-off
Security lead confirms all 40 R1 controls executed or explicitly justified, Critical risks closed, High
residual risks accepted only under policy, restore and incident tabletop performed, privacy
retention approved, cross-document traceability complete, and no unresolved security architecture
contradictions. Sponsor signs release risk acceptance. DOC-206 design approval is separate from
operational pilot clearance.



16. Outstanding decisions
DEC-S01 exact Nginx   ↔Swarm secure connectivity; DEC-S02 cluster size/manager quorum; DEC-S03
auth/token architecture; DEC-S04 points thresholds and fraud policy; DEC-S05 privacy retention;
DEC-S06 provider/webhook contract; DEC-S07 RTO/RPO and backup architecture; DEC-S08
monitoring stack; DEC-S09 exact ASVS/MASVS control IDs; DEC-S10 performance/load limits. Owners
and due dates to be assigned in DOC-209.
<PARSED TEXT FOR PAGE: 4 / 12>
17. Governance and revision control
Changes to approved DOC-201–205 must go through ADR/change control. Any new externally
exposed API, provider integration, privilege, data category or payout behavior triggers threat-model
and test-matrix update. R2–R4 have independent security sign-offs. Version 1.0 is ready for review
but not approved until the user explicitly signs off.



18. Detailed control-by-control verification

SEC-001 — Cloudflare origin bypass
Priority: Critical | Release: R1 | Owner: SRE | Component: Nginx VM

Framework family: ASVS V5 Configuration

Acceptance criteria: Reject direct origin connections unless trusted Cloudflare origin auth + source
allowlist

Test procedure: Origin direct-connect probe, invalid client cert, firewall inspection

Evidence: Network config, probe log | Execution: NOT RUN | Residual risk: TBD

SEC-002 — Proxy-to-Swarm encryption
Priority: Critical | Release: R1 | Owner: SRE | Component: Nginx →Swarm gateway

Framework family: ASVS V5 Communication

Acceptance criteria: Mutually authenticated upstream TLS or authenticated encrypted tunnel

Test procedure: MITM/certificate rejection test

Evidence: TLS config and packet capture | Execution: NOT RUN | Residual risk: TBD

SEC-003 — Trusted proxy header chain
Priority: High | Release: R1 | Owner: Backend | Component: Nginx/Django

Framework family: ASVS V5 HTTP

Acceptance criteria: Overwrite forwarded headers; strict host/CSRF/proxy trust

Test procedure: Host/XFF/XFP spoof tests

Evidence: Integration test | Execution: NOT RUN | Residual risk: TBD

SEC-004 — Public Swarm port exposure
Priority: Critical | Release: R1 | Owner: SRE | Component: Swarm nodes

Framework family: ASVS V5 Configuration

Acceptance criteria: Only private gateway reachable from Nginx; deny public service ports

Test procedure: External and internal nmap reachability

Evidence: Firewall inventory | Execution: NOT RUN | Residual risk: TBD
<PARSED TEXT FOR PAGE: 5 / 12>
SEC-005 — Credential stuffing
Priority: High | Release: R1 | Owner: Identity | Component: Login endpoints

Framework family: ASVS V5 Authentication

Acceptance criteria: Rate limits, breached credential defense, secure password hashing

Test procedure: Distributed attempts and lockout tests

Evidence: Auth test report | Execution: NOT RUN | Residual risk: TBD

SEC-006 — Refresh token replay
Priority: High | Release: R1 | Owner: Identity | Component: Identity service

Framework family: ASVS V5 Session

Acceptance criteria: Rotate/revoke refresh credentials; secure storage

Test procedure: Replay previous refresh token

Evidence: Token test evidence | Execution: NOT RUN | Residual risk: TBD

SEC-007 — IDOR / BOLA
Priority: Critical | Release: R1 | Owner: All services | Component: Creator/content/moderation
APIs

Framework family: ASVS V5 Access Control

Acceptance criteria: Object-level authz with deny-by-default

Test procedure: Cross-user matrix with 401/403/404 semantics

Evidence: Authorization matrix | Execution: NOT RUN | Residual risk: TBD

SEC-008 — Mobile token storage
Priority: High | Release: R1 | Owner: Mobile | Component: Flutter Android/iOS

Framework family: MASVS-AUTH

Acceptance criteria: Platform-backed secure storage, no tokens in logs

Test procedure: Static analysis and device runtime inspection

Evidence: MASTG test notes | Execution: NOT RUN | Residual risk: TBD

SEC-009 — Deep links and exported components
Priority: High | Release: R1 | Owner: Mobile | Component: Flutter Android/iOS

Framework family: MASVS-PLATFORM

Acceptance criteria: Strict deep-link validation; minimal exported components

Test procedure: Malformed URI and component invocation
<PARSED TEXT FOR PAGE: 6 / 12>
Evidence: Manifest and runtime tests | Execution: NOT RUN | Residual risk: TBD

SEC-010 — Mobile TLS trust
Priority: High | Release: R1 | Owner: Mobile | Component: Flutter Android/iOS

Framework family: MASVS-NETWORK

Acceptance criteria: Reject invalid certs; no unsafe trust bypass

Test procedure: MITM with invalid/expired certificate

Evidence: Proxy test results | Execution: NOT RUN | Residual risk: TBD

SEC-011 — Release build protections
Priority: Medium | Release: R1 | Owner: Mobile | Component: Flutter build

Framework family: MASVS-RESILIENCE

Acceptance criteria: Disable debug, protect secrets, tamper detection risk-based

Test procedure: Release build analysis

Evidence: Build configuration | Execution: NOT RUN | Residual risk: TBD

SEC-012 — CSRF for Django template sessions
Priority: High | Release: R1 | Owner: Web | Component: Django web frontend

Framework family: ASVS V5 Session

Acceptance criteria: CSRF protection, secure SameSite/HttpOnly cookies

Test procedure: Cross-origin state-changing POST

Evidence: Web integration test | Execution: NOT RUN | Residual risk: TBD

SEC-013 — Stored and reflected XSS
Priority: High | Release: R1 | Owner: Web | Component: Profiles/comments/metadata

Framework family: ASVS V5 Encoding

Acceptance criteria: Contextual escaping, CSP, safe rendering

Test procedure: Payload suite across all display contexts

Evidence: DAST findings | Execution: NOT RUN | Residual risk: TBD

SEC-014 — Upload metadata validation
Priority: High | Release: R1 | Owner: Content | Component: Content service

Framework family: ASVS V5 Input

Acceptance criteria: Strict schema, MIME and size validation

Test procedure: Malformed metadata / file mismatch
<PARSED TEXT FOR PAGE: 7 / 12>
Evidence: Fuzz test results | Execution: NOT RUN | Residual risk: TBD

SEC-015 — Service-to-service impersonation
Priority: Critical | Release: R1 | Owner: Platform | Component: All internal APIs

Framework family: ASVS V5 API

Acceptance criteria: Workload identity, audience-scoped credentials, authz

Test procedure: Wrong-service token and expired cert

Evidence: Identity policy and tests | Execution: NOT RUN | Residual risk: TBD

SEC-016 — Swarm manager control plane
Priority: Critical | Release: R1 | Owner: SRE | Component: Swarm managers

Framework family: NIST SSDF PW

Acceptance criteria: Restrict 2377, protect managers, quorum and join tokens

Test procedure: Unauthorized manager join / port scan

Evidence: Swarm audit | Execution: NOT RUN | Residual risk: TBD

SEC-017 — Secrets in images and environment
Priority: Critical | Release: R1 | Owner: DevSecOps | Component: Build and runtime

Framework family: NIST SSDF PW

Acceptance criteria: Swarm secrets/external secret manager; rotate

Test procedure: Image/log/env scans and rotation drill

Evidence: Secret scan report | Execution: NOT RUN | Residual risk: TBD

SEC-018 — Image provenance
Priority: High | Release: R1 | Owner: DevSecOps | Component: CI/CD

Framework family: NIST SSDF PS

Acceptance criteria: Pin digests, SBOM, SCA, signing and approvals

Test procedure: Unsigned image deploy rejection

Evidence: Pipeline run | Execution: NOT RUN | Residual risk: TBD

SEC-019 — Container privileges and egress
Priority: High | Release: R1 | Owner: SRE | Component: All Swarm services

Framework family: ASVS V5 Configuration

Acceptance criteria: Non-root, read-only FS where feasible, no docker.sock, minimal networks

Test procedure: Container escape precondition audit
<PARSED TEXT FOR PAGE: 8 / 12>
Evidence: Compose lint and host checks | Execution: NOT RUN | Residual risk: TBD

SEC-020 — Forged video upload completion
Priority: High | Release: R1 | Owner: Content | Component: Upload lifecycle

Framework family: ASVS V5 File

Acceptance criteria: One-time intent, authoritative provider verification

Test procedure: Fake callback / nonexistent upload

Evidence: API tests | Execution: NOT RUN | Residual risk: TBD

SEC-021 — Provider webhook forgery/replay
Priority: High | Release: R1 | Owner: Content | Component: Webhook endpoint

Framework family: ASVS V5 API

Acceptance criteria: Signature, timestamp, event deduplication

Test procedure: Invalid signature and replay tests

Evidence: Webhook test log | Execution: NOT RUN | Residual risk: TBD

SEC-022 — Private video access
Priority: High | Release: R1 | Owner: Content | Component: Playback service

Framework family: ASVS V5 Access Control

Acceptance criteria: Publish-state checks and expiring signed access

Test procedure: Removed/unpublished video replay

Evidence: Access test | Execution: NOT RUN | Residual risk: TBD

SEC-023 — Synthetic view farming
Priority: Critical | Release: R1 | Owner: Engagement | Component: Qualified watch workflow

Framework family: ASVS V5 Business Logic

Acceptance criteria: Server-side qualification, velocity and collusion controls

Test procedure: Bot farm simulation and hold policy

Evidence: Fraud simulation | Execution: NOT RUN | Residual risk: TBD

SEC-024 — Duplicate points from replay
Priority: Critical | Release: R1 | Owner: Engagement/Points | Component: Engagement →points

Framework family: ASVS V5 Business Logic

Acceptance criteria: Unique idempotency, atomic posting and deduplication

Test procedure: 100 concurrent identical events
<PARSED TEXT FOR PAGE: 9 / 12>
Evidence: DB transaction tests | Execution: NOT RUN | Residual risk: TBD

SEC-025 — Unauthorized ledger posting
Priority: Critical | Release: R1 | Owner: Points | Component: Points service

Framework family: ASVS V5 Access Control

Acceptance criteria: Private write API; restricted service identity; append-only

Test procedure: Client and unrelated-service posting attempts

Evidence: Negative authorization tests | Execution: NOT RUN | Residual risk: TBD

SEC-026 — Points reversal integrity
Priority: High | Release: R1 | Owner: Points | Component: Points ledger

Framework family: ASVS V5 Business Logic

Acceptance criteria: Compensating entries and reconciliation

Test procedure: Concurrent reversal and ledger rebuild

Evidence: Ledger reconciliation report | Execution: NOT RUN | Residual risk: TBD

SEC-027 — Ad clicks/impressions award points
Priority: Critical | Release: R1 | Owner: Security/Product | Component: Ad metrics vs points

Framework family: Policy invariant

Acceptance criteria: No ad callback can generate points; no rewards for ad views

Test procedure: Ad event injection: assert zero points

Evidence: Invariant regression test | Execution: NOT RUN | Residual risk: TBD

SEC-028 — Moderator privilege escalation
Priority: High | Release: R1 | Owner: Moderation | Component: Moderation cases

Framework family: ASVS V5 Access Control

Acceptance criteria: Scoped role permissions and audit reason

Test procedure: Bulk action / cross-case access tests

Evidence: RBAC report | Execution: NOT RUN | Residual risk: TBD

SEC-029 — Missing action audit
Priority: High | Release: R1 | Owner: Security | Component: Moderation/audit

Framework family: ASVS V5 Logging

Acceptance criteria: Tamper-evident central audit events

Test procedure: Delete local logs; verify central audit
<PARSED TEXT FOR PAGE: 10 / 12>
Evidence: Audit trace | Execution: NOT RUN | Residual risk: TBD

SEC-030 — Public PostgreSQL access
Priority: Critical | Release: R1 | Owner: DBA | Component: PostgreSQL

Framework family: ASVS V5 Data Protection

Acceptance criteria: Private listeners, TLS, service-scoped DB roles

Test procedure: External port probe and role privilege audit

Evidence: DB config and psql tests | Execution: NOT RUN | Residual risk: TBD

SEC-031 — Cross-service SQL modification
Priority: High | Release: R1 | Owner: DBA | Component: Service databases

Framework family: ASVS V5 Access Control

Acceptance criteria: Separate DB ownership and credentials

Test procedure: Try content role writing points schema

Evidence: SQL privilege tests | Execution: NOT RUN | Residual risk: TBD

SEC-032 — Backup exposure and restore failure
Priority: High | Release: R1 | Owner: SRE | Component: Backup storage

Framework family: ASVS V5 Data Protection

Acceptance criteria: Encrypted backups, isolated credentials, PITR and drills

Test procedure: Restore isolated snapshot and key access test

Evidence: Restore evidence and RPO/RTO | Execution: NOT RUN | Residual risk: TBD

SEC-033 — Queue poisoning / replay
Priority: High | Release: R1 | Owner: Platform | Component: Redis/Celery

Framework family: ASVS V5 Input

Acceptance criteria: Private authenticated Redis, typed events, retries/DLQ

Test procedure: Malformed job and crash/retry

Evidence: Worker test | Execution: NOT RUN | Residual risk: TBD

SEC-034 — Excess fraud signal retention
Priority: High | Release: R1 | Owner: Privacy | Component: Fraud telemetry

Framework family: ASVS V5 Privacy

Acceptance criteria: Data minimization, retention policy, access limits

Test procedure: Retention expiry and subject request workflow
<PARSED TEXT FOR PAGE: 11 / 12>
Evidence: Privacy review | Execution: NOT RUN | Residual risk: TBD

SEC-035 — Vulnerability management
Priority: High | Release: R1 | Owner: DevSecOps | Component: Source/dependencies/images

Framework family: NIST SSDF RV

Acceptance criteria: SAST/SCA/container scans and remediation SLAs

Test procedure: Known-vuln fixture in CI

Evidence: CI report | Execution: NOT RUN | Residual risk: TBD

SEC-036 — Secrets/PII in logs
Priority: High | Release: R1 | Owner: SRE/Security | Component: Observability

Framework family: ASVS V5 Logging

Acceptance criteria: Redaction and access-controlled retention

Test procedure: Inject test token; ensure absent

Evidence: Log inspection | Execution: NOT RUN | Residual risk: TBD

SEC-037 — Incident response readiness
Priority: High | Release: R1 | Owner: Security/SRE | Component: Production operations

Framework family: NIST SSDF PO

Acceptance criteria: Runbooks, alerting, escalation and evidence preservation

Test procedure: Tabletop incident exercise

Evidence: Tabletop minutes | Execution: NOT RUN | Residual risk: TBD

SEC-038 — Failover and restore
Priority: High | Release: R1 | Owner: SRE | Component: Nginx/Swarm/Postgres

Framework family: NIST SSDF PO

Acceptance criteria: Tested recovery, explicit RTO/RPO and manager quorum

Test procedure: Kill node, restore data, measure recovery

Evidence: DR drill report | Execution: NOT RUN | Residual risk: TBD

SEC-039 — Rate limits and resource exhaustion
Priority: High | Release: R1 | Owner: SRE | Component: Nginx/API

Framework family: ASVS V5 API

Acceptance criteria: Per-route limits, upload limits, backpressure

Test procedure: Load/burst and slow client tests
<PARSED TEXT FOR PAGE: 12 / 12>
Evidence: Load test report | Execution: NOT RUN | Residual risk: TBD

SEC-040 — Unapproved production changes
Priority: Critical | Release: R1 | Owner: DevSecOps | Component: CI/CD

Framework family: NIST SSDF PS

Acceptance criteria: Branch protection, signed artifacts, 2-person deploy approval

Test procedure: Attempt deploy without approval

Evidence: Pipeline gate logs | Execution: NOT RUN | Residual risk: TBD

SEC-041 — Forged ticket payment confirmation
Priority: Critical | Release: R3 | Owner: Payments | Component: Ticketing

Framework family: Payment controls

Acceptance criteria: Signed PSP callbacks, settlement lookup, idempotency

Test procedure: Forgery/replay test before R3

Evidence: Future gate | Execution: NOT RUN | Residual risk: TBD

SEC-042 — Unauthorized payout
Priority: Critical | Release: R4 | Owner: Finance | Component: Payouts

Framework family: Financial controls

Acceptance criteria: Double-entry money ledger, dual approval, reconciliation

Test procedure: Maker-checker abuse tests before R4

Evidence: Future gate | Execution: NOT RUN | Residual risk: TBD



19. Formal design review
Sponsor approval: _______________________ Date: __________

Security reviewer: ______________________ Date: __________

Pilot readiness remains separately gated on executed tests and documented evidence.