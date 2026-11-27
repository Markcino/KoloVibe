# FP-CM Comments — requirements (PRD and SRS content)

**Status: APPROVED by the owner on 27 November 2026 at 12:26 UTC ("Approve all as recommended"), with the recommended option for every open choice. The file name keeps its original `_PROPOSED` suffix so links stay stable.** Approval covers development scope only. It does not approve a provider, an account, a value marked `[OWNER VALUE]`, live payments, live ads or store submission. Written in Phase 1 (27 November 2026) to implement the owner's approval of **GD-07 option (a)**, "comments with moderation and creator controls" (27 November, 11:31 UTC). Indexed in [FP-000](FP-000_Full_Product_Requirements_Baseline.md). Values marked **[OWNER VALUE]** are configuration with no default; the feature refuses to enable until they are set.

## 1. Scope

Text comments and one level of replies on published videos, with reporting, moderation, creator controls and blocking. Out of scope: images, links rendered as previews, mentions that notify (see FP-NT once approved), reactions on comments, comments on businesses or events (Business has reviews and inquiries), live chat (live streaming is excluded).

## 2. Ownership and architecture

| Item | Decision used |
| --- | --- |
| Owning service | **Engagement** (it owns likes, follows and shares; comments are social engagement). No new service |
| Moderation | Moderation's existing `Report`, decision and appeal workflow is extended with a `target_type` (`video`, `comment`) and `target_id`; no second moderation queue |
| Content | Supplies video state (published, restricted, deleted) through the existing internal lookup; a video that stops being public hides its comments |
| Identity | Supplies account standing; suspended or restricted accounts cannot post (Decision F) |
| Audit | Moderation decisions and creator removals are audited through the existing delivery |
| Gateway | New routes behind a new capability flag `comments`, default off |

## 3. Roles

| Role | Can |
| --- | --- |
| Viewer (signed in, verified email) | Read; post; reply; edit own comment within the edit window; delete own; report; block an account |
| Anonymous | Read comments on public videos only, if the owner enables anonymous reads ([OWNER VALUE] `comments.anonymous_read`, recommended off) |
| Creator (video owner) | Everything a viewer can; turn comments off or on per video and as a default; remove any comment on their own video; pin one comment; hold comments with listed words for review |
| Moderator | Review reported comments; hide, restore or remove; apply account measures through the existing Decision F flow |
| Administrator | Set the configuration values; see comment audit |

## 4. User journeys

1. Viewer opens a video, opens the comment sheet, reads newest or top comments, writes a comment, sees it appear with a "posting" state then a confirmed state.
2. Viewer replies to a comment; replies appear under the parent, one level deep.
3. Viewer reports a comment with a reason; the comment stays visible to others until a decision or until the hide threshold is reached; the reporter sees the report in "My reports".
4. Creator turns comments off for a video; existing comments are hidden from everyone but kept; turning them back on restores them.
5. Creator removes a comment on their video; the author sees "removed by the creator" on their own copy and cannot appeal (creator removal is not a platform decision).
6. Moderator removes a reported comment; the author is told the reason code and may appeal once through the existing appeal flow.
7. Viewer blocks an account; neither sees the other's comments or replies.

## 5. Functional requirements

