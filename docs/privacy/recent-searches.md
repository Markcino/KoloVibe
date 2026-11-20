# Recent searches — device-local history (D-5, screen M-021)

**Status:** specification and privacy behaviour, written before the feature (product direction D-5). The feature is implemented in the same change and is the only place this data exists.

## What it is

A short list of the words a signed-in person typed into KoloVibe search on this phone, so they can run the same search again with one tap. It is a convenience for the person using the phone. It is **not** a profile, a recommendation signal or analytics.

## Rules

| Topic | Rule |
| --- | --- |
| Where it lives | Only on the device, in the operating system's secure store (iOS Keychain / Android Keystore through `flutter_secure_storage`). Never written to files, logs, crash reports, screenshots or backups made by the app. |
| What is stored | The search text exactly as submitted (trimmed, 1–100 characters, control characters rejected) and the time it was submitted. No video, creator, result, location or device identifier is stored with it. |
| Who it belongs to | One list **per signed-in account**, stored under a key derived from the account id. Another account on the same phone never sees it, and a signed-out person has no list. |
| Size | At most **8** entries; the newest replaces the oldest. Searching a phrase again moves it to the top instead of adding a copy (comparison ignores case and surrounding spaces). |
| Retention | An entry expires **14 days** after it was last searched. Expired entries are deleted when the list is read or written, never shown. |
| Visible control | The M-021 list has a **Clear** action that deletes every entry for the current account immediately, with no confirmation step that could be missed and an announcement for assistive technology. Each entry also has a remove button. |
| Sign-out | Signing out deletes that account's list, including when the server cannot confirm the sign-out. If a session ends any other way (expiry, password reset elsewhere) the list is simply not shown while signed out and still expires after 14 days. |
| Server | **Never sent.** Search requests carry only the query the person just submitted, exactly as before; the list itself is not uploaded, synchronised or backed up. |
| Analytics and logging | The app has no analytics. The list and its entries are never written to logs or error messages. |
| Failure | If the secure store is unavailable the list is empty and search still works; nothing is kept in memory beyond the screen. |
| Sensitive text | Searches may reveal interests. The list is therefore opt-out by clearing, is capped and short-lived, and is not shown on any screen except M-021. |

## Honest limits

- On iOS, Keychain items can survive deleting the app. Entries still expire after 14 days and are purged on the next read, and the signed-out state shows no list, but a person who reinstalls within 14 days and signs in to the same account will see their recent searches again. This is stated in the privacy information inside the app.
- Anyone who can unlock the phone and open the app as that account can see the list. Clear it before lending the phone.

## Where the person is told

- M-021: a one-line note under the list — "Saved on this phone for 14 days. Not sent to KoloVibe." — and the **Clear** button.
- Terms & Privacy (M-088) and Privacy settings (M-084) topics: "Recent searches stay on your phone, are kept for 14 days, and can be cleared."
- This document is the reference for the published privacy notice; the published notice must carry the same wording before the feature reaches a public build.

## Verification

`apps/mobile/test/search_history_test.dart` covers: cap, newest first, duplicate promotion, 14-day expiry (boundary), rejection of empty / over-length / control-character text, clear, per-account separation, deletion on sign-out (including when sign-out fails on the server), unavailable store, nothing leaving the device (no request is made by saving, listing or clearing), and the M-021 widget (list, tap to search, remove, Clear, no list when signed out).
