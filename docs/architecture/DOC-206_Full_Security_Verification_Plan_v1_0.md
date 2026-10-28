# DOC-206 — Full Security Verification Plan
**Version 1.0 — FULL REVIEW DRAFT — 28 October 2026**
**Status:** Not approved; no tests executed or passed.

## 1. Document control and approval
DOC-206 v1.0 | FULL DESIGN-STAGE DRAFT | 28 October 2026. Baselines: DOC-201 to DOC-205 approved; DOC-203 STRIDE register contains 42 threats. This document defines planned controls and proof obligations, not passing test results. Project sponsor and security reviewer approval is required. Mapping to OWASP ASVS 5.0 and MASVS is thematic until requirement-level control IDs are verified against authoritative standards.

## 2. Scope and boundaries
R1: Flutter Android/iOS, Django template web, Django/DRF identity/content/engagement/points/moderation services, Cloudflare edge, dedicated Nginx VM outside Docker Swarm, Swarm manager/worker hosts, PostgreSQL logical service databases, Redis/Celery, managed video provider, CI/CD and observability. R2 business reviews, R3 ticketing and R4 financial settlement are explicitly excluded from R1 release certification, but their future gate controls are recorded.

## 3. Security assurance goals
Prove identity integrity, object-level authorization, transport confidentiality, points ledger integrity, content authorization, trusted service identity, tamper-resistant audit trails, controlled deployments, privacy minimization, restore capability and prevention of ad-driven rewards. Never infer security from a private overlay network alone.

## 4. Test environments and isolation
Use dedicated staging with representative Nginx VM and Docker Swarm topology; separate domains, test provider credentials and synthetic users. No production secrets or live payment details in testing. Use disposable DB snapshots, synthetic fraud events and scoped test accounts. Document exact environment versions, deployed image digests, firewall rules, TLS settings and network topology for reproducibility.

## 5. Framework and requirement traceability
Use OWASP ASVS 5.0 Level 2 as the Django/web/API target; OWASP MASVS/MASTG for Flutter; OWASP API Security Top 10 for API abuse; NIST SSDF for secure development. The control matrix maps security areas to framework families, not definitive clause numbers. Security lead must confirm exact clause IDs and add hyperlinks in the baseline before test execution. Cross-link each SEC-ID to DOC-203 threat IDs and DOC-205 operations in the final traceability sheet.

## 6. Test techniques
SAST and secret scanning on every PR; SCA and image scanning on build; unit tests for authz, token rotation, idempotency, ledger accounting; API contract fuzzing and DAST in staging; manual adversarial tests for cross-service trust, origin bypass, moderation abuse, bot farms and provider webhook forgery; mobile static/runtime checks; host and Swarm configuration review; load/chaos/restore exercises. Penetration testing requires written authorization and controlled scope.

## 7. Severity and acceptance gates
Critical: exploitable cluster/admin takeover, material sensitive-data breach or systemic points manipulation. High: material unauthorized access or disruption. Medium/Low: bounded impact. R1 pilot BLOCKED by any open Critical, any untested Critical control, or failed backup restoration. High issues require remediation or a time-limited documented risk exception approved by security lead and sponsor. An exception cannot override an invariant prohibiting ad-generated rewards or public ledger writes. No test result is prefilled as passed.

## 8. Identity and session testing
Check registration/login, enumeration, credential stuffing, privileged MFA, refresh token rotation and revocation, browser CSRF/cookie flags, mobile secure token storage and logout. Verify cross-user, cross-role and cross-service authorization using a deny-by-default matrix. For each endpoint include anonymous, viewer, creator, moderator, admin and service-token negative cases.

## 9. Nginx and Docker Swarm testing
Confirm Nginx is on a separate VM, not a Swarm service. Verify Cloudflare-origin restriction, TLS/certificate chain, trusted forwarding headers, request size/rate limits, Nginx hardening and recovery. Scan public Swarm nodes for unintended service ports; validate manager port 2377 restrictions, node joining, overlay membership, service-to-service identity, non-root containers, secrets and image provenance. Test loss of a worker and manager quorum according to deployment topology.

## 10. Engagement and points abuse testing
Generate valid, partial, replayed, concurrent, self-generated, scripted and coordinated view events. Client watch counters and timestamps are untrusted. Require server qualification, idempotency constraints, atomic posting, explainable rule version/evidence references, append-only reversals and reconciliation. Inject advertising impression/click callbacks and assert no points entry. R1 points are non-cash and cannot be withdrawn or transferred.

## 11. Media and moderation testing
Use malicious metadata, fake upload-complete callbacks, stale playback tokens, unpublished video URLs and replayed provider webhooks. Confirm authoritative provider state, signature verification and content lifecycle checks. Exercise moderator case scoping, bulk-action permissions, reason codes, immutable audit correlation and reporter privacy.

