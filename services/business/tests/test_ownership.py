"""B1: registration, ownership, staff and cross-business isolation (BZ-NT-01…04, 08…10, 12, AC-REG, AC-AZ)."""
import json
from datetime import timedelta
from unittest.mock import patch
from uuid import uuid4

from django.utils import timezone

from service import limits
from service.models import (AuditDelivery, AuditEvent, Business, BusinessMembership, IdempotencyRecord,
                            RegistrationGrant, StaffInvitation)
from .support import BusinessTestCase


class RegistrationTests(BusinessTestCase):
    def test_invited_account_registers_and_becomes_sole_owner_with_audit(self):
        account = uuid4()
        self.invite(account)
        status, body = self.call("register", {"display_name": "Ma Kolo Foods", "legal_name": "Kolo Foods Ltd"},
                                 actor=account, role="creator")
        self.assertEqual(status, 201)
        self.assertEqual(set(body), {"id", "state", "my_role", "verified", "listed", "display_name", "created_at",
                                     "legal_name"})
        self.assertEqual((body["state"], body["my_role"], body["verified"], body["listed"]),
                         ("draft", "owner", False, False))
        membership = BusinessMembership.objects.get()
        self.assertEqual((membership.account_id, membership.role, membership.status),
                         (account, "owner", "active"))
        kinds = sorted(AuditEvent.objects.values_list("kind", flat=True))
        self.assertEqual(kinds, ["business.membership_granted", "business.registered"])
        self.assertEqual(AuditDelivery.objects.count(), 2)

    def test_registration_requires_invitation_verified_email_and_a_customer_role(self):
        body = {"display_name": "Shop", "legal_name": "Shop Ltd"}
        self.assertEqual(self.call("register", body)[1]["code"], "invitation_required")
        account = uuid4()
        self.invite(account)
        self.assertEqual(self.call("register", body, actor=account, verified=False)[0], 403)
        for role in ("moderator", "administrator"):
            self.assertEqual(self.call("register", body, actor=account, role=role, mfa=True)[0], 403)
        self.assertEqual(Business.objects.count(), 0)

    def test_deactivated_grant_blocks_registration(self):
        account, _ = self.register()
        RegistrationGrant.objects.filter(account_id=account).update(active=False)
        self.assertEqual(self.call("register", {"display_name": "Two", "legal_name": "Two Ltd"}, actor=account)[0], 403)

    def test_per_account_cap(self):
        account, _ = self.register()
        for index in range(limits.MAX_BUSINESSES_PER_ACCOUNT - 1):
            self.register(account, f"Shop {index}")
        status, body = self.call("register", {"display_name": "One more", "legal_name": "One more Ltd"}, actor=account)
        self.assertEqual((status, body["code"]), (409, "business_limit"))

    def test_client_cannot_name_authority_or_state(self):
        account = uuid4()
        self.invite(account)
        base = {"display_name": "Shop", "legal_name": "Shop Ltd"}
        for extra in ({"account_id": str(uuid4())}, {"state": "verified"}, {"role": "owner"}, {"verified": True},
                      {"listed": True}, {"created_by_account_id": str(uuid4())}, {"id": str(uuid4())}):
            self.assertEqual(self.call("register", {**base, **extra}, actor=uuid4())[0], 400, extra)
        for bad in ({"display_name": "x", "legal_name": "Shop Ltd"}, {"display_name": "Shop"},
                    {"display_name": "S" * 81, "legal_name": "Shop Ltd"}, {"display_name": "Sh\x00p", "legal_name": "Shop Ltd"},
                    {"display_name": 5, "legal_name": "Shop Ltd"}, {"display_name": "Shop", "legal_name": "L" * 161}):
            self.assertEqual(self.call("register", bad, actor=uuid4())[0], 400, bad)
        self.assertEqual(Business.objects.count(), 0)

    def test_idempotency_replays_and_rejects_a_different_payload(self):
        account = uuid4()
        self.invite(account)
        body = {"display_name": "Shop", "legal_name": "Shop Ltd"}
        first = self.call("register", body, actor=account, key="k" * 20)
        again = self.call("register", body, actor=account, key="k" * 20)
        self.assertEqual((first[0], again[0], again[1]), (201, 201, first[1]))
        self.assertEqual(Business.objects.count(), 1)
        self.assertEqual(AuditEvent.objects.filter(kind="business.registered").count(), 1)
        changed = self.call("register", {**body, "display_name": "Other"}, actor=account, key="k" * 20)
        self.assertEqual((changed[0], changed[1]["code"]), (409, "idempotency_conflict"))
        self.assertEqual(self.call("register", body, actor=account, key=None)[0], 400)
        self.assertEqual(self.call("register", body, actor=account, key="short")[0], 400)

    def test_registration_attempts_are_throttled_per_account(self):
        account = uuid4()
        self.invite(account)
        statuses = [self.call("register", {"display_name": "x"}, actor=account)[0]
                    for _ in range(limits.BUDGETS["register"][0] + 1)]
        self.assertEqual(statuses[-1], 429)
        self.assertEqual(set(statuses[:-1]), {400})


