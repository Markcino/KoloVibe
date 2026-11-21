# Automated copyright and safety pre-screen (R1)

Status: implemented in the Content media worker; **off by default**. Not legal advice. The policy needs legal review before public launch.

## Behaviour

After FFmpeg produces the playback rendition, the worker runs the configured screeners and records one decision:

| Result | Action | `rights_status` | Video state |
| --- | --- | --- | --- |
| Clean | automated approval (`approval_source = automated`) | `attested` | `published` (still private until the creator publishes) |
| Reused music above the mute threshold | the matched segments are muted with FFmpeg, then approved | `muted` | `published` |
| Duplicate or explicit content above the hide threshold, or music covering most of the video | held for a moderator | `hidden` | `review` |
| Uncertain score, screener failure, misconfiguration, or failed mute | held for a moderator | `flagged` | `review` |
| Random sample of otherwise clean uploads (`KOLOVIBE_SCREEN_SAMPLE_RATE`) | held for a moderator | as above | `review` |

Human removal and restoration set `removed` and `restored`. Reports, appeals and moderator scope, MFA and audit redaction are unchanged. Every finding and decision is stored in `ScreeningRecord` (provider, score, reason, muted segments; no media or raw payloads). Notifying creators and the appeal path for automated holds stay with the Moderation service and are not wired yet.

## Configuration

| Variable | Default | Meaning |
| --- | --- | --- |
| `KOLOVIBE_AUTO_SCREENING` | unset (off; every upload gets human review) | `1` enables screening |
| `KOLOVIBE_SCREENERS` | `exact_hash,pdq,chromaprint,nsfw` | add `music_id` for commercial-music identification |
| `KOLOVIBE_SCREEN_{DUPLICATE,NSFW}_{HIDE,REVIEW}` | 0.85 / 0.5 | score thresholds, 0 to 1 |
| `KOLOVIBE_SCREEN_MUSIC_{MUTE,REVIEW}` | 0.6 / 0.4 | score thresholds |
| `KOLOVIBE_SCREEN_MAX_MUTE_RATIO` | 0.8 | share of the video that may be muted before it is held instead |
| `KOLOVIBE_SCREEN_SAMPLE_RATE` | 0.05 | share of clean uploads sent to a human |
| `KOLOVIBE_AUDD_TOKEN_FILE` | unset | private (0600) file holding the AudD token |

Invalid values hold every video for review; they never skip screening. A takedown is added to the blocklist with `python manage.py block_video_fingerprints <video_id>`.

## Providers and licences

| Provider | Library | Licence | Notes |
| --- | --- | --- | --- |
| `exact_hash` | Python `hashlib` | PSF | Matches blocklisted files and other creators' uploads |
| `pdq` | `pdqhash` (Meta PDQ), `numpy`, `Pillow` | MIT (`pdqhash`) | Score is `1 - hamming / 64` of the median frame; linear scan, fine for the pilot |
| `chromaprint` | `fpcalc` binary (Chromaprint) | LGPL-2.1+ (verify when packaging) | Matches only our own takedown blocklist, not commercial catalogues |
| `nsfw` | `nudenet` (ONNX) | MIT | Optional dependency; may not run on the Alpine image |
| `music_id` | AudD HTTPS API (client is pluggable, e.g. for ACRCloud) | commercial service terms | Sends 12-second audio clips to a third party; disabled unless configured. Review its privacy terms and add it to the privacy notice first |

A screener whose dependency is missing raises an error that becomes a human hold, so enabling screening without installing a dependency is safe but slow.

## Limits

- Open-source tools cannot identify commercial songs without a licensed catalogue. `music_id` (a paid service) is the practical route, or restrict audio to original and royalty-free sounds.
- The media image needs `fpcalc` and the optional Python packages. The FFmpeg build now also enables the `volume` filter, the `wav` muxer and the `pcm_s16le` encoder.
- No automated system is perfect. Appeals, takedown handling and repeat-infringer policy still need human and legal ownership.