## 12. Data, backup and privacy testing
Check private PostgreSQL exposure, TLS, per-service database roles, migration ownership and no cross-service direct writes. Test Redis authentication and poisoned jobs. Verify encrypted backup access, point-in-time recovery and restore in isolated staging. Test retention expiration, PII minimization, audit access controls and deletion/hold workflows. RPO/RTO values must be set by operations and signed off.

## 13. CI/CD and supply-chain verification
Every change: lint/type checks, tests, SAST, secret scan and dependency scan. Every image: pinned digest, SBOM, container scan and provenance verification. Release: signed change, two-person approval, immutable deployment manifest, rollback plan, post-deploy smoke tests and security regression. Store artifacts with build SHA and timestamps.

## 14. Evidence and defect workflow
Each control record has ID, owner, environment, command/tool, version, prerequisites, expected/actual result, execution date, tester, screenshots/logs or machine-readable output, issue reference and retest date. Results: NOT RUN, BLOCKED, PASS, FAIL, ACCEPTED EXCEPTION (with signer/expiry). Never use PASS without evidence. Record reproducible findings without embedding credentials or sensitive user data.

## 15. Pilot gate and sign-off
Security lead confirms all 40 R1 controls executed or explicitly justified, Critical risks closed, High residual risks accepted only under policy, restore and incident tabletop performed, privacy retention approved, cross-document traceability complete, and no unresolved security architecture contradictions. Sponsor signs release risk acceptance. DOC-206 design approval is separate from operational pilot clearance.

## 16. Outstanding decisions
DEC-S01 exact Nginx↔Swarm secure connectivity; DEC-S02 cluster size/manager quorum; DEC-S03 auth/token architecture; DEC-S04 points thresholds and fraud policy; DEC-S05 privacy retention; DEC-S06 provider/webhook contract; DEC-S07 RTO/RPO and backup architecture; DEC-S08 monitoring stack; DEC-S09 exact ASVS/MASVS control IDs; DEC-S10 performance/load limits. Owners and due dates to be assigned in DOC-209.

## 17. Governance and revision control
Changes to approved DOC-201–205 must go through ADR/change control. Any new externally exposed API, provider integration, privilege, data category or payout behavior triggers threat-model and test-matrix update. R2–R4 have independent security sign-offs. Version 1.0 is ready for review but not approved until the user explicitly signs off.

## Control register overview
42 mapped controls; R1: 40; R3/R4: 2. See CSV for test-by-test evidence requirements.