class IsolationTests(BusinessTestCase):
    def setUp(self):
        super().setUp()
        self.owner_a, self.a = self.register(name="Alpha Foods")
        self.owner_b, self.b = self.register(name="Beta Fabrics")

    def test_non_member_gets_the_same_404_as_an_unknown_id(self):
        unknown = str(uuid4())
        for operation, extra in (("get_mine", {}), ("member_list", {}), ("staff_invite", {"label": "x"}),
                                 ("member_leave", {}), ("member_remove", {"member_id": str(uuid4())}),
                                 ("staff_invitation_revoke", {"invitation_id": str(uuid4())})):
            foreign = self.call(operation, {"business_id": self.b["id"], **extra}, actor=self.owner_a)
            missing = self.call(operation, {"business_id": unknown, **extra}, actor=self.owner_a)
            self.assertEqual(foreign, missing, operation)
            self.assertEqual(foreign[0], 404, operation)

    def test_owner_sees_only_own_businesses(self):
        status, body = self.call("list_mine", actor=self.owner_a)
        self.assertEqual([item["id"] for item in body["items"]], [self.a["id"]])

    def test_list_pagination_is_bounded_and_stable(self):
        account = uuid4()
        self.invite(account)
        ids = [self.register(account, f"Shop {i}")[1]["id"] for i in range(3)]
        first = self.call("list_mine", {"limit": 2}, actor=account)[1]
        self.assertEqual(len(first["items"]), 2)
        second = self.call("list_mine", {"limit": 2, "cursor": first["next_cursor"]}, actor=account)[1]
        self.assertEqual(sorted(i["id"] for i in first["items"] + second["items"]), sorted(ids))
        self.assertIsNone(second["next_cursor"])
        for bad in ({"limit": 21}, {"limit": 0}, {"cursor": "nope"}, {"limit": "x"}, {"extra": 1}):
            self.assertEqual(self.call("list_mine", bad, actor=account)[0], 400, bad)

    def test_membership_is_resolved_only_in_the_authz_module(self):
        from pathlib import Path
        service = Path(__file__).resolve().parents[1] / "service"
        for path in service.glob("*.py"):
            if path.name in {"authz.py", "models.py"}:
                continue
            self.assertNotIn("BusinessMembership.objects", path.read_text(), path.name)


