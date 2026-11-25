"""Phase 6E security hardening: properties that cut across every Business operation.

The per-feature suites prove each rule where it is written. This file proves the rules that must hold for the
service as a whole, and it is driven by the dispatcher's own registry and the source, so a new operation or a new field
cannot quietly escape it: authority never comes from the request, a business cannot skip verification, a reviewer's
grant is exactly as wide as it says, a decision cannot be replayed into a second effect, every budget is real, no
response discloses another person, nothing here can read or write a file, and the service answers only the Gateway.
"""
import ast
import hashlib
import hmac
import json
import os
import re
import secrets
import time
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from django.db import DatabaseError, connection
from django.test import Client

from service import limits, throttle
from service.api import KEY_PATTERN, OPERATIONS
from service.models import (AuditEvent, Business, BusinessMembership, ThrottleCounter, VerificationCase,
                            VerificationDecision, BusinessReport)
from .test_reviews import BODY, ReviewBase

SERVICE_DIR = Path(__file__).resolve().parents[1] / "service"
UUID_TEXT = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
EVIDENCE = [{"kind": "registration_number", "value": "LBR-9"}]


def modules():
    return {path.name: ast.parse(path.read_text()) for path in sorted(SERVICE_DIR.glob("*.py"))}


def entitled(name):
    """The role, MFA and email state that pass the dispatcher's gate for an operation."""
    op = OPERATIONS[name]
    role = next((r for r in op.roles if r != "anonymous"), "viewer")
    return {"role": role, "mfa": op.mfa, "verified": True}


class Scenario(ReviewBase):
    """Alpha Bakery (listed, owner `self.owner`) with a reviewer who holds every scope, plus helpers for new reviewers."""

    def reviewer_with(self, *scopes, target=None):
        account = uuid4()
        for scope in scopes:
            data = {"reviewer_account_id": str(account), "scope": scope, "active": True}
            if target:
                data["target_business_id"] = target
            self.assertEqual(self.call("reviewer_grant", data, actor=self.admin, role="administrator", mfa=True)[0], 200)
        return account

    def as_reviewer(self, account, operation, data=None, **kw):
        return self.call(operation, data or {}, actor=account, role="moderator", mfa=True, **kw)

    def pending_case(self, name="Pending Co"):
        """A business with an approved profile whose verification case waits for a reviewer."""
        owner, bid = self.make_business(name, verify=False, publish=False)
        self.assertEqual(self.call("verification_submit", {"business_id": bid, "method": "manual_review", "declaration": True,
                                                           "evidence": EVIDENCE}, actor=owner)[0], 201)
        return owner, bid, str(VerificationCase.objects.get(business_id=bid).id)


# ---- authority never comes from the request -----------------------------------------------------------------------
class AuthorityTests(Scenario):
    # Fields that name WHO is acting, WHAT something is or WHETHER it is allowed. Only the service decides these.
    AUTHORITY = {"actor_id", "owner_id", "owner_account_id", "author_account_id", "customer_account_id", "member_account_id",
                 "submitted_by_account_id", "decided_by_account_id", "reporter_account_id", "assigned_reviewer_account_id",
                 "role", "my_role", "state", "status", "basis", "verified", "listed", "eligible", "published", "is_owner",
                 "hold_reasons", "version", "granted_by_account_id"}
    # The two administrator operations whose subject IS an account, named by the administrator and the contract.
    NAMED_SUBJECT = {("ownership.py", "account_id"), ("verification.py", "reviewer_account_id")}
    # `verified` on public search is a visitor's FILTER ("only verified businesses"); it grants nothing and sets nothing.
    FILTERS = {("listings.py", "verified")}

    def accepted_fields(self):
        found = []
        for name, tree in modules().items():
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "parse" and len(node.args) >= 2:
                    spec = node.args[1]
                    if isinstance(spec, ast.Name):  # a module-level table
                        spec = next((a.value for a in tree.body if isinstance(a, ast.Assign)
                                     and any(getattr(t, "id", None) == spec.id for t in a.targets)), None)
                    if isinstance(spec, ast.Dict):
                        found += [(name, key.value) for key in spec.keys if isinstance(key, ast.Constant)]
        return found

    def test_no_operation_accepts_a_field_that_names_authority(self):
        fields = self.accepted_fields()
        self.assertGreater(len(fields), 100, "the field scan found too little; the guard is not reading the handlers")
        offending = sorted({(m, f) for m, f in fields if f in self.AUTHORITY} - self.FILTERS)
        self.assertEqual(offending, [], "a handler accepts authority from the request body")
        named = {(m, f) for m, f in fields if f.endswith("account_id")}
        self.assertEqual(named - self.NAMED_SUBJECT, set(), "an account id is accepted that is not an administrator's subject")

    def test_the_actor_is_only_ever_read_from_the_attested_envelope(self):
        for name, tree in modules().items():
            for node in ast.walk(tree):
                if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name) and node.value.id == "data":
                    if isinstance(node.slice, ast.Constant) and node.slice.value in self.AUTHORITY:
                        self.fail(f"{name} reads {node.slice.value} straight from the request data")

    def test_authority_in_the_body_changes_nothing_for_the_main_write_operations(self):
        forged = {"owner_account_id": str(uuid4()), "role": "owner", "state": "verified", "verified": True, "listed": True,
                  "basis": "interaction_confirmed", "author_account_id": str(uuid4()), "customer_account_id": str(uuid4())}
        invited = uuid4()
        self.invite(invited)
        before = (Business.objects.count(), BusinessMembership.objects.count())
        calls = [("register", {"display_name": "Forger Ltd", "legal_name": "Forger Ltd Co"}, invited),
                 ("profile_edit", {"business_id": self.bid, "city": "Paynesville"}, self.owner),
                 ("listing_publish", {"business_id": self.bid}, self.owner),
                 ("inquiry_create", {"business_id": self.bid, "subject_code": "order_question", "body": "hi there"}, uuid4()),
                 ("review_create", {"business_id": self.bid, "rating": 5, "body": BODY}, uuid4()),
                 ("staff_invite", {"business_id": self.bid, "label": "x"}, self.owner)]
        lifted = {name: (10000, window) for name, (_, window) in limits.BUDGETS.items()}  # attempts count; this test is about parsing
        with patch.dict(limits.BUDGETS, lifted):
            for operation, data, actor in calls:
                for field, value in forged.items():
                    with self.subTest(operation=operation, field=field):
                        self.assertEqual(self.call(operation, {**data, field: value}, actor=actor)[0], 400)
        self.assertEqual((Business.objects.count(), BusinessMembership.objects.count()), before)


