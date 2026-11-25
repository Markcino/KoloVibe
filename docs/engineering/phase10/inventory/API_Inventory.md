# API inventory (generated)

Source: `docs/architecture/DOC-205_OpenAPI_3_1_DRAFT.yaml` (the contract of record; draft status). **158 operations**, 22 anonymous, 136 bearer-authenticated. By `x-implementation` marker: local 144, local-only 3, staging-gated 9, unmarked 2.

Gateway route parity with this contract is enforced by `scripts/test_gateway_route_contract.py`; Business parity across Gateway, service, console and Dart by `scripts/test_business_contract_reconciliation.py`.

## Operations by tag

| Tag | Operations |
| --- | --- |
| Administration | 9 |
| Business | 57 |
| Content | 15 |
| Creators | 12 |
| Discovery | 1 |
| Engagement | 9 |
| Identity | 27 |
| Internal Events | 1 |
| Moderation | 21 |
| Operations | 3 |
| Points | 3 |

## Administration

| Method | Path | Tag | Auth | Roles | Implementation | operationId |
| --- | --- | --- | --- | --- | --- | --- |
| GET | /moderation/totals | Administration | bearer | moderator, administrator | local | read_scoped_moderation_totals |
| GET | /engagement/fraud-holds | Administration | bearer | moderator, administrator | local | read_active_scoped_fraud_holds |
| GET | /admin/moderation/assignments | Administration | bearer | administrator | local | list_moderator_assignments |
| POST | /admin/moderation/assignments | Administration | bearer | administrator | local | set_moderator_assignment |
| GET | /admin/moderation/assignments/summary | Administration | bearer | administrator | local | summarize_moderator_assignments |
| POST | /admin/accounts/lookup | Administration | bearer | administrator | local | lookup_creator_candidate |
| GET | /admin/audit | Administration | bearer | moderator, administrator | local | get_admin_audit |
| GET | /admin/points/balances | Administration | bearer | administrator | local | get_admin_points_balances |
| GET | /admin/points/accounts/{account_id} | Administration | bearer | administrator | local | get_admin_points_account |

## Business

