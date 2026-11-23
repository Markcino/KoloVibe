# P2-03 — Search within the creator's own video library

**Type:** additive feature (Content + Gateway + DOC-205 together). **Backlog:** M-040 gap recorded in the 20 Nov parity review ("no search field: no query parameter"); Content and discovery capability in the Phase 2 scope.

## Contract
`GET /creators/me/videos` gains an optional `q` query parameter (1–100 characters after trimming, no control characters). It composes with `state` and `cursor`; clients reuse the same `q` and `state` while following a cursor. Existing requests without `q` behave exactly as before, so this is a non-breaking, additive change. DOC-205 is updated and still validates.

## Behaviour
- **Content** (`media_api._library`): case-insensitive match on title or description, applied only to the caller's own non-deleted videos. `%` and `_` are literal. The cursor anchor is looked up inside the filtered view, so a cursor from outside it is rejected with 400 and never confirms the existence of other videos.
- **Gateway** (`own_video_library`): accepts `q` (repeats and unknown parameters are still rejected), validates and trims it before any internal call, and rejects an upstream page containing a video whose title and description do not contain `q` (503, as it already does for a state mismatch).
- Ownership is unchanged: the creator id still comes from the authenticated session and is never client-supplied.

## Tests
- Content (`test_library_search_matches_only_own_undeleted_videos_and_composes_with_state_and_cursor`): matches title and description case-insensitively with trimming, excludes other creators' and deleted videos, composes with `state`, literal `%`/`_`, out-of-view cursor rejected, invalid `q` (empty, blank, 101 chars, control char, non-string, list) rejected.
- Gateway (`test_owner_library_search_is_validated_forwarded_trimmed_and_checked_in_the_response`): trimmed value forwarded, non-matching upstream item refused, invalid or repeated `q` and extra parameters rejected with no internal call.
- Content suite 124 OK, gateway suite 184 OK; DOC-205 validates with `openapi_spec_validator`.

## Not done
Mobile adoption (a search field in M-040) is client work outside this phase.
