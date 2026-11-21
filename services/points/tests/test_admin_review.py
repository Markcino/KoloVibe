import json
from uuid import uuid4
from django.test import TestCase, RequestFactory
from service.models import PointsEntry, AuditEvent
from service.admin_review import review


class PointsReviewTests(TestCase):
    def setUp(self):
        self.actor, self.account, self.other = uuid4(), uuid4(), uuid4()
        self.award = PointsEntry.objects.create(creator_user_id=self.account, source_decision_id=uuid4(),
            delta=5, entry_type="AWARD", rule_version="v1", reason_code="QUALIFIED_VIEW")
        self.reversal = PointsEntry.objects.create(creator_user_id=self.account, delta=-5, entry_type="REVERSAL",
            reversal_of=self.award, rule_version="v1", reason_code="REVIEWED")
        self.adjustment = PointsEntry.objects.create(creator_user_id=self.account, delta=2, entry_type="ADJUSTMENT",
            rule_version="v1", reason_code="REVIEWED")
        self.other_entry = PointsEntry.objects.create(creator_user_id=self.other, source_decision_id=uuid4(),
            delta=1, entry_type="AWARD", rule_version="v1", reason_code="QUALIFIED_VIEW")

    def call(self, operation="account", data=None, role="administrator", mfa=True, caller="gateway"):
        request = RequestFactory().post("/internal/points/admin/" + operation, {"actor_id": str(self.actor), "role": role,
            "mfa_verified": mfa, "data": data if data is not None else {"account_id": str(self.account)}}, content_type="application/json")
        request.service_caller = caller
        return review(request, operation)

    def test_balance_recomputes_from_ledger_and_reversal_state_is_read_only(self):
        payload = json.loads(self.call().content)
        self.assertEqual(payload["balance"], sum(PointsEntry.objects.filter(creator_user_id=self.account).values_list("delta", flat=True)))
        self.assertEqual(payload["balance"], 2)
        states = {item["id"]: item["reversal_review_state"] for item in payload["items"]}
        self.assertEqual(states[str(self.award.pk)], "reversed")
        self.assertEqual(states[str(self.reversal.pk)], "reversal")
        self.assertEqual(states[str(self.adjustment.pk)], "not_applicable")
        self.assertNotIn(str(self.other_entry.pk).encode(), self.call().content)
        self.assertEqual(PointsEntry.objects.count(), 4)
        self.assertTrue(AuditEvent.objects.filter(actor_id=self.actor, kind="points.review_read", subject_id=self.account).exists())
        repeated = json.loads(self.call(data={"account_id": str(self.account), "as_of": payload["as_of"]}).content)
        self.assertEqual(repeated, payload)

    def test_balances_filters_and_cross_account_cursor(self):
        payload = json.loads(self.call("balances", {}).content)
        self.assertEqual({item["account_id"]: item["balance"] for item in payload["items"]}, {str(self.account): 2, str(self.other): 1})
        awards = json.loads(self.call(data={"account_id": str(self.account), "status": "awards"}).content)
        self.assertEqual([item["id"] for item in awards["items"]], [str(self.award.pk)])
        self.assertEqual(awards["balance"], 2)
        self.assertEqual(self.call(data={"account_id": str(self.account), "cursor": str(self.other_entry.pk)}).status_code, 400)
        self.assertEqual(self.call(data={"account_id": str(uuid4())}).status_code, 404)
        self.assertEqual(self.call(data={"account_id": str(self.account), "status": "execute"}).status_code, 400)
        self.assertEqual(self.call("reverse", {}).status_code, 404)

    def test_all_other_roles_and_missing_mfa_are_denied_and_audited(self):
        for role in ("viewer", "creator", "moderator", "support", "finance", "worker"):
            self.assertEqual(self.call(role=role).status_code, 403)
        self.assertEqual(self.call(mfa=False).status_code, 403)
        self.assertEqual(self.call(caller="moderation").status_code, 403)
        self.assertEqual(AuditEvent.objects.filter(kind="points.review_denied").count(), 7)
        self.assertEqual(PointsEntry.objects.count(), 4)
