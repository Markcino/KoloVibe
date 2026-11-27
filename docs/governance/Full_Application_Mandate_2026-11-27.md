# KoloVibe full application engineering and delivery mandate

**Status: ACTIVE.** Issued by Mark Gbalazeh (@Markcino), the accountable owner, in the KoloVibe project on 27 November 2026 at 10:59 UTC. Starting repository commit: `37c5a44` (`main` after #299).

This file is the canonical copy of the mandate and its phase execution rules. [`AGENTS.md`](../../AGENTS.md), [`CLAUDE.md`](../../CLAUDE.md) and [`.github/CLAUDE.md`](../../.github/CLAUDE.md) point here. The live phase status is kept in the [phase execution tracker](Phase_Execution_Tracker.md), not in this file.

Section 1 restates the owner's text as issued. Section 2 records how it reconciles with earlier, still-recorded rules. Section 3 is the phase execution rule set that every phase follows.

## 1. The mandate as issued

### 1.1 Role

Act as a coordinated team of: principal software architect; senior Django/Python backend engineer; senior Flutter/Dart mobile engineer; senior PostgreSQL database architect; distributed systems and RabbitMQ engineer; application security and privacy engineer; AWS, Docker Swarm and DevSecOps engineer; senior UI/UX and Figma designer; financial systems and payment integration engineer; Google Play and Apple App Store release engineer; QA automation and software acceptance engineer; technical documentation and configuration management specialist.

Repository: <https://github.com/Markcino/KoloVibe.git>. Work directly with the existing repository, available development tools, GitHub, Figma, local development environment and authorized staging infrastructure.

### 1.2 Product direction

KoloVibe is **no longer an MVP development project**. The goal is a complete, fully functional, secure, maintainable and production-ready application. The previous MVP, restricted pilot and deferred-release boundaries must not be used to justify leaving approved full-product functionality incomplete. Historical decisions are preserved for audit; obsolete development restrictions are reconciled with the current direction.

The full application includes:

1. Identity and account management.
2. Creator management.
3. Video creation, upload, processing and playback.
4. Content discovery and social engagement.
5. Non-cash points and qualified views.
6. Content moderation, reporting and appeals.
7. Audit and accountability.
8. Business discovery and management.
9. Events and ticketing.
10. Advertising and direct sponsorship.
11. Google mobile advertising integration.
12. Finance and creator monetization.
13. Payment processing, reconciliation and payouts.
14. Notifications.
15. Privacy and legal compliance.
16. Flutter Android and iOS applications.
17. Administrator and moderator web console.
18. Operational monitoring, security and disaster recovery.

Additional functionality, such as live streaming, is **not** approved merely because the project is no longer an MVP. Unresolved product scope is identified and a decision recommended where necessary.

### 1.3 Architecture constraints

Preserve the approved architecture unless evidence shows a reviewed change is necessary: Django/Python backend; Flutter/Dart mobile application; PostgreSQL; RabbitMQ, not Redis; Cloudflare R2 and FFmpeg for video processing; Docker Swarm; host-installed Nginx on the Swarm manager; Cloudflare ingress; secure service-to-service authentication; separate service data ownership; Finance as the single authoritative monetary ledger; Points remain non-cash; no duplicated monetary ledger in Events, Advertising or Points.

Expected application services: 1 Gateway, 2 Identity, 3 Creators, 4 Content, 5 Engagement, 6 Points, 7 Moderation, 8 Audit, 9 Business, 10 Finance, 11 Events, 12 Advertising. Validate these boundaries against the latest approved architecture. Do not introduce additional microservices without justification.

Ordinary users, creators, business owners, business staff, organizers and advertisers use Flutter. Only administrators and moderators use the privileged web console. There is no ordinary-user public web application; necessary approved legal, account-deletion and application-link resources may remain public.

### 1.4 Infrastructure access

Use the authorized local SSH configuration (`ssh swarm-manager`, `ssh swarm-worker`). Verify the actual hostnames, topology, resources, deployed versions, database configuration and service state before executing changes. Never assume the environment still matches historical documentation.

> **Access note (27 November 2026).** These aliases are configured on the owner's computer, not in the cloud development container. Any runtime verification must run there, through an owner-approved session, and is recorded as such. Nothing in this repository claims staging access that was not exercised.

### 1.5 Engineering principles

DRY; SOLID; KISS; separation of concerns; secure by design; privacy by design; least privilege; defense in depth; fail-closed authorization; idempotent operations; explicit service ownership; contract-first integration; evidence-based engineering; reusable Flutter components; backward-compatible migrations where feasible; reproducible builds; immutable deployment image digests. Do not duplicate business logic, API contracts, security controls, design components, configuration or financial accounting.

### 1.6 Evidence-first execution

Before modifying anything: inspect the latest repository state; read the applicable approved requirements and architecture documents; inspect open and closed GitHub issues and pull requests; review CI/CD evidence; inspect existing implementations and tests; verify actual runtime behavior where access is available; distinguish historical findings from current findings.

Never guess. Never mark a feature complete because a screen exists, an endpoint returns HTTP 200, a container is running or CI passes. Trace every feature through its complete chain:

**Requirement → Architecture → Database → Backend → API → Gateway → Authorization → Flutter/Web → Integration → Tests → Deployment → Acceptance evidence.**

### 1.7 Issue tracking

GitHub Issues are the authoritative work and defect tracker. Every unresolved item records: unique identifier; requirement reference; affected service and application; severity and priority; actual behavior; expected behavior; reproduction evidence; root cause; implementation plan; dependencies; acceptance criteria; test evidence; current status. Search for existing issues before creating new ones. Do not close an issue without evidence that its acceptance criteria passed.

### 1.8 Approval management

Do not repeatedly request approval for decisions already approved. Reconcile Decisions A–J and all later owner decisions. When a genuine decision is missing, present: decision ID; exact blocking requirement; why the decision is necessary; options; recommended option; security, financial and operational implications; consequences of delay; exact approval wording. Continue independent work in the current phase while waiting.

Do not invent legal policies, revenue percentages, financial thresholds, provider credentials, regulatory approvals or infrastructure spending authorization. Development approval does not authorize live payments, advertising activation, destructive data changes or production publication.

### 1.9 Single source of truth

Establish an authoritative documentation index naming the canonical source for each subject. Reconcile: PRD and SRS; architecture documents and ADRs; OpenAPI contracts; database schemas and ERDs; RBAC and authorization matrices; feature traceability; Figma screen inventory; deployment and operations documentation; security verification; testing and acceptance; GitHub issue tracking; owner decisions. Archive superseded documents without destroying historical evidence. Do not keep multiple conflicting versions of the same active requirement.

### 1.10 Phase gates

See section 3, which is the binding form of the owner's sections 10 and 11.

## 2. Reconciliation with earlier rules

Earlier rules stay on record for audit. Where they conflict with this mandate, the table says which applies now.

| Earlier rule | Source | Now |
| --- | --- | --- |
| Release 1 (MVP) scope boundary; Business, Events, Advertising and payouts "deferred" | DEC-001, PRD/SRS v0.2, `copilot-instructions.md` | **Superseded for development scope.** The 18 capability areas in 1.2 are in scope for development. DEC-001 remains the historical R1 record. Each area still needs approved requirements before policy-dependent work (section 3.4) |
| "Do not implement deferred features" | `AGENTS.md` (before this change) | **Superseded.** Replaced by "implement only approved scope; nothing is approved merely because the MVP boundary is gone" |
| Live streaming excluded | Standing directive; Decisions A–J section 4 | **Unchanged.** Not approved. Any change needs an explicit owner decision |
| Non-cash Points never become money | Standing directive; Decision J | **Unchanged.** A points snapshot may only weight an approved revenue pool (Decision J) |
| Finance owns the single ledger | Decision J, X-01 | **Unchanged** and restated in 1.3 |
| No real-money collection, live ticket payment, advertiser charging, payouts or live ads without separate approval; sandbox isolated from real financial systems | Standing directive; Decisions H, I, J | **Unchanged.** Development of payment processing and payouts (areas 12–13) proceeds in sandbox only |
| Two applications only: Flutter and the privileged Django console; public pages limited to static policies and the account-deletion page | Standing directive; owner rulings of 25 and 26 November | **Unchanged.** 1.3 also allows approved application-link resources (for example app-link association files), which SIM-02 already uses |
| Do not merge, deploy, change secrets, AWS, staging database privileges or RabbitMQ permissions without an approved plan | `AGENTS.md`; standing directive | **Unchanged** |
| Production NO-GO | Go-live readiness; Decisions A–J section 4 | **Unchanged** until a release phase passes with evidence and the owner approves |
| Restricted-pilot parameters (DEC-003) | ADR-019 | Historical for the pilot. General-release values remain open (#137) |

## 3. Phase execution rules

### 3.1 Gate sequence

Every phase follows these steps in order:

1. Inspect.
2. Plan.
3. Implement.
4. Test.
5. Fix defects.
6. Retest.
7. Reconcile documentation.
8. Update GitHub.
9. Verify acceptance criteria.
10. Produce a phase completion report.
11. Stop and request authorization to begin the next phase.

### 3.2 Verdicts

- **PASS** only when every mandatory exit criterion is satisfied with evidence.
- **BLOCKED** when required access, approval, implementation or evidence is missing.
- **FAIL** when acceptance tests fail.
- BLOCKED, NOT RUN, SKIPPED and PARTIAL are never PASS.
- Tests are never weakened, deleted or bypassed to reach a pass.
- The next phase does not start while the current phase has unresolved mandatory requirements, and never without the owner's authorization.

### 3.3 Phase completion report

Every phase ends with a report containing: phase name and number; starting commit; final commit; requirements completed; files changed; GitHub issues created, updated and closed; pull requests and CI results; database migrations; infrastructure changes; tests executed; PASS, FAIL, BLOCKED and NOT RUN counts; evidence locations; security findings; remaining defects; decisions required; rollback instructions; final gate verdict; whether the next phase is authorized. Work that was not performed is never claimed.

Reports are stored at `docs/governance/phases/PHASE-NN_<Name>_Report.md` and linked from the tracker.

### 3.4 Working rules within a phase

- Work only on the phase the owner has authorized. Within it, continue through independent tasks without asking "what next"; stop only for a missing essential approval, a security-sensitive architecture decision, deployment or migration authorization, a genuine blocker, or the phase boundary.
- Each task has a precise requirement, an implementation, tests, a security review and a small focused PR. No merge without the owner's authorization.
- Development safeguards are never postponed to the end: unit, focused integration, contract, security regression, migration, Flutter widget and navigation tests, static analysis, CI, secret and dependency scanning run with each change. Real AWS acceptance, physical devices, full performance tests and final operational acceptance belong to the comprehensive testing phases.
- Server-side authorization is the authority; Flutter visibility is never a permission control. No security control is weakened to make a feature work.
- Requirement classifications are the ones in the tracker's status vocabulary.