| Method | Path | Tag | Auth | Roles | Implementation | operationId |
| --- | --- | --- | --- | --- | --- | --- |
| GET | /me/businesses | Business | bearer | viewer, creator | local | get_my_businesses |
| POST | /me/businesses | Business | bearer | viewer, creator | local | post_my_business |
| GET | /me/businesses/{business_id} | Business | bearer | viewer, creator | local | get_my_business |
| GET | /me/businesses/{business_id}/members | Business | bearer | viewer, creator | local | get_my_business_members |
| POST | /me/businesses/{business_id}/members/invitations | Business | bearer | viewer, creator | local | post_my_business_staff_invitation |
| DELETE | /me/businesses/{business_id}/members/invitations/{invitation_id} | Business | bearer | viewer, creator | local | delete_my_business_staff_invitation |
| DELETE | /me/businesses/{business_id}/members/{member_id} | Business | bearer | viewer, creator | local | delete_my_business_member |
| POST | /me/businesses/{business_id}/leave | Business | bearer | viewer, creator | local | post_my_business_leave |
| POST | /me/business-invitations/redeem | Business | bearer | viewer, creator | local | post_business_invitation_redeem |
| PUT | /admin/business-registration-grants/{account_id} | Business | bearer | administrator | local | put_business_registration_grant |
| GET | /me/businesses/{business_id}/verification | Business | bearer | viewer, creator | local | get_my_business_verification |
| POST | /me/businesses/{business_id}/verification | Business | bearer | viewer, creator | local | post_my_business_verification |
| POST | /me/businesses/{business_id}/verification/evidence | Business | bearer | viewer, creator | local | post_my_business_verification_evidence |
| GET | /moderation/business-verifications | Business | bearer | moderator, administrator | local | get_business_verification_queue |
| GET | /moderation/business-verifications/{case_id} | Business | bearer | moderator, administrator | local | get_business_verification_case |
| POST | /moderation/business-verifications/{case_id}/claim | Business | bearer | moderator, administrator | local | post_business_verification_claim |
| POST | /moderation/business-verifications/{case_id}/decision | Business | bearer | moderator, administrator | local | post_business_verification_decision |
| PUT | /admin/business-reviewer-grants | Business | bearer | administrator | local | put_business_reviewer_grant |
| GET | /me/businesses/{business_id}/profile | Business | bearer | viewer, creator | local | get_my_business_profile |
| PATCH | /me/businesses/{business_id}/profile | Business | bearer | viewer, creator | local | patch_my_business_profile |
| POST | /me/businesses/{business_id}/profile/submit | Business | bearer | viewer, creator | local | post_my_business_profile_submit |
| PUT | /me/businesses/{business_id}/hours | Business | bearer | viewer, creator | local | put_my_business_hours |
| GET | /business-categories | Business | anonymous | viewer, creator, moderator, administrator | local | get_business_categories |
| PUT | /admin/business-categories/{slug} | Business | bearer | administrator | local | put_business_category |
| GET | /moderation/business-profile-revisions | Business | bearer | moderator, administrator | local | get_business_profile_queue |
| GET | /moderation/business-profile-revisions/{revision_id} | Business | bearer | moderator, administrator | local | get_business_profile_revision |
| POST | /moderation/business-profile-revisions/{revision_id}/decision | Business | bearer | moderator, administrator | local | post_business_profile_decision |
| GET | /businesses | Business | anonymous | anonymous | local | get_businesses |
| GET | /businesses/{business_id} | Business | anonymous | anonymous | local | get_business |
| GET | /me/businesses/{business_id}/listing | Business | bearer | viewer, creator | local | get_my_business_listing |
| POST | /me/businesses/{business_id}/listing/publish | Business | bearer | viewer, creator | local | post_my_business_listing_publish |
| POST | /me/businesses/{business_id}/listing/unpublish | Business | bearer | viewer, creator | local | post_my_business_listing_unpublish |
| POST | /businesses/{business_id}/inquiries | Business | bearer | viewer, creator | local | post_business_inquiry |
| GET | /me/inquiries | Business | bearer | viewer, creator | local | get_my_inquiries |
| GET | /me/inquiries/{thread_id} | Business | bearer | viewer, creator | local | get_my_inquiry |
| POST | /me/inquiries/{thread_id}/messages | Business | bearer | viewer, creator | local | post_my_inquiry_message |
| POST | /me/inquiries/{thread_id}/close | Business | bearer | viewer, creator | local | post_my_inquiry_close |
| POST | /me/inquiries/{thread_id}/confirm | Business | bearer | viewer, creator | local | post_my_inquiry_confirm |
| GET | /me/businesses/{business_id}/inquiries | Business | bearer | viewer, creator | local | get_my_business_inquiries |
| GET | /me/businesses/{business_id}/inquiries/{thread_id} | Business | bearer | viewer, creator | local | get_my_business_inquiry |
| POST | /me/businesses/{business_id}/inquiries/{thread_id}/messages | Business | bearer | viewer, creator | local | post_my_business_inquiry_reply |
| POST | /me/businesses/{business_id}/inquiries/{thread_id}/close | Business | bearer | viewer, creator | local | post_my_business_inquiry_close |
| POST | /me/businesses/{business_id}/inquiries/{thread_id}/confirm | Business | bearer | viewer, creator | local | post_my_business_inquiry_confirm |
| POST | /me/businesses/{business_id}/inquiries/{thread_id}/block | Business | bearer | viewer, creator | local | post_my_business_inquiry_block |
| GET | /businesses/{business_id}/reviews | Business | anonymous | anonymous | local | get_business_reviews |
| POST | /businesses/{business_id}/reviews | Business | bearer | viewer, creator | local | post_business_review |
| GET | /me/reviews | Business | bearer | viewer, creator | local | get_my_reviews |
| PATCH | /me/reviews/{review_id} | Business | bearer | viewer, creator | local | patch_my_review |
| DELETE | /me/reviews/{review_id} | Business | bearer | viewer, creator | local | delete_my_review |
| PUT | /me/businesses/{business_id}/reviews/{review_id}/response | Business | bearer | viewer, creator | local | put_my_business_review_response |
| DELETE | /me/businesses/{business_id}/reviews/{review_id}/response | Business | bearer | viewer, creator | local | delete_my_business_review_response |
| POST | /me/businesses/{business_id}/review-invitations | Business | bearer | viewer, creator | local | post_my_business_review_invitation |
| DELETE | /me/businesses/{business_id}/review-invitations/{invitation_id} | Business | bearer | viewer, creator | local | delete_my_business_review_invitation |
| POST | /business-reports | Business | bearer | viewer, creator | local | post_business_report |
| GET | /moderation/business-reports | Business | bearer | moderator, administrator | local | get_business_report_queue |
| GET | /moderation/business-reports/{report_id} | Business | bearer | moderator, administrator | local | get_business_report |
| POST | /moderation/business-reports/{report_id}/decision | Business | bearer | moderator, administrator | local | post_business_report_decision |

