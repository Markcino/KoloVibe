import json
from datetime import timedelta
from uuid import uuid4
from django.test import TestCase, RequestFactory
from django.utils import timezone
from service.models import FraudHold
from service.fraud_holds import read_holds


class FraudHoldTests(TestCase):
    def setUp(self):
        self.video, self.other = uuid4(), uuid4()
        for video, active, expiry in ((self.video, True, None), (self.other, True, None),
                (self.video, False, None), (self.video, True, timezone.now() - timedelta(seconds=1))):
            FraudHold.objects.create(account_id=uuid4(), video_id=video, active=active, expires_at=expiry, reason_code="REVIEW")

    def call(self, role="moderator", mfa=True, scope=None, caller="gateway"):
        request = RequestFactory().post("/internal/engagement/fraud-holds", {"actor_id": str(uuid4()), "role": role,
            "mfa_verified": mfa, "data": {"video_ids": [str(self.video)] if scope is None and role == "moderator" else scope,
                                         "cursor": None}}, content_type="application/json")
        request.service_caller = caller
        return read_holds(request)

    def test_active_totals_and_records_are_scoped_and_redacted(self):
        data = json.loads(self.call().content)
        self.assertEqual(data["total"], 1)
        self.assertEqual([item["video_id"] for item in data["items"]], [str(self.video)])
        self.assertNotIn("account_id", data["items"][0])
        self.assertEqual(json.loads(self.call(role="administrator").content)["total"], 2)
        self.assertEqual(json.loads(self.call(scope=[]).content)["total"], 0)

    def test_roles_mfa_and_signed_caller_are_required(self):
        for role, mfa, caller in (("viewer", True, "gateway"), ("support", True, "gateway"),
                ("moderator", False, "gateway"), ("administrator", True, "content")):
            self.assertEqual(self.call(role=role, mfa=mfa, caller=caller).status_code, 403)
