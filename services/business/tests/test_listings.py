"""B4: eligibility, projection, public search and detail, contact reveal and cursor safety."""
import datetime as dt
from datetime import timedelta
from unittest.mock import patch
from uuid import uuid4

from service import limits
from service.api import NIL_ACTOR
from service.models import AuditEvent, Business, BusinessListing, ProfileRevision, RegistrationGrant
from .support import BusinessTestCase


class ListingBase(BusinessTestCase):
    def setUp(self):
        super().setUp()
        self.admin, self.reviewer = uuid4(), uuid4()
        for scope in ("profile_review", "verification"):
            self.call("reviewer_grant", {"reviewer_account_id": str(self.reviewer), "scope": scope, "active": True},
                      actor=self.admin, role="administrator", mfa=True)
        for slug, name in (("food", "Food and drink"), ("fabric", "Fabric and tailoring")):
            self.call("category_put", {"slug": slug, "name": name, "active": True}, actor=self.admin, role="administrator", mfa=True)

    def rv(self, operation, data, key="auto"):
        return self.call(operation, data, actor=self.reviewer, role="moderator", mfa=True, key=key)

    def make_business(self, name="Monrovia Bakery", *, category="food", county="montserrado", city="Monrovia",
                      verify=True, publish=True, owner=None, **profile):
        owner, biz = self.register(owner, name)
        bid = biz["id"]
        status, body = self.call("profile_edit", {"business_id": bid, "category": category, "county_code": county,
                                                  "city": city, "description": f"{name} sells good things.", **profile}, actor=owner)
        assert status == 200, body
        self.call("profile_submit", {"business_id": bid}, actor=owner)
        rid = str(ProfileRevision.objects.get(business_id=bid, state="pending_review").id)
        assert self.rv("profile_decide", {"revision_id": rid, "decision": "approve", "reason_code": "looks_correct"})[0] == 200
        if verify:
            self.call("verification_submit", {"business_id": bid, "method": "manual_review", "declaration": True,
                                              "evidence": [{"kind": "registration_number", "value": "LBR-1"}]}, actor=owner)
            cid = self.rv("verification_queue", {})[1]["items"][0]["case_id"]
            self.rv("verification_claim", {"case_id": cid})
            assert self.rv("verification_decide", {"case_id": cid, "decision": "verify", "reason_code": "documents_checked"})[0] == 200
        if publish:
            assert self.call("listing_publish", {"business_id": bid}, actor=owner)[0] == 200
        return owner, bid

    def public(self, operation, data=None, *, signed_in=False, verified=True, origin=None, role="viewer"):
        if signed_in:
            return self.call(operation, data or {}, actor=uuid4(), role=role, verified=verified, origin=origin)
        return self.call(operation, data or {}, role="anonymous", verified=False, origin=origin,
                         envelope={"actor_id": NIL_ACTOR, "role": "anonymous", "mfa_verified": False,
                                   "email_verified": False, "idempotency_key": None, "origin": origin, "data": data or {}})

    def search(self, **params):
        return self.public("public_search", params)


