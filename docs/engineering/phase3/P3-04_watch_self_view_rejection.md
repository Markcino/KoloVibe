# P3-04 — Self-views never qualify (regression tests)

**Type:** regression guard (test only). **Scope item:** Engagement "self-engagement rejection".

The rule exists twice: the Gateway refuses a viewer who is the video's creator (`pilot_points.watch`) and Engagement refuses `account_id == creator_user_id` itself (`watch.watch_api`). Until now only the gateway's *start* path and one incidental Engagement case exercised it; progress, session issuance and the "no side effects" half were not asserted.

## Tests
- Engagement `test_a_creator_cannot_qualify_views_of_their_own_video`: start and progress for the creator's own video return 403, issue no session, create no qualified watch, record no outbox event.
- Gateway `test_self_views_are_refused_for_progress_as_well_as_start_before_engagement_is_called`: the progress path returns 403 with no call to Engagement.
- Mutation checks: removing either guard fails the new test (and a pre-existing one that depended on it implicitly).

## Observation (not changed)
**Likes by the video's own creator are accepted.** A like is stored without any qualification or points event, so it is not an award vector; whether to forbid self-likes is a product decision and is left as is.
