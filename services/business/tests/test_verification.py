"""B2: verification requests, reviewer grants, decisions, separation of duties and status."""
from datetime import timedelta
from unittest.mock import patch
from uuid import uuid4

from service import limits

from service.models import AuditEvent, Business, ReviewerGrant, VerificationCase, VerificationDecision
from .support import BusinessTestCase

EVIDENCE = [{"kind": "registration_number", "value": "LBR-000123"}]


class VerificationBase(BusinessTestCase):
    def setUp(self):
        super().setUp()
        self.owner, self.biz = self.register()
        self.bid = self.biz["id"]
        self.admin, self.reviewer = uuid4(), uuid4()

    def grant(self, reviewer=None, scope="verification", target=None, active=True):
        data = {"reviewer_account_id": str(reviewer or self.reviewer), "scope": scope, "active": active}
        if target is not None:
            data["target_business_id"] = target
        return self.call("reviewer_grant", data, actor=self.admin, role="administrator", mfa=True)

    def submit(self, owner=None, bid=None, evidence=EVIDENCE, **kw):
        return self.call("verification_submit", {"business_id": bid or self.bid, "method": "manual_review",
                                                 "declaration": True, "evidence": evidence}, actor=owner or self.owner, **kw)

    def rv(self, operation, data=None, actor=None, role="moderator", mfa=True, **kw):
        return self.call(operation, data or {}, actor=actor or self.reviewer, role=role, mfa=mfa, **kw)

    def case_id(self):
        return str(VerificationCase.objects.latest("submitted_at").id)

    def verify(self, decision="verify", code="documents_checked"):
        cid = self.case_id()
        self.assertEqual(self.rv("verification_claim", {"case_id": cid})[0], 200)
        return self.rv("verification_decide", {"case_id": cid, "decision": decision, "reason_code": code})


class SubmissionTests(VerificationBase):
    def test_owner_submits_once_and_state_moves_with_audit(self):
        status, body = self.submit()
        self.assertEqual((status, body["state"], body["reason_code"]), (201, "submitted", None))
        self.assertEqual(self.call("get_mine", {"business_id": self.bid}, actor=self.owner)[1]["state"], "submitted")
        self.assertEqual(self.submit()[0], 409)  # already submitted: state machine refuses
        self.assertEqual(VerificationCase.objects.count(), 1)
        self.assertEqual(AuditEvent.objects.filter(kind="business.verification_submitted").count(), 1)

    def test_only_the_owner_may_submit_or_read_status_and_foreign_ids_are_404(self):
        staff = self.add_staff(self.owner, self.bid)
        self.assertEqual(self.submit(owner=staff)[0], 404)
        self.assertEqual(self.call("verification_status", {"business_id": self.bid}, actor=staff)[0], 404)
        _, other = self.register(name="Other Shop")
        self.assertEqual(self.submit(owner=self.owner, bid=other["id"])[0], 404)
        self.assertEqual(self.call("verification_status", {"business_id": other["id"]}, actor=self.owner)[0], 404)
        self.assertEqual(VerificationCase.objects.count(), 0)

    @patch.dict(limits.BUDGETS, {"verification_submit": (100, timedelta(days=1))})
    def test_inputs_are_bounded_and_authority_cannot_be_named(self):
        base = {"business_id": self.bid, "method": "manual_review", "declaration": True, "evidence": EVIDENCE}
        for change in ({"declaration": False}, {"declaration": "yes"}, {"evidence": []}, {"evidence": EVIDENCE * 6},
                       {"evidence": [{"kind": "Bad Kind", "value": "x" * 5}]},
                       {"evidence": [{"kind": "doc", "value": "x"}]}, {"evidence": [{"kind": "doc", "value": "v" * 301}]},
                       {"evidence": [{"kind": "doc", "value": "ok value", "state": "accepted"}]},
                       {"method": "NOT VALID"}, {"state": "verified"}, {"verified": True}, {"submitted_by": str(uuid4())}):
            self.assertEqual(self.call("verification_submit", {**base, **change}, actor=self.owner)[0], 400, change)
        self.assertEqual(VerificationCase.objects.count(), 0)
        self.assertEqual(Business.objects.get(pk=self.bid).state, "draft")

    def test_submissions_are_throttled(self):
        statuses = [self.call("verification_submit", {"business_id": self.bid}, actor=self.owner)[0]
                    for _ in range(limits.BUDGETS["verification_submit"][0] + 1)]
        self.assertEqual(statuses[-1], 429)

    def test_status_shows_only_applicant_safe_fields(self):
        self.assertEqual(self.call("verification_status", {"business_id": self.bid}, actor=self.owner)[1],
                         {"state": "none", "submitted_at": None, "decided_at": None, "reason_code": None})
        self.submit()
        self.grant()
        self.verify("reject", "documents_unclear")
        _, body = self.call("verification_status", {"business_id": self.bid}, actor=self.owner)
        self.assertEqual(set(body), {"state", "submitted_at", "decided_at", "reason_code"})
        self.assertEqual((body["state"], body["reason_code"]), ("rejected", "documents_unclear"))
        self.assertNotIn("note", str(body))

    def test_duplicates_are_flagged_for_the_reviewer_not_rejected(self):
        _, twin = self.register(name="Monrovia  Bakery!")  # same normalised name as the fixture business
        self.assertEqual(self.submit()[0], 201)
        self.grant()
        status, body = self.rv("verification_case", {"case_id": self.case_id()})
        self.assertEqual(status, 200)
        self.assertEqual([c["business_id"] for c in body["duplicate_candidates"]], [twin["id"]])
        self.assertEqual(body["legal_name"], "Monrovia Bakery Ltd")