# ---- verification cannot be skipped ----------------------------------------------------------------------------------
class VerificationBypassTests(Scenario):
    def test_no_state_other_than_verified_can_be_listed_or_found(self):
        owner, bid = self.make_business("Gate Co", verify=False, publish=False)  # approved profile, never verified
        states = [s for s in Business.State.values if s != Business.State.VERIFIED]
        self.assertGreaterEqual(len(states), 7)
        for state in states:
            with self.subTest(state=state):
                Business.objects.filter(pk=bid).update(state=state)
                status, body = self.call("listing_publish", {"business_id": bid}, actor=owner)
                self.assertEqual((status, body.get("code")), (409, "not_eligible"))
                self.assertEqual(self.public("public_detail", {"business_id": bid})[0], 404)
                self.assertNotIn(bid, [i["id"] for i in self.search(q="Gate")[1]["items"]])
        Business.objects.filter(pk=bid).update(state=Business.State.VERIFIED)
        self.assertEqual(self.call("listing_publish", {"business_id": bid}, actor=owner)[0], 200)

    def test_an_owner_cannot_decide_claim_or_grant_in_their_own_verification(self):
        owner, bid, case = self.pending_case()
        for operation, data in (("verification_claim", {"case_id": case}),
                                ("verification_decide", {"case_id": case, "decision": "verify", "reason_code": "documents_checked"}),
                                ("verification_case", {"case_id": case}), ("verification_queue", {})):
            self.assertEqual(self.call(operation, data, actor=owner)[0], 403, operation)  # a customer role
            self.assertEqual(self.call(operation, data, actor=owner, role="moderator")[0], 403, operation)  # no MFA
        self.assertEqual(self.call("reviewer_grant", {"reviewer_account_id": str(owner), "scope": "verification", "active": True},
                                   actor=owner, role="administrator")[0], 403)  # even claiming the role without MFA
        self.assertEqual(Business.objects.get(pk=bid).state, Business.State.SUBMITTED)

    def test_a_reviewer_cannot_skip_the_claim_or_decide_a_case_that_is_not_theirs(self):
        owner, bid, case = self.pending_case()
        first, second = self.reviewer_with("verification"), self.reviewer_with("verification")
        decide = {"case_id": case, "decision": "verify", "reason_code": "documents_checked"}
        self.assertEqual(self.as_reviewer(first, "verification_decide", decide)[1]["code"], "claim_required")
        self.assertEqual(self.as_reviewer(first, "verification_claim", {"case_id": case})[0], 200)
        self.assertEqual(self.as_reviewer(second, "verification_decide", decide)[1]["code"], "claim_required")  # not their claim
        self.assertEqual(self.as_reviewer(second, "verification_claim", {"case_id": case})[0], 409)  # already claimed
        self.assertEqual(Business.objects.get(pk=bid).state, Business.State.UNDER_REVIEW)
        self.assertEqual(self.as_reviewer(first, "verification_decide", decide)[0], 200)
        self.assertEqual(self.call("get_mine", {"business_id": bid}, actor=owner)[1]["verified"], True)

    def test_a_decided_case_cannot_be_decided_again_with_a_new_key(self):
        _, bid, case = self.pending_case()
        reviewer = self.reviewer_with("verification")
        self.as_reviewer(reviewer, "verification_claim", {"case_id": case})
        reject = {"case_id": case, "decision": "reject", "reason_code": "documents_unclear"}
        self.assertEqual(self.as_reviewer(reviewer, "verification_decide", reject)[0], 200)
        for decision in ("verify", "reject", "request_info"):
            status, body = self.as_reviewer(reviewer, "verification_decide", {**reject, "decision": decision})
            self.assertEqual((status, body["code"]), (409, "claim_required"), decision)
        self.assertEqual(Business.objects.get(pk=bid).state, Business.State.REJECTED)
        self.assertEqual(VerificationDecision.objects.filter(case_id=case).count(), 1)


