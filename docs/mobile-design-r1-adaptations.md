# Approved R1 adaptations to the mobile design

These are product directions the owner approved for R1. The approved Figma page **Mobile Designed** is
unchanged; each adaptation is a frame on the page **R1 adaptations (pending owner review)** in the same file
([ANaV0jnwjZ0LEcByTc98HP](https://www.figma.com/design/ANaV0jnwjZ0LEcByTc98HP/KoloVibe?node-id=60-2)), with a change-record frame
that repeats this table. Code, tests and parity evidence are linked by screen ID in
[`mobile-design-parity.md`](mobile-design-parity.md). Tracking issue: #100.

| ID | Screen | Approved adaptation | Figma frame | Code |
| --- | --- | --- | --- | --- |
| D-3 | M-034 (and the M-033 hint, M-089 help row, M-096) | R1 has one FFmpeg rendition. The Data Saver sheet, its switch, the “Data Saver is on” badge and every claim that playback changes quality are removed. The state says the connection is slow, that the video keeps loading, gives connection guidance (stronger signal, Wi-Fi or mobile data, normal carrier charges) and offers **Try again** and **Keep waiting**. | nodes `60:321` (M-034), `64:2` (M-033), `64:73` (M-096), `64:136` (M-089) | `slow_connection_sheet.dart`, `live_video_screen.dart` |
| D-4 | M-019 | The hero is the newest eligible original (the service's newest-created public, published, moderation-approved video), labelled **LATEST ORIGINAL · category**. No human curation is implied; the spotlight action is **View**, not Follow. | node `60:403` | `discovery_catalog_screen.dart` |
| D-7 | M-078 (eligible) | New states in the established system: statement entry, validation, sending, failure (statement kept) and receipt. The unavailable state is kept. The server alone decides eligibility, authorises the owner and rejects duplicates; a submit action is never drawn for an ineligible notice. **Not visually approved until the owner reviews the frames.** | nodes `60:3`, `60:68`, `60:133`, `60:196`, `60:259` | separate pull request |

## D-3 behaviour

- After 5 seconds of buffering the slow-connection sheet appears over a dimmed video (full-screen player) or as a card (detail page).
- **Try again** abandons the pending attempt, asks the service for a fresh playback grant and starts again. A late success or failure of the abandoned attempt can neither take over the screen nor leak a player.
- **Keep waiting** hides the sheet and keeps loading; the spinner reads “Still loading on a slow connection…”. No request is made.
- Nothing is stored and nothing about rendition or quality is claimed.

## D-4 definition

“Latest original” is the first record of `GET /videos?sort=recent`: public, published, moderation-approved, not deleted, ordered by creation time then id (newest first). The phone does not re-rank. Hero, “Fresh perspectives” and the spotlight (the hero's creator) all come from that list.
