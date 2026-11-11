import json
from uuid import uuid4

from django.test import RequestFactory, TestCase

from service.follows import follow_api, followed_creators
from service.models import CreatorFollow


class CreatorFollowTests(TestCase):
    def setUp(self):
        self.account_id = str(uuid4())
        self.creator_id = str(uuid4())

    def call(self, operation, *, account_id=None, caller="gateway"):
        request = RequestFactory().post("/internal/follows", data=json.dumps({
            "operation": operation, "account_id": account_id or self.account_id,
            "creator_id": self.creator_id,
        }), content_type="application/json")
        request.service_caller = caller
        return follow_api(request)

    def test_repeats_are_idempotent_and_scoped_to_account(self):
        other = str(uuid4())
        self.assertEqual(json.loads(self.call("follow").content)["following"], True)
        self.assertEqual(json.loads(self.call("follow").content)["following"], True)
        self.assertEqual(self.call("follow", account_id=other).status_code, 200)
        self.assertEqual(CreatorFollow.objects.count(), 2)
        self.assertEqual(self.call("unfollow").status_code, 200)
        self.assertEqual(self.call("unfollow").status_code, 200)
        self.assertEqual(json.loads(self.call("status").content)["following"], False)
        self.assertTrue(CreatorFollow.objects.filter(account_id=other).exists())

    def test_requires_gateway_and_rejects_invalid_intent(self):
        self.assertEqual(self.call("follow", caller="identity").status_code, 403)
        self.assertEqual(self.call("award").status_code, 400)
        self.assertFalse(CreatorFollow.objects.exists())

    def test_membership_returns_only_current_accounts_follows(self):
        other = str(uuid4())
        self.call("follow")
        self.call("follow", account_id=other)
        request = RequestFactory().post("/internal/follows/membership", data=json.dumps({
            "account_id": self.account_id,
            "creator_ids": [self.creator_id, str(uuid4())],
        }), content_type="application/json")
        request.service_caller = "gateway"
        self.assertEqual(json.loads(followed_creators(request).content),
                         {"creator_ids": [self.creator_id]})
        request.service_caller = "identity"
        self.assertEqual(followed_creators(request).status_code, 403)
