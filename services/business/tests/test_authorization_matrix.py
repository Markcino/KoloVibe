"""Registry-driven negative-authorization matrix: every registered operation must be covered.

Three layers, all driven by the dispatcher's own operation registry so a new operation cannot ship unchecked:

1. Gate matrix (every operation): each role the operation does not allow is refused with 403, an allowed role without
   MFA or a verified email is refused where the operation requires it, a caller that is not the Gateway is refused,
   and a refusal writes nothing.
2. Object matrix: for every operation that names a business, thread, review, invitation, member, case, revision or
   report, every actor who is not entitled to that object gets the same 404 as for a random id (existence is never
   disclosed) and the database is unchanged.
3. Coverage guard: an operation must be in the object matrix or carry a named, existing test that covers it.
"""
import importlib
from uuid import UUID, uuid4

from django.apps import apps
from django.db import transaction

from service.api import OPERATIONS
from service.models import ProfileRevision, VerificationCase
from .test_reviews import ReviewBase

VOLATILE = {"ThrottleCounter", "IdempotencyRecord", "AuditEvent", "AuditDelivery"}
ROLES = ("anonymous", "viewer", "creator", "moderator", "administrator")
PRIVILEGED = ("moderator", "administrator")
CUSTOMER_LABELS = ("owner", "staff", "stranger", "other_owner", "customer", "author")
REVIEWER_LABELS = ("granted", "wrong_target", "no_grant")


def _snapshot():
    return {model.__name__: [repr(row) for row in model.objects.order_by("pk").values()]
            for model in apps.get_app_config("service").get_models() if model.__name__ not in VOLATILE}


def _is_uuid(value):
    try:
        return isinstance(value, str) and str(UUID(value)) == value
    except ValueError:
        return False


