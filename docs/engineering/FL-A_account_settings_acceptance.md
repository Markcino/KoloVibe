# FL-A account, settings and system binding

Baseline: main `b1971d9b0a9a07f99d3f18bc1ecfc344fc909c1c`. The gap-first commit records inspection in [FL-A_account_settings_screen_gaps.md](FL-A_account_settings_screen_gaps.md) before implementation. Existing session storage, refresh serialization, session endpoints, notification repository and DeviceBridge capabilities were extended rather than replaced. Source recipes and unavailable-dependency rendering remain unchanged.

## Per-screen result

| Screen | Mode | Endpoint (all under `/api/v1`) | Result |
|---|---|---|---|
| M-001 · Splash Screen | Live | POST /auth/refresh; GET /me | Restores saved session; rejected saved credentials show M-101. |
| M-002 · Welcome Screen | Static | — | Recipe welcome routes to sign-in/register. |
| M-003 · A world of original voices | Static | — | Recipe introduction and discovery navigation. |
| M-004 · Sign in | Live | POST /auth/login | Typed failure navigation; passwords cleared. |
| M-005 · Create an account | Live | POST /auth/register | Terms acknowledgment; 409 selects M-012. |
| M-006 · Verify your email | Live | POST /auth/verify | Full delivered code; actual email context; expired/rejected code selects M-008. |
| M-007 · Resend verification | Live | POST /auth/verification/resend | Generic eligible response; code-entry navigation. |
| M-008 · Verification expired | Live | POST /auth/verification/resend | Request fresh code; preserves entered email. |
| M-009 · Forgot password | Live | POST /auth/password/reset-request | Generic eligible response; reset-code form. |
| M-010 · Reset password | Live | POST /auth/password/reset | New/confirmed password; clears local session after success. |
| M-011 · Password reset | Live result | — | Reset completion only acknowledged after successful reset; return to sign-in. |
| M-012 · Account already exists | Live result | — | Registration conflict; sign-in/reset/alternate-email actions. |
| M-013 · Make it yours | Live | GET /me; PATCH /me | Saves display_name, read-only email. Optional photo action honestly unavailable. |
| M-014 · Your voice belongs here | Static | — | Original-work/role-based creator introduction; setup/explore navigation. |
| M-015 · Sign-in problem | Live | POST /auth/login | Generic sign-in failure and retry; recovery/register actions. |
| M-016 · Confirm it’s you | Live | GET /me; POST /me/reauthenticate | Typed ephemeral proof returned to caller; no storage/URL/session-state token. |
| M-079 · My account | Live | GET /me | Actual identity/roles; profile/settings/help; creator studio/points entry points. |
| M-080 · Edit personal profile | Live | GET /me; PATCH /me | Display name save; read-only email; photo policy placeholder; discard guard. |
| M-081 · Account settings | Live/static | GET /me | Actual account email; recipe settings/support/legal/logout/deletion navigation. |
| M-082 · Change password | Live | PATCH /me/password | Requires current password; retains current session; explains other-session revocation. |
| M-083 · Active sessions | Live | GET /me/sessions; DELETE /me/sessions/{id} | Current session identified; explicit confirmation; actual reload after revocation. |
| M-084 · Privacy settings | Live/static | POST /me/reauthenticate; POST /me/privacy-requests | Data-request flow; privacy/security/deletion links. |
| M-085 · Security settings | Live | GET /me | Read-only account email; password/session links; no invented verification flag. |
| M-086 · Notification preferences | Live/native | GET/PATCH /me/preferences | Real email/push preferences; DeviceBridge.openAppSettings; no inferred OS permission. |
| M-087 · Community guidelines | Static/native | — | Recipe community principles; optional configured HTTPS official link. |
| M-088 · Terms & Privacy | Static/native | — | Recipe Terms/Privacy topics and tabs; optional configured HTTPS official links. |
| M-089 · Help & Support | Static/native | — | Recipe help topics; optional configured HTTPS /help through DeviceBridge. |
| M-090 · Logout confirmation | Live | GET /me; POST /auth/logout | Confirmation; secure local cleanup; welcome route; honest server-revocation uncertainty on failure. |
| M-091 · Delete account request | Live | GET /me; POST /me/reauthenticate via M-016 | Deletion intake introduction; identity verification before confirmation. |
| M-092 · Confirm account deletion | Live | POST /me/privacy-requests | DELETE acknowledgment plus one-use proof, or inline password→proof; intake only. |
| M-093 · Deletion request received | Live | GET /me/privacy-requests or POST receipt | Actual deletion id/status/UTC date; duplicate open request is shown. |
| M-094 · Privacy request received | Live | GET /me/privacy-requests or POST receipt | Actual access-request id/status/UTC date; all four statuses supported. |
| M-095 · No Internet Connection | Live/reusable | — | ApiFailure.offline → connection state with retry. |
| M-096 · Slow Connection | Live/reusable | — | Outstanding request exceeds 3-second UI threshold; does not invent connectivity diagnosis. |
| M-097 · Loading Skeleton | Reusable | — | Static loading skeleton; timer disposed on completion/removal. |
| M-098 · No search results | Reusable | — | Query-aware empty widget with edit callback; adoption by other feature owners remains separate. |
| M-099 · Application error | Live/reusable | — | Unexpected/malformed failures; generic safe detail and retry. |
| M-100 · Access denied | Live/reusable | — | HTTP 403 access-denied state. |
| M-101 · Session expired | Live/reusable | POST /auth/refresh | Rejected refresh clears stored credentials; session-expired sign-in action. |
| M-102 · Service unavailable | Live/reusable | — | HTTP 503 service-unavailable state. |
| M-103 · Rate limit exceeded | Live/reusable | — | HTTP 429 rate-limit state; wait guidance and manual retry. |
| M-104 · Media permission | Native/reusable | — | DeviceBridge.openAppSettings; honest unavailable result. |
| M-105 · Unsaved Changes Warning | Native/reusable | — | PopScope unsaved-form guard; blocks departure during mutation. |
| M-106 · Destructive-Action Confirmation | Native/reusable | — | Explicit destructive confirmation dialog, used for session revocation. |
| M-107 · Success Notification | Native/reusable | — | Success notification after acknowledged mutation. |
| M-108 · Application Update / Compatibility Notice | Live/native | GET /app/compatibility?platform=&version= | Installed DeviceBridge version; required blocks, available dismisses, unknown/errors never block; HTTPS store action. |

