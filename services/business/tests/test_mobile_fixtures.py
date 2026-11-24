"""Contract fixtures for the Flutter app: real responses from the Business service, and a drift check.

`apps/mobile/test/fixtures/business/<name>.json` holds `{"status": n, "body": ...}` captured from this service for every
operation the app calls. The Dart parsers are tested against exactly these files, so the app and the service cannot
silently disagree. This test regenerates the responses and fails if their *shape* (keys and value types, not ids or
times) differs from the committed files. To refresh the files after an intended contract change:

    KOLOVIBE_WRITE_FIXTURES=1 python manage.py test tests.test_mobile_fixtures
"""
import json
import os
import re
from pathlib import Path
from uuid import uuid4

import yaml

from .test_reviews import ReviewBase

FIXTURES = Path(__file__).resolve().parents[3] / "apps" / "mobile" / "test" / "fixtures" / "business"
HOURS = {"rules": [{"weekday": 0, "opens": "08:00", "closes": "17:00"}, {"weekday": 5, "opens": "09:00", "closes": "13:00"}],
         "exceptions": [{"on_date": "2026-12-25", "closed": True}, {"on_date": "2026-12-31", "closed": False, "opens": "09:00", "closes": "12:00"}]}


DOC205 = Path(__file__).resolve().parents[3] / "docs" / "architecture" / "DOC-205_OpenAPI_3_1_DRAFT.yaml"


def app_operations():
    """`METHOD /path` for every Business operation the Flutter app may call: all of them except the reviewer and
    administrator ones, which belong to the protected console (DR-BZ-21)."""
    paths = yaml.safe_load(DOC205.read_text())["paths"]
    found = set()
    for path, item in paths.items():
        for method, operation in item.items():
            if (method in ("get", "post", "put", "patch", "delete") and str(operation.get("x-capability", "")).startswith("business")
                    and not path.startswith(("/moderation/", "/admin/"))):
                found.add(f"{method.upper()} {re.sub(r'{[^}]+}', '{id}', path)}")
    return sorted(found)


def shape(value):
    """Keys and value kinds only. A list is described by its first element, so an empty list has no shape."""
    if isinstance(value, dict):
        return {key: shape(item) for key, item in sorted(value.items())}
    if isinstance(value, list):
        return [shape(value[0])] if value else []
    if value is None:
        return "null"
    return type(value).__name__