# ---- a reviewer's grant is exactly as wide as it says --------------------------------------------------------------------
class ReviewerScopeTests(Scenario):
    def test_a_grant_opens_only_its_own_queue(self):
        _, bid, case = self.pending_case()
        owner = Business.objects.get(pk=bid).memberships.get().account_id
        self.call("profile_edit", {"business_id": bid, "city": "Paynesville", "display_name": "Scope Renamed Co"}, actor=owner)
        self.call("profile_submit", {"business_id": bid}, actor=owner)
        revision = self.rv("profile_queue", {})[1]["items"][0]["revision_id"]
        review = self.published()
        report = self.call("report_create", {"subject_type": "review", "subject_id": review["id"], "reason_code": "misleading"},
                           actor=uuid4())[1]["id"]
        only_verification = self.reviewer_with("verification")
        self.assertEqual(len(self.as_reviewer(only_verification, "verification_queue")[1]["items"]), 1)
        self.assertEqual(self.as_reviewer(only_verification, "verification_case", {"case_id": case})[0], 200)
        self.assertEqual(self.as_reviewer(only_verification, "profile_queue")[1]["items"], [])
        self.assertEqual(self.as_reviewer(only_verification, "report_queue")[1]["items"], [])
        self.assertEqual(self.as_reviewer(only_verification, "profile_revision", {"revision_id": revision})[0], 404)
        self.assertEqual(self.as_reviewer(only_verification, "report_case", {"report_id": report})[0], 404)
        self.assertEqual(self.as_reviewer(only_verification, "profile_decide", {"revision_id": revision, "decision": "approve",
                                                                                "reason_code": "looks_correct"})[0], 404)
        self.assertEqual(self.as_reviewer(only_verification, "report_decide", {"report_id": report, "decision": "remove",
                                                                               "reason_code": "policy_breach"})[0], 404)
        only_reports = self.reviewer_with("review_queue")
        self.assertEqual(self.as_reviewer(only_reports, "verification_case", {"case_id": case})[0], 404)
        self.assertEqual(self.as_reviewer(only_reports, "verification_queue")[1]["items"], [])
        self.assertEqual(Review_state(review["id"]), "published")

    def test_administrators_are_not_reviewers_until_granted(self):
        _, bid, case = self.pending_case()
        admin = uuid4()
        for operation, data in (("verification_queue", {}), ("profile_queue", {}), ("report_queue", {})):
            self.assertEqual(self.call(operation, data, actor=admin, role="administrator", mfa=True)[1]["items"], [], operation)
        self.assertEqual(self.call("verification_case", {"case_id": case}, actor=admin, role="administrator", mfa=True)[0], 404)
        self.assertEqual(self.call("verification_claim", {"case_id": case}, actor=admin, role="administrator", mfa=True)[0], 404)

    def test_revoking_a_grant_takes_effect_on_the_next_request_even_mid_case(self):
        _, bid, case = self.pending_case()
        reviewer = self.reviewer_with("verification")
        self.assertEqual(self.as_reviewer(reviewer, "verification_claim", {"case_id": case})[0], 200)
        revoke = {"reviewer_account_id": str(reviewer), "scope": "verification", "active": False}
        self.assertEqual(self.call("reviewer_grant", revoke, actor=self.admin, role="administrator", mfa=True)[0], 200)
        decide = {"case_id": case, "decision": "verify", "reason_code": "documents_checked"}
        self.assertEqual(self.as_reviewer(reviewer, "verification_decide", decide)[0], 404)
        self.assertEqual(self.as_reviewer(reviewer, "verification_case", {"case_id": case})[0], 404)
        self.assertEqual(self.as_reviewer(reviewer, "verification_queue")[1]["items"], [])
        self.assertEqual(Business.objects.get(pk=bid).state, Business.State.UNDER_REVIEW)  # nothing moved

    def test_a_grant_for_one_business_does_not_cover_another(self):
        _, first, first_case = self.pending_case("First Pending Co")
        _, second, second_case = self.pending_case("Second Pending Co")
        reviewer = self.reviewer_with("verification", target=first)
        self.assertEqual([i["business_id"] for i in self.as_reviewer(reviewer, "verification_queue")[1]["items"]], [first])
        self.assertEqual(self.as_reviewer(reviewer, "verification_case", {"case_id": second_case})[0], 404)
        self.assertEqual(self.as_reviewer(reviewer, "verification_claim", {"case_id": second_case})[0], 404)


def Review_state(review_id):
    from service.models import Review
    return Review.objects.get(pk=review_id).state


# ---- a decision cannot be replayed into a second effect --------------------------------------------------------------------
class DecisionReplayTests(Scenario):
    def test_a_replayed_verification_decision_returns_the_first_answer_and_records_one_decision(self):
        _, bid, case = self.pending_case()
        reviewer = self.reviewer_with("verification")
        self.as_reviewer(reviewer, "verification_claim", {"case_id": case})
        decide = {"case_id": case, "decision": "verify", "reason_code": "documents_checked"}
        first = self.as_reviewer(reviewer, "verification_decide", decide, key="decision-key-0123456789")
        audited = AuditEvent.objects.filter(kind="business.verification_decided").count()
        for _ in range(3):
            self.assertEqual(self.as_reviewer(reviewer, "verification_decide", decide, key="decision-key-0123456789"), first)
        self.assertEqual(VerificationDecision.objects.filter(case_id=case).count(), 1)
        self.assertEqual(AuditEvent.objects.filter(kind="business.verification_decided").count(), audited)
        status, body = self.as_reviewer(reviewer, "verification_decide", {**decide, "decision": "reject"}, key="decision-key-0123456789")
        self.assertEqual((status, body["code"]), (409, "idempotency_conflict"))  # the same key cannot carry a different decision
        self.assertEqual(Business.objects.get(pk=bid).state, Business.State.VERIFIED)

    def test_a_key_is_private_to_the_actor_and_the_operation_that_used_it(self):
        _, bid, case = self.pending_case()
        first, second = self.reviewer_with("verification"), self.reviewer_with("verification")
        key = "shared-key-0123456789"
        claim = self.as_reviewer(first, "verification_claim", {"case_id": case}, key=key)
        self.assertEqual(claim[0], 200)
        decide = {"case_id": case, "decision": "verify", "reason_code": "documents_checked"}
        status, body = self.as_reviewer(second, "verification_decide", decide, key=key)  # someone else's key is not a free pass
        self.assertEqual((status, body.get("code")), (409, "claim_required"))
        status, body = self.as_reviewer(first, "verification_decide", decide, key=key)  # nor does it replay another operation
        self.assertEqual((status, body["state"]), (200, "verified"))
        self.assertEqual(VerificationDecision.objects.filter(case_id=case).count(), 1)

    def test_profile_and_report_decisions_replay_once_and_conflicting_keys_are_refused(self):
        owner, bid = self.make_business("Replay Co", publish=False)
        self.call("profile_edit", {"business_id": bid, "display_name": "Replay Renamed Co"}, actor=owner)
        self.call("profile_submit", {"business_id": bid}, actor=owner)
        revision = self.rv("profile_queue", {})[1]["items"][0]["revision_id"]
        approve = {"revision_id": revision, "decision": "approve", "reason_code": "looks_correct"}
        decided = AuditEvent.objects.filter(kind="business.profile_decided").count()
        first = self.rv("profile_decide", approve, key="profile-key-0123456789")
        self.assertEqual(first[0], 200)
        self.assertEqual(self.rv("profile_decide", approve, key="profile-key-0123456789"), first)
        self.assertEqual(self.rv("profile_decide", {**approve, "decision": "reject"}, key="profile-key-0123456789")[1]["code"],
                         "idempotency_conflict")
        self.assertEqual(AuditEvent.objects.filter(kind="business.profile_decided").count(), decided + 1)  # one for this decision
        self.assertEqual(self.rv("profile_decide", approve, key="a-new-key-0123456789")[0], 404)  # decided already
        self.assertEqual(AuditEvent.objects.filter(kind="business.profile_decided").count(), decided + 1)

        review = self.published()
        report = self.call("report_create", {"subject_type": "review", "subject_id": review["id"], "reason_code": "misleading"},
                           actor=uuid4())[1]["id"]
        remove = {"report_id": report, "decision": "remove", "reason_code": "policy_breach"}
        done = self.call("report_decide", remove, actor=self.reviewer, role="moderator", mfa=True, key="report-key-0123456789")
        again = self.call("report_decide", remove, actor=self.reviewer, role="moderator", mfa=True, key="report-key-0123456789")
        self.assertEqual((done[0], again), (200, done))
        other = self.call("report_decide", remove, actor=self.reviewer, role="moderator", mfa=True, key="report-key-9876543210")
        self.assertEqual(other[0], 404)  # a different key is a new attempt on a closed report
        self.assertEqual(BusinessReport.objects.get(pk=report).decision, "remove")
        self.assertEqual(AuditEvent.objects.filter(kind="business.report_decided").count(), 1)

    def test_a_replayed_write_is_never_applied_twice(self):
        owner, bid = self.make_business("Once Co", publish=False)
        publish = lambda: self.call("listing_publish", {"business_id": bid}, actor=owner, key="publish-key-0123456789")
        first = publish()
        self.assertEqual(publish(), first)
        self.assertEqual(AuditEvent.objects.filter(kind="business.listing_published", subject_id=bid).count(), 1)