class ReviewerTests(VerificationBase):
    def setUp(self):
        super().setUp()
        self.submit()

    def test_grants_are_administrator_mfa_only_and_never_self(self):
        data = {"reviewer_account_id": str(self.reviewer), "scope": "verification", "active": True}
        self.assertEqual(self.call("reviewer_grant", data, actor=self.admin, role="administrator")[0], 403)
        for role in ("viewer", "creator", "moderator"):
            self.assertEqual(self.call("reviewer_grant", data, actor=self.admin, role=role, mfa=True)[0], 403)
        self.assertEqual(self.call("reviewer_grant", {**data, "reviewer_account_id": str(self.admin)}, actor=self.admin,
                                   role="administrator", mfa=True)[1]["code"], "self_grant")
        self.assertEqual(self.call("reviewer_grant", {**data, "scope": "everything"}, actor=self.admin,
                                   role="administrator", mfa=True)[0], 400)
        self.assertEqual(self.call("reviewer_grant", {**data, "target_business_id": str(uuid4())}, actor=self.admin,
                                   role="administrator", mfa=True)[0], 404)
        self.assertEqual(self.grant()[0], 200)
        self.assertEqual(self.grant()[0], 200)  # upsert, one row
        self.assertEqual(ReviewerGrant.objects.count(), 1)

    def test_reviewer_routes_need_role_and_mfa(self):
        self.grant()
        cid = self.case_id()
        for operation, data in (("verification_queue", {}), ("verification_case", {"case_id": cid}),
                                ("verification_claim", {"case_id": cid}),
                                ("verification_decide", {"case_id": cid, "decision": "verify", "reason_code": "ok_code"})):
            for role, mfa in (("viewer", True), ("creator", True), ("moderator", False), ("administrator", False)):
                self.assertEqual(self.rv(operation, data, role=role, mfa=mfa)[0], 403, (operation, role, mfa))

    def test_a_reviewer_without_a_grant_sees_nothing_and_cannot_act(self):
        cid = self.case_id()
        self.assertEqual(self.rv("verification_queue")[1]["items"], [])
        unknown = str(uuid4())
        for operation, data in (("verification_case", {}), ("verification_claim", {}),
                                ("verification_decide", {"decision": "verify", "reason_code": "ok_code"})):
            self.assertEqual(self.rv(operation, {"case_id": cid, **data}), self.rv(operation, {"case_id": unknown, **data}))
            self.assertEqual(self.rv(operation, {"case_id": cid, **data})[0], 404)
        self.assertEqual(Business.objects.get(pk=self.bid).state, "submitted")

    def test_a_grant_for_another_business_does_not_help(self):
        _, other = self.register(name="Unrelated Co")
        self.grant(target=other["id"])
        self.assertEqual(self.rv("verification_queue")[1]["items"], [])
        self.assertEqual(self.rv("verification_case", {"case_id": self.case_id()})[0], 404)

    def test_queue_case_claim_decide_and_state_follow_the_machine(self):
        self.grant()
        _, queue = self.rv("verification_queue")
        self.assertEqual([i["business_id"] for i in queue["items"]], [self.bid])
        self.assertNotIn("legal_name", str(queue))
        cid = self.case_id()
        self.assertEqual(self.rv("verification_decide", {"case_id": cid, "decision": "verify", "reason_code": "ok_code"})[1]["code"],
                         "claim_required")
        self.assertEqual(self.rv("verification_claim", {"case_id": cid})[1]["state"], "under_review")
        other = uuid4()
        self.grant(other)
        self.assertEqual(self.rv("verification_decide", {"case_id": cid, "decision": "verify", "reason_code": "ok_code"},
                                 actor=other)[1]["code"], "claim_required")  # claimed by someone else
        status, body = self.rv("verification_decide", {"case_id": cid, "decision": "verify", "reason_code": "documents_checked",
                                                       "note": "Registry entry matched."})
        self.assertEqual((status, body["state"], body["business_state"]), (200, "verified", "verified"))
        self.assertTrue(self.call("get_mine", {"business_id": self.bid}, actor=self.owner)[1]["verified"])
        self.assertEqual(VerificationDecision.objects.count(), 1)
        self.assertEqual(self.rv("verification_decide", {"case_id": cid, "decision": "reject", "reason_code": "ok_code"})[0], 409)

    def test_decisions_are_idempotent_and_conflicting_keys_are_refused(self):
        self.grant()
        cid = self.case_id()
        self.rv("verification_claim", {"case_id": cid})
        data = {"case_id": cid, "decision": "verify", "reason_code": "documents_checked"}
        first = self.rv("verification_decide", data, key="decision-key-0123456789")
        again = self.rv("verification_decide", data, key="decision-key-0123456789")
        self.assertEqual(first, again)
        self.assertEqual(VerificationDecision.objects.count(), 1)
        self.assertEqual(self.rv("verification_decide", {**data, "decision": "reject"}, key="decision-key-0123456789")[1]["code"],
                         "idempotency_conflict")

    def test_decision_inputs_are_validated(self):
        self.grant()
        cid = self.case_id()
        self.rv("verification_claim", {"case_id": cid})
        for bad in ({"decision": "approve"}, {"decision": "verify", "reason_code": "BAD CODE"}, {"decision": "verify"},
                    {"decision": "verify", "reason_code": "ok_code", "note": "n" * 501},
                    {"decision": "verify", "reason_code": "ok_code", "business_state": "verified"}):
            self.assertEqual(self.rv("verification_decide", {"case_id": cid, **bad})[0], 400, bad)
        self.assertEqual(Business.objects.get(pk=self.bid).state, "under_review")

    def test_conflict_of_interest_blocks_the_submitter_creator_and_members(self):
        for conflicted in (self.owner, self.reviewer):
            Business.objects.filter(pk=self.bid).update(created_by_account_id=conflicted)
            self.grant(conflicted)
            cid = self.case_id()
            for operation, data in (("verification_case", {}), ("verification_claim", {}),
                                    ("verification_decide", {"decision": "verify", "reason_code": "ok_code"})):
                self.assertEqual(self.rv(operation, {"case_id": cid, **data}, actor=conflicted)[0], 404, (conflicted, operation))
        VerificationCase.objects.filter(pk=self.case_id()).update(submitted_by_account_id=self.reviewer)
        Business.objects.filter(pk=self.bid).update(created_by_account_id=uuid4())
        self.assertEqual(self.rv("verification_claim", {"case_id": self.case_id()})[0], 404)
        self.assertEqual(Business.objects.get(pk=self.bid).state, "submitted")

    def test_request_info_then_owner_response_returns_to_review_without_a_second_case(self):
        self.grant()
        self.verify("request_info", "need_registration_proof")
        self.assertEqual(self.call("get_mine", {"business_id": self.bid}, actor=self.owner)[1]["state"], "needs_info")
        self.assertEqual(self.submit()[1]["code"], "use_respond")
        status, body = self.call("verification_respond", {"business_id": self.bid, "evidence": EVIDENCE}, actor=self.owner)
        self.assertEqual((status, body["state"]), (200, "submitted"))
        self.assertEqual(VerificationCase.objects.count(), 1)
        self.assertEqual(VerificationCase.objects.get().evidence.count(), 2)
        self.assertEqual(self.call("verification_respond", {"business_id": self.bid, "evidence": EVIDENCE}, actor=self.owner)[0], 409)

    def test_revocation_applies_only_to_verified_and_allows_a_fresh_request(self):
        self.grant()
        cid = self.case_id()
        self.assertEqual(self.rv("verification_decide", {"case_id": cid, "decision": "revoke", "reason_code": "ok_code"})[0], 409)
        self.verify()
        status, body = self.rv("verification_decide", {"case_id": cid, "decision": "revoke", "reason_code": "fraud_confirmed"})
        self.assertEqual((status, body["business_state"]), (200, "revoked"))
        self.assertFalse(self.call("get_mine", {"business_id": self.bid}, actor=self.owner)[1]["verified"])
        self.assertEqual(self.submit()[0], 201)

    def test_every_step_is_audited_with_ids_only(self):
        self.grant()
        self.verify()
        kinds = set(AuditEvent.objects.values_list("kind", flat=True))
        self.assertTrue({"business.verification_submitted", "business.verification_claimed",
                         "business.verification_decided", "business.reviewer_grant_changed"} <= kinds)
        self.rv("verification_case", {"case_id": self.case_id()})
        self.rv("verification_queue")
        self.assertTrue({"business.verification_case_read", "business.verification_queue_read"} <=
                        set(AuditEvent.objects.values_list("kind", flat=True)))
        for event in AuditEvent.objects.all():
            self.assertEqual(set(vars(event)) - {"_state"}, {"id", "actor_id", "kind", "occurred_at", "subject_type", "subject_id"})

    def test_cross_business_isolation_for_owners(self):
        self.grant()
        self.verify()
        other_owner, other = self.register(name="Second Shop")
        self.assertEqual(self.call("verification_status", {"business_id": self.bid}, actor=other_owner)[0], 404)
        self.assertEqual(self.call("verification_respond", {"business_id": self.bid, "evidence": EVIDENCE}, actor=other_owner)[0], 404)
        self.assertEqual(self.submit(owner=other_owner, bid=self.bid)[0], 404)