## Content

| Method | Path | Tag | Auth | Roles | Implementation | operationId |
| --- | --- | --- | --- | --- | --- | --- |
| GET | /creators/me/analytics | Content | bearer | viewer, creator | local | get_own_creator_analytics |
| GET | /creators/me/videos/{video_id}/analytics | Content | bearer | viewer, creator | local | get_own_video_analytics |
| GET | /creators/me/videos | Content | bearer |  | local | get_own_videos |
| GET | /creators/me/videos/{video_id} | Content | bearer | viewer, creator | local | get_own_video_detail |
| GET | /videos | Content | anonymous | anonymous | local | get__videos |
| POST | /videos | Content | bearer | viewer, creator | local | post__videos |
| GET | /videos/{video_id} | Content | anonymous | anonymous | local | get__videos_video_id |
| PATCH | /videos/{video_id} | Content | bearer | viewer, creator | local | patch__videos_video_id |
| DELETE | /videos/{video_id} | Content | bearer | viewer, creator | local | delete_own_video |
| POST | /videos/{video_id}/upload-intents | Content | bearer | viewer, creator | local | post__videos_video_id_upload-intents |
| GET | /videos/{video_id}/upload-status | Content | bearer |  | local | get_video_upload_status |
| POST | /videos/{video_id}/upload-status | Content | bearer |  | local | post_video_upload_complete |
| POST | /videos/{video_id}/publish | Content | bearer | viewer, creator | local | post__videos_video_id_publish |
| POST | /videos/{video_id}/unpublish | Content | bearer | viewer, creator | local | post__videos_video_id_unpublish |
| GET | /videos/{video_id}/playback | Content | bearer |  | local-only | get__videos_video_id_playback |

## Creators

| Method | Path | Tag | Auth | Roles | Implementation | operationId |
| --- | --- | --- | --- | --- | --- | --- |
| GET | /creator-invitations | Creators | bearer | administrator | staging-gated | get_creator_invitations |
| POST | /creator-invitations | Creators | bearer | moderator, administrator | staging-gated | post_creator_invitation |
| POST | /creator-invitations/{account_id}/revoke | Creators | bearer | administrator | staging-gated | post_creator_invitation_revoke |
| GET | /creator-applications | Creators | bearer | moderator, administrator | staging-gated | get_creator_applications |
| POST | /creator-applications/{account_id}/decision | Creators | bearer | moderator, administrator | staging-gated | post_creator_application_decision |
| GET | /creators/me/application | Creators | bearer | viewer, creator | staging-gated | get_own_creator_application |
| POST | /creators/me/application | Creators | bearer | viewer, creator | staging-gated | post_own_creator_application |
| GET | /creators/me/upload-eligibility | Creators | bearer | viewer, creator | staging-gated | get_own_creator_upload_eligibility |
| GET | /creators/search | Creators | anonymous | anonymous | local | searchCreators |
| GET | /creators/{creator_id} | Creators | anonymous | anonymous | local | get__creators_creator_id |
| GET | /creators/me | Creators | bearer | creator | local | getMyCreatorProfile |
| PATCH | /creators/me | Creators | bearer | creator | local | patch__creators_me |