## Contracts and boundaries

- `/me` returns `id`, `email`, `display_name`, `roles`; `PATCH /me` accepts `display_name` (2–80 characters). Email is read-only. Creator entry points use the actual `creator` role, with service authorization still authoritative.
- Auth endpoints accept existing email/password/display_name or full 32–128-character delivered verification/reset codes. Registration conflicts use 409; resend/reset-request responses remain generic. MFA-required login responses never establish a password-only session; completing MFA sign-in is outside these recipes.
- `POST /me/reauthenticate {current_password}` returns `{reauth_token, expires_at}` (URL-safe token, future timestamp with timezone; backend enforces account/session binding, five-minute expiry, throttling and single use). Proof is held only in memory and consumed before sending a privacy request. It is discarded on success, failure, expiry and leaving its flow.
- `POST /me/privacy-requests {kind, reauth_token}` uses `access|deletion`. GET returns `{items:[...]}` (bounded to 40). Receipts are exactly `{id, kind, status, created_at}`, status `received|in_review|completed|declined`. `409 code: request_open` retrieves and shows the matching open request. If delivery is uncertain, reauthentication is required again. Deletion is intake only (ADR-020): no disabling, purge or automatic sign-out.
- `PATCH /me/password {current_password,new_password}` revokes other sessions and keeps the current one; public reset revokes every session server-side. Logout sends the stored refresh token to `/auth/logout` and always attempts secure local cleanup. Server-side session/access-token rejection remains a backend obligation.
- Compatibility returns exactly `{status,minimum_version,latest_version,store_url}`; status `unknown|supported|update_available|update_required`, nullable versions/store URL. Startup calls once using the installed platform/version; a two-second policy timeout is nonblocking. Required policy has no dismiss path; available policy is dismissible. An invalid/missing native version, unsupported platform, malformed response or HTTP/transport failure is unknown.
- Build-time `KOLOVIBE_PUBLIC_WEB_ORIGIN` must be an HTTPS origin without credentials/path/query/fragment. Optional official paths `/community-guidelines`, `/terms`, `/privacy`, `/help` must be hosted there. Links are hidden when invalid/unconfigured. All external links go through `DeviceBridge.openUrl`.
- Profile photos remain honestly unavailable pending moderation policy. Notifications store preferences without claiming actual OS permission or delivery. Native settings/store opening depends on DeviceBridge platform support.
- The small public API is documented at the top of `lib/features/system/system_ui.dart`. Other feature owners can adopt failure/loading/empty/guard/dialog/success/permission widgets; their screens were not rewritten here.