## Execution checklist
- [ ] **SEC-001** (Critical, R1) — Cloudflare origin bypass: Origin direct-connect probe, invalid client cert, firewall inspection. **Expected:** Reject direct origin connections unless trusted Cloudflare origin auth + source allowlist.
- [ ] **SEC-002** (Critical, R1) — Proxy-to-Swarm encryption: MITM/certificate rejection test. **Expected:** Mutually authenticated upstream TLS or authenticated encrypted tunnel.
- [ ] **SEC-003** (High, R1) — Trusted proxy header chain: Host/XFF/XFP spoof tests. **Expected:** Overwrite forwarded headers; strict host/CSRF/proxy trust.
- [ ] **SEC-004** (Critical, R1) — Public Swarm port exposure: External and internal nmap reachability. **Expected:** Only private gateway reachable from Nginx; deny public service ports.
- [ ] **SEC-005** (High, R1) — Credential stuffing: Distributed attempts and lockout tests. **Expected:** Rate limits, breached credential defense, secure password hashing.
- [ ] **SEC-006** (High, R1) — Refresh token replay: Replay previous refresh token. **Expected:** Rotate/revoke refresh credentials; secure storage.
- [ ] **SEC-007** (Critical, R1) — IDOR / BOLA: Cross-user matrix with 401/403/404 semantics. **Expected:** Object-level authz with deny-by-default.
- [ ] **SEC-008** (High, R1) — Mobile token storage: Static analysis and device runtime inspection. **Expected:** Platform-backed secure storage, no tokens in logs.
- [ ] **SEC-009** (High, R1) — Deep links and exported components: Malformed URI and component invocation. **Expected:** Strict deep-link validation; minimal exported components.
- [ ] **SEC-010** (High, R1) — Mobile TLS trust: MITM with invalid/expired certificate. **Expected:** Reject invalid certs; no unsafe trust bypass.
- [ ] **SEC-011** (Medium, R1) — Release build protections: Release build analysis. **Expected:** Disable debug, protect secrets, tamper detection risk-based.
- [ ] **SEC-012** (High, R1) — CSRF for Django template sessions: Cross-origin state-changing POST. **Expected:** CSRF protection, secure SameSite/HttpOnly cookies.
- [ ] **SEC-013** (High, R1) — Stored and reflected XSS: Payload suite across all display contexts. **Expected:** Contextual escaping, CSP, safe rendering.
- [ ] **SEC-014** (High, R1) — Upload metadata validation: Malformed metadata / file mismatch. **Expected:** Strict schema, MIME and size validation.
- [ ] **SEC-015** (Critical, R1) — Service-to-service impersonation: Wrong-service token and expired cert. **Expected:** Workload identity, audience-scoped credentials, authz.
- [ ] **SEC-016** (Critical, R1) — Swarm manager control plane: Unauthorized manager join / port scan. **Expected:** Restrict 2377, protect managers, quorum and join tokens.
- [ ] **SEC-017** (Critical, R1) — Secrets in images and environment: Image/log/env scans and rotation drill. **Expected:** Swarm secrets/external secret manager; rotate.
- [ ] **SEC-018** (High, R1) — Image provenance: Unsigned image deploy rejection. **Expected:** Pin digests, SBOM, SCA, signing and approvals.
- [ ] **SEC-019** (High, R1) — Container privileges and egress: Container escape precondition audit. **Expected:** Non-root, read-only FS where feasible, no docker.sock, minimal networks.
- [ ] **SEC-020** (High, R1) — Forged video upload completion: Fake callback / nonexistent upload. **Expected:** One-time intent, authoritative provider verification.
- [ ] **SEC-021** (High, R1) — Provider webhook forgery/replay: Invalid signature and replay tests. **Expected:** Signature, timestamp, event deduplication.
- [ ] **SEC-022** (High, R1) — Private video access: Removed/unpublished video replay. **Expected:** Publish-state checks and expiring signed access.
- [ ] **SEC-023** (Critical, R1) — Synthetic view farming: Bot farm simulation and hold policy. **Expected:** Server-side qualification, velocity and collusion controls.
- [ ] **SEC-024** (Critical, R1) — Duplicate points from replay: 100 concurrent identical events. **Expected:** Unique idempotency, atomic posting and deduplication.
- [ ] **SEC-025** (Critical, R1) — Unauthorized ledger posting: Client and unrelated-service posting attempts. **Expected:** Private write API; restricted service identity; append-only.
- [ ] **SEC-026** (High, R1) — Points reversal integrity: Concurrent reversal and ledger rebuild. **Expected:** Compensating entries and reconciliation.
- [ ] **SEC-027** (Critical, R1) — Ad clicks/impressions award points: Ad event injection: assert zero points. **Expected:** No ad callback can generate points; no rewards for ad views.
- [ ] **SEC-028** (High, R1) — Moderator privilege escalation: Bulk action / cross-case access tests. **Expected:** Scoped role permissions and audit reason.
- [ ] **SEC-029** (High, R1) — Missing action audit: Delete local logs; verify central audit. **Expected:** Tamper-evident central audit events.
- [ ] **SEC-030** (Critical, R1) — Public PostgreSQL access: External port probe and role privilege audit. **Expected:** Private listeners, TLS, service-scoped DB roles.
- [ ] **SEC-031** (High, R1) — Cross-service SQL modification: Try content role writing points schema. **Expected:** Separate DB ownership and credentials.
- [ ] **SEC-032** (High, R1) — Backup exposure and restore failure: Restore isolated snapshot and key access test. **Expected:** Encrypted backups, isolated credentials, PITR and drills.
- [ ] **SEC-033** (High, R1) — Queue poisoning / replay: Malformed job and crash/retry. **Expected:** Private authenticated Redis, typed events, retries/DLQ.
- [ ] **SEC-034** (High, R1) — Excess fraud signal retention: Retention expiry and subject request workflow. **Expected:** Data minimization, retention policy, access limits.
- [ ] **SEC-035** (High, R1) — Vulnerability management: Known-vuln fixture in CI. **Expected:** SAST/SCA/container scans and remediation SLAs.
- [ ] **SEC-036** (High, R1) — Secrets/PII in logs: Inject test token; ensure absent. **Expected:** Redaction and access-controlled retention.
- [ ] **SEC-037** (High, R1) — Incident response readiness: Tabletop incident exercise. **Expected:** Runbooks, alerting, escalation and evidence preservation.
- [ ] **SEC-038** (High, R1) — Failover and restore: Kill node, restore data, measure recovery. **Expected:** Tested recovery, explicit RTO/RPO and manager quorum.
- [ ] **SEC-039** (High, R1) — Rate limits and resource exhaustion: Load/burst and slow client tests. **Expected:** Per-route limits, upload limits, backpressure.
- [ ] **SEC-040** (Critical, R1) — Unapproved production changes: Attempt deploy without approval. **Expected:** Branch protection, signed artifacts, 2-person deploy approval.
- [ ] **SEC-041** (Critical, R3) — Forged ticket payment confirmation: Forgery/replay test before R3. **Expected:** Signed PSP callbacks, settlement lookup, idempotency.
- [ ] **SEC-042** (Critical, R4) — Unauthorized payout: Maker-checker abuse tests before R4. **Expected:** Double-entry money ledger, dual approval, reconciliation.

## Approval signatures
Project sponsor: _____________________  Date: __________
Security lead: _______________________  Date: __________
Approved exceptions / conditions: __________________________