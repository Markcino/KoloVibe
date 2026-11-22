import json
from uuid import uuid4
from django.test import RequestFactory, TestCase
from django.utils import timezone
from service.models import CreatorApplication, CreatorProfile, CopyrightReviewPolicy
from service.onboarding import onboarding, POLICY_VERSION


class CopyrightPolicyTests(TestCase):
    def setUp(self):
        self.actor, self.admin = uuid4(), uuid4()
        self.creator = CreatorProfile.objects.create(user_id=self.actor, handle='rights_test', status='active', reviewed_at=timezone.now())
        CreatorApplication.objects.create(account_id=self.actor, invited_by=self.admin, profile=self.creator,
            status='approved', attestation_version=POLICY_VERSION)

    def call(self, actor=None):
        request = RequestFactory().post('/internal/', {'actor_id': str(actor or self.actor), 'role': 'creator', 'data': {}}, content_type='application/json')
        request.service_caller = 'gateway'
        return json.loads(onboarding(request, 'review_policy').content)

    def test_creator_approval_does_not_imply_trust_or_sampling_exemption(self):
        self.assertEqual(self.call(), {'account_id': str(self.actor), 'creator_id': str(self.creator.id),
            'trusted': False, 'sample_percent': 100, 'policy_version': None})

    def test_explicit_policy_and_live_eligibility_are_required_and_bound_to_account(self):
        policy = CopyrightReviewPolicy.objects.create(creator=self.creator, active=True, approved_by=self.admin,
            approved_at=timezone.now(), version='owner-approved-v1', reason='Reviewed trust grant')
        self.assertTrue(self.call()['trusted'])
        self.assertEqual(self.call()['sample_percent'], 100)
        self.assertFalse(self.call(uuid4())['trusted'])
        self.creator.restricted_at = timezone.now(); self.creator.status='restricted'; self.creator.save()
        self.assertFalse(self.call()['trusted'])

    def test_self_approved_policy_never_confers_trust(self):
        CopyrightReviewPolicy.objects.create(creator=self.creator, active=True, approved_by=self.actor,
            approved_at=timezone.now(), version='invalid-self-v1', reason='Self approval')
        self.assertFalse(self.call()['trusted'])