class EligibilityTests(ListingBase):
    def test_publish_requires_verification_and_an_approved_profile(self):
        owner, biz = self.register(name="New Shop")
        status, body = self.call("listing_publish", {"business_id": biz["id"]}, actor=owner)
        self.assertEqual((status, body["code"]), (409, "not_eligible"))
        self.assertIn("not_verified", body["detail"])
        self.assertEqual(self.call("listing_status", {"business_id": biz["id"]}, actor=owner)[1],
                         {"listed": False, "owner_wants_listing": False, "eligible": False,
                          "reasons": ["not_verified", "no_approved_profile"]})
        self.assertEqual(BusinessListing.objects.count(), 0)

    def test_only_the_owner_publishes_and_staff_and_strangers_get_404(self):
        owner, bid = self.make_business(publish=False)
        staff = self.add_staff(owner, bid)
        for actor in (staff, uuid4()):
            for operation in ("listing_publish", "listing_unpublish"):
                self.assertEqual(self.call(operation, {"business_id": bid}, actor=actor)[0], 404)
        self.assertEqual(self.call("listing_status", {"business_id": bid}, actor=staff)[0], 200)
        self.assertEqual(self.call("listing_publish", {"business_id": bid}, actor=owner)[0], 200)
        self.assertEqual(BusinessListing.objects.count(), 1)
        self.assertEqual(self.call("listing_unpublish", {"business_id": bid}, actor=owner)[1]["listed"], False)
        self.assertEqual(BusinessListing.objects.count(), 0)
        self.assertEqual(AuditEvent.objects.filter(kind__startswith="business.listing_").count(), 2)

    def test_revocation_removes_the_listing_in_the_same_request(self):
        owner, bid = self.make_business()
        self.assertEqual(self.public("public_detail", {"business_id": bid})[0], 200)
        cid = self.call("verification_status", {"business_id": bid}, actor=owner) and str(
            __import__("service.models", fromlist=["VerificationCase"]).VerificationCase.objects.get(business_id=bid).id)
        self.assertEqual(self.rv("verification_decide", {"case_id": cid, "decision": "revoke", "reason_code": "fraud_confirmed"})[0], 200)
        self.assertEqual(self.public("public_detail", {"business_id": bid})[0], 404)
        self.assertEqual(self.search()[1]["items"], [])
        status, body = self.call("listing_status", {"business_id": bid}, actor=owner)[0:2]
        self.assertEqual((body["listed"], body["owner_wants_listing"], body["reasons"]), (False, True, ["not_verified"]))

    def test_unapproved_and_rejected_revisions_never_reach_the_public_view(self):
        owner, bid = self.make_business()
        self.call("profile_edit", {"business_id": bid, "display_name": "Misleading Name"}, actor=owner)
        self.call("profile_submit", {"business_id": bid}, actor=owner)  # pending review
        self.assertEqual(self.public("public_detail", {"business_id": bid})[1]["display_name"], "Monrovia Bakery")
        rid = str(ProfileRevision.objects.get(business_id=bid, state="pending_review").id)
        self.rv("profile_decide", {"revision_id": rid, "decision": "reject", "reason_code": "name_misleading"})
        self.assertEqual(self.public("public_detail", {"business_id": bid})[1]["display_name"], "Monrovia Bakery")

    def test_an_approved_revision_and_hours_update_the_projection(self):
        owner, bid = self.make_business()
        self.call("profile_edit", {"business_id": bid, "display_name": "Ma Kolo Bakery"}, actor=owner)
        self.call("profile_submit", {"business_id": bid}, actor=owner)
        rid = str(ProfileRevision.objects.get(business_id=bid, state="pending_review").id)
        self.rv("profile_decide", {"revision_id": rid, "decision": "approve", "reason_code": "looks_correct"})
        self.call("hours_replace", {"business_id": bid, "rules": [{"weekday": 0, "opens": "08:00", "closes": "17:00"}]}, actor=owner)
        body = self.public("public_detail", {"business_id": bid})[1]
        self.assertEqual((body["display_name"], len(body["hours"]["rules"])), ("Ma Kolo Bakery", 1))

    def test_reconciliation_reports_and_repairs_drift(self):
        owner, bid = self.make_business()
        other_owner, other = self.make_business("Unlisted Co", publish=False)
        BusinessListing.objects.filter(business_id=bid).delete()
        listing = BusinessListing.objects.create(business_id=other, display_name="x", name_sort="x", category_slug="food",
                                                 category_name="Food", county_code="x1", city="c", time_zone="UTC")
        from service import listings
        self.assertEqual(listings.reconcile(), {"missing": 1, "stale": 0, "orphaned": 1})
        self.assertEqual(listings.reconcile(apply=True), {"missing": 1, "stale": 0, "orphaned": 1})
        self.assertEqual(listings.reconcile(), {"missing": 0, "stale": 0, "orphaned": 0})
        self.assertEqual(list(BusinessListing.objects.values_list("business_id", flat=True)), [__import__("uuid").UUID(bid)])