# ---- budgets are real -------------------------------------------------------------------------------------------------------
class RateLimitTests(Scenario):
    def test_every_budget_is_used_by_something_and_everything_named_exists(self):
        used = {op.budget for op in OPERATIONS.values() if op.budget}
        for tree in modules().values():
            for node in ast.walk(tree):
                if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "allow"
                        and node.args and isinstance(node.args[0], ast.Constant)):
                    used.add(node.args[0].value)
        self.assertEqual(used - set(limits.BUDGETS), set(), "an operation names a budget that does not exist")
        self.assertEqual(set(limits.BUDGETS) - used, set(), "a budget is configured that nothing enforces")
        for name, (limit, window) in limits.BUDGETS.items():
            self.assertTrue(limit > 0 and timedelta(minutes=1) <= window <= timedelta(days=1), name)

    def test_every_write_that_creates_something_is_budgeted(self):
        creators = ("register", "staff_invite", "staff_redeem", "verification_submit", "verification_respond", "profile_edit",
                    "profile_submit", "hours_replace", "listing_publish", "listing_unpublish", "inquiry_create", "inquiry_message_customer",
                    "inquiry_reply", "review_create", "review_edit_mine", "review_invite_create", "report_create")
        for name in creators:
            self.assertTrue(OPERATIONS[name].budget, f"{name} can be repeated without limit")
        for name, op in OPERATIONS.items():
            if not op.idempotent:
                self.assertTrue(op.budget or "anonymous" in op.roles or name.endswith(("_get", "get_mine")) or name in
                                ("category_list",), f"{name} is a read with no budget")

    def test_an_exhausted_budget_stops_the_request_before_any_handler_runs(self):
        with patch.dict(limits.BUDGETS, {"read": (2, timedelta(hours=1))}):
            op = OPERATIONS["list_mine"]
            with patch.object(op, "handler", wraps=op.handler) as handler:
                statuses = [self.call("list_mine", {}, actor=self.owner)[0] for _ in range(4)]
            self.assertEqual(statuses, [200, 200, 429, 429])
            self.assertEqual(handler.call_count, 2)
            self.assertEqual(self.call("list_mine", {}, actor=uuid4())[0], 200)  # another account is unaffected

    def test_a_budget_is_per_account_and_recovers_when_its_window_ends(self):
        actor = uuid4()
        with patch.dict(limits.BUDGETS, {"read": (1, timedelta(hours=1))}):
            self.assertTrue(throttle.allow("read", actor))
            self.assertFalse(throttle.allow("read", actor))
            ThrottleCounter.objects.update(window_started_at=ThrottleCounter.objects.first().window_started_at - timedelta(hours=2))
            self.assertTrue(throttle.allow("read", actor))
        self.assertEqual(ThrottleCounter.objects.filter(key__contains=str(actor)).count(), 0)  # only a hash is ever stored

    def test_anonymous_reads_are_limited_per_client_address_and_the_address_cannot_be_chosen_by_the_caller(self):
        with patch.dict(limits.BUDGETS, {"public_read": (2, timedelta(hours=1))}):
            statuses = [self.public("public_detail", {"business_id": self.bid}, origin="203.0.113.7")[0] for _ in range(4)]
            self.assertEqual(statuses, [200, 200, 429, 429])
            self.assertEqual(self.public("public_detail", {"business_id": self.bid}, origin="203.0.113.8")[0], 200)
            self.assertEqual(self.call("public_detail", {"business_id": self.bid, "origin": "203.0.113.9"}, role="anonymous", verified=False,
                                       envelope={"actor_id": "00000000-0000-0000-0000-000000000000", "role": "anonymous",
                                                 "mfa_verified": False, "email_verified": False, "idempotency_key": None,
                                                 "origin": "203.0.113.7", "data": {"business_id": self.bid, "origin": "203.0.113.9"}})[0], 400)


