"""D11-005 (Business): authorization is decided before the request body is validated.

An actor who is not entitled to a business must get the same refusal whether the body is well formed or not, so a
refused caller never learns the request schema and a staff member cannot probe owner-only operations by their errors.
The check is driven by the dispatcher's own registry, so a new business-scoped operation cannot skip it.
"""
from uuid import uuid4

from service.api import OPERATIONS
from .support import BusinessTestCase


class AuthorizationBeforeValidation(BusinessTestCase):
    def setUp(self):
        super().setUp()
        self.owner, self.biz = self.register()
        self.bid = self.biz["id"]
        self.staff = self.add_staff(self.owner, self.bid)
        self.stranger = uuid4()

    def test_verification_submit_refuses_staff_identically_for_valid_and_malformed_bodies(self):
        valid = self.call("verification_submit", {"business_id": self.bid, "method": "manual_review", "declaration": True,
                                                  "evidence": [{"kind": "registration_number", "value": "LBR-000123"}]},
                          actor=self.staff)
        malformed = self.call("verification_submit", {"business_id": self.bid, "nonsense": 1}, actor=self.staff)
        self.assertEqual((valid[0], malformed[0]), (404, 404))
        self.assertEqual(valid[1], malformed[1])

    def test_every_owner_only_business_operation_hides_its_schema_from_staff_and_strangers(self):
        checked = []
        for name, op in sorted(OPERATIONS.items()):
            if not op.member_roles:
                continue
            for actor in (self.staff, self.stranger):
                if actor == self.staff and "staff" in op.member_roles:
                    continue  # staff is entitled here: a malformed body is legitimately a 400
                status, body = self.call(name, {"business_id": self.bid, "nonsense": 1}, actor=actor)
                self.assertEqual((status, body), (404, {"detail": "Not found"}), f"{name} leaked validation to a refused actor")
            checked.append(name)
        self.assertGreaterEqual(len(checked), 15, checked)

    def test_every_operation_that_checks_membership_declares_it_to_the_dispatcher(self):
        """A handler that calls require_member or _business_thread must declare member_roles, so the gate runs first."""
        import inspect
        undeclared = [name for name, op in OPERATIONS.items() if op.member_roles is None
                      and any(call in inspect.getsource(op.handler) for call in ("require_member(", "_business_thread("))]
        self.assertEqual(undeclared, [])

    def test_an_entitled_actor_still_gets_validation_errors(self):
        self.assertEqual(self.call("verification_submit", {"business_id": self.bid, "nonsense": 1}, actor=self.owner)[0], 400)
        self.assertEqual(self.call("listing_status", {"business_id": self.bid, "nonsense": 1}, actor=self.owner)[0], 400)

    def test_a_missing_or_invalid_business_id_is_still_a_validation_error(self):
        self.assertEqual(self.call("listing_status", {}, actor=self.stranger)[0], 400)
        self.assertEqual(self.call("listing_status", {"business_id": "nope"}, actor=self.stranger)[0], 400)
