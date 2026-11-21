from datetime import timedelta
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch
from uuid import uuid4

from django.db import DatabaseError, transaction
from django.test import RequestFactory, TestCase, override_settings
from django.utils import timezone
from service.copyright import ATTESTATION_VERSION, analyze, route
from service.media_api import media_api
from service.models import (MediaUpload, OriginalityAttestation, PrescreenResult,
                            RightsEvent, Video)
from service.moderation import moderation_video


class CopyrightPipelineTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.account, self.creator = uuid4(), uuid4()
        self.video = Video.objects.create(creator_id=self.creator, title='Copyright test')
        self.policy = {'trusted': False, 'sample_percent': 100, 'policy_version': None}
        self.intent = {'creator_id': str(self.creator), 'account_id': str(self.account),
            'video_id': str(self.video.id), 'size_bytes': 10, 'idempotency_key': 'copyright-upload-001',
            'originality_attestation': {'version': ATTESTATION_VERSION, 'accepted': True}, 'review_policy': self.policy}

    def call(self, operation, data, *, moderation=False, caller=None):
        request = self.factory.post('/internal/', data, content_type='application/json')
        request.service_caller = caller or ('moderation' if moderation else 'gateway')
        return moderation_video(request, operation) if moderation else media_api(request, operation)

    @patch('service.media_storage.sign_upload', return_value='https://example.invalid/upload')
    def test_attestation_is_explicit_owner_bound_immutable_and_replay_safe(self, sign):
        for invalid in ({'accepted': False, 'version': ATTESTATION_VERSION}, {'accepted': True, 'version': 'old'}):
            self.assertEqual(self.call('intent', self.intent | {'originality_attestation': invalid}).status_code, 400)
        self.assertEqual(self.call('intent', self.intent | {'creator_id': str(uuid4())}).status_code, 404)
        self.assertEqual(self.call('intent', self.intent).status_code, 200)
        evidence = OriginalityAttestation.objects.get()
        stamp = evidence.accepted_at
        self.assertEqual((evidence.account_id, evidence.version), (self.account, ATTESTATION_VERSION))
        self.assertEqual(self.call('intent', self.intent).status_code, 200)
        self.assertEqual(OriginalityAttestation.objects.get().accepted_at, stamp)
        self.assertEqual(RightsEvent.objects.filter(event='originality_attested').count(), 1)
        with self.assertRaises(DatabaseError), transaction.atomic():
            OriginalityAttestation.objects.update(version='rewritten')
        with self.assertRaises(DatabaseError), transaction.atomic():
            RightsEvent.objects.all().delete()
        self.video.refresh_from_db()
        self.assertEqual(self.video.rights_status, 'attested')

    def test_legacy_records_are_flagged_without_fabricated_attestation(self):
        self.assertEqual(self.video.rights_status, 'flagged')
        self.assertFalse(OriginalityAttestation.objects.exists())

    def test_claim_takedown_restore_have_real_states_reasons_and_idempotent_receipts(self):
        now = timezone.now()
        Video.objects.filter(pk=self.video.id).update(state='published', visibility='public',
            provider_asset_id='playback/test.mp4', moderation_approved_at=now, published_at=now)
        report = str(uuid4())
        payload = {'video_id': str(self.video.id), 'command_id': report, 'report_id': report,
            'event': 'claim', 'actor_id': str(self.account), 'reason': 'Identified original work and allegation'}
        self.assertEqual(self.call('rights', payload, moderation=True).status_code, 200)
        self.video.refresh_from_db()
        self.assertEqual(self.video.rights_status, 'claimed')
        action = {'video_id': str(self.video.id), 'action_id': str(uuid4()), 'action': 'remove', 'revision': 0,
            'copyright': True, 'actor_id': str(self.account), 'reason': 'Confirmed copyright takedown after review', 'report_id': report}
        for _ in range(2):
            self.assertEqual(self.call('apply', action, moderation=True).status_code, 200)
        self.assertEqual(self.call('apply', action | {'reason': 'A conflicting decision reason'}, moderation=True).status_code, 409)
        self.video.refresh_from_db()
        self.assertEqual((self.video.rights_status, self.video.state, self.video.visibility), ('removed', 'removed', 'private'))
        restore = action | {'action_id': str(uuid4()), 'action': 'restore', 'revision': 1,
                            'reason': 'Independent reviewer accepted rights evidence'}
        self.assertEqual(self.call('apply', restore, moderation=True).status_code, 200)
        self.video.refresh_from_db()
        self.assertEqual(self.video.rights_status, 'restored')
        # Retrying old intake cannot reopen a dismissed/restored case.
        self.assertEqual(self.call('rights', payload, moderation=True).status_code, 200)
        self.video.refresh_from_db()
        self.assertEqual(self.video.rights_status, 'restored')
        self.assertEqual(RightsEvent.objects.count(), 3)
        self.assertEqual(self.call('rights', payload, moderation=True, caller='gateway').status_code, 403)

    def screen(self, *, rate=100, trusted=True, reasons=None, expired=False):
        upload = MediaUpload.objects.create(id=uuid4(), video=self.video, expected_bytes=10,
            expires_at=timezone.now() + timedelta(minutes=-1 if expired else 5))
        OriginalityAttestation.objects.create(upload_id=upload.id, video=self.video, account_id=self.account,
            version=ATTESTATION_VERSION, review_policy={'trusted': trusted, 'sample_percent': rate, 'policy_version': 'approved-test-v1'})
        with transaction.atomic():
            automatic = route(self.video, upload, {'sha256': 'a'*64, 'fingerprint': 'b'*64, 'audio': reasons or 'clear'})
        return automatic

    def test_clean_trusted_is_sampled_at_100_percent_and_explicit_unsampled_can_approve(self):
        self.assertFalse(self.screen())
        self.assertEqual(PrescreenResult.objects.get().disposition, 'sampled')

    def test_clean_unsampled_trusted_approval_and_expired_trust_fails_closed(self):
        self.assertTrue(self.screen(rate=0))

    def test_automatic_approval_commits_only_with_current_lease_and_stays_private(self):
        from service.media_processing import _claim, _finish
        self.video.state = 'processing'; self.video.save(update_fields=['state'])
        upload = MediaUpload.objects.create(id=uuid4(), video=self.video, expected_bytes=10,
            source_etag='"test"', expires_at=timezone.now() + timedelta(minutes=5))
        OriginalityAttestation.objects.create(upload_id=upload.id, video=self.video, account_id=self.account,
            version=ATTESTATION_VERSION, review_policy={'trusted': True, 'sample_percent': 0, 'policy_version': 'approved-test-v1'})
        reservation, token = _claim(self.video.id)
        result = {'sha256': 'd'*64, 'fingerprint': 'e'*64, 'audio': 'clear'}
        _finish(reservation, uuid4(), Video.State.REVIEW, key='playback/test', duration=1000, screening_result=result)
        self.assertFalse(PrescreenResult.objects.exists())
        _finish(reservation, token, Video.State.REVIEW, key='playback/test', duration=1000, screening_result=result)
        self.video.refresh_from_db()
        self.assertEqual((self.video.state, self.video.visibility, self.video.rights_status), ('published', 'private', 'attested'))
        self.assertIsNotNone(self.video.moderation_approved_at)
        self.assertEqual(RightsEvent.objects.filter(event='automatically_approved').count(), 1)

    def test_expired_policy_snapshot_never_autoapproves(self):
        self.assertFalse(self.screen(rate=0, expired=True))

    def test_untrusted_clean_is_never_automatically_approved(self):
        self.assertFalse(self.screen(rate=0, trusted=False))
        self.assertEqual(PrescreenResult.objects.get().disposition, 'untrusted')

    def test_active_claim_prevents_automatic_approval(self):
        self.video.rights_status = 'claimed'
        self.assertFalse(self.screen(rate=0))

    def test_unknown_audio_and_untrusted_creators_require_review(self):
        self.assertFalse(self.screen(rate=0, reasons='unavailable'))
        self.assertEqual(PrescreenResult.objects.get().reasons, ['audio_unavailable'])

    def test_exact_duplicate_goes_to_review_without_exposing_other_video_id(self):
        self.assertTrue(self.screen(rate=0))
        self.video = Video.objects.create(creator_id=uuid4(), title='Second copy')
        self.assertFalse(self.screen(rate=0))
        result = PrescreenResult.objects.get(video=self.video)
        self.assertIn('exact_duplicate', result.reasons)
        self.assertNotIn('first_video_id', result.reasons)

    def test_real_hashes_and_reused_pluggable_audio_provider(self):
        from service.screening import ProviderResult, Finding, MUSIC
        with TemporaryDirectory() as directory:
            source = Path(directory)/'source.mp4'
            source.write_bytes(b'first source')
            plugin = Mock(); plugin.screen.return_value = ProviderResult(fingerprints=[('chromaprint', '1,2,3')])
            first = analyze(source, audio_provider=plugin)
            self.assertEqual(first['audio'], 'clear')
            plugin.screen.return_value = ProviderResult([Finding('chromaprint', MUSIC, 1.0, 'reference_match')])
            self.assertEqual(analyze(source, audio_provider=plugin)['audio'], 'matched')
            source.write_bytes(b'second source')
            self.assertNotEqual(analyze(source, audio_provider=plugin)['sha256'], first['sha256'])
            plugin.screen.side_effect = RuntimeError('provider unavailable')
            self.assertEqual(analyze(source, audio_provider=plugin)['audio'], 'unavailable')