# ---- one submission, one effect ----------------------------------------------------------------------------------------------
class DuplicateSubmissionTests(Scenario):
    def test_every_idempotent_operation_refuses_a_missing_or_malformed_key(self):
        idempotent = [name for name, op in OPERATIONS.items() if op.idempotent]
        self.assertGreaterEqual(len(idempotent), 30)
        for name in idempotent:
            for bad in (None, "", "short", "has spaces in it 0123456789", "x" * 129, "bad/char/0123456789"):
                with self.subTest(operation=name, key=bad):
                    status, body = self.call(name, {}, actor=uuid4(), key=bad, **entitled(name))
                    self.assertEqual((status, body["detail"]), (400, "A valid Idempotency-Key is required"))
        self.assertTrue(KEY_PATTERN.fullmatch("a" * 16) and not KEY_PATTERN.fullmatch("a" * 15))

    def test_operations_that_do_not_declare_a_key_do_not_demand_one(self):
        for name, op in OPERATIONS.items():
            if not op.idempotent:
                with self.subTest(operation=name):
                    self.assertNotEqual(self.call(name, {}, actor=uuid4(), key=None, **entitled(name))[1].get("detail"),
                                        "A valid Idempotency-Key is required")

    def test_the_same_key_from_two_accounts_makes_two_independent_results(self):
        first, second = uuid4(), uuid4()
        self.invite(first), self.invite(second)
        data = {"display_name": "Twin Bakery", "legal_name": "Twin Bakery Ltd"}
        one = self.call("register", data, actor=first, key="twin-key-0123456789")
        two = self.call("register", data, actor=second, key="twin-key-0123456789")
        self.assertEqual((one[0], two[0]), (201, 201))
        self.assertNotEqual(one[1]["id"], two[1]["id"])
        self.assertEqual(BusinessMembership.objects.get(business_id=two[1]["id"]).account_id, second)

    def test_a_second_open_request_of_the_same_kind_is_refused_not_duplicated(self):
        owner, bid, case = self.pending_case()
        again = self.call("verification_submit", {"business_id": bid, "method": "manual_review", "declaration": True,
                                                  "evidence": EVIDENCE}, actor=owner)
        self.assertEqual(again[0], 409)
        self.assertEqual(VerificationCase.objects.filter(business_id=bid).count(), 1)
        customer = uuid4()
        review = self.published(customer=customer)
        report = {"subject_type": "review", "subject_id": review["id"], "reason_code": "misleading"}
        reporter = uuid4()
        self.assertEqual(self.call("report_create", report, actor=reporter)[0], 201)
        self.assertEqual(self.call("report_create", report, actor=reporter)[1]["code"], "already_reported")
        self.assertEqual(BusinessReport.objects.filter(reporter_account_id=reporter).count(), 1)


