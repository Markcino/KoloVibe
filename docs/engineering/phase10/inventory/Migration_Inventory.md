# Database migration inventory (generated)

60 migrations across the services and the console. Each service owns its schema and role; there are no cross-service foreign keys. `makemigrations --check --dry-run` is clean for every service and the console (CI step 'Service checks'); every migration is applied to a real TLS PostgreSQL by `scripts/test_postgres_foundations.py` and `scripts/test_business_postgres.py`.

| Service | Count | Migrations in order |
| --- | --- | --- |
| identity | 11 | 0001 initial, 0002 loginthrottle_usedrefreshtoken_emailverification_and_more, 0003 internal_nonce, 0004 securityevent_loginsession_authenticated_role_and_more, 0005 security_event_guard, 0006 account_email_verified_at, 0007 passwordreset, 0008 notificationpreferences_privacyrequest, 0009 reauthentication_open_privacy_requests, 0010 six_digit_codes, 0011 moderator_invitations |
| creators | 6 | 0001 initial, 0002 internal_nonce, 0003 pilot_creator_application, 0004 creator_profile_fields, 0005 copyright_review_policy, 0006 invitation_revocation_and_events |
| content | 11 | 0001 initial, 0002 internal_nonce, 0003 stream_upload_reservation, 0004 moderation_receipt, 0005 moderation_revision_default, 0005 r2_media_upload, 0006 merge_r2_revision_default, 0007 video_duration_ms, 0008 video_metadata_and_soft_delete, 0009 automated_screening, 0010 copyright_pipeline |
| engagement | 6 | 0001 initial, 0002 watch_session, 0003 creator_follow, 0004 watch_video_qualification_index, 0005 discovery_shares_and_qualified_history, 0006 fraud_holds |
| points | 6 | 0001 initial, 0002 append_only_guard, 0003 dailyawardcount, 0004 pointsentry_video_id_qualificationreceipt, 0005 audit_evidence, 0006 review_actor |
| moderation | 6 | 0001 pilot_moderation, 0002 internal_nonce, 0003 auditevent_moderationaction_creator_id_and_more, 0004 moderator_assignments, 0005 reviewer_preview, 0006 copyright_notices |
| audit | 6 | 0001 initial, 0002 security_event_guard, 0003 internal_nonce, 0004 securityevent_producer_securityevent_subject_id_and_more, 0005 audit_read_grants, 0006 business_producer |
| business | 7 | 0001 initial, 0002 internal_nonce, 0003 verification, 0004 profiles, 0005 listings, 0006 inquiries, 0007 reviews |
| gateway | 0 | none (no database) |
| web (console) | 1 | 0001 initial |
