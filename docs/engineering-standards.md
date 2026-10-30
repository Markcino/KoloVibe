# Engineering standards

KoloVibe is developed as a maintainable mobile application backed by independently owned services. Work is reviewed against functionality, security and release-readiness criteria.

## Pull requests and code ownership

- Changes to application behavior and services require review.
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

Protect `main` with required pull requests, at least one independent code-owner approval, administrator enforcement, resolved conversations and up-to-date CI. Require the API, Flutter, dependency and all eight container checks listed in [the protection policy](../.github/branch-protection/main.json). Disable force pushes and deletion. Apply classic branch protection or an equivalent reviewed ruleset; the committed JSON does not activate server-side enforcement.

Follow [FND-01 activation and acceptance](engineering/FND-01_repository_governance.md). An eligible private-repository plan, an independent reviewer with write access and an administrator action remain pending. No branch-protection claim is made until the effective settings and acceptance evidence are verified.