# ---- nothing discloses another person -----------------------------------------------------------------------------------------
class DisclosureTests(Scenario):
    KEYS = {"account_id", "actor_id", "owner_account_id", "author_account_id", "customer_account_id", "reporter_account_id",
            "submitted_by_account_id", "decided_by_account_id", "assigned_reviewer_account_id", "reviewer_account_id",
            "granted_by_account_id", "body_digest", "code_digest", "key_digest", "payload_digest", "password", "secret", "token",
            "internal", "stack", "trace"}

    def people(self):
        return {"owner": self.owner, "staff": self.add_staff(self.owner, self.bid), "customer": self.customer, "author": uuid4(),
                "reporter": uuid4(), "reviewer": self.reviewer, "admin": self.admin, "stranger": uuid4()}

    def collect_keys(self, value, found=None):
        found = set() if found is None else found
        if isinstance(value, dict):
            for key, item in value.items():
                found.add(key)
                self.collect_keys(item, found)
        elif isinstance(value, list):
            for item in value:
                self.collect_keys(item, found)
        return found

    def test_no_response_names_an_account_other_than_the_caller_or_carries_an_internal_field(self):
        who = self.people()
        thread = self.confirmed_thread(who["customer"])
        review = self.review(customer=who["customer"], interaction_thread_id=thread)[1]
        self.call("review_respond", {"business_id": self.bid, "review_id": review["id"], "body": "Thank you for visiting."}, actor=who["owner"])
        report = self.call("report_create", {"subject_type": "review", "subject_id": review["id"], "reason_code": "misleading",
                                             "details": "Not my experience."}, actor=who["reporter"])[1]["id"]
        self.call("review_invite_create", {"business_id": self.bid}, actor=who["owner"])
        _, pending, case = self.pending_case("Disclosure Pending Co")
        pending_owner = Business.objects.get(pk=pending).memberships.get().account_id
        who["pending_owner"] = pending_owner
        self.call("profile_edit", {"business_id": pending, "display_name": "Disclosure Renamed Co"}, actor=pending_owner)
        self.call("profile_submit", {"business_id": pending}, actor=pending_owner)
        revision = self.rv("profile_queue", {})[1]["items"][0]["revision_id"]
        bid, anon = self.bid, None
        views = [  # (who, operation, data, privileged)
            (anon, "category_list", {}), (anon, "public_search", {}), (anon, "public_detail", {"business_id": bid}),
            (anon, "review_list_public", {"business_id": bid}),
            ("customer", "public_detail", {"business_id": bid}), ("customer", "inquiry_list_mine", {}),
            ("customer", "inquiry_get_mine", {"thread_id": thread}), ("customer", "review_list_mine", {}),
            ("author", "review_list_mine", {}), ("reporter", "review_list_public", {"business_id": bid}),
            ("owner", "get_mine", {"business_id": bid}), ("owner", "list_mine", {}), ("owner", "member_list", {"business_id": bid}),
            ("owner", "inquiry_inbox", {"business_id": bid}), ("owner", "inquiry_inbox_get", {"business_id": bid, "thread_id": thread}),
            ("owner", "profile_get", {"business_id": bid}), ("owner", "listing_status", {"business_id": bid}),
            ("owner", "verification_status", {"business_id": bid}),
            ("staff", "get_mine", {"business_id": bid}), ("staff", "inquiry_inbox_get", {"business_id": bid, "thread_id": thread}),
            ("staff", "inquiry_inbox", {"business_id": bid}),
            ("pending_owner", "verification_status", {"business_id": pending}),
            ("reviewer", "verification_queue", {}), ("reviewer", "verification_case", {"case_id": case}),
            ("reviewer", "profile_queue", {}), ("reviewer", "profile_revision", {"revision_id": revision}),
            ("reviewer", "report_queue", {}), ("reviewer", "report_case", {"report_id": report})]
        privileged = {"reviewer"}
        for person, operation, data in views:
            with self.subTest(person=person, operation=operation):
                if person is None:
                    status, body = self.public(operation, data)
                elif person in privileged:
                    status, body = self.call(operation, data, actor=who[person], role="moderator", mfa=True)
                else:
                    status, body = self.call(operation, data, actor=who[person])
                self.assertEqual(status, 200, body)
                text = json.dumps(body)
                mine = str(who.get(person)) if person else None
                for name, account in who.items():
                    if str(account) != mine:
                        self.assertNotIn(str(account), text, f"{operation} shows the {name}'s account id to {person or 'an anonymous caller'}")
                self.assertEqual(self.collect_keys(body) & self.KEYS, set(), f"{operation} carries an internal field")

    def test_public_projections_carry_only_what_a_stranger_may_see(self):
        self.review(customer=uuid4())
        allowed_detail = {"id", "display_name", "summary", "description", "category", "county_code", "city", "address_line", "time_zone",
                          "hours", "open_now", "verified", "rating", "contacts", "contacts_access"}
        detail = self.public("public_detail", {"business_id": self.bid})[1]
        self.assertEqual(set(detail) - allowed_detail, set())
        self.assertNotIn("legal_name", json.dumps(detail))
        item = self.search()[1]["items"][0]
        self.assertEqual(set(item), {"id", "display_name", "summary", "category", "county_code", "city", "open_now", "verified"})
        self.assertIsNone(detail["contacts"])  # anonymous callers do not receive contact values

    def test_every_refusal_is_a_bounded_message_without_ids_or_internals(self):
        bogus = str(uuid4())
        refusals = [self.call("get_mine", {"business_id": bogus}, actor=uuid4()), self.call("get_mine", {"business_id": bogus}, actor=uuid4(), role="moderator"),
                    self.call("listing_publish", {"business_id": self.bid}, actor=uuid4()), self.call("verification_case", {"case_id": bogus},
                                                                                                         actor=uuid4(), role="moderator", mfa=True),
                    self.call("get_mine", {"business_id": "not-an-id"}, actor=uuid4()), self.call("get_mine", {"nope": 1}, actor=uuid4()),
                    self.call("register", {}, actor=uuid4(), verified=False), self.call("nope", {}, actor=uuid4()),
                    self.call("list_mine", {}, actor=uuid4(), caller="identity"), self.call("review_create", {"business_id": self.bid, "rating": 5,
                                                                                                                  "body": BODY}, actor=self.owner)]
        with patch.dict(limits.BUDGETS, {"read": (1, timedelta(hours=1))}):
            actor = uuid4()
            self.call("list_mine", {}, actor=actor)
            refusals.append(self.call("list_mine", {}, actor=actor))
        for status, body in refusals:
            with self.subTest(status=status):
                self.assertGreaterEqual(status, 400)
                self.assertTrue({"detail"} <= set(body) <= {"detail", "code"}, body)
                self.assertFalse(UUID_TEXT.search(json.dumps(body)), body)
                for leak in ("Traceback", "service.", "SELECT ", "Error", "django"):
                    self.assertNotIn(leak, json.dumps(body))

    def test_a_database_failure_is_a_generic_503(self):
        with patch.object(OPERATIONS["list_mine"], "handler", side_effect=DatabaseError('relation "business_x" does not exist')):
            with self.assertLogs("service.api", level="ERROR") as logs:
                status, body = self.call("list_mine", {}, actor=uuid4())
        self.assertEqual((status, body), (503, {"detail": "Business service unavailable"}))
        self.assertNotIn("business_x", "".join(logs.output))  # the database's words never reach the log either

    def test_audit_events_record_ids_and_codes_never_message_text_or_contacts(self):
        thread = self.confirmed_thread(self.customer)
        self.review(customer=self.customer, interaction_thread_id=thread, body="A private opinion that must not be copied around.")
        blob = json.dumps([[e.kind, str(e.subject_id), str(e.actor_account_id)] for e in AuditEvent.objects.all()] if hasattr(AuditEvent, "actor_account_id")
                          else list(AuditEvent.objects.values_list("kind", flat=True)))
        for text in ("A private opinion", "Do you take large orders", "+2317"):
            self.assertNotIn(text, blob)
        for event in AuditEvent.objects.all():
            self.assertNotIn("A private opinion", json.dumps({f.name: str(getattr(event, f.name)) for f in event._meta.fields}))


