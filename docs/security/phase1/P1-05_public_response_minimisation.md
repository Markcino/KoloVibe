# P1-05 — Public responses expose only allow-listed fields

**Type:** regression guard (test only; no production code changed). **Baseline reference:** Phase 0 risk R-06, backlog B-06.

## Issue examined
Anonymous video and creator reads pass through the gateway from Content and Creators. A future change in an owning service could add an internal field (storage key, moderation reason, account id, email) and the gateway must not forward it. The 13 November review fixed `user_id` leakage for creators; no test covered the video endpoints or the broader class.

## Method and result
`services/gateway/tests/test_public_response_minimisation.py` (7 tests) feeds the gateway upstream records carrying each of twelve internal fields and asserts:

- video list/detail and creator detail/search answer 503 (refused, never forwarded) and the body contains none of the secret values;
- non-public states (`draft`, `review`, `removed`, `rejected`) and non-public visibility (`private`, `unlisted`) are refused;
- inactive creator profiles (`pending`, `restricted`, `suspended`) are refused;
- upstream failure text (hostnames, paths, credentials) is never reflected in an error body;
- creator detail never contains the account identifier.

No gap found at HEAD `bb79e1a`: the existing exact-key validation (`video_validation.valid_video`, `creators._validate_profile`) already refuses all cases. Mutation check: removing the extra-key rule in `valid_video` makes the new tests fail; reverted.

## Notes
- Video `creator_id` is the Creators profile id, not the Identity account id (`user_id`); mobile uses it to read the public creator profile.
- No API shape changed.