class Matrix(ReviewBase):
    """Builds one world with a real object of every kind, so isolation is proved against real data."""

    def setUp(self):
        super().setUp()
        self.staff = self.add_staff(self.owner, self.bid)
        self.stranger = uuid4()
        self.author = uuid4()
        self.reporter = uuid4()
        review = self.published(customer=self.author)
        self.rid = review["id"]
        self.invite_id = self.call("staff_invite", {"business_id": self.bid, "label": "Spare"}, actor=self.owner)[1]["id"]
        self.review_invite_id = self.call("review_invite_create", {"business_id": self.bid}, actor=self.owner)[1]["id"]
        self.member_id = next(m["id"] for m in self.call("member_list", {"business_id": self.bid}, actor=self.owner)[1]["members"]
                              if m["role"] == "staff")
        self.tid = self.thread(self.customer)
        self.call("review_respond", {"business_id": self.bid, "review_id": self.rid, "body": "Thank you for visiting."},
                  actor=self.owner)
        report = self.call("report_create", {"subject_type": "review", "subject_id": self.rid, "reason_code": "misleading"},
                           actor=self.reporter)
        assert report[0] == 201, report
        self.report_id = report[1]["id"]
        # A business with an open verification case and one with a pending profile revision.
        self.ver_owner, self.ver_bid = self.make_business("Verifying Co", verify=False, publish=False)
        self.call("verification_submit", {"business_id": self.ver_bid, "method": "manual_review", "declaration": True,
                                          "evidence": [{"kind": "registration_number", "value": "LBR-7"}]}, actor=self.ver_owner)
        self.ver_staff = self.add_staff(self.ver_owner, self.ver_bid)
        self.case_id = str(VerificationCase.objects.get(business_id=self.ver_bid).id)
        self.rev_owner, rev = self.register(name="Revision Co")
        self.rev_bid = rev["id"]
        self.call("profile_edit", {"business_id": self.rev_bid, "category": "food", "county_code": "montserrado",
                                   "city": "Monrovia", "description": "Fresh bread daily."}, actor=self.rev_owner)
        self.call("profile_submit", {"business_id": self.rev_bid}, actor=self.rev_owner)
        self.revision_id = str(ProfileRevision.objects.get(business_id=self.rev_bid, state="pending_review").id)
        # Reviewers: fully granted, granted only for another business, and not granted at all.
        self.wrong_target, self.no_grant = uuid4(), uuid4()
        for scope in ("verification", "profile_review", "review_queue"):
            self.call("reviewer_grant", {"reviewer_account_id": str(self.wrong_target), "scope": scope, "active": True,
                                         "target_business_id": self.other}, actor=self.admin, role="administrator", mfa=True)
        self.actors = {"owner": self.owner, "staff": self.staff, "stranger": self.stranger, "other_owner": self.other_owner,
                       "customer": self.customer, "author": self.author, "granted": self.reviewer,
                       "wrong_target": self.wrong_target, "no_grant": self.no_grant,
                       "ver_owner": self.ver_owner, "ver_staff": self.ver_staff}

    def as_actor(self, label, operation, data):
        role, mfa = ("moderator", True) if label in REVIEWER_LABELS else ("viewer", False)
        return self.call(operation, data, actor=self.actors[label], role=role, mfa=mfa)

    # ---- the object matrix: (operation, payload, labels entitled to the object) ---------------------------------
    def cases(self):
        b, t, r = self.bid, self.tid, self.rid
        owner_staff, owner_only = {"owner", "staff"}, {"owner"}
        review_body = "A long enough replacement body."
        return {
            "get_mine": ({"business_id": b}, owner_staff, set()),
            "member_list": ({"business_id": b}, owner_only, set()),
            "staff_invite": ({"business_id": b, "label": "Another"}, owner_only, set()),
            "staff_invitation_revoke": ({"business_id": b, "invitation_id": self.invite_id}, owner_only, set()),
            "member_remove": ({"business_id": b, "member_id": self.member_id}, owner_only, set()),
            "member_leave": ({"business_id": b}, {"staff"}, {"owner"}),   # an owner gets 409, a different refusal
            "profile_get": ({"business_id": b}, owner_staff, set()),
            "profile_edit": ({"business_id": b, "description": "Changed by someone else."}, owner_only, set()),
            "profile_submit": ({"business_id": b}, owner_only, set()),
            "hours_replace": ({"business_id": b, "rules": [], "exceptions": []}, owner_staff, set()),
            "listing_status": ({"business_id": b}, owner_staff, set()),
            "listing_publish": ({"business_id": b}, owner_only, set()),
            "listing_unpublish": ({"business_id": b}, owner_only, set()),
            "verification_submit": ({"business_id": self.ver_bid, "method": "manual_review", "declaration": True,
                                     "evidence": [{"kind": "registration_number", "value": "LBR-9"}]}, {"ver_owner"}, set()),
            "verification_respond": ({"business_id": self.ver_bid, "evidence": [{"kind": "note", "value": "More."}]},
                                     {"ver_owner"}, set()),
            "verification_status": ({"business_id": self.ver_bid}, {"ver_owner"}, set()),
            "inquiry_get_mine": ({"thread_id": t}, {"customer"}, set()),
            "inquiry_message_customer": ({"thread_id": t, "body": "Anyone there?"}, {"customer"}, set()),
            "inquiry_close_customer": ({"thread_id": t}, {"customer"}, set()),
            "inquiry_confirm_customer": ({"thread_id": t}, {"customer"}, set()),
            "inquiry_inbox": ({"business_id": b}, owner_staff, set()),
            "inquiry_inbox_get": ({"business_id": b, "thread_id": t}, owner_staff, set()),
            "inquiry_reply": ({"business_id": b, "thread_id": t, "body": "We can help."}, owner_staff, set()),
            "inquiry_close_business": ({"business_id": b, "thread_id": t}, owner_staff, set()),
            "inquiry_confirm_business": ({"business_id": b, "thread_id": t}, owner_staff, set()),
            "inquiry_block": ({"business_id": b, "thread_id": t}, owner_only, set()),
            "review_edit_mine": ({"review_id": r, "body": review_body}, {"author"}, set()),
            "review_withdraw_mine": ({"review_id": r}, {"author"}, set()),
            "review_respond": ({"business_id": b, "review_id": r, "body": "Replacement answer."}, owner_only, set()),
            "review_response_delete": ({"business_id": b, "review_id": r}, owner_only, set()),
            "review_invite_create": ({"business_id": b}, owner_only, set()),
            "review_invite_revoke": ({"business_id": b, "invitation_id": self.review_invite_id}, owner_only, set()),
            # Reviewer operations: entitlement comes from an explicit grant that covers the business.
            "verification_case": ({"case_id": self.case_id}, {"granted"}, set()),
            "verification_claim": ({"case_id": self.case_id}, {"granted"}, set()),
            "verification_decide": ({"case_id": self.case_id, "decision": "verify", "reason_code": "documents_checked"},
                                    {"granted"}, set()),
            "profile_revision": ({"revision_id": self.revision_id}, {"granted"}, set()),
            "profile_decide": ({"revision_id": self.revision_id, "decision": "approve", "reason_code": "looks_correct"},
                               {"granted"}, set()),
            "report_case": ({"report_id": self.report_id}, {"granted"}, set()),
            "report_decide": ({"report_id": self.report_id, "decision": "remove", "reason_code": "misleading"},
                              {"granted"}, set()),
        }

    # Entitled callers are still refused by design: these need the purpose-bound step-up proof (P6B-04, DR-BZ-33).
    FAIL_CLOSED = {"member_remove": "step-up in Identity does not exist"}

    # Operations with no object id to isolate. Each names the test in this class that covers its refusals.
    EXEMPT = {
        "register": "test_register_needs_an_invitation_and_a_customer_role",
        "list_mine": "test_lists_only_ever_return_the_callers_own_items",
        "staff_redeem": "test_unknown_and_foreign_codes_are_one_answer",
        "registration_grant": "test_administrator_only_operations_refuse_everyone_else",
        "category_put": "test_administrator_only_operations_refuse_everyone_else",
        "reviewer_grant": "test_administrator_only_operations_refuse_everyone_else",
        "category_list": "test_public_operations_never_expose_an_unlisted_business",
        "public_search": "test_public_operations_never_expose_an_unlisted_business",
        "public_detail": "test_public_operations_never_expose_an_unlisted_business",
        "review_list_public": "test_public_operations_never_expose_an_unlisted_business",
        "inquiry_create": "test_customer_creation_refuses_members_and_unlisted_businesses",
        "inquiry_list_mine": "test_lists_only_ever_return_the_callers_own_items",
        "review_create": "test_customer_creation_refuses_members_and_unlisted_businesses",
        "review_list_mine": "test_lists_only_ever_return_the_callers_own_items",
        "report_create": "test_customer_creation_refuses_members_and_unlisted_businesses",
        "verification_queue": "test_queues_show_only_what_the_reviewers_grant_covers",
        "profile_queue": "test_queues_show_only_what_the_reviewers_grant_covers",
        "report_queue": "test_queues_show_only_what_the_reviewers_grant_covers",
    }

    # ---- layer 3: coverage guard -------------------------------------------------------------------------------
    def test_every_registered_operation_is_covered(self):
        covered, exempt = set(self.cases()), set(self.EXEMPT)
        self.assertEqual(set(OPERATIONS) - covered - exempt, set(),
                         "A new operation needs an entry in the object matrix or a named, existing covering test")
        self.assertEqual(covered & exempt, set())
        self.assertEqual((covered | exempt) - set(OPERATIONS), set(), "Matrix names an operation that no longer exists")
        for operation, test in self.EXEMPT.items():
            self.assertTrue(callable(getattr(type(self), test, None)), f"{operation}: covering test {test} does not exist")

    # ---- layer 1: gate matrix, every operation ------------------------------------------------------------------
    def test_gate_matrix_refuses_wrong_role_missing_mfa_unverified_email_and_foreign_caller(self):
        for name, op in OPERATIONS.items():
            for role in ROLES:
                if role in op.roles:
                    continue
                before = _snapshot()
                actor_kwargs = ({"envelope": {"actor_id": "00000000-0000-0000-0000-000000000000", "role": "anonymous",
                                              "mfa_verified": False, "email_verified": False, "idempotency_key": None,
                                              "origin": None, "data": {}}} if role == "anonymous" else {})
                status, _ = self.call(name, {}, role=role, mfa=role in PRIVILEGED, **actor_kwargs)
                self.assertEqual(status, 403, f"{name} must refuse role {role}")
                self.assertEqual(_snapshot(), before, f"{name} wrote data while refusing {role}")
            allowed = [r for r in op.roles if r != "anonymous"]
            if op.mfa:
                for role in allowed:
                    self.assertEqual(self.call(name, {}, role=role, mfa=False)[0], 403, f"{name} without MFA as {role}")
            if op.verified_email and allowed:
                self.assertEqual(self.call(name, {}, role=allowed[0], mfa=allowed[0] in PRIVILEGED, verified=False)[0], 403,
                                 f"{name} must need a verified email")
            self.assertEqual(self.call(name, {}, role=allowed[0] if allowed else "viewer", caller="moderation")[0], 403,
                             f"{name} must accept the gateway only")

    # ---- layer 2: object matrix -------------------------------------------------------------------------------
    def test_object_matrix_non_entitled_actors_get_the_unknown_id_answer_and_change_nothing(self):
        for name, (data, entitled, skip) in self.cases().items():
            denied_actors = 0
            reviewer_op = OPERATIONS[name].roles == ("moderator", "administrator")
            labels = REVIEWER_LABELS if reviewer_op else CUSTOMER_LABELS + ("ver_owner", "ver_staff")
            for label in labels:
                if label in entitled or label in skip:
                    continue
                baseline_data = {k: (str(uuid4()) if _is_uuid(v) else v) for k, v in data.items()}
                before = _snapshot()
                status, body = self.as_actor(label, name, data)
                unknown = self.as_actor(label, name, baseline_data)
                self.assertEqual((status, body), unknown, f"{name} as {label} reveals the object (differs from an unknown id)")
                self.assertEqual(status, 404, f"{name} as {label}")
                self.assertEqual(_snapshot(), before, f"{name} as {label} changed data")
                denied_actors += 1
            self.assertGreaterEqual(denied_actors, 2, f"{name} was checked against too few non-entitled actors")

    def nested_cases(self):
        """Operations whose path names a business AND a nested object: the object must belong to that business."""
        t, r, o = self.tid, self.rid, self.other
        return {
            "inquiry_inbox_get": {"business_id": o, "thread_id": t},
            "inquiry_reply": {"business_id": o, "thread_id": t, "body": "We can help."},
            "inquiry_close_business": {"business_id": o, "thread_id": t},
            "inquiry_confirm_business": {"business_id": o, "thread_id": t},
            "inquiry_block": {"business_id": o, "thread_id": t},
            "review_respond": {"business_id": o, "review_id": r, "body": "Replacement answer."},
            "review_response_delete": {"business_id": o, "review_id": r},
            "staff_invitation_revoke": {"business_id": o, "invitation_id": self.invite_id},
            "review_invite_revoke": {"business_id": o, "invitation_id": self.review_invite_id},
            "member_remove": {"business_id": o, "member_id": self.member_id},
        }

    def test_nested_ids_must_belong_to_the_path_business(self):
        """BZ-NT-02 and 19: a real member of business B cannot reach business A's objects by naming B in the path."""
        for name, data in self.nested_cases().items():
            baseline = {k: (str(uuid4()) if _is_uuid(v) and k != "business_id" else v) for k, v in data.items()}
            for label in ("other_owner",):
                before = _snapshot()
                status, body = self.as_actor(label, name, data)
                self.assertEqual((status, body), self.as_actor(label, name, baseline), f"{name}: a foreign object id is distinguishable")
                self.assertIn(status, (403, 404), f"{name}: member of {self.other} reached an object of {self.bid}")
                if name != "member_remove":      # member_remove is closed for everyone until step-up exists
                    self.assertEqual(status, 404, name)
                self.assertEqual(_snapshot(), before, f"{name} changed data")

    def test_entitled_actors_are_not_blocked_by_the_matrix_itself(self):
        """Positive control: the refusals above come from entitlement, not from payloads that are always invalid."""
        reached = []
        for name, (data, entitled, _skip) in self.cases().items():
            label = sorted(entitled)[0]
            before = _snapshot()
            with transaction.atomic():      # each entitled call runs against the pristine world
                status, body = self.as_actor(label, name, data)
                transaction.set_rollback(True)
            self.assertNotEqual(status, 404, f"{name} as entitled {label} was refused as unknown: payload is invalid")
            if name in self.FAIL_CLOSED:   # refuses for every caller until the named prerequisite exists
                self.assertEqual(status, 403, f"{name} must stay closed ({self.FAIL_CLOSED[name]})")
                self.assertEqual(_snapshot(), before)
                reached.append(name)
                continue
            self.assertNotIn(status, (400, 403), f"{name} as entitled {label} was refused: {status}")
            reached.append(name)
            if status in (200, 201, 204):
                continue
            self.assertEqual(_snapshot(), before)
        self.assertEqual(set(reached), set(self.cases()))

    # ---- covering tests for operations without an object id ---------------------------------------------------
    def test_register_needs_an_invitation_and_a_customer_role(self):
        data = {"display_name": "Uninvited Co", "legal_name": "Uninvited Co Ltd"}
        before = _snapshot()
        self.assertEqual(self.call("register", data, actor=uuid4())[1]["code"], "invitation_required")
        for role in PRIVILEGED:
            self.assertEqual(self.call("register", data, actor=self.admin, role=role, mfa=True)[0], 403)
        self.assertEqual(_snapshot(), before)

    def test_lists_only_ever_return_the_callers_own_items(self):
        for operation, label, key in (("list_mine", "owner", "id"), ("inquiry_list_mine", "customer", "id"),
                                      ("review_list_mine", "author", "id")):
            mine = self.as_actor(label, operation, {})[1]["items"]
            self.assertTrue(mine, f"{operation} should show the caller's own item")
            for other in ("stranger", "other_owner" if operation == "list_mine" else "stranger"):
                theirs = self.as_actor(other, operation, {})[1]["items"]
                self.assertFalse({i[key] for i in mine} & {i[key] for i in theirs}, f"{operation} leaked items to {other}")
        stranger = self.as_actor("stranger", "list_mine", {})[1]["items"]
        self.assertEqual(stranger, [])

    def test_unknown_and_foreign_codes_are_one_answer(self):
        unknown = self.call("staff_redeem", {"code": "x" * 32}, actor=self.stranger)
        revoked_code = self.call("staff_invite", {"business_id": self.bid, "label": "Gone"}, actor=self.owner)
        self.call("staff_invitation_revoke", {"business_id": self.bid, "invitation_id": revoked_code[1]["id"]}, actor=self.owner)
        revoked = self.call("staff_redeem", {"code": revoked_code[1]["code"]}, actor=self.stranger)
        self.assertEqual(unknown, revoked)
        self.assertEqual(unknown[0], 404)
        for role in PRIVILEGED:
            self.assertEqual(self.call("staff_redeem", {"code": "x" * 32}, role=role, mfa=True)[0], 403)

    def test_administrator_only_operations_refuse_everyone_else(self):
        bodies = {"registration_grant": {"account_id": str(uuid4()), "active": True},
                  "category_put": {"slug": "extra", "name": "Extra", "active": True},
                  "reviewer_grant": {"reviewer_account_id": str(uuid4()), "scope": "verification", "active": True}}
        for name, data in bodies.items():
            before = _snapshot()
            for role, mfa in (("viewer", False), ("creator", False), ("moderator", True), ("administrator", False)):
                self.assertEqual(self.call(name, data, actor=uuid4(), role=role, mfa=mfa)[0], 403, f"{name} as {role}")
            self.assertEqual(_snapshot(), before)
        self.assertEqual(self.call("reviewer_grant", {"reviewer_account_id": str(self.admin), "scope": "verification",
                                                      "active": True}, actor=self.admin, role="administrator", mfa=True)[0], 409)

    def test_public_operations_never_expose_an_unlisted_business(self):
        _, hidden = self.make_business("Hidden Shop", publish=False)
        for operation, data in (("public_detail", {"business_id": hidden}), ("review_list_public", {"business_id": hidden})):
            answers = {str(self.public(operation, data)), str(self.public(operation, data, signed_in=True)),
                       str(self.public(operation, {"business_id": str(uuid4())}))}
            self.assertEqual(len(answers), 1, f"{operation} distinguishes an unlisted business from an unknown id")
            self.assertEqual(self.public(operation, data)[0], 404)
        names = [item["display_name"] for item in self.search()[1]["items"]]
        self.assertNotIn("Hidden Shop", names)
        self.assertEqual(self.public("category_list", {})[0], 200)

    def test_customer_creation_refuses_members_and_unlisted_businesses(self):
        _, hidden = self.make_business("Another Hidden", publish=False)
        before = _snapshot()
        for label in ("owner", "staff"):   # members of a business never inquire about or review it
            self.assertEqual(self.as_actor(label, "inquiry_create", {"business_id": self.bid, "subject_code": "order_question",
                                                                     "body": "Do you take large orders?"})[0], 404)
            self.assertEqual(self.as_actor(label, "review_create", {"business_id": self.bid, "rating": 5,
                                                                    "body": "A very good business indeed."})[0], 404)
        unlisted = self.call("inquiry_create", {"business_id": hidden, "subject_code": "order_question",
                                                "body": "Do you take large orders?"}, actor=self.stranger)
        unknown = self.call("inquiry_create", {"business_id": str(uuid4()), "subject_code": "order_question",
                                               "body": "Do you take large orders?"}, actor=self.stranger)
        self.assertEqual(unlisted, unknown)
        self.assertEqual(self.call("report_create", {"subject_type": "review", "subject_id": str(uuid4()), "reason_code": "misleading"},
                                   actor=self.stranger)[0], 404)
        self.assertEqual(_snapshot(), before)

    def test_queues_show_only_what_the_reviewers_grant_covers(self):
        for operation, expected in (("verification_queue", self.case_id), ("profile_queue", self.revision_id),
                                    ("report_queue", self.report_id)):
            granted = self.as_actor("granted", operation, {})[1]["items"]
            ids = {str(value) for item in granted for value in item.values()}
            self.assertIn(expected, ids, f"{operation} should show the granted reviewer the open item")
            for label in ("no_grant", "wrong_target"):
                items = self.as_actor(label, operation, {})[1]["items"]
                self.assertEqual(items, [], f"{operation} shows items to {label}")