# ---- the service reads and writes no files on a caller's behalf ------------------------------------------------------------------
class FileAccessTests(Scenario):
    FILE_NAMES = {"file", "files", "path", "filename", "file_name", "url", "uri", "attachment", "attachments", "upload", "image",
                  "photo", "document", "href", "link", "redirect", "download"}
    CONTRACT = Path(__file__).resolve().parents[3] / "docs" / "architecture" / "DOC-205_OpenAPI_3_1_DRAFT.yaml"
    # Modules that open a file whose name the operator chose through configuration, never one a caller named.
    CONFIGURED = {"settings.py", "service_auth.py", "internal_client.py", "security_audit.py"}
    FILE_APIS = {"open", "FileResponse", "StreamingHttpResponse", "FileSystemStorage", "default_storage", "send_file", "urlopen", "urlretrieve",
                 "listdir", "scandir", "walk", "rmtree", "unlink", "remove", "rename", "makedirs", "mkdir", "copyfile", "read_text", "read_bytes",
                 "write_text", "write_bytes", "check_output", "Popen", "system", "eval", "exec", "loads_pickle", "run"}

    def test_the_models_have_no_file_or_image_field(self):
        from django.db import models
        from service import models as module
        for name in dir(module):
            cls = getattr(module, name)
            if isinstance(cls, type) and issubclass(cls, models.Model) and cls._meta.app_label == "service":
                for field in cls._meta.get_fields():
                    self.assertNotIsInstance(field, (models.FileField, models.ImageField, models.FilePathField), f"{name}.{field.name}")

    def test_no_request_handling_module_touches_the_file_system_network_or_a_process(self):
        for name, tree in modules().items():
            if name in self.CONFIGURED or name == "__init__.py":
                continue
            for node in ast.walk(tree):
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    imported = [a.name for a in node.names] + ([node.module] if isinstance(node, ast.ImportFrom) and node.module else [])
                    for module in imported:
                        top = module.split(".")[0]
                        if module == "urllib.parse":  # string handling only: no I/O
                            continue
                        self.assertNotIn(top, {"os", "shutil", "subprocess", "tempfile", "socket", "requests", "urllib", "http", "boto3",
                                               "pathlib", "glob", "pickle", "zipfile", "tarfile"}, f"{name} imports {module}")
                if isinstance(node, ast.Call):
                    called = getattr(node.func, "id", None) or getattr(node.func, "attr", None)
                    self.assertNotIn(called, self.FILE_APIS - {"run", "remove", "walk", "rename"}, f"{name} calls {called}")

    def test_the_contract_has_no_file_url_or_non_json_surface_for_business(self):
        import yaml
        spec = yaml.safe_load(self.CONTRACT.read_text())
        count = 0
        for path, item in spec["paths"].items():
            for method, op in item.items():
                if method not in ("get", "post", "put", "patch", "delete") or not str(op.get("x-capability", "")).startswith("business"):
                    continue
                count += 1
                with self.subTest(operation=f"{method} {path}"):
                    for parameter in op.get("parameters", []):
                        self.assertNotIn(parameter["name"].lower(), self.FILE_NAMES)
                    for content in op.get("requestBody", {}).get("content", {}):
                        self.assertEqual(content, "application/json")
                    for response in op["responses"].values():
                        for content in response.get("content", {}):
                            self.assertEqual(content, "application/json")
        self.assertEqual(count, 57)
        for name, schema in spec["components"]["schemas"].items():
            if name.startswith(("Business", "Verification", "Inquiry", "Review", "Profile", "Staff", "Member", "Listing", "Category")):
                text = json.dumps(schema)
                self.assertNotIn('"format": "binary"', text, name)
                self.assertNotIn('"format": "uri"', text, name)
                self.assertNotIn('"contentMediaType"', text, name)

    def test_evidence_and_message_text_is_stored_as_inert_text_and_never_followed(self):
        hostile = ["../../etc/passwd", "file:///etc/passwd", "http://127.0.0.1:22/", "\\\\server\\share\\x", "$(rm -rf /)"]
        with patch("urllib.request.urlopen", side_effect=AssertionError("the service fetched a URL")), \
                patch("builtins.open", side_effect=AssertionError("the service opened a file")):
            for number, value in enumerate(hostile):
                owner, bid = self.make_business(f"Evidence Co {number}", verify=False, publish=False)
                status, body = self.call("verification_submit", {"business_id": bid, "method": "manual_review", "declaration": True,
                                                                 "evidence": [{"kind": "document_reference", "value": value}]}, actor=owner)
                self.assertIn(status, (201, 400), body)
                if status == 201:  # stored exactly as typed, as text
                    stored = VerificationCase.objects.get(business_id=bid).evidence.get()
                    self.assertEqual(stored.value, value)
                self.assertIn(self.ask(customer=uuid4(), body=value)[0], (201, 400))

    def test_ids_are_uuids_so_a_path_cannot_be_smuggled_through_them(self):
        for bad in ("../../etc/passwd", "..%2f..%2fetc", "/etc/passwd", "a" * 36, "123e4567-e89b-42d3-a456-42661417400g", "{}", "null"):
            self.assertEqual(self.call("get_mine", {"business_id": bad}, actor=self.owner)[0], 400, bad)

    def test_a_non_json_body_is_refused_by_the_dispatcher(self):
        from django.test import RequestFactory
        from service.api import dispatch
        request = RequestFactory().post("/internal/business/register", data={"file": "x"})  # multipart
        request.service_caller = "gateway"
        self.assertEqual(dispatch(request, "register").status_code, 400)
        request = RequestFactory().post("/internal/business/register", data=b"\x89PNG\r\n\x1a\n", content_type="image/png")
        request.service_caller = "gateway"
        self.assertEqual(dispatch(request, "register").status_code, 400)


