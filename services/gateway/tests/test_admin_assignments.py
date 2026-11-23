import json
from unittest.mock import patch
from uuid import uuid4

from django.http import JsonResponse
from django.test import RequestFactory, SimpleTestCase

from service import admin_reads
from service.admin_contracts import valid_assignment, valid_assignment_list
from service.invitation_contracts import valid_page


class AssignmentGatewayTests(SimpleTestCase):
    def setUp(self):
        self.admin, self.moderator, self.target = str(uuid4()), str(uuid4()), str(uuid4())
        self.body = {"scope": "reports", "target_id": self.target, "moderator_id": self.moderator, "active": True}

    def post(self, body=None, role="administrator"):
        request = RequestFactory().post("/assignments", json.dumps(body or self.body), content_type="application/json")
        with patch("service.admin_reads.principal", return_value=(self.admin, role)), \
             patch("service.admin_reads.forward", return_value=JsonResponse(self.body)) as forward:
            return admin_reads.moderation_assignments(request), forward

    def test_only_administrators_reach_moderation(self):
        for role in ("moderator", "viewer"):
            response, forward = self.post(role=role)
            self.assertEqual(response.status_code, 403)
            forward.assert_not_called()
        response, forward = self.post()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(forward.call_args.args[:5], ("moderation", "/internal/moderation/assignment_set",
                                                      self.admin, "administrator", self.body))

    def test_unauthenticated_principal_is_returned_unchanged(self):
        with patch("service.admin_reads.principal", return_value=JsonResponse({}, status=401)), \
             patch("service.admin_reads.forward") as forward:
            response = admin_reads.moderation_assignments(RequestFactory().get("/assignments"))
        self.assertEqual(response.status_code, 401)
        forward.assert_not_called()

    def test_invalid_writes_never_reach_moderation(self):
        for change in ({"scope": "users"}, {"active": "yes"}, {"target_id": "x"}, {"moderator_id": self.moderator.upper()},
                       {"extra": 1}, {"actor_id": self.admin}):
            response, forward = self.post({**self.body, **change})
            self.assertEqual(response.status_code, 400, change)
            forward.assert_not_called()
        missing = dict(self.body)
        missing.pop("active")
        self.assertEqual(self.post(missing)[0].status_code, 400)

    def test_list_requires_exact_query_and_binds_the_response(self):
        def get(query):
            with patch("service.admin_reads.principal", return_value=(self.admin, "administrator")), \
                 patch("service.admin_reads.forward", return_value=JsonResponse({})) as forward:
                return admin_reads.moderation_assignments(RequestFactory().get("/assignments", query)), forward
        for query in ({}, {"scope": "reports"}, {"scope": "x", "target": self.target},
                      {"scope": "reports", "target": "x"}, {"scope": "reports", "target": self.target, "more": "1"}):
            response, forward = get(query)
            self.assertEqual(response.status_code, 400, query)
            forward.assert_not_called()
        response, forward = get({"scope": "reports", "target": self.target})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(forward.call_args.args[5].__name__, "<lambda>")
        validate = forward.call_args.args[5]
        good = {"scope": "reports", "target_id": self.target, "items": [{"moderator_id": self.moderator}]}
        self.assertTrue(validate(good))
        self.assertFalse(validate({**good, "target_id": str(uuid4())}))

    def test_response_contracts_are_strict(self):
        good = {"scope": "reports", "target_id": self.target, "items": [{"moderator_id": self.moderator}]}
        self.assertTrue(valid_assignment_list(good, "reports", self.target))
        for bad in ({**good, "scope": "videos"}, {**good, "extra": 1}, {**good, "items": [{"moderator_id": "x"}]},
                    {**good, "items": [{"moderator_id": self.moderator, "email": "a@b.test"}]},
                    {**good, "items": [{"moderator_id": self.moderator}] * 2}):
            self.assertFalse(valid_assignment_list(bad, "reports", self.target), bad)
        self.assertTrue(valid_assignment(self.body, self.body))
        self.assertFalse(valid_assignment({**self.body, "active": False}, self.body))
        self.assertFalse(valid_assignment({**self.body, "active": 1}, {**self.body, "active": 1}))
        self.assertFalse(valid_assignment({**self.body, "extra": 1}, self.body))

    def test_invitation_rows_expose_account_id_only_when_accepted(self):
        row = {"id": str(uuid4()), "display_name": "Ria", "email_masked": "r***@example.test",
               "status": "pending", "expires_at": "2026-11-24T10:00:00+00:00"}
        page = lambda *rows: {"items": list(rows), "next_cursor": None}
        self.assertTrue(valid_page(page(row)))
        self.assertTrue(valid_page(page({**row, "status": "accepted", "account_id": self.moderator})))
        self.assertFalse(valid_page(page({**row, "status": "accepted"})))
        self.assertFalse(valid_page(page({**row, "account_id": self.moderator})))
        self.assertFalse(valid_page(page({**row, "status": "accepted", "account_id": "x"})))
