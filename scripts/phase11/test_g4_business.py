"""Phase 11, test group 4: Business over real HTTP: ownership, cross-business denial, staff scope, discovery.

The generated cross-business test walks every business-scoped operation in DOC-205, so a new operation cannot escape it.
The full happy path (verification, listing, inquiries, reviews, reports) is the existing real-HTTP journey; see the matrix.
"""

import re
import secrets
import time
import unittest
import uuid

import yaml

import lib

SPEC = yaml.safe_load((lib.ROOT / "docs/architecture/DOC-205_OpenAPI_3_1_DRAFT.yaml").read_text())


def S():
    return lib.CURRENT


def admin_session():
    admin = S().privileged("administrator")
    status, challenge = S().post("/auth/login", {"email": admin["email"], "password": admin["password"]})
    assert status == 202, status
    status, session = S().post("/auth/mfa/verify", {"challenge_token": challenge["challenge_token"], "code": admin["recovery"]})
    assert status == 200, status
    return session["access_token"]


class Business(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.admin = admin_session()
        cls.owners = []
        for _ in range(2):
            user, tokens = S().signed_in()
            account = tokens["user"]["id"]
            status, _ = S().call("PUT", f"/admin/business-registration-grants/{account}", {"active": True}, token=cls.admin, key=secrets.token_urlsafe(16))
            assert status in (200, 204), ("grant", status)
            cls.owners.append({"user": user, "token": tokens["access_token"], "id": account})
        cls.businesses = []
        for number, owner in enumerate(cls.owners):
            status, body = S().post("/me/businesses", {"display_name": f"Bakery {number}{secrets.token_hex(2)}", "legal_name": f"Legal {number} Ltd"},
                                    token=owner["token"], key=secrets.token_urlsafe(16))
            assert status == 201, (status, body)
            cls.businesses.append(body["id"] if "id" in body else body["business"]["id"])

    # ---- registration and ownership ------------------------------------------------------------------------
    def test_T4_01_registering_a_business_needs_an_administrator_grant(self):
        _, tokens = S().signed_in()
        status, body = S().post("/me/businesses", {"display_name": "No Grant Shop", "legal_name": "No Grant Ltd"}, token=tokens["access_token"], key=secrets.token_urlsafe(16))
        self.assertIn(status, (403, 409), (status, body))
        self.assertEqual(S().get("/me/businesses", token=tokens["access_token"])[1].get("items", []), [])

    def test_T4_02_the_owner_is_assigned_by_the_server_and_a_client_cannot_choose_one(self):
        owner = self.owners[0]
        status, body = S().post("/me/businesses", {"display_name": "Spoof Shop", "legal_name": "Spoof Ltd", "owner_id": self.owners[1]["id"], "status": "verified"},
                                token=owner["token"], key=secrets.token_urlsafe(16))
        self.assertEqual(status, 400, "unknown fields such as owner_id and status must be refused")
        mine = S().get("/me/businesses", token=owner["token"])[1]["items"]
        self.assertTrue(all(item["id"] != self.businesses[1] for item in mine), "an owner must not see another owner's business")

    def test_T4_03_a_retry_with_the_same_idempotency_key_returns_the_same_business(self):
        owner, key = self.owners[0], secrets.token_urlsafe(16)
        body = {"display_name": "Idempotent Shop", "legal_name": "Idem Ltd"}
        first = S().post("/me/businesses", body, token=owner["token"], key=key)
        second = S().post("/me/businesses", body, token=owner["token"], key=key)
        self.assertEqual(first[0], second[0])
        self.assertEqual(first[1], second[1])

    # ---- cross-business denial, generated from the contract -------------------------------------------------
    def test_T4_10_every_business_scoped_operation_answers_a_stranger_exactly_like_a_missing_business(self):
        mine, theirs = self.owners[1]["token"], self.businesses[0]  # owner 1 acts on owner 0's business
        probed, leaks = 0, []
        for path, item in SPEC["paths"].items():
            if "{business_id}" not in path or not path.startswith("/me/businesses/{business_id}"):
                continue
            for method in ("get", "post", "put", "patch", "delete"):
                if method not in item:
                    continue
                filled = lambda business: re.sub(r"\{[a-z_]+\}", lambda m: business if m.group(0) == "{business_id}" else str(uuid.uuid4()), path)
                body = None if method in ("get", "delete") else {}
                a = S().call(method.upper(), filled(theirs), body, token=mine, key=secrets.token_urlsafe(16) if method != "get" else None)
                b = S().call(method.upper(), filled(str(uuid.uuid4())), body, token=mine, key=secrets.token_urlsafe(16) if method != "get" else None)
                probed += 1
                if a[0] != b[0] or a[1] != b[1] or a[0] < 400:
                    leaks.append((method.upper(), path, a[0], b[0]))
        self.assertEqual(leaks, [], f"{len(leaks)} of {probed} operations answered a stranger differently from a missing business: {leaks[:6]}")
        self.assertGreaterEqual(probed, 20, "the probe found too few business-scoped operations")

    def test_T4_11_the_owner_still_has_access_to_their_own_business(self):
        for owner, business in zip(self.owners, self.businesses):
            self.assertEqual(S().get(f"/me/businesses/{business}", token=owner["token"])[0], 200)
            self.assertEqual(S().get(f"/me/businesses/{business}/profile", token=owner["token"])[0], 200)

    def test_T4_12_an_anonymous_caller_cannot_use_any_owner_operation(self):
        for method, path in (("GET", "/me/businesses"), ("POST", "/me/businesses"), ("GET", f"/me/businesses/{self.businesses[0]}"),
                             ("PATCH", f"/me/businesses/{self.businesses[0]}/profile"), ("GET", "/me/inquiries")):
            self.assertEqual(S().call(method, path, {} if method in ("POST", "PATCH") else None)[0], 401, path)

    # ---- staff ---------------------------------------------------------------------------------------------------------
    def test_T4_20_staff_invitations_are_single_use_and_staff_cannot_do_owner_things(self):
        owner, business = self.owners[0], self.businesses[0]
        status, invite = S().post(f"/me/businesses/{business}/members/invitations", {"label": "Counter staff"}, token=owner["token"], key=secrets.token_urlsafe(16))
        self.assertEqual(status, 201, invite)
        code = invite.get("code") or invite.get("invitation_code")
        self.assertTrue(code, "the one-time code must be returned once")
        _, staff = S().signed_in()
        self.assertEqual(S().post("/me/business-invitations/redeem", {"code": "WRONG-" + secrets.token_hex(6)}, token=staff["access_token"], key=secrets.token_urlsafe(16))[0] in (400, 404), True)
        self.assertEqual(S().post("/me/business-invitations/redeem", {"code": code}, token=staff["access_token"], key=secrets.token_urlsafe(16))[0], 200)
        _, other = S().signed_in()
        self.assertIn(S().post("/me/business-invitations/redeem", {"code": code}, token=other["access_token"], key=secrets.token_urlsafe(16))[0], (400, 404, 409), "a code must work once")
        token = staff["access_token"]
        # owner-only operations
        for method, path, body in (("POST", f"/me/businesses/{business}/members/invitations", {"label": "x"}),
                                   ("POST", f"/me/businesses/{business}/verification", {"method": "manual_review", "declaration": True, "evidence": [{"kind": "registration_number", "value": "LBR-1"}]}),
                                   ("POST", f"/me/businesses/{business}/profile/submit", {}), ("POST", f"/me/businesses/{business}/listing/publish", {}),
                                   ("DELETE", f"/me/businesses/{business}/members/{uuid.uuid4()}", None)):
            status, _ = S().call(method, path, body, token=token, key=secrets.token_urlsafe(16))
            self.assertIn(status, (403, 404), f"staff reached an owner operation: {method} {path} -> {status}")
        # but staff can see the business they work for
        self.assertEqual(S().get(f"/me/businesses/{business}", token=token)[0], 200)

    def test_T4_21_a_staff_member_who_leaves_loses_access_at_once(self):
        owner, business = self.owners[1], self.businesses[1]
        status, invite = S().post(f"/me/businesses/{business}/members/invitations", {"label": "Temp"}, token=owner["token"], key=secrets.token_urlsafe(16))
        _, staff = S().signed_in()
        S().post("/me/business-invitations/redeem", {"code": invite.get("code") or invite.get("invitation_code")}, token=staff["access_token"], key=secrets.token_urlsafe(16))
        self.assertEqual(S().get(f"/me/businesses/{business}", token=staff["access_token"])[0], 200)
        self.assertIn(S().post(f"/me/businesses/{business}/leave", {}, token=staff["access_token"], key=secrets.token_urlsafe(16))[0], (200, 204))
        self.assertEqual(S().get(f"/me/businesses/{business}", token=staff["access_token"])[0], 404, "access must end immediately")

    def test_T4_22_removing_a_member_needs_step_up_which_is_not_available_and_so_fails_closed(self):
        owner, business = self.owners[0], self.businesses[0]
        members = S().get(f"/me/businesses/{business}/members", token=owner["token"])[1]["members"]
        staff = [m for m in members if m.get("role") != "owner"]
        if not staff:
            self.skipTest("no staff to remove")
        status, body = S().call("DELETE", f"/me/businesses/{business}/members/{staff[0]['id']}", None, token=owner["token"], key=secrets.token_urlsafe(16))
        self.assertEqual(status, 403, (status, body))
        self.assertIn("step", str(body).lower())

    # ---- discovery ------------------------------------------------------------------------------------------------------
    def test_T4_30_an_unverified_business_is_not_discoverable(self):
        name = "Bakery 0"
        status, found = S().get("/businesses?q=Bakery")
        self.assertEqual(status, 200)
        listed = [item.get("id") for item in found.get("items", [])]
        for business in self.businesses:
            self.assertNotIn(business, listed, "a business that has not been verified and listed must not be public")

    def test_T4_31_search_input_is_bounded_and_does_not_break_the_query(self):
        for q in ("%", "_", "' OR 1=1 --", "a" * 5000, "\u0000", "<script>", "\\", "%00"):
            status, body = S().get("/businesses", headers={}) if False else S().call("GET", "/businesses?q=" + __import__("urllib.parse", fromlist=["quote"]).quote(q))
            self.assertIn(status, (200, 400), (q[:20], status))
            self.assertNotIn("Traceback", str(body))
        self.assertEqual(S().get("/businesses?cursor=garbage")[0] in (400, 200), True)

    def test_T4_32_public_business_reads_never_expose_owner_or_legal_details(self):
        status, found = S().get("/businesses")
        self.assertEqual(status, 200)
        text = str(found).lower()
        for forbidden in ("legal_name", "owner", "member", "evidence", "latitude", "longitude"):
            self.assertNotIn(forbidden, text)

    def test_T4_23_staff_get_the_same_refusal_for_a_malformed_owner_request_as_for_a_valid_one(self):
        """Authorization should come before validation: a refused actor must not learn the request schema or its errors."""
        owner, business = self.owners[0], self.businesses[0]
        _, invite = S().post(f"/me/businesses/{business}/members/invitations", {"label": "Probe"}, token=owner["token"], key=secrets.token_urlsafe(16))
        _, staff = S().signed_in()
        S().post("/me/business-invitations/redeem", {"code": invite.get("code") or invite.get("invitation_code")}, token=staff["access_token"], key=secrets.token_urlsafe(16))
        valid = S().post(f"/me/businesses/{business}/verification", {"method": "manual_review", "declaration": True, "evidence": [{"kind": "registration_number", "value": "LBR-1"}]},
                         token=staff["access_token"], key=secrets.token_urlsafe(16))
        malformed = S().post(f"/me/businesses/{business}/verification", {"nonsense": 1}, token=staff["access_token"], key=secrets.token_urlsafe(16))
        self.assertEqual(valid[0], malformed[0], f"valid -> {valid[0]}, malformed -> {malformed[0]}: validation runs before authorization")