class PublicViewTests(ListingBase):
    def setUp(self):
        super().setUp()
        self.owner, self.bid = self.make_business(
            address_line="12 Broad Street",
            contacts=[{"kind": "phone", "value": "+231770000000", "is_public": True},
                      {"kind": "email", "value": "secret@shop.example", "is_public": False}])

    def test_projection_holds_public_columns_only(self):
        names = {field.name for field in BusinessListing._meta.get_fields()}
        self.assertEqual(names, {"business", "display_name", "name_sort", "category_slug", "category_name", "county_code",
                                 "city", "summary", "description", "address_line", "time_zone", "hours", "contacts",
                                 "verified", "updated_at"})

    def test_anonymous_sees_the_minimal_set_and_never_private_data(self):
        status, body = self.public("public_detail", {"business_id": self.bid})
        self.assertEqual(status, 200)
        self.assertEqual(set(body), {"id", "display_name", "category", "county_code", "city", "summary", "verified",
                                     "open_now", "description", "address_line", "time_zone", "hours", "contacts",
                                     "contacts_access"})
        self.assertEqual((body["contacts"], body["contacts_access"], body["address_line"]), (None, "sign_in_required", None))
        text = str(body)
        for secret in ("Monrovia Bakery Ltd", "secret@shop.example", "+231770000000", "12 Broad Street", "created_by"):
            self.assertNotIn(secret, text)

    def test_signed_in_verified_accounts_see_only_public_contacts_under_a_budget(self):
        status, body = self.public("public_detail", {"business_id": self.bid}, signed_in=True)
        self.assertEqual((body["contacts_access"], body["contacts"]), ("available", [{"kind": "phone", "value": "+231770000000"}]))
        self.assertEqual(self.public("public_detail", {"business_id": self.bid}, signed_in=True, verified=False)[1]["contacts_access"],
                         "verified_email_required")
        actor = uuid4()
        with patch.dict(limits.BUDGETS, {"contact_reveal": (2, timedelta(days=1))}):
            access = [self.call("public_detail", {"business_id": self.bid}, actor=actor)[1]["contacts_access"] for _ in range(3)]
        self.assertEqual(access, ["available", "available", "limit_reached"])

    def test_address_is_public_only_when_the_owner_opts_in(self):
        self.call("profile_edit", {"business_id": self.bid, "address_public": True}, actor=self.owner)
        self.call("profile_submit", {"business_id": self.bid}, actor=self.owner)  # address flag is not material: applies
        self.assertEqual(self.public("public_detail", {"business_id": self.bid})[1]["address_line"], "12 Broad Street")

    def test_unknown_unlisted_and_unpublished_are_indistinguishable(self):
        other_owner, other = self.make_business("Hidden Co", publish=False)
        answers = {str(self.public("public_detail", {"business_id": b})) for b in (other, str(uuid4()))}
        self.assertEqual(len(answers), 1)
        self.call("listing_unpublish", {"business_id": self.bid}, actor=self.owner)
        self.assertEqual(self.public("public_detail", {"business_id": self.bid})[0], 404)

    def test_anonymous_envelopes_are_strict(self):
        base = {"actor_id": NIL_ACTOR, "role": "anonymous", "mfa_verified": False, "email_verified": False,
                "idempotency_key": None, "origin": None, "data": {"business_id": self.bid}}
        self.assertEqual(self.call("public_detail", envelope=base)[0], 200)
        for change in ({"actor_id": str(uuid4())}, {"mfa_verified": True}, {"email_verified": True}, {"origin": 5},
                       {"origin": "x" * 46}):
            self.assertEqual(self.call("public_detail", envelope={**base, **change})[0], 400, change)
        self.assertEqual(self.call("public_detail", envelope={**base, "role": "viewer"})[0], 400)
        self.assertEqual(self.call("get_mine", envelope={**base, "data": {"business_id": self.bid}})[0], 403)  # anonymous cannot use private operations

    def test_public_reads_are_throttled_per_account_or_client_address(self):
        with patch.dict(limits.BUDGETS, {"public_read": (3, timedelta(hours=1))}):
            first = [self.public("public_detail", {"business_id": self.bid}, origin="203.0.113.5")[0] for _ in range(4)]
            other = self.public("public_detail", {"business_id": self.bid}, origin="203.0.113.6")[0]
            unknown = [self.public("public_detail", {"business_id": self.bid})[0] for _ in range(4)]
        self.assertEqual((first, other, unknown[-1]), ([200, 200, 200, 429], 200, 429))