# ---- only the Gateway, signed, once -------------------------------------------------------------------------------------------------
class ServiceIdentityFailureTests(Scenario):
    """Through the real middleware and URL conf: a request that is not the Gateway's own signed request never reaches a handler."""

    def setUp(self):
        super().setUp()
        with connection.cursor() as cursor:
            cursor.execute("CREATE TABLE IF NOT EXISTS internal_request_nonce (caller text NOT NULL, nonce text NOT NULL, "
                           "received_at timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP, PRIMARY KEY (caller, nonce))")
        self.key = secrets.token_urlsafe(48)
        environment = patch.dict(os.environ, {"KOLOVIBE_ENV": "local", "KOLOVIBE_SERVICE_NAME": "business",
                                              "KOLOVIBE_CALLER_GATEWAY_KEY": self.key, "KOLOVIBE_CALLER_MODERATION_KEY": secrets.token_urlsafe(48)})
        environment.start()
        self.addCleanup(environment.stop)
        self.client = Client()

    def send(self, operation, *, key=None, caller="gateway", body=None, path=None, stamp=None, nonce=None, tamper=False, audience="business",
             method="POST", omit=()):
        payload = json.dumps(body if body is not None else {
            "actor_id": "00000000-0000-0000-0000-000000000000", "role": "anonymous", "mfa_verified": False, "email_verified": False,
            "idempotency_key": None, "origin": None, "data": {}}).encode()
        path = path or f"/internal/business/{operation}"
        stamp, nonce = str(int(time.time())) if stamp is None else stamp, nonce or secrets.token_urlsafe(24)
        canonical = "\n".join((caller, audience, stamp, nonce, method, path, hashlib.sha256(payload).hexdigest()))
        signature = hmac.new((key or self.key).encode(), canonical.encode(), hashlib.sha256).hexdigest()
        headers = {"HTTP_X_KOLOVIBE_CALLER": caller, "HTTP_X_KOLOVIBE_TIMESTAMP": stamp, "HTTP_X_KOLOVIBE_NONCE": nonce,
                   "HTTP_X_KOLOVIBE_SIGNATURE": signature}
        for name in omit:
            headers.pop(name)
        return self.client.generic(method, path, payload + (b" " if tamper else b""), content_type="application/json", **headers)

    def test_the_gateways_own_signed_request_is_the_only_one_that_reaches_the_dispatcher(self):
        self.assertEqual(self.send("category_list").status_code, 200)

    def test_every_operation_refuses_an_unsigned_or_wrongly_signed_request_before_its_handler_runs(self):
        for name, op in OPERATIONS.items():
            with self.subTest(operation=name), patch.object(op, "handler", side_effect=AssertionError("handler ran")) as handler:
                for omitted in ("HTTP_X_KOLOVIBE_SIGNATURE", "HTTP_X_KOLOVIBE_NONCE", "HTTP_X_KOLOVIBE_CALLER", "HTTP_X_KOLOVIBE_TIMESTAMP"):
                    self.assertEqual(self.send(name, omit=(omitted,)).status_code, 403, omitted)
                self.assertEqual(self.send(name, key=secrets.token_urlsafe(48)).status_code, 403)  # a key that is not the Gateway's
                self.assertEqual(self.send(name, caller="moderation", key=os.environ["KOLOVIBE_CALLER_MODERATION_KEY"]).status_code, 403)
                self.assertEqual(self.send(name, caller="identity").status_code, 403)  # a peer this service does not list
                self.assertEqual(self.send(name, audience="identity").status_code, 403)  # signed for another audience
                self.assertEqual(self.send(name, tamper=True).status_code, 403)  # a body that is not the one signed
                self.assertEqual(self.send(name, stamp=str(int(time.time()) - 600)).status_code, 403)  # stale
                self.assertEqual(self.send(name, stamp=str(int(time.time()) + 600)).status_code, 403)  # from the future
                handler.assert_not_called()

    def test_a_signature_for_one_operation_cannot_be_used_on_another(self):
        request = self.send("category_list")
        self.assertEqual(request.status_code, 200)
        stamp, nonce = str(int(time.time())), secrets.token_urlsafe(24)
        payload = json.dumps({"actor_id": "00000000-0000-0000-0000-000000000000", "role": "anonymous", "mfa_verified": False,
                              "email_verified": False, "idempotency_key": None, "origin": None, "data": {}}).encode()
        canonical = "\n".join(("gateway", "business", stamp, nonce, "POST", "/internal/business/category_list", hashlib.sha256(payload).hexdigest()))
        signature = hmac.new(self.key.encode(), canonical.encode(), hashlib.sha256).hexdigest()
        response = self.client.post("/internal/business/public_search", payload, content_type="application/json", HTTP_X_KOLOVIBE_CALLER="gateway",
                                    HTTP_X_KOLOVIBE_TIMESTAMP=stamp, HTTP_X_KOLOVIBE_NONCE=nonce, HTTP_X_KOLOVIBE_SIGNATURE=signature)
        self.assertEqual(response.status_code, 403)

    def test_a_captured_request_cannot_be_sent_twice(self):
        nonce = secrets.token_urlsafe(24)
        self.assertEqual(self.send("category_list", nonce=nonce).status_code, 200)
        self.assertEqual(self.send("category_list", nonce=nonce).status_code, 403)

    def test_the_forbidden_answer_reveals_nothing_about_which_check_failed(self):
        answers = {self.send("category_list", key=secrets.token_urlsafe(48)).content, self.send("category_list", caller="identity").content,
                   self.send("category_list", stamp="1").content, self.send("category_list", tamper=True).content,
                   self.send("no_such_operation", caller="identity").content}
        self.assertEqual(answers, {b'{"detail": "Forbidden"}'})

    def test_the_gateway_cannot_reach_a_path_outside_the_business_prefix_and_the_probe(self):
        for path in ("/internal/identity/validate", "/internal/audit/events", "/internal/business", "/internal/"):
            self.assertEqual(self.send("category_list", path=path).status_code, 403, path)
        self.assertIn(self.send("category_list", path="/internal/business/no_such_operation").status_code, (404,))  # an unknown operation, signed

    def test_a_missing_or_weak_credential_closes_the_service(self):
        with patch.dict(os.environ, {"KOLOVIBE_CALLER_GATEWAY_KEY": "short"}):
            self.assertEqual(self.send("category_list", key="short").status_code, 403)
        with patch.dict(os.environ, {"KOLOVIBE_CALLER_GATEWAY_KEY": ""}):
            self.assertEqual(self.send("category_list").status_code, 403)
        with patch.dict(os.environ, {"KOLOVIBE_SERVICE_NAME": ""}):
            self.assertEqual(self.send("category_list").status_code, 403)
