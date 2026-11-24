"""Shared test helpers: call the dispatcher exactly as the Gateway's signed envelope would."""
import json
from uuid import uuid4

from django.test import RequestFactory, TestCase

from service.api import dispatch
from service.models import RegistrationGrant

KEY = "idem-key-0123456789"


class BusinessTestCase(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.n = 0

    def call(self, operation, data=None, *, actor=None, role="viewer", mfa=False, verified=True, key="auto",
             caller="gateway", method="post", envelope=None, origin=None):
        self.n += 1
        if key == "auto":
            key = f"idem-key-{self.n:016d}"
        body = envelope if envelope is not None else {
            "actor_id": str(actor or uuid4()), "role": role, "mfa_verified": mfa, "email_verified": verified,
            "idempotency_key": key, "origin": origin, "data": data or {}}
        request = self.factory.generic(method.upper(), f"/internal/business/{operation}", json.dumps(body),
                                       content_type="application/json")
        request.service_caller = caller
        response = dispatch(request, operation)
        payload = json.loads(response.content) if response.content else None
        return response.status_code, payload

    def invite(self, account):
        RegistrationGrant.objects.create(account_id=account, granted_by_account_id=uuid4())

    def register(self, account=None, name="Monrovia Bakery"):
        account = account or uuid4()
        self.invite(account) if not RegistrationGrant.objects.filter(account_id=account).exists() else None
        status, body = self.call("register", {"display_name": name, "legal_name": f"{name} Ltd"}, actor=account)
        assert status == 201, (status, body)
        return account, body

    def add_staff(self, owner, business_id, staff=None, label="Cashier"):
        staff = staff or uuid4()
        status, body = self.call("staff_invite", {"business_id": business_id, "label": label}, actor=owner)
        assert status == 201, (status, body)
        status, _ = self.call("staff_redeem", {"code": body["code"]}, actor=staff)
        assert status == 200
        return staff