## Files and ownership

Account: `live_account_repository.dart`, `live_account_screen.dart`, `account_sessions_screen.dart`, new `live_account_flow.dart`. Settings: `live_settings_repository.dart`, `live_settings_screen.dart`, new `live_information_screen.dart`. System: new `system_ui.dart`, `compatibility.dart`. Owned routing: `app/routes/account_routes.dart`, `settings_routes.dart`.

Minimal shared edits: `app/kolovibe_app.dart` for compatibility and typed session-restore states; `app/app_dependencies.dart` adds an optional HTTP client for deterministic app integration tests; `features/shell/screen_controller.dart` recognizes token fields as sensitive. `main.dart`, backend/native source, recipes, dependencies and other feature files are unchanged. No models or migrations. Documentation changes are this acceptance report, the gap-first report, and `docs/mobile-design-coverage.md` (46-screen status table).

Tests: new `fl_a_account_repository_test.dart`, `fl_a_account_widgets_test.dart`, `fl_a_system_test.dart`, support fixture `fl_a_support.dart`; existing `live_settings_repository_test.dart` updated for the two-step proof contract. Tests use mocked HTTP and DeviceBridge; they do not claim deployed-backend or physical-device acceptance.

## Open integration items

- Physical-device and deployed-backend UAT remain separate from these mocked HTTP/native tests.
- Photo upload awaits the photo moderation policy. Completing MFA-required sign-in needs an MFA design/flow; password-only responses are rejected safely.
- Identity currently lists only the latest 40 privacy requests. The duplicate-receipt flow assumes that list includes the open request. An unusually old open request could fall outside the window after many closed requests of the other kind; the API then needs an open-request filter, open-first ordering, or a receipt in the conflict response. The client fails without inventing a request id/status.
- Other feature owners must adopt the reusable empty/system components in their own live flows. Static policy topics remain summaries; configured official web pages must exist before exposing links.

## Validation

Working directory for Flutter commands: `apps/mobile`.

| Exact command | Result |
|---|---|
| `FX=/tmp/fl-a-fx; $FX analyze` | PASS — No issues found (zero errors, warnings or infos). |
| `FX=/tmp/fl-a-fx; $FX test --reporter expanded` | PASS — 425 tests, including all 108 unavailable-dependency design captures. |
| `python scripts/check_mobile_design.py` (repository root) | PASS — 108 entries, 150 local assets, valid routes and source slots. |
| `git diff --check` (repository root) | PASS. |

The suite includes success, 400/401/403/409/429/503/offline account actions; reauthentication expiry and single-use consumption; conflict receipt handling; password-change session retention; reset/logout cleanup; session revocation; native settings/support/store actions; preference failures; compatibility strict parsing, timeout, required blocking and optional dismissal; startup refresh rejection; form guards and secret clearing. HTTP mocks exercise the real repository/client, with asynchronous stream work explicitly drained in widget tests.

Toolchain: Flutter 3.47.8 / Dart 3.13.7. `FX=/tmp/fl-a-fx` invokes the pinned Flutter executable with `CI=true BOT=true FLUTTER_SUPPRESS_ANALYTICS=true`. This supported CI configuration prevents Flutter's Azure metadata bot-detection request and suppresses analytics. The original automatic review rejection was resolved by preventing that request, without contacting instance metadata.