class SearchTests(ListingBase):
    def setUp(self):
        super().setUp()
        self.shops = {name: self.make_business(name, category=category, county=county, city=city)[1]
                      for name, category, county, city in (
                          ("Alpha Bakery", "food", "montserrado", "Monrovia"), ("Beta Cafe", "food", "montserrado", "Paynesville"),
                          ("Gamma Tailors", "fabric", "montserrado", "Monrovia"), ("Delta Cakes", "food", "margibi", "Kakata"),
                          ("100% Fresh", "food", "nimba", "Ganta"))}

    def names(self, **params):
        status, body = self.search(**params)
        self.assertEqual(status, 200, body)
        return [item["display_name"] for item in body["items"]]

    def test_filters_narrow_results_and_unlisted_businesses_never_appear(self):
        self.make_business("Draft Only", verify=False, publish=False) if False else None
        self.assertEqual(self.names(), ["100% Fresh", "Alpha Bakery", "Beta Cafe", "Delta Cakes", "Gamma Tailors"])
        self.assertEqual(self.names(category="fabric"), ["Gamma Tailors"])
        self.assertEqual(self.names(county="montserrado"), ["Alpha Bakery", "Beta Cafe", "Gamma Tailors"])
        self.assertEqual(self.names(county="montserrado", city="monrovia", category="food"), ["Alpha Bakery"])
        self.assertEqual(self.names(verified="true"), self.names())
        self.assertEqual(self.names(verified="false"), [])
        owner, other = self.make_business("Not Public", publish=False)
        self.assertNotIn("Not Public", self.names())

    def test_text_search_ranks_name_matches_first_and_treats_wildcards_literally(self):
        self.assertEqual(self.names(q="cake"), ["Delta Cakes"])
        self.assertEqual(self.names(q="good things")[0], "100% Fresh")  # description-only matches share a tier, then by name
        self.assertEqual(self.names(q="Fabric")[0], "Gamma Tailors")    # category name match
        self.assertEqual(self.names(q="%"), ["100% Fresh"])
        self.assertEqual(self.names(q="_"), [])
        for hostile in ("'; DROP TABLE x;--", "a & b | !c", "\\", "ａｂｃ"):
            self.assertEqual(self.search(q=hostile)[0], 200, hostile)
        self.assertEqual(BusinessListing.objects.count(), 5)

    def test_relevance_orders_name_matches_before_other_matches(self):
        self.make_business("Cake Palace", category="food", county="margibi", city="Kakata")
        owner, bid = self.make_business("Zeta Foods", category="food", county="margibi", city="Kakata")
        self.call("profile_edit", {"business_id": bid, "description": "We also sell cake."}, actor=owner)
        self.call("profile_submit", {"business_id": bid}, actor=owner)
        self.assertEqual(self.names(q="cake"), ["Cake Palace", "Delta Cakes", "Zeta Foods"])
        self.assertEqual(self.names(q="cake", sort="name"), ["Cake Palace", "Delta Cakes", "Zeta Foods"])
        self.assertEqual(self.search(sort="relevance")[0], 400)  # relevance needs a query

    def test_pagination_is_complete_stable_and_cursors_are_bound_to_their_query(self):
        seen, cursor = [], None
        for _ in range(10):
            status, body = self.search(limit=2, **({"cursor": cursor} if cursor else {}))
            self.assertEqual(status, 200)
            seen += [i["display_name"] for i in body["items"]]
            cursor = body["next_cursor"]
            if not cursor:
                break
        self.assertEqual(seen, self.names())
        _, first = self.search(limit=2)
        for bad in ("garbage", first["next_cursor"][:-3] + "abc", first["next_cursor"] + "x", "a." + "b" * 64):
            self.assertEqual(self.search(limit=2, cursor=bad)[0], 400, bad)
        self.assertEqual(self.search(limit=2, cursor=first["next_cursor"], category="food")[0], 400)  # other filters
        self.assertEqual(self.search(limit=2, cursor=first["next_cursor"])[0], 200)

    def test_inputs_are_rejected_not_ignored(self):
        for bad in ({"q": ""}, {"q": "x" * 101}, {"q": "a\x00b"}, {"category": "Bad Slug"}, {"county": "A B"},
                    {"open_now": "maybe"}, {"verified": 1}, {"sort": "price"}, {"limit": 21}, {"limit": 0},
                    {"limit": "x"}, {"lat": "6.3"}, {"near": "me"}, {"boost": "true"}, {"cursor": 5}):
            self.assertEqual(self.search(**bad)[0], 400, bad)

    def test_open_now_filter_uses_the_business_clock(self):
        monday_9am = dt.datetime(2026, 11, 30, 9, 0, tzinfo=dt.timezone.utc)
        for name in ("Alpha Bakery", "Beta Cafe"):
            owner = self.owner_of(name)
            self.call("hours_replace", {"business_id": self.shops[name], "rules": [{"weekday": 0, "opens": "08:00" if name == "Alpha Bakery" else "10:00",
                                                                                    "closes": "17:00"}]}, actor=owner)
        with patch("service.listings.timezone.now", return_value=monday_9am):
            self.assertEqual(self.names(open_now="true"), ["Alpha Bakery"])
            self.assertEqual(self.names(open_now="false"), ["Beta Cafe"])  # unknown hours are neither open nor closed
            status, body = self.search()
            states = {i["display_name"]: i["open_now"] for i in body["items"]}
        self.assertEqual((states["Alpha Bakery"], states["Beta Cafe"], states["Delta Cakes"]), (True, False, None))

    def owner_of(self, name):
        from service.models import BusinessMembership
        return BusinessMembership.objects.get(business_id=self.shops[name], role="owner").account_id

    def test_a_scan_cap_returns_a_resumable_cursor_instead_of_scanning_everything(self):
        monday_9am = dt.datetime(2026, 11, 30, 9, 0, tzinfo=dt.timezone.utc)
        with patch.object(limits, "SEARCH_SCAN_CAP", 2), patch.object(limits, "SEARCH_CHUNK", 2), \
                patch("service.listings.timezone.now", return_value=monday_9am):
            status, body = self.search(open_now="true", limit=1)
        self.assertEqual((status, body["items"]), (200, []))  # nothing among the first rows examined is open
        self.assertIsNotNone(body["next_cursor"])
