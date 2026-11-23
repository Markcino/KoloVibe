# P5-02 — Fraud review page

**Type:** feature (console only; no backend change). **Scope item:** "Fraud review".

## Gap
Active fraud holds were visible only as a card on the dashboard: the first **five** of the (up to 20) holds the first gateway page returns, with a count. The backend's cursor for the rest was unused, and no hold linked to its video, so a reviewer could not browse all holds or open the affected video.

## Change
`/admin/fraud/` (`views.fraud_holds`, template `fraud.html`, navigation entry "Fraud", dashboard link "Review all N active holds"):
- reads `GET /engagement/fraud-holds?cursor=…` through the existing `_api` client and `privileged` guard; the gateway scopes the result (an administrator sees all active holds, a moderator only holds on videos in an active assignment) and Engagement owns the records. **No business rule and no authorization decision is made in the console.**
- validates the query (only a single, well-formed `cursor`) before any gateway call and the response with the existing `valid_holds` contract, plus a first-page consistency check; malformed data is a 503, never rendered;
- 20 per page with "Next page"/"First page" links, a table with the same responsive card reflow as the review queues, a captioned, scoped table and an accessible per-row link name ("Open video review for video …");
- **read-only**: no form, POST is 405; clearing or creating holds is not offered because no approved rule or backend operation exists;
- a moderator with nothing assigned gets the same explicit empty state as the dashboard, only for the gateway's exact "Request unavailable" refusal; any other 403 stays a 403, and an administrator never gets that state.

Reused: `privileged`, `_api`, `_render`, `_gateway_error`, `valid_id`, `valid_holds`, the table, pagination, empty-state and navigation components. The README route table is updated.

## Tests (`tests/test_fraud_review.py`, 8)
First page with 20 links to video reviews and a cursor link; cursor validation and forwarding (invalid, repeated and extra parameters never reach the gateway); five malformed or inconsistent gateway bodies refused with no data shown; 403/404/429/500/503 shown as errors and never as an empty list; moderator empty state only for the exact refusal; administrator never gets it; read-only and `no-store`; navigation link with current-page marking for both roles. Removing the response validation fails three of them. Whole web suite 109 tests OK; `makemigrations --check` clean.