| ID | Requirement | Pri | Acceptance criterion |
| --- | --- | --- | --- |
| CM-R-001 | Only signed-in accounts with a verified email and no posting restriction can post or reply | M | Unverified, restricted and suspended accounts get 403 with a reason code; tests per state |
| CM-R-002 | Comments exist only on videos that are published and public; posting to any other video returns 404 | M | Draft, processing, private, restricted and deleted videos tested |
| CM-R-003 | Body is plain text, 1 to [OWNER VALUE] `comments.max_length` characters (recommended 500), Unicode NFC-normalized, control characters removed, stored as text and rendered as text only | M | Over-length 400; HTML and script render as literal text in Flutter widget tests |
| CM-R-004 | One level of replies; a reply to a reply attaches to the top-level parent | M | Depth never exceeds 1 |
| CM-R-005 | Every write is idempotent by an `Idempotency-Key`; a retried post never creates a duplicate | M | Same key twice gives one comment and the same response |
| CM-R-006 | Authors may edit within [OWNER VALUE] `comments.edit_window_minutes` (recommended 15); edits keep the previous text for moderation and show "edited" | S | After the window edit returns 409; history visible to moderators only |
| CM-R-007 | Authors may delete their own comments; replies remain under a "deleted comment" placeholder | M | Deleted text is not returned to anyone except moderators during the retention period |
| CM-R-008 | Lists are cursor-paginated, newest first and "top" (by reply count and likes on the video's comments is out of scope; "top" = most replies, ties by newest); page size at most 50 | M | Stable pagination under inserts; no offset paging |
| CM-R-009 | Creator can turn comments off per video and set a default for new videos | M | Off returns 403 `comments_off` for posts and an empty list with `comments_off` for reads |
| CM-R-010 | Creator can remove any comment on their own videos and pin one top-level comment | M | Non-owner attempts 404; pin moves to top |
| CM-R-011 | Creator word list holds matching comments for the creator's review instead of publishing them | S | Held comment visible only to its author ("pending") and the creator |
| CM-R-012 | Report a comment through the existing reasons, one open report per reporter per comment | M | Second open report 409; Moderation queue shows target type |
| CM-R-013 | A comment with reports from [OWNER VALUE] `comments.auto_hide_reports` distinct accounts (recommended 3) is hidden pending review; it is never deleted automatically | M | Hidden at threshold; restored on a "no violation" decision |
| CM-R-014 | Moderator decisions (hide, restore, remove) carry a reason code and policy version, are audited, and are appealable once by the author | M | Audit event per decision; appeal reviewed by a different moderator (existing rule) |
| CM-R-015 | Blocking hides the blocked account's comments and replies from the blocker and stops replies between them | M | Two-account tests both directions |
| CM-R-016 | Rate limits per account: [OWNER VALUE] `comments.rate_per_minute` and `comments.rate_per_day` (recommended 5 and 200); per-video flood limit | M | 429 with retry-after; counters server-side |
| CM-R-017 | Comment counts on videos are eventually consistent and never reveal hidden or held comments | S | Count matches visible comments after the projection catches up |
| CM-R-018 | Erasure: on account erasure (Decision C) the account's comments are deleted or anonymized per the approved retention category; access export includes the person's own comments | M | Engagement erasure and export tests extended |
| CM-R-019 | Notifications to the video owner and the parent author are sent only through FP-NT and only if FP-NT is approved and the person's preferences allow | S | No notification code path in Engagement |
| CM-R-020 | Console: moderator queue filter by target type, comment context view (video, parent, author standing), and decision form; administrator configuration page | M | Route-security matrix covers the pages; MFA required |

## 6. Security

Object-level authorization on every route (author, video owner, moderator). Server-side standing check on every write, not cached beyond the existing standing contract. Text only: no markup rendering anywhere, including the console (Django autoescape kept). Abuse: rate limits, flood limits, report thresholds, block lists. No comment text in logs; only ids. STRIDE additions to DOC-203 in Phase 2: spam and harassment (DoS of attention), impersonation through display names, data exposure through deleted text.

## 7. Privacy

Comments are personal data of the author. Public visibility follows the video. Retention category `comments` is added to the ADR-020 schedule ([OWNER VALUE], legal approval required). Moderator-only retention of edited and deleted text for [OWNER VALUE] days.

## 8. API (proposed, to be added to the canonical contract in Phase 2)

| Method and path | Purpose |
| --- | --- |
| `GET /api/v1/videos/{video_id}/comments?order=newest|top&cursor=` | List top-level comments |
| `POST /api/v1/videos/{video_id}/comments` | Post (Idempotency-Key) |
| `GET /api/v1/comments/{comment_id}/replies?cursor=` | List replies |
| `POST /api/v1/comments/{comment_id}/replies` | Reply |
| `PATCH /api/v1/comments/{comment_id}` | Edit own |
| `DELETE /api/v1/comments/{comment_id}` | Delete own, or remove as video owner |
| `POST /api/v1/comments/{comment_id}/reports` | Report |
| `PUT /api/v1/creators/me/videos/{video_id}/comment-settings` | Off or on, pin, word list |
| `POST /api/v1/me/blocks`, `DELETE /api/v1/me/blocks/{account_id}` | Block and unblock |
| `GET /api/v1/moderation/reports?target_type=comment` and existing decision routes | Moderation |

## 9. Event contracts (RabbitMQ, proposed)

| Event | Producer | Consumers |
| --- | --- | --- |
| `kolovibe.engagement.comment.created.v1` (ids only) | Engagement | Notifications (FP-NT), analytics |
| `kolovibe.engagement.comment.removed.v1` | Engagement | Notifications |
| `kolovibe.moderation.decision.applied.v1` with `target_type=comment` | Moderation | Engagement (apply hide or remove), Audit |

Events carry ids, never text. Consumers are idempotent by event id (existing inbox pattern).

## 10. Flutter screens (route space M-400 to M-419, Figma frames required first, #306)

M-400 comment sheet (list, sort, composer); M-401 replies; M-402 posting and failure states; M-403 edit; M-404 report comment; M-405 comments off and empty states; M-406 creator comment settings; M-407 held comments review; M-408 blocked accounts list. Error, offline and rate-limited states on each.

## 11. Failure scenarios

Network loss while posting (kept as draft, retried with the same key); video becomes private while the sheet is open (sheet shows unavailable, no further posts); author suspended between load and post (403 shown); moderation decision arrives twice (idempotent); broker outage (Engagement writes succeed, events wait in the outbox); report flood by a group (threshold counts distinct verified accounts only and is audited).

## 12. Non-functional

p95 list latency under 300 ms at the Gateway for a page of 50 on staging hardware [measured in Phase 10]; post p95 under 500 ms; no N+1 queries (query-count test); comments table indexed by `(video_id, created_at)` and `(parent_id, created_at)`.

## 13. Choices still open

| Choice | Options | Recommendation |
| --- | --- | --- |
| CM-D1 Values marked [OWNER VALUE] | — | Accept the recommended values for development; confirm before activation |
| CM-D2 Anonymous reads | (a) off; (b) on | (a) off: fewer scraping and abuse paths |
| CM-D3 Creator removal appealable | (a) no; (b) yes | (a) no, it is the creator's space; platform removals stay appealable |

## 14. Traceability

FP-EN-05 in the [feature matrix](../governance/phase1/PHASE-01_Feature_Traceability_Matrix.csv); GD-07; issues #135 and #307.
