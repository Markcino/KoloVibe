# P3-03 — Creator upload to authorized playback, as one chain

**Type:** integration journey test (no production code changed). **Scope items:** upload contracts, media validation, secure R2 initiation, private storage, completion, FFmpeg processing, status transitions, moderation before publication, authorized playback, signed URL expiry, creator management.

`services/content/tests/test_upload_to_playback_journey.py` runs Content's real code and database through the whole creator journey. R2 is an in-memory private bucket keyed exactly as production keys it (`originals/<upload>.mp4`, `playback/<upload>/<lease>.mp4|jpg`); every signed grant is recorded. When FFmpeg is on the sandbox PATH (the media worker image in CI) the **real encoder and poster renderer** run; otherwise deterministic stand-ins keep every other boundary exercised (locally FFmpeg is not on that PATH; the real path was run once by widening the sandbox PATH and passed).

Asserted at each step:
1. **Draft:** metadata only; no playback.
2. **Upload initiation:** the grant is for the private original key, size-bound with create-only headers (`Content-Length`, `If-None-Match: *`); a wrong attestation version is refused (400).
3. **Completion:** refused while the object is missing and when it does not match the reserved size (a truncated upload); accepted only for the exact object, then the video is `processing` and one task is queued; still not playable.
4. **FFmpeg processing:** the rendition and poster are stored privately, the video is `review` and `private`, duration is recorded, the lease is released, and neither playback nor tracked-playback facts are available; no playback grant has been signed.
5. **Creator cannot skip moderation:** publish before approval is refused (409).
6. **Moderation approval:** only the Moderation caller (the gateway is refused, 403), against the current revision, idempotent on replay; approved is `published` but still `private`, so still not playable.
7. **Publication:** playback becomes available as a 300-second signed grant for the stored rendition; tracked playback returns exactly `creator_id`, `duration_ms`, `revision` (what Engagement needs) and no URL.
8. **Unpublish:** playback and tracked playback close again.
9. **Another creator** cannot publish, unpublish, complete, read or inspect the video (404).

Mutation check: letting playback ignore `visibility` fails step 6 (`200 != 404`); reverted.

## How the full acceptance journey is covered
Upload → R2 → FFmpeg → moderation → publication → playback is this test. Playback facts → qualified view → Engagement outbox → broker message → Points inbox → receipt → append-only ledger is P3-02 (#207), with the gateway's watch route composing the two (self-view rule in #208, signed-account and metadata test already present). **There is no single live run through all services and a real RabbitMQ and R2; that needs the owner's staging environment, and nothing has been recorded as staging-accepted.**
