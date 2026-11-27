# FP-NT Notifications — requirements (PRD and SRS content)

**Status: PROPOSED for owner approval.** Written in Phase 1 (27 November 2026). Architecture follows the owner's approval of **GD-03 option (a)**: an Identity-owned notification module with its own dispatcher process and database role, no thirteenth service. Indexed in [FP-000](FP-000_Full_Product_Requirements_Baseline.md). **[OWNER VALUE]** marks configuration with no default.

Platform facts were checked on 27 November 2026 against: Firebase Cloud Messaging for Flutter ([get started](https://firebase.google.com/docs/cloud-messaging/flutter/get-started)): an APNs authentication key must be uploaded to Firebase before iOS delivery, the push notification capability and the "Background fetch" and "Remote notifications" background modes must be enabled, and FCM on Android needs Android 7.0 or later with Google Play services. Android 13 and later require the `POST_NOTIFICATIONS` runtime permission ([Android notification permission](https://developer.android.com/develop/ui/views/notifications/notification-permission)). Apple App Review Guideline 4.5.4 governs push use (see FP-DST section 4).

## 1. Scope

Three channels: **in-app inbox** (always available to signed-in accounts), **push** (FCM on Android; FCM over APNs on iOS) and **transactional email** (existing Identity sender). Marketing messages are a separate category that needs the separate marketing consent of Decision B. SMS is out of scope.

## 2. Ownership and architecture

| Component | Owner | Notes |
| --- | --- | --- |
| Notification records, device tokens, preferences, templates | Identity (`notifications` tables in the Identity schema, own DB role `identity_notify_rt` with access to those tables only) | Identity already owns contact addresses and `NotificationPreferences` |
| Dispatcher | New Identity process role `notify-dispatch` (zero replicas until approved) | Consumes events, renders templates, calls providers through interfaces |
| Producers | Every service publishes **domain events it already owns** (ids only); no service calls a provider directly | DRY: one delivery path |
| Providers | `PushProvider` (FCM HTTP v1) and `EmailProvider` (existing SMTP) behind interfaces; a `NullProvider` for tests and staging | Credentials are Swarm secrets, never in Git |

## 3. Roles

Every signed-in account receives its own notifications only. Administrators see delivery metrics and can disable a template or a channel; they cannot read another person's inbox content in the console (only counts and ids for support). Moderators have no notification powers.

## 4. Notification catalogue (initial)

| Key | Trigger event | Default channels | Category |
| --- | --- | --- | --- |
| NT-MOD-OUTCOME | Moderation decision on the person's video, comment or report | Inbox, push | Account and safety (cannot be turned off for inbox) |
| NT-CR-MEASURE | Creator warning, restriction, suspension, appeal outcome (Decision F) | Inbox, push, email | Account and safety |
| NT-PV-REQUEST | Privacy request state changes, export ready, deletion complete (Decision C; completion email is GD-12) | Inbox, email | Account and safety |
| NT-SEC | New sign-in, password changed, MFA changed | Email, inbox | Security (cannot be turned off) |
| NT-CR-UPLOAD | Video processed, published, failed | Inbox, push | Activity |
| NT-EN-FOLLOW | New follower | Inbox | Activity |
| NT-CM | Reply to the person's comment; comment on the person's video (FP-CM) | Inbox, push | Activity |
| NT-BZ | Business inquiry message, verification decision, review response | Inbox, push | Activity |
| NT-EV | Ticket purchased, event changed or cancelled, refund state (FP-EV) | Inbox, push, email | Transactional |
| NT-FN | Statement available, payout state (FP-FN) | Inbox, email | Transactional |
| NT-AD | Campaign or creative review outcome (FP-AD) | Inbox, email | Transactional |
| NT-MKT | Marketing | Push, email | Marketing: only with marketing consent; off by default |

## 5. Functional requirements

| ID | Requirement | Pri | Acceptance criterion |
| --- | --- | --- | --- |
| NT-R-001 | Producers publish ids-only domain events; the dispatcher resolves recipients and content; no provider call exists outside the dispatcher | M | Static check: provider clients imported only by the dispatcher module |
| NT-R-002 | Every notification is created once per (event id, recipient, key): idempotent under redelivery | M | Redelivered event creates no duplicate inbox row or push |
| NT-R-003 | Inbox: list (cursor paginated), unread count, mark read, mark all read, delete; 90-day visibility [OWNER VALUE] `notifications.inbox_days` | M | API and widget tests |
| NT-R-004 | Preferences per category and channel; security and account-and-safety inbox items cannot be disabled; marketing requires the Decision B consent record | M | Preference matrix tests; marketing never sent without consent |
| NT-R-005 | Device registration stores the FCM token, platform, app version and locale, bound to the session; a token is removed on sign-out, session revocation, account erasure, or an `UNREGISTERED`/invalid-token answer from FCM | M | Revoked session gets no further pushes; invalid token row deleted |
| NT-R-006 | Push payloads carry no personal content beyond a short generic title and a deep link id; body text that names another person or contains message text is shown only after opening the app | M | Payload snapshot tests contain no names or message text |
| NT-R-007 | Android 13+ asks for `POST_NOTIFICATIONS` only after an in-app explanation, at a moment tied to a feature (for example after first follow or first upload), never at first launch | M | Widget test of the pre-prompt; denied state handled |
| NT-R-008 | iOS asks for notification authorization the same way; the app works fully when notifications are denied (Guideline 4.5.4) | M | Denied path test; no feature blocked |
| NT-R-009 | Deep links open the right screen after the server re-authorizes the target; a link to something the person can no longer see shows an unavailable state | M | Route tests with revoked access |
| NT-R-010 | Quiet hours per account [OWNER VALUE] default off; transactional and security items ignore quiet hours | S | Scheduling tests |
| NT-R-011 | Per-recipient rate limits per category [OWNER VALUE] `notifications.max_push_per_hour` (recommended 10 activity pushes); excess goes to inbox only | M | Burst test |
| NT-R-012 | Retries with backoff for provider errors; a bounded dead-letter path (reuses #311); delivery outcome recorded per channel | M | Provider outage test leaves inbox rows and retries push |
| NT-R-013 | Templates are versioned, localized (English first; others [OWNER VALUE]) and reviewed; wording that is legal in nature is marked pending legal review | M | Template registry with version in each record |
| NT-R-014 | Console: template enable or disable, channel kill switch, delivery metrics (sent, failed, invalid tokens) without content | M | Route-security matrix; MFA |
| NT-R-015 | Erasure removes inbox rows, tokens and preferences; access export includes inbox items and preferences | M | Erasure and export tests extended |
| NT-R-016 | Email keeps the existing sender, adds `List-Unsubscribe` on marketing only, and never includes secrets or one-time links in push | M | Email tests |

## 6. Security

Dispatcher role reads only notification tables and the minimal account fields (id, email, locale, preference); it cannot read credentials, sessions or MFA. FCM service-account key and APNs key are Swarm secrets owned by Identity; rotation procedure documented. Deep links are never trusted for authorization. Push tokens are treated as personal data and never logged in full (last 6 characters only).

## 7. Privacy

Lawful basis and retention per category are [OWNER VALUE] (ADR-020). Inbox content is the recipient's personal data. Notification about other people (follows, comments) shows public display names only. Store disclosures: push tokens and notification preferences are declared in the Play Data safety form and Apple privacy details (FP-DST).

## 8. API (proposed)

`GET /api/v1/me/notifications?cursor=`, `GET /api/v1/me/notifications/unread-count`, `POST /api/v1/me/notifications/{id}/read`, `POST /api/v1/me/notifications/read-all`, `DELETE /api/v1/me/notifications/{id}`, `PUT /api/v1/me/notification-preferences` (extends `me/preferences`), `POST /api/v1/me/devices` (register token), `DELETE /api/v1/me/devices/{device_id}`. Console: `GET /api/v1/admin/notifications/metrics`, `PUT /api/v1/admin/notifications/templates/{key}`.

## 9. Event contracts

The dispatcher consumes the producer events listed in section 4 (for example `moderation.decision_applied`, `kolovibe.engagement.comment.created.v1`, Business `business.inquiry_created`). It publishes `kolovibe.identity.notification.delivered.v1` (ids, channel, outcome) for metrics only. The event catalogue in #305 records each.

## 10. Flutter screens (M-420 to M-439; Figma frames first, #306)

M-420 inbox; M-421 empty and offline states; M-422 notification settings by category and channel; M-423 permission pre-prompt; M-424 permission denied guidance; M-425 quiet hours. The inbox entry is a bell in the shell header with an unread badge.

## 11. Failure scenarios

FCM unavailable (inbox still written, push retried); APNs key expired (push fails closed, alert raised through #145); token belongs to a signed-out device (deleted on first failure); event for an erased account (dropped and recorded); duplicate events (idempotent); recipient blocked the actor (FP-CM block suppresses the notification).

## 12. Non-functional

95% of activity pushes handed to FCM within 60 seconds of the source event on staging; inbox list p95 under 300 ms; dispatcher sustains [measured in Phase 10] events per second on staging hardware.

## 13. Choices still open

| Choice | Options | Recommendation |
| --- | --- | --- |
| NT-D1 Firebase project ownership | (a) a KoloVibe Google Cloud project owned by the owner's organization; (b) a personal project | (a): provider accounts are business assets (external provider approval, gate register section 6) |
| NT-D2 Marketing notifications in the first release | (a) none; (b) allowed with consent | (a) none until legal review |
| NT-D3 Values marked [OWNER VALUE] | — | Accept the recommended values for development |

## 14. Traceability

FP-NT-01; GD-03; DR-EV-18; DR-FIN-42; issues #307, #309.