class MobileFixtureTests(ReviewBase):
    def capture(self):
        out = {}

        def take(name, response):
            status, body = response
            out[name] = {"status": status, "body": body}
            return body

        # public reads (anonymous), then signed in
        self.public_session = uuid4()
        cafe_owner, cafe = self.make_business("Fixture Cafe", contacts=[{"kind": "phone", "value": "+231770000001", "is_public": True}])
        self.call("hours_replace", {"business_id": cafe, "rules": [{"weekday": d, "opens": "00:00", "closes": "24:00"} for d in range(7)]},
                  actor=cafe_owner)
        take("category_list", self.public("category_list", {}))
        take("public_search", self.search())
        take("public_detail_anonymous", self.public("public_detail", {"business_id": cafe}))
        take("public_detail_signed_in", self.public("public_detail", {"business_id": cafe}, signed_in=True))
        author = uuid4()
        review = self.published(customer=author)
        take("review_list_public", self.public("review_list_public", {"business_id": self.bid}))
        # customer
        customer = uuid4()
        take("inquiry_create", self.ask(customer=customer))
        tid = out["inquiry_create"]["body"]["id"]
        take("inquiry_list_mine", self.call("inquiry_list_mine", {}, actor=customer))
        take("inquiry_get_mine", self.call("inquiry_get_mine", {"thread_id": tid}, actor=customer))
        take("inquiry_message_customer", self.call("inquiry_message_customer", {"thread_id": tid, "body": "Any update?"}, actor=customer))
        owner, bid = self.owner, self.bid
        take("inquiry_reply", self.call("inquiry_reply", {"business_id": bid, "thread_id": tid, "body": "Yes, we do."}, actor=owner))
        take("inquiry_confirm_customer", self.call("inquiry_confirm_customer", {"thread_id": tid}, actor=customer))
        take("inquiry_confirm_business", self.call("inquiry_confirm_business", {"business_id": bid, "thread_id": tid}, actor=owner))
        take("inquiry_inbox", self.call("inquiry_inbox", {"business_id": bid}, actor=owner))
        take("inquiry_inbox_get", self.call("inquiry_inbox_get", {"business_id": bid, "thread_id": tid}, actor=owner))
        take("inquiry_close_business", self.call("inquiry_close_business", {"business_id": bid, "thread_id": tid}, actor=owner))
        closer = uuid4()
        tid3 = self.ask(customer=closer)[1]["id"]
        take("review_create", self.call("review_create", {"business_id": self.bid, "rating": 4, "title": "Good", "body": "A solid experience overall."},
                                        actor=customer))
        take("review_list_mine", self.call("review_list_mine", {}, actor=author))
        take("review_edit_mine", self.call("review_edit_mine", {"review_id": review["id"], "body": "Updated review text here."}, actor=author))
        take("report_create", self.call("report_create", {"subject_type": "review", "subject_id": review["id"], "reason_code": "misleading",
                                                           "details": "Looks wrong."}, actor=customer))
        take("review_withdraw_mine", self.call("review_withdraw_mine", {"review_id": review["id"]}, actor=author))
        take("inquiry_close_customer", self.call("inquiry_close_customer", {"thread_id": tid3}, actor=closer))
        # owner of the listed business
        take("list_mine", self.call("list_mine", {}, actor=owner))
        take("get_mine_owner", self.call("get_mine", {"business_id": bid}, actor=owner))
        take("profile_get", self.call("profile_get", {"business_id": bid}, actor=owner))
        take("hours_replace", self.call("hours_replace", HOURS | {"business_id": bid}, actor=owner))
        take("listing_status", self.call("listing_status", {"business_id": bid}, actor=owner))
        take("listing_unpublish", self.call("listing_unpublish", {"business_id": bid}, actor=owner))
        take("listing_publish", self.call("listing_publish", {"business_id": bid}, actor=owner))
        take("staff_invite", self.call("staff_invite", {"business_id": bid, "label": "Cashier"}, actor=owner))
        code = take("staff_invite", self.call("staff_invite", {"business_id": bid, "label": "Counter"}, actor=owner))
        # the one-time code is part of the real 201 answer; keep its shape, never a usable value
        staff = uuid4()
        take("staff_redeem", self.call("staff_redeem", {"code": code["code"]}, actor=staff))
        out["staff_invite"]["body"] = {**out["staff_invite"]["body"], "code": "REDACTED-ONE-TIME-CODE"}
        take("get_mine_staff", self.call("get_mine", {"business_id": bid}, actor=staff))
        take("member_list", self.call("member_list", {"business_id": bid}, actor=owner))
        invitation = self.call("staff_invite", {"business_id": bid, "label": "Spare"}, actor=owner)[1]
        take("staff_invitation_revoke", self.call("staff_invitation_revoke", {"business_id": bid, "invitation_id": invitation["id"]}, actor=owner))
        other = uuid4()
        tid2 = self.ask(customer=other)[1]["id"]
        take("inquiry_block", self.call("inquiry_block", {"business_id": bid, "thread_id": tid2}, actor=owner))
        live = self.published(customer=uuid4())
        take("review_respond", self.call("review_respond", {"business_id": bid, "review_id": live["id"], "body": "Thank you for visiting."}, actor=owner))
        take("review_response_delete", self.call("review_response_delete", {"business_id": bid, "review_id": live["id"]}, actor=owner))
        invite = self.call("review_invite_create", {"business_id": bid}, actor=owner)
        take("review_invite_create", invite)
        out["review_invite_create"]["body"] = {**out["review_invite_create"]["body"], "code": "REDACTED-ONE-TIME-CODE"}
        take("review_invite_revoke", self.call("review_invite_revoke", {"business_id": bid, "invitation_id": invite[1]["id"]}, actor=owner))
        take("member_leave", self.call("member_leave", {"business_id": bid}, actor=staff))
        # a new business: register, profile, submit, verification
        newcomer = uuid4()
        self.invite(newcomer)
        take("register", self.call("register", {"display_name": "Fixture Bakery", "legal_name": "Fixture Bakery Ltd"}, actor=newcomer))
        nid = out["register"]["body"]["id"]
        take("verification_status_none", self.call("verification_status", {"business_id": nid}, actor=newcomer))
        take("profile_edit", self.call("profile_edit", {"business_id": nid, "category": "food", "county_code": "montserrado",
                                                         "city": "Monrovia", "description": "Fresh.",
                                                         "contacts": [{"kind": "phone", "value": "+231770000000", "is_public": True}]},
                                       actor=newcomer))
        take("profile_get_working", self.call("profile_get", {"business_id": nid}, actor=newcomer))
        take("profile_submit", self.call("profile_submit", {"business_id": nid}, actor=newcomer))
        take("verification_submit", self.call("verification_submit", {"business_id": nid, "method": "manual_review", "declaration": True,
                                                                       "evidence": [{"kind": "registration_number", "value": "LBR-1"}]}, actor=newcomer))
        take("verification_status_pending", self.call("verification_status", {"business_id": nid}, actor=newcomer))
        take("register_no_invitation", self.call("register", {"display_name": "No Invite", "legal_name": "No Invite Ltd"}, actor=uuid4()))
        return out

    def test_the_committed_fixtures_have_the_shape_the_service_returns_today(self):
        captured = self.capture()
        if os.environ.get("KOLOVIBE_WRITE_FIXTURES") == "1":
            FIXTURES.mkdir(parents=True, exist_ok=True)
            for name, value in captured.items():
                (FIXTURES / f"{name}.json").write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
            return
        self.assertTrue(FIXTURES.is_dir(), "run with KOLOVIBE_WRITE_FIXTURES=1 to create the fixtures")
        committed = {path.stem for path in FIXTURES.glob("*.json") if not path.stem.startswith("_")}
        self.assertEqual(committed, set(captured), "fixture set differs from the captured operations")
        for name, value in captured.items():
            stored = json.loads((FIXTURES / f"{name}.json").read_text())
            self.assertEqual(stored["status"], value["status"], name)
            self.assertEqual(shape(stored["body"]), shape(value["body"]), f"{name}: the service response shape changed")

    def test_the_list_of_app_operations_matches_the_contract(self):
        path = FIXTURES / "_operations.json"
        current = app_operations()
        self.assertEqual(len(current), 44, "the app-facing Business operations changed; update the app and this count")
        if os.environ.get("KOLOVIBE_WRITE_FIXTURES") == "1":
            path.write_text(json.dumps(current, indent=2) + "\n")
            return
        self.assertEqual(json.loads(path.read_text()), current)

    def test_no_fixture_contains_a_usable_secret_or_a_real_personal_value(self):
        for name, value in self.capture().items():
            text = json.dumps(value)
            for forbidden in ("@example", "Bearer ", "password"):
                self.assertNotIn(forbidden, text, name)