class StaffTests(BusinessTestCase):
    def setUp(self):
        super().setUp()
        self.owner, self.biz = self.register()
        self.bid = self.biz["id"]

    def test_code_is_returned_once_and_only_a_digest_is_stored(self):
        status, body = self.call("staff_invite", {"business_id": self.bid, "label": "Cashier"}, actor=self.owner,
                                 key="i" * 20)
        self.assertEqual(status, 201)
        code = body["code"]
        invitation = StaffInvitation.objects.get()
        self.assertNotIn(code, (invitation.code_digest, str(invitation.__dict__)))
        replay = self.call("staff_invite", {"business_id": self.bid, "label": "Cashier"}, actor=self.owner, key="i" * 20)
        self.assertEqual(replay[0], 201)
        self.assertNotIn("code", replay[1])
        self.assertEqual(StaffInvitation.objects.count(), 1)
        self.assertNotIn(code, str(list(IdempotencyRecord.objects.values())))

    def test_redeem_makes_a_staff_member_with_owner_only_private_fields_hidden(self):
        staff = self.add_staff(self.owner, self.bid)
        status, body = self.call("get_mine", {"business_id": self.bid}, actor=staff)
        self.assertEqual((status, body["my_role"]), (200, "staff"))
        self.assertNotIn("legal_name", body)
        self.assertEqual(self.call("get_mine", {"business_id": self.bid}, actor=self.owner)[1]["legal_name"],
                         "Monrovia Bakery Ltd")
        kinds = AuditEvent.objects.filter(kind__in=["business.invitation_redeemed"]).count()
        self.assertEqual(kinds, 1)

    def test_staff_cannot_use_owner_operations(self):
        staff = self.add_staff(self.owner, self.bid)
        for operation, extra in (("staff_invite", {"label": "x"}), ("member_list", {}), ("member_remove", {"member_id": str(uuid4())}),
                                 ("staff_invitation_revoke", {"invitation_id": str(uuid4())})):
            self.assertEqual(self.call(operation, {"business_id": self.bid, **extra}, actor=staff)[0], 404, operation)

    def test_invalid_used_revoked_and_expired_codes_are_indistinguishable(self):
        _, body = self.call("staff_invite", {"business_id": self.bid, "label": "A"}, actor=self.owner)
        used = body["code"]
        self.assertEqual(self.call("staff_redeem", {"code": used}, actor=uuid4())[0], 200)
        revoked = self.call("staff_invite", {"business_id": self.bid, "label": "B"}, actor=self.owner)[1]
        self.assertEqual(self.call("staff_invitation_revoke", {"business_id": self.bid, "invitation_id": revoked["id"]},
                                   actor=self.owner)[0], 200)
        expired = self.call("staff_invite", {"business_id": self.bid, "label": "C"}, actor=self.owner)[1]
        StaffInvitation.objects.filter(pk=expired["id"]).update(expires_at=timezone.now() - timedelta(seconds=1))
        answers = {json.dumps(self.call("staff_redeem", {"code": code}, actor=uuid4()))
                   for code in (used, revoked["code"], expired["code"], "x" * 32)}
        self.assertEqual(answers, {json.dumps((404, {"detail": "Invitation unavailable"}))})

    def test_redeem_guards(self):
        _, body = self.call("staff_invite", {"business_id": self.bid, "label": "A"}, actor=self.owner)
        self.assertEqual(self.call("staff_redeem", {"code": body["code"]}, actor=self.owner)[1]["code"], "already_member")
        for role in ("moderator", "administrator"):
            self.assertEqual(self.call("staff_redeem", {"code": body["code"]}, role=role, mfa=True)[0], 403)
        self.assertEqual(self.call("staff_redeem", {"code": body["code"]}, verified=False)[0], 403)
        self.assertEqual(StaffInvitation.objects.get().redeemed_at, None)

    def test_redeem_attempts_are_throttled(self):
        actor = uuid4()
        statuses = [self.call("staff_redeem", {"code": "g" * 32}, actor=actor)[0]
                    for _ in range(limits.BUDGETS["staff_redeem"][0] + 1)]
        self.assertEqual(statuses[-1], 429)

    def test_staff_and_pending_invitation_caps(self):
        with patch.object(limits, "MAX_ACTIVE_STAFF_PER_BUSINESS", 2):
            self.add_staff(self.owner, self.bid)
            self.call("staff_invite", {"business_id": self.bid, "label": "B"}, actor=self.owner)
            status, body = self.call("staff_invite", {"business_id": self.bid, "label": "C"}, actor=self.owner)
            self.assertEqual((status, body["code"]), (409, "staff_limit"))

    def test_step_up_gated_removal_fails_closed_for_the_owner(self):
        staff = self.add_staff(self.owner, self.bid)
        member = BusinessMembership.objects.get(account_id=staff)
        status, body = self.call("member_remove", {"business_id": self.bid, "member_id": str(member.id)}, actor=self.owner)
        self.assertEqual((status, body["code"]), (403, "step_up_unavailable"))
        member.refresh_from_db()
        self.assertEqual(member.status, "active")

    def test_staff_can_leave_immediately_and_owner_cannot(self):
        staff = self.add_staff(self.owner, self.bid)
        self.assertEqual(self.call("member_leave", {"business_id": self.bid}, actor=staff)[0], 200)
        self.assertEqual(self.call("get_mine", {"business_id": self.bid}, actor=staff)[0], 404)  # next request
        status, body = self.call("member_leave", {"business_id": self.bid}, actor=self.owner)
        self.assertEqual((status, body["code"]), (409, "owner_protected"))
        self.assertEqual(BusinessMembership.objects.filter(business_id=self.bid, role="owner", status="active").count(), 1)

    def test_member_list_never_exposes_account_ids(self):
        self.add_staff(self.owner, self.bid)
        status, body = self.call("member_list", {"business_id": self.bid}, actor=self.owner)
        self.assertEqual(status, 200)
        self.assertEqual(len(body["members"]), 2)
        self.assertNotIn("account", str(body))
        self.assertEqual({m["role"] for m in body["members"]}, {"owner", "staff"})


