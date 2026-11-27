# KoloVibe full application engineering and delivery mandate (27 November 2026)

**Status: in force.** Mark Gbalazeh (@Markcino), the accountable owner, sent this mandate on 27 November 2026 at 10:59 UTC. It is recorded below word for word, with only the formatting changed. Where it differs from an older instruction, it governs. Older instructions and decisions are kept as dated history and are not deleted. [`PHASE_EXECUTION_TRACKER.md`](PHASE_EXECUTION_TRACKER.md) shows where execution stands and how the mandate fits with earlier work. Decisions A to J stay in force, as recorded in [Owner decisions A to J](../planning/Owner_Decisions_A-J_2026-11-25.md).

This record approves nothing that the mandate itself does not approve. As section 8 says, development approval does not authorize live payments, advertising activation, destructive data changes or production publication.

---

## 1. Your role

Act as a coordinated team of:

* Principal software architect.
* Senior Django/Python backend engineer.
* Senior Flutter/Dart mobile engineer.
* Senior PostgreSQL database architect.
* Distributed systems and RabbitMQ engineer.
* Application security and privacy engineer.
* AWS, Docker Swarm and DevSecOps engineer.
* Senior UI/UX and Figma designer.
* Financial systems and payment integration engineer.
* Google Play and Apple App Store release engineer.
* QA automation and software acceptance engineer.
* Technical documentation and configuration management specialist.

Repository: https://github.com/Markcino/KoloVibe.git

Work directly with the existing repository, available development tools, GitHub, Figma, local development environment and authorized staging infrastructure.

## 2. New authoritative product direction

KoloVibe is NO LONGER an MVP development project.

We are developing a complete, fully functional, secure, maintainable and production-ready application.

The previous MVP, restricted pilot and deferred-release boundaries must not be used to justify leaving approved full-product functionality incomplete.

Preserve historical decisions for audit purposes, but reconcile obsolete development restrictions with the current product direction.

The full application includes:

* Identity and account management.
* Creator management.
* Video creation, upload, processing and playback.
* Content discovery and social engagement.
* Non-cash points and qualified views.
* Content moderation, reporting and appeals.
* Audit and accountability.
* Business discovery and management.
* Events and ticketing.
* Advertising and direct sponsorship.
* Google mobile advertising integration.
* Finance and creator monetization.
* Payment processing, reconciliation and payouts.
* Notifications.
* Privacy and legal compliance.
* Flutter Android and iOS applications.
* Administrator and moderator web console.
* Operational monitoring, security and disaster recovery.

Do not assume that additional functionality, such as live streaming, is approved merely because we are no longer developing an MVP. Identify unresolved product scope and recommend a decision where necessary.

## 3. Architecture constraints

Preserve the approved architecture unless evidence demonstrates that a reviewed change is necessary.

* Django/Python backend.
* Flutter/Dart mobile application.
* PostgreSQL.
* RabbitMQ, not Redis.
* Cloudflare R2 and FFmpeg for video processing.
* Docker Swarm.
* Host-installed Nginx on the Swarm manager.
* Cloudflare ingress.
* Secure service-to-service authentication.
* Separate service data ownership.
* Finance as the single authoritative monetary ledger.
* Points remain non-cash.
* No duplicated monetary ledger in Events, Advertising or Points.

Expected application services:

1. Gateway.
2. Identity.
3. Creators.
4. Content.
5. Engagement.
6. Points.
7. Moderation.
8. Audit.
9. Business.
10. Finance.
11. Events.
12. Advertising.

Validate these boundaries against the latest approved architecture. Do not introduce additional microservices without justification.

Ordinary users, creators, business owners, business staff, organizers and advertisers use Flutter.

Only administrators and moderators use the privileged web console.

There must be no ordinary-user public web application. Necessary approved legal, account-deletion and application-link resources may remain publicly accessible.

## 4. Infrastructure access

Use the available authorized local SSH configuration:

* Manager: `ssh swarm-manager`
* Worker: `ssh swarm-worker`

Verify the actual hostnames, topology, resources, deployed versions, database configuration and service state before executing changes.

Never assume the environment still matches historical documentation.

## 5. Non-negotiable engineering principles

Apply:

* DRY.
* SOLID.
* KISS.
* Separation of concerns.
* Secure by design.
* Privacy by design.
* Least privilege.
* Defense in depth.
* Fail-closed authorization.
* Idempotent operations.
* Explicit service ownership.
* Contract-first integration.
* Evidence-based engineering.
* Reusable Flutter components.
* Backward-compatible migrations where feasible.
* Reproducible builds.
* Immutable deployment image digests.

Do not duplicate business logic, API contracts, security controls, design components, configuration or financial accounting.

## 6. Evidence-first execution

Before modifying anything:

* Inspect the latest repository state.
* Read applicable approved requirements and architecture documents.
* Inspect open and closed GitHub issues and pull requests.
* Review CI/CD evidence.
* Inspect existing implementations and tests.
* Verify actual runtime behavior where access is available.
* Distinguish historical findings from current findings.

Never guess.

Never mark a feature complete because a screen exists, an endpoint returns HTTP 200, a container is running or CI passes.

Trace every feature through its complete implementation chain:

Requirement → Architecture → Database → Backend → API → Gateway → Authorization → Flutter/Web → Integration → Tests → Deployment → Acceptance evidence.

## 7. Mandatory issue tracking

Use GitHub Issues as the authoritative work and defect tracker.

For every unresolved item, record:

* Unique issue identifier.
* Requirement reference.
* Affected service and application.
* Severity and priority.
* Actual behavior.
* Expected behavior.
* Reproduction evidence.
* Root cause.
* Implementation plan.
* Dependencies.
* Acceptance criteria.
* Test evidence.
* Current status.

Search for existing issues before creating new ones.

Do not close issues without evidence that their acceptance criteria have passed.

## 8. Approval management

Do not repeatedly request approval for decisions already approved.

Reconcile existing Decisions A–J and all subsequent owner decisions.

When a genuine decision is missing, provide:

* Decision ID.
* Exact blocking requirement.
* Why the decision is necessary.
* Available options.
* Recommended option.
* Security implications.
* Financial implications.
* Operational implications.
* Consequences of delaying the decision.
* Exact approval wording.

Continue independent work within the current phase while awaiting the decision.

Do not invent legal policies, revenue percentages, financial thresholds, provider credentials, regulatory approvals or infrastructure spending authorization.

Development approval does not automatically authorize live payments, advertising activation, destructive data changes or production publication.

## 9. Single source of truth

Establish an authoritative documentation index and clearly identify the canonical source for each subject.

Reconcile:

* PRD and SRS.
* Architecture documents and ADRs.
* OpenAPI contracts.
* Database schemas and ERDs.
* RBAC and authorization matrices.
* Feature traceability.
* Figma screen inventory.
* Deployment and operations documentation.
* Security verification.
* Testing and acceptance.
* GitHub issue tracking.
* Owner decisions.

Archive superseded documents without destroying historical evidence.

Do not maintain multiple conflicting versions of the same active requirement.

## 10. Mandatory phase gates

Every phase must follow:

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

A phase is PASS only when all mandatory exit criteria have been satisfied with evidence.

A phase is BLOCKED when required access, approval, implementation or evidence is missing.

A phase is FAIL when acceptance tests fail.

Never treat BLOCKED, NOT RUN, SKIPPED or PARTIAL as PASS.

Do not weaken, delete or bypass tests to achieve a passing result.

Do not proceed to the next phase while the current phase has unresolved mandatory requirements.

## 11. Required phase completion report

At the end of every phase, report:

* Phase name and number.
* Starting repository commit.
* Final repository commit.
* Requirements completed.
* Files changed.
* GitHub issues created, updated and closed.
* Pull requests and CI results.
* Database migrations.
* Infrastructure changes.
* Tests executed.
* PASS, FAIL, BLOCKED and NOT RUN counts.
* Evidence locations.
* Security findings.
* Remaining defects.
* Decisions required.
* Rollback instructions.
* Final gate verdict.
* Whether the next phase is authorized to begin.

Do not claim work was performed when it was not.

Store the master mandate and phase execution rules in the appropriate canonical repository documentation and reference them from the existing CLAUDE.md or equivalent project instruction file.

Begin by acknowledging these instructions, locating the existing governance files and establishing the phase execution tracker.

Do not begin Phase 1 until instructed.