## Discovery

| Method | Path | Tag | Auth | Roles | Implementation | operationId |
| --- | --- | --- | --- | --- | --- | --- |
| GET | /videos/following | Discovery | bearer |  | local | get_following_videos |

## Engagement

| Method | Path | Tag | Auth | Roles | Implementation | operationId |
| --- | --- | --- | --- | --- | --- | --- |
| GET | /creators/{creator_id}/follow | Engagement | bearer |  | local | get_creator_follow_status |
| PUT | /creators/{creator_id}/follow | Engagement | bearer |  | local | follow_creator |
| DELETE | /creators/{creator_id}/follow | Engagement | bearer |  | local | unfollow_creator |
| POST | /videos/{video_id}/watch-sessions | Engagement | bearer |  | local-only | startPilotWatchSession |
| POST | /engagement/watch-events | Engagement | bearer |  | local-only | post__engagement_watch-events |
| GET | /videos/{video_id}/like | Engagement | bearer |  | local | get__videos_video_id_like |
| PUT | /videos/{video_id}/like | Engagement | bearer |  | local | put__videos_video_id_like |
| DELETE | /videos/{video_id}/like | Engagement | bearer |  | local | delete__videos_video_id_like |
| POST | /videos/{video_id}/shares | Engagement | bearer | viewer, creator | local | recordVideoShare |

## Identity

| Method | Path | Tag | Auth | Roles | Implementation | operationId |
| --- | --- | --- | --- | --- | --- | --- |
| POST | /auth/register | Identity | anonymous | anonymous | local | post__auth_register |
| POST | /auth/verification/resend | Identity | anonymous | anonymous | local | resendEmailVerification |
| POST | /auth/verify | Identity | anonymous | anonymous | local | post__auth_verify |
| POST | /auth/password/reset-request | Identity | anonymous | anonymous | local | requestPasswordReset |
| POST | /auth/password/reset | Identity | anonymous | anonymous | local | resetPassword |
| POST | /auth/login | Identity | anonymous | anonymous | local | post__auth_login |
| POST | /auth/mfa/verify | Identity | anonymous | anonymous | staging-gated | post__auth_mfa_verify |
| POST | /auth/refresh | Identity | anonymous | anonymous | local | post__auth_refresh |
| POST | /auth/logout | Identity | anonymous | anonymous | local | post__auth_logout |
| GET | /me/preferences | Identity | bearer |  | local | getMyPreferences |
| PATCH | /me/preferences | Identity | bearer |  | local | updateMyPreferences |
| GET | /me/privacy-requests | Identity | bearer |  | local | listMyPrivacyRequests |
| POST | /me/privacy-requests | Identity | bearer |  | local | requestMyPrivacyAction |
| POST | /me/reauthenticate | Identity | bearer |  | local | reauthenticateMyAccount |
| GET | /me/sessions | Identity | bearer |  | local | listMySessions |
| PATCH | /me/password | Identity | bearer |  | local | changeMyPassword |
| DELETE | /me/sessions/{session_id} | Identity | bearer |  | local | revokeMySession |
| GET | /me | Identity | bearer |  | local | get__me |
| PATCH | /me | Identity | bearer |  | local | updateMyProfile |
| GET | /admin/moderator-invitations | Identity | bearer |  | local | get_admin_moderator_invitations |
| POST | /admin/moderator-invitations | Identity | bearer |  | local | post_admin_moderator_invitations |
| POST | /admin/moderator-invitations/{invitation_id}/revoke | Identity | bearer |  | local | post_admin_moderator_invitation_revoke |
| POST | /auth/moderator-invitations/setup | Identity | anonymous | anonymous | local | post_auth_moderator_invitation_setup |
| POST | /auth/moderator-invitations/complete | Identity | anonymous | anonymous | local | post_auth_moderator_invitation_complete |
| POST | /internal/auth/moderator-invitations | Identity | bearer |  | local | post_internal_auth_moderator_invitations |
| POST | /internal/auth/moderator-invitations/setup | Identity | bearer |  | local | post_internal_auth_moderator_invitations_setup |
| POST | /internal/auth/moderator-invitations/complete | Identity | bearer |  | local | post_internal_auth_moderator_invitations_complete |