class GrantAndEnvelopeTests(BusinessTestCase):
    def test_only_an_mfa_administrator_grants_and_never_to_self(self):
        target, admin = uuid4(), uuid4()
        data = {"account_id": str(target), "active": True}
        self.assertEqual(self.call("registration_grant", data, actor=admin, role="administrator")[0], 403)
        for role in ("viewer", "creator", "moderator"):
            self.assertEqual(self.call("registration_grant", data, actor=admin, role=role, mfa=True)[0], 403)
        self.assertEqual(self.call("registration_grant", {"account_id": str(admin), "active": True}, actor=admin,
                                   role="administrator", mfa=True)[1]["code"], "self_grant")
        status, body = self.call("registration_grant", data, actor=admin, role="administrator", mfa=True)
        self.assertEqual((status, body), (200, {"account_id": str(target), "active": True}))
        self.assertEqual(self.call("registration_grant", {**data, "active": False}, actor=admin, role="administrator",
                                   mfa=True)[1]["active"], False)
        self.assertEqual(AuditEvent.objects.filter(kind="business.registration_grant_changed").count(), 2)

    def test_envelope_is_strict(self):
        good = {"actor_id": str(uuid4()), "role": "viewer", "mfa_verified": False, "email_verified": True,
                "idempotency_key": None, "origin": None, "data": {"business_id": str(uuid4())}}
        self.assertEqual(self.call("get_mine", envelope=good)[0], 404)
        for change in ({"extra": 1}, {"mfa_verified": "yes"}, {"data": []}, {"actor_id": "not-a-uuid"},
                       {"role": 5}, {"idempotency_key": 5}):
            self.assertEqual(self.call("get_mine", envelope={**good, **change})[0], 400, change)
        missing = dict(good)
        del missing["role"]
        self.assertEqual(self.call("get_mine", envelope=missing)[0], 400)

    def test_caller_method_and_operation_are_enforced(self):
        self.assertEqual(self.call("get_mine", {"business_id": str(uuid4())}, caller="moderation")[0], 403)
        self.assertEqual(self.call("get_mine", {}, method="get")[0], 405)
        self.assertEqual(self.call("does_not_exist", {})[0], 404)
