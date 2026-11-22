import json
from unittest.mock import patch
from uuid import uuid4
from django.http import JsonResponse
from django.test import RequestFactory, SimpleTestCase
from service.moderation import moderation_endpoint
from service.media import issue_video_upload
from .test_videos import Response


class CopyrightGatewayTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.account, self.creator, self.video = [str(uuid4()) for _ in range(3)]
        self.actor = self.enterContext(patch('service.moderation.authenticated_actor', return_value=(self.account, 'creator')))
        self.owner = self.enterContext(patch('service.moderation.creator_ownership', return_value=JsonResponse({'creator_id': self.creator})))
        self.peer = self.enterContext(patch('service.moderation.signed_internal_request'))

    def test_counter_notice_binds_creator_to_session_and_requires_idempotency_key(self):
        receipt = {'id': str(uuid4()), 'video_id': self.video, 'status': 'open', 'created_at': '2026-11-21T10:00:00Z'}
        self.peer.return_value = Response(json.dumps(receipt).encode())
        data = {'reason': 'My independently supplied rights evidence.', 'accuracy_attested': True}
        request = self.factory.post('/counter-notices', data, content_type='application/json', HTTP_IDEMPOTENCY_KEY='counter-gateway-001')
        self.assertEqual(moderation_endpoint(request, 'counter_notice', self.video).status_code, 200)
        forwarded = json.loads(self.peer.call_args.kwargs['payload'])
        self.assertEqual((forwarded['actor_id'], forwarded['data']['creator_id']), (self.account, self.creator))
        forged = self.factory.post('/counter-notices', data | {'creator_id': str(uuid4())}, content_type='application/json', HTTP_IDEMPOTENCY_KEY='counter-gateway-001')
        self.assertEqual(moderation_endpoint(forged, 'counter_notice', self.video).status_code, 400)
        self.assertEqual(moderation_endpoint(self.factory.post('/counter-notices', data, content_type='application/json'), 'counter_notice', self.video).status_code, 400)

    def test_strike_count_has_no_caller_selected_creator_and_no_other_role_access(self):
        self.peer.return_value = Response(b'{"strike_count":2}')
        self.assertEqual(moderation_endpoint(self.factory.get('/copyright'), 'copyright_status').status_code, 200)
        forwarded = json.loads(self.peer.call_args.kwargs['payload'])
        self.assertEqual(forwarded['data'], {'creator_id': self.creator})
        self.assertEqual(moderation_endpoint(self.factory.get('/copyright?creator_id=foreign'), 'copyright_status').status_code, 400)
        self.actor.return_value = (self.account, 'viewer')
        self.assertEqual(moderation_endpoint(self.factory.get('/copyright'), 'copyright_status').status_code, 403)

    def test_upload_rejects_missing_consent_and_forged_trust_before_content(self):
        with patch('service.media.creator_eligibility', return_value=JsonResponse({'upload_eligible': True, 'creator_id': self.creator})), patch('service.media.forward_media') as peer:
            for data in ({'size_bytes': 10}, {'size_bytes': 10, 'originality_attestation': {'version': 'R1-originality-v1', 'accepted': False}},
                         {'size_bytes': 10, 'originality_attestation': {'version': 'R1-originality-v1', 'accepted': True}, 'review_policy': {'trusted': True}}):
                request = self.factory.post('/intent', data, content_type='application/json', HTTP_IDEMPOTENCY_KEY='upload-gateway-001')
                self.assertEqual(issue_video_upload(request, self.video).status_code, 400)
            peer.assert_not_called()

    def test_cross_video_counter_response_is_rejected(self):
        self.peer.return_value = Response(json.dumps({'id': str(uuid4()), 'video_id': str(uuid4()), 'status': 'open', 'created_at': '2026-11-21T10:00:00Z'}).encode())
        request = self.factory.post('/counter', {'reason': 'Rights evidence for this specific video.', 'accuracy_attested': True}, content_type='application/json', HTTP_IDEMPOTENCY_KEY='counter-gateway-001')
        self.assertEqual(moderation_endpoint(request, 'counter_notice', self.video).status_code, 503)