## Internal Events

| Method | Path | Tag | Auth | Roles | Implementation | operationId |
| --- | --- | --- | --- | --- | --- | --- |
| POST | /internal/security-events | Internal Events | bearer |  | local | ingestAuditEvent |

## Moderation

| Method | Path | Tag | Auth | Roles | Implementation | operationId |
| --- | --- | --- | --- | --- | --- | --- |
| POST | /reports | Moderation | bearer | viewer, creator, moderator, administrator | local | post__reports |
| GET | /me/reports | Moderation | bearer | viewer, creator, moderator, administrator | local | get_own_reports |
| GET | /me/reports/{report_id} | Moderation | bearer | viewer, creator, moderator, administrator | local | get_own_report |
| GET | /me/appeals | Moderation | bearer | viewer, creator | local | get_own_appeals |
| GET | /me/appeals/{appeal_id} | Moderation | bearer | viewer, creator | local | get_own_appeal |
| GET | /moderation/reports | Moderation | bearer | moderator, administrator | local | get__moderation_reports |
| POST | /moderation/reports/{report_id}/decisions | Moderation | bearer | moderator, administrator | local | post__moderation_reports_report_id_decisions |
| GET | /moderation/videos | Moderation | bearer | moderator, administrator | local | get_pilot_video_review_queue |
| POST | /moderation/videos/{video_id}/decisions | Moderation | bearer | moderator, administrator | local | post_pilot_video_decision |
| POST | /videos/{video_id}/appeals | Moderation | bearer | viewer, creator | local | post_pilot_video_appeal |
| GET | /moderation/appeals | Moderation | bearer | moderator, administrator | local | get_pilot_appeal_queue |
| POST | /moderation/appeals/{appeal_id}/decisions | Moderation | bearer | moderator, administrator | local | post_pilot_appeal_decision |
| GET | /creators/me/videos/{video_id}/notice | Moderation | bearer | creator | local | getOwnVideoNotice |
| GET | /me/standing | Moderation | bearer |  | local | getOwnStanding |
| GET | /moderation/videos/{video_id} | Moderation | bearer | moderator, administrator | local | get_reviewer_videos_detail |
| GET | /moderation/reports/{report_id} | Moderation | bearer | moderator, administrator | local | get_reviewer_reports_detail |
| GET | /moderation/appeals/{appeal_id} | Moderation | bearer | moderator, administrator | local | get_reviewer_appeals_detail |
| GET | /moderation/previews/{preview_id} | Moderation | bearer | moderator, administrator | local | get_reviewer_preview |
| POST | /copyright/reports | Moderation | bearer | viewer, creator, moderator, administrator | local | post_copyright_report |
| POST | /videos/{video_id}/counter-notices | Moderation | bearer | creator | local | post_copyright_counter_notice |
| GET | /creators/me/copyright | Moderation | bearer | creator | local | get_own_copyright_strikes |

## Operations

| Method | Path | Tag | Auth | Roles | Implementation | operationId |
| --- | --- | --- | --- | --- | --- | --- |
| GET | /app/compatibility | Operations | anonymous | anonymous | local | getAppCompatibility |
| GET | /health/live | Operations | anonymous | anonymous |  | get__health_live |
| GET | /health/ready | Operations | anonymous | anonymous |  | get__health_ready |

## Points

| Method | Path | Tag | Auth | Roles | Implementation | operationId |
| --- | --- | --- | --- | --- | --- | --- |
| GET | /creators/me/points | Points | bearer |  | local | get__creators_me_points |
| GET | /creators/me/points/entries | Points | bearer |  | local | get__creators_me_points_entries |
| GET | /creators/me/points/entries/{entry_id} | Points | bearer |  | local | getOwnPointsEntry |
