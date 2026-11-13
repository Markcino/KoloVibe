# FL-D Points and moderation gap matrix (M-061–M-078) and journey 1

Baseline: `origin/main` `a1e419a` (PR #55 merged). Local verification only: no deployment, device or live staging acceptance is implied. Contract sources: `services/gateway/service/pilot_points.py`, `moderation.py`, `standing.py`, `routes/points.py`, `routes/moderation.py`, and [BE-TR acceptance](BE-TR_points_moderation_audit_acceptance.md). No backend contract was changed.

## How each screen was classified

VERIFIED = live screen, real gateway data, all states, tests. PARTIAL = some behaviour is live, parts of the recipe are missing or wrong. MISSING = contract exists, no live screen (the route falls back to the protected design placeholder, which shows no sample data in a live build). BLOCKED = a recipe element has no contract or approved copy yet.

| Screen | Recipe | Before this PR | After this PR | Contract and dependency |
| --- | --- | --- | --- | --- |
| M-061 | Lone Stars | PARTIAL (one screen, balance only) | **VERIFIED** (journey 1) | `GET /creators/me/points` returns `balance` plus server totals `confirmed`, `pending`, `withheld`, `reversed`; the app ignored the last three. |
| M-062 | Confirmed Lone Stars | PARTIAL (filtered the same page) | **VERIFIED** | `entries?status=confirmed`. |
| M-063 | Pending Lone Stars | **Fake**: the filter was `false`, so it always showed "No points activity yet" | **VERIFIED** | `entries?status=pending`; pending rows are potential awards, not posted balance. |
| M-064 | Transaction history | PARTIAL (no filters, kind shown raw) | **VERIFIED** | `entries?status=all\|confirmed\|pending\|adjustments&cursor=`, 20 per page. |
| M-065 | Transaction details | MISSING | **VERIFIED** | `GET /creators/me/points/entries/{id}`; foreign or missing id is 404. Source title is a best-effort public read. |
| M-066 | Withheld points | **Fake**: the filter was `false` | **VERIFIED** | The server has **no** `withheld` filter. Withheld rows exist only under `all`; the app picks them by their server `status`. |
| M-067 | Reversed points | PARTIAL (rows with `kind == reversal` from the first page only) | **VERIFIED** | `entries?status=adjustments`, total from `reversed`. |
| M-068 | Engagement eligibility | MISSING (fell into the points screen) | **VERIFIED** (static approved copy) | No contract needed. |
| M-069 | No points activity | PARTIAL (a list tile) | **VERIFIED** | Shown for an empty ledger, with no sample figures. |
| M-070 | Report video entry | MISSING | PARTIAL (journey 2) | The player's "Report this video" and overflow control open M-071 with the video id (signed-out goes to sign-in). The designed options sheet ("Share public link" plus a report row with its privacy note) was not rebuilt. |
| M-071 | Report a video | PARTIAL (live) | **VERIFIED** (journey 2) | `GET /videos/{id}` then reasons. Six labels map onto five server codes, so "Violence" and "Sexual content" both send `harmful`; receipts name the reason from the server code only. Loading, offline, expired, video gone, no video id. |
| M-072 | Report details | PARTIAL (live) | **VERIFIED** | Reason required, text optional (2000 max, trimmed, cleared when sent or left). A cold entry starts at the reasons (it cannot skip the required reason). |
| M-073 | Report submitted | PARTIAL (live) | **VERIFIED** | `POST /reports` receipt. A cold entry shows the latest own report for the video (paged `GET /me/reports`); a decided one reads "has been reviewed"; none found falls back to the reasons. |
| M-074 | Report submission error | PARTIAL (inline text) | **VERIFIED** | Dedicated state with the designed actions. Failure kinds: unconfirmed (offline, 5xx, unreadable) retries with the same key; rate limit retries; expired offers sign-in; 403 and 404 offer no retry. No cold entry (no failed attempt to show). |
| M-075 | Already reported | PARTIAL | **VERIFIED** | `409 code: already_reported` becomes this state (not an error) and the earlier report's reason is looked up (best effort). A cold entry needs an *open* report; a decided one does not count. |
| M-076 | Content restriction notice | MISSING | MISSING | `GET /creators/me/videos/{id}/notice` needs approved copy for each `reason_code` (unknown codes must not be guessed). |
| M-077 | Account status | MISSING | MISSING | `GET /me/standing` (`account_status`, `creator_status`, `publishing_allowed`, up to 20 notices). |
| M-078 | Appeal / review request | MISSING (the repository method exists, no screen) | MISSING | `POST /videos/{id}/appeals`; only when the notice says `appealable` (a removed video with no appeal yet). |

Staging capabilities `points`, `watch` and `moderation` are closed by default; every client must treat 403, 404 and 503 as normal states.

## Remaining journeys, in priority order

1. **Points ledger (M-061–M-069): PR 56.**
2. **Reporting completion (M-071–M-075): journey 2 (stacked on PR 56).** Remaining: the M-070 options sheet.
3. Notices and standing (M-076, M-077): read-only; blocked on owner-approved copy per `reason_code`.
4. Appeal (M-078): depends on the notice read; one appeal per removal, no client-side status guessing.

## Journey 1: what changed

| Area | Change |
| --- | --- |
| Defects fixed | M-063 and M-066 could never show anything (`false` filter). Pending, withheld and reversed totals were returned by the server but never shown. Withheld rows were unreachable. The history had no status filter and no way to open an entry. |
| Repository | `PointsBalance` carries the server's four totals. `PointsEntry` carries `status` and `video_id`. Both parse strictly (exact keys, non-negative totals, award positive, reversal negative, status/kind consistency, as the gateway validates). `entries` takes the server `status` filter and rejects a page that does not match it. New `entry(id)`. **No write method exists.** |
| Controller | `PointsController` pages with one request in flight, a stale-response guard when the filter changes, a failed page that keeps its rows and retries from the same cursor, repeated rows refused, foreign-creator rows refused, and a refresh that keeps data on failure. The withheld view reads further `all` pages (at most 5 per action) until a withheld row appears, then offers "Check older activity". |
| Screens | `LivePointsScreen` dispatches M-061–M-069 to the ledger, entry and rules screens. M-037 Creator Studio gains a "Lone Stars" link with no figure. |
| Server owns the numbers | Headline = `balance`; tiles = `pending`, `withheld`, `reversed`. The app never sums rows, never estimates and never adds a figure. A test shows the headline stays the server value when the rows add up differently. |
| States | Loading, offline with retry, expired session with sign-in that returns to the same screen, "approved creators only" for 403, not found for a foreign entry, unreadable response, empty ledger, empty filter, load-more failure. |
| Not shown | No cash value, rate, payout, redeem or withdraw control, no processing-time promise, no withheld reason (the gateway returns none; the design says details are limited). |

### Semantics worth knowing

- `balance` is the net ledger total; `confirmed` is the gross of posted awards (it includes awards later reversed). The headline "Confirmed Lone Stars" uses `balance`, because the approved M-067 copy says the confirmed total reflects reversals. `confirmed` is parsed but not displayed. If the owner prefers the gross, it is a one-word change.
- Pending and withheld rows carry one potential point each and are not posted changes, so they are shown unsigned (withheld) or as "+n" with a "Pending" label.
- Adjustment entries (`kind: adjustment`) have no approved design copy beyond "Recognition adjustment"; the app says only that an adjustment was recorded.

## Tests

| Suite | Type | Count |
| --- | --- | --- |
| `test/live_points_repository_test.dart` | Repository contract tests with **mocked HTTP** (`MockClient`), including a source scan that fails on any write verb or arithmetic over amounts | 15 |
| `test/points_controller_test.dart` | Controller tests with **fake repositories** | 20 |
| `test/live_points_screens_test.dart` | Widget tests with **fake repositories** and the real design catalog; includes 2.0 text scale and semantics | 38 |
| `test/trust_routes_test.dart` | Route dispatch (M-061–M-069 live; M-070, M-076–M-078 stay protected) | 3 |
| `test/live_repositories_test.dart` | Existing points test updated to the current gateway shape (`confirmed`, `pending`, `withheld`, `reversed`, `status`, `video_id`) | 1 changed |
| `test/live_creator_identity_screens_test.dart` | M-037 assertion updated: a Lone Stars link is allowed, a Lone Stars figure is not | 1 changed |

Flutter `analyze`: no issues. Full suite: 781 passed (705 before). Mutation checks: removing the stale-response guard, and making the withheld view show every row, each fail the tests that name them.

## Not covered

Local mocked and fake-repository tests only. No live gateway, device, staging or accessibility screen-reader pass was run.

## Journey 2: reporting (M-071–M-075)

| Area | Change |
| --- | --- |
| Defects fixed | A `409 already_reported` showed as a generic error. M-075 looked only at the first 20 reports and for any status. One idempotency key was reused for the life of the screen, so changing the reason or text after a failed attempt would have been rejected as a key conflict. M-074 had no state. A cold M-072 allowed a chosen-reason chip reading "Choose a reason above". |
| Repository | `ReportRecord` and paged `ownReports` (strict keys, reason must be one of the five codes, cursor rules mirror the gateway). `findReport(videoId, openOnly, maxPages)` walks pages with a bound. `isAlreadyReported`. |
| Controller | `ReportController`: one submit in flight; identical retry reuses the key (a lost response replays instead of duplicating); a changed reason or text, or a plain 409, gets a new key; an unreadable response is "not confirmed", never "sent"; the text is kept through failures and cleared once sent. |
| Not done | The M-070 options sheet. Reporting your own video, and any reviewer-side decision, are the server's call; the app adds no rule. |

Tests added for this journey: `test/live_report_repository_test.dart` (13, mocked HTTP), `test/report_controller_test.dart` (19, fake services), `test/live_report_screens_test.dart` (28, fake services and the real catalog, 2.0 text scale), route dispatch extended in `test/trust_routes_test.dart`.
