# Security verification and web administration evidence

Cross-service tests cover authenticated service identities, PostgreSQL privilege separation, immutable evidence and network/TLS boundaries. The web console adds the targeted evidence below. These are implementation tests, not independent security assurance or a claim of complete ASVS L2 conformance. Owner acceptance remains pending.

## Baseline and trace IDs

ASVS reference: [OWASP ASVS 5.0.0, versioned requirement data](https://github.com/OWASP/ASVS/blob/v5.0.0/5.0/docs_en/OWASP_Application_Security_Verification_Standard_5.0.0_en.flat.json). IDs were checked against that release. Descriptions below identify the tested scope only; unlisted controls are not implicitly satisfied.

| Evidence ID | Scope / ASVS reference | Executable evidence |
| --- | --- | --- |
| WEB-SEC-001 | Browser headers/cache; 3.4.3–3.4.6, 14.3.2 | `apps/web_django/tests/test_hardening.py::test_WEB_SEC_001_headers_and_cache_on_documents_redirects_and_errors` |
| WEB-SEC-002 | Secure/Host/HttpOnly cookies; 3.3.1–3.3.4 | `test_WEB_SEC_002_staging_transport_and_cookie_attributes`; `test_staging_sessions.py` |
| WEB-SEC-003 | Text escaping and same-origin preview; 3.2.2 | `test_WEB_SEC_003_reviewer_history_is_autoescaped_and_preview_is_same_origin`; `test_admin.py` escaping cases |
| WEB-SEC-004 | Session termination/client cleanup; 7.4.1, 14.3.1 | `test_WEB_SEC_004_logout_clears_client_state_and_get_is_not_mutating`; logout outage and expiry cases |
| WEB-SEC-005 | Session backend/rotation/deadlines; 7.2.1, 7.2.4, 7.3.1–7.3.2 | `test_privileged_login.py`, `test_staging_sessions.py` |
| WEB-SEC-006 | CSRF; 3.5.1 | `test_admin.py::test_csrf_enforced_on_every_decision_and_mutation`; MFA CSRF test |
| WEB-SEC-007 | Owning-service role/object/field authorization; 8.2.1–8.2.3, 8.3.1 | Moderation assignment/reviewer/operation tests; Audit reader tests; Points admin review tests |
| WEB-SEC-008 | Denials/evidence/generic failures; 16.3.2, 16.4.2, 16.5.1–16.5.3 | Service denied-read audit tests, append-only guards, gateway denial/error and web leakage tests |
| WEB-ADM-001 | Bounded Unicode detail; FR-023/026 | `test_hardening.py::test_WEB_ADM_001_bounded_unicode_detail_exceeding_64k_remains_valid` |
| WEB-ADM-002 | Real MFA and full console/service boundary; FR-021–FR-030 | `scripts/verify_local_journeys.py::test_WEB_ADM_002_real_privileged_console_and_owning_services` |
| WEB-ADM-003 | Decisions/CSRF/idempotency; FR-025 | Web decision tests; moderation replay/pending-delivery and independent-appeal tests |
| WEB-ADM-004 | Headerless sign-in, active navigation, keyboard/390px layout; NFR-011 | `test_hardening.py::test_WEB_ADM_004_entry_is_headerless_sign_in_and_navigation_marks_current_page`; browser evidence below |
| WEB-ADM-005 | Cross-record reviewer metadata rejection; FR-026 | `test_hardening.py::test_WEB_ADM_005_cross_record_metadata_is_rejected` |
| BE-MOD-WEB-001 | Assigned scope/inactive/revoked/unassigned denial; FR-024 | `services/moderation/tests/test_assignments.py` |
| BE-MOD-WEB-002 | Detail/preview ownership/expiry/audit; FR-026 | `services/moderation/tests/test_reviewer.py`, `services/content/tests/test_moderation.py` |
| BE-MOD-WEB-003 | Fixture totals/status/hold scope; FR-027 | `services/moderation/tests/test_operations.py`, `services/engagement/tests/test_fraud_holds.py` |
| BE-AUD-WEB-001 | Own/producer grants, pagination, redaction; FR-028 | `services/audit/tests/test_reader.py` |
| BE-PTS-WEB-001 | Ledger sum/snapshot/reversal state/no writes; FR-029 | `services/points/tests/test_admin_review.py` |

## Execution procedure

Run focused service tests through `scripts/run_local_service.py <service> test <module>` and web tests with `.venv/bin/python scripts/run_local_web.py test tests`. Run the real-service HTTP fixture with PostgreSQL binaries on PATH: `PATH="$(pg_config --bindir):$PATH" .venv/bin/python scripts/verify_local_journeys.py`. It provisions task-owned TLS PostgreSQL and distinct peer keys, exercises existing Identity MFA without changing real settings, validates live response schemas, and destroys the fixture afterward. No live credential or production dataset is needed.

Then run the repository CI gates: script suites, all service tests/migration checks, PostgreSQL foundations, staging WSGI/TLS and database preflight, dependency locks, OpenAPI, Bandit enforcement, secret scan, dependency audits/SBOM, Flutter, image vulnerability gates and image smoke tests. GitHub PR validation records the exact run and result; no merge or deployment is implied.

## Browser and acceptance evidence

WEB-ADM-004 / NFR-011: keyboard and 390px browser inspection is performed against a loopback fixture with synthetic data. Observed on 21 November 2026: sign-in → MFA → dashboard → queue → reviewer detail → audit → points balances/history succeeded in the browser. The skip link moved focus to `main`; Tab reached review links and the labelled decision/reason controls. After the requested Material 3 redesign, the native mobile menu opened and its Videos link navigated using Enter. `/` opens headerless sign-in even with an existing session. At 390×844, dashboard, queue, detail, audit, balances and history had root scroll width 390px (no document horizontal overflow). The 640px queue table remained readable in its labelled scroll region; ArrowRight advanced horizontal table scrolling. Desktop was checked at 1280×900. A versioned stylesheet URL ensures the new table rules replace cached assets. Screenshots contain synthetic data only: [desktop](evidence/web-admin-desktop.png), [390px dashboard](evidence/web-admin-mobile.png), [review form](evidence/web-review-mobile.png), [headerless sign-in](evidence/web-sign-in.png). No production sign-in, real R2 byte delivery or independent accessibility audit is claimed.

The UI uses [Material 3 color roles](https://m3.material.io/styles/color/the-color-system) and [type roles](https://m3.material.io/styles/typography/applying-type), implemented with local CSS, inline SVG icons and native controls. No CDN, new framework or client-side permission logic is introduced.

## Remaining acceptance work

- NFR-002 remains partial. Targeted L1/L2 checks above are evidence toward ASVS 5.0 L2, not a full certification. In particular, the restricted-staging HSTS profile is 2592000 seconds (30 days) without includeSubDomains and does not demonstrate full 3.4.1 acceptance; TLS/subdomain rollout review is still needed.
- Real staged R2 preview delivery, buffering/resource behavior under load, and independent security/accessibility review remain unobserved.
- Assignment routing/model policy and moderation SLAs remain open owner decisions. Explicit per-resource grants do not choose those policies.
- Audit retention and broader redaction policy remain open. The implemented projection conservatively omits actor/subject IDs, digests and payloads.
- Form documents retain `Referrer-Policy: same-origin` so Django can validate same-origin form requests; only the media preview response uses no-referrer. Browser inspection caught and corrected a no-referrer/CSRF incompatibility before release.
- Administrators need explicit audit producer grants; the new `audit_read` capability/peer credential must be approved before activation. No current deployment config or secret is modified.
- Reversal state is a ledger observation, not a separate approval workflow; no award/reversal/payout execution is reachable from the web.
