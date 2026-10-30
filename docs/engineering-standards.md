# Engineering standards

KoloVibe is developed by Mark Allen Gbalazeh (@Markcino), the sole developer, with AI assistance. The mobile application is backed by independently owned services. Mark records owner self-review against functionality, security and release-readiness criteria; AI assistance does not constitute independent security assurance.

## Pull requests and code ownership

- Changes to application behavior and services require a pull request and documented owner self-review.
- Protect the default branch and require relevant CI checks before merging.
- Record architecture-impacting decisions and review changes to API contracts.
- Keep credentials and personal data out of commits, issue descriptions and logs.

## Application delivery requirements

- Reproducible builds and pinned development toolchains.
- Automated checks for Dart, Python and API contracts.
- Database ownership enforced by separate database roles.
- Authenticated and authorized service communication.
- Documented migrations, rollback and backup restoration.
- Redacted structured logs, trace IDs and operational alerts.
- Security scanning of dependencies, images and source code.
- Access-controlled environment configuration and deployment credentials.

## Release review

The following are engineering release requirements, **not assertions that they have passed**:

- [ ] Flutter native builds, static analysis, widget and device checks.
- [ ] Independent service builds and contract verification.
- [ ] Database permission isolation and migration verification.
- [ ] Service authentication and least-privilege authorization.
- [ ] Idempotent event delivery and audited non-cash points ledger.
- [ ] Protected edge-to-service networking and safe proxy headers.
- [ ] Observability, backup restoration and rollback exercises.
- [ ] Security assessment and authorized deployment approval.

There is no production deployment or security certification implied by the repository layout.

## Repository protection

Protect `main` with required pull requests, documented owner self-review, administrator enforcement, resolved conversations and up-to-date CI. For the sole-developer workflow, require zero approving reviews and disable mandatory code-owner and latest-push approvals. Require the API, Flutter, dependency and all eight container checks listed in [the protection policy](../.github/branch-protection/main.json). Disable force pushes and deletion. Apply classic branch protection or an equivalent reviewed ruleset; the committed JSON does not activate server-side enforcement.

Follow [FND-01 activation and acceptance](engineering/FND-01_repository_governance.md). An eligible private-repository plan, administrator activation and enforcement evidence remain pending. Appointing another developer or reviewer is not required for this development workflow. No branch-protection claim is made until the effective settings and acceptance evidence are verified.
