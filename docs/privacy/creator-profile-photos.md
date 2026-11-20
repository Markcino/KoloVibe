# Creator profile photos — moderation and privacy rules (D-10)

**Status: rules written for owner approval; upload is DISABLED.** Nothing in the app, gateway or services accepts a photo yet. These rules must be agreed before any upload code is enabled, and the feature stays behind `KOLOVIBE_CREATOR_PHOTOS=0` until the moderation queue exists and the items under “Before enabling” are met.

## Scope

Only a **reviewed, active creator's public profile photo**. Not personal-account photos, not video posters, not cover art. Viewers and unreviewed creators have the initial-letter avatar. No unrestricted upload path is added for personal accounts.

## Rules

| Topic | Rule |
| --- | --- |
| Who | The creator who owns the profile (the server resolves ownership from the session; the client never names a creator id). |
| Accepted input | JPEG or PNG, at most **5 MB**, decoded width and height each **256–4096 px**, a single static frame. HEIC and animated formats are refused (the app converts on the device). The declared type, the file signature and the decoded content must agree. |
| Validation | The server decodes the image (bounded pixel count, no external resources) and rejects anything that does not decode, is animated or exceeds the limits. Failure is a clean 400 that never echoes the content. |
| Metadata | Never stored or served: the server **re-encodes** to JPEG, so EXIF (including GPS and device data), ICC profiles, comments and embedded thumbnails are dropped. Original bytes are deleted after processing. |
| Stored forms | Two square JPEGs only: 512 px and 128 px, centre-cropped to what the creator chose. |
| Storage | Cloudflare R2, **private** bucket, keys `creator-photos/<creator id>/<photo id>/<size>.jpg`. No public bucket access, no listing. |
| States | `pending` → `approved` or `rejected`; `removed` by the creator or by moderation. Only `approved` is ever public. |
| Moderation | A moderator (MFA-protected, audited) approves or rejects each new photo from a queue showing the 512 px image. A decision records reviewer, time and reason code. A creator cannot approve their own photo. |
| Public delivery | The public creator JSON carries `photo_url` only for the **approved** photo, as a short-lived signed URL from the gateway; otherwise `null` and the app draws the initial avatar. An unapproved image is never reachable by URL, by guessing an id or by listing. |
| Owner view | The owner sees their own pending photo (owner-only signed URL) and its status; nobody else does. |
| Replacement | A new upload becomes `pending`. The earlier **approved** photo stays public until the new one is approved; then it is deleted. Rejection leaves the earlier approved photo in place. |
| Removal | The creator can remove their photo at any time; objects are deleted immediately and the avatar falls back to the initial. Suspension, account deletion or removal of the creator profile also removes it. |
| Abuse limits | At most 5 uploads per creator per day and 1 pending photo at a time; the request body is capped before it is read; the usual gateway limits apply. |
| Logging and analytics | Image bytes, file names and EXIF are never logged. Audit events carry ids and decisions only. |
| Rights | The creator confirms they may use the image and that it shows no one who has not agreed. Moderation can reject for rights, impersonation, minors in an unsafe context, nudity, hate or violence. Rejections and removals follow the existing appeal path. |
| Retention | Approved photos last as long as the profile; rejected photos are deleted after 30 days (kept only for the appeal window). |

## Before enabling

1. Moderation queue and decision endpoints, with tests for object-level access (a creator cannot read, approve or delete another creator's photo; a viewer cannot read a pending photo).
2. Decode-and-re-encode worker, with tests for corrupt, mismatched-type, oversized, animated, EXIF-bearing and decompression-bomb inputs and proof that EXIF is gone.
3. Private R2 bucket policy review (no public read, scoped credentials).
4. Contract (`POST` and `DELETE /creators/me/photo`, `photo_url`, `photo_status`) and Figma states for pick, crop, uploading, pending, approved, rejected and remove.
5. Owner approval of this document and of the published privacy notice wording.

## Implementation status

**Not implemented.** The app shows the initial avatar and the note that photos are unavailable (M-013, M-038, M-039, M-079, M-080) until this ships; those notes are accurate today.
