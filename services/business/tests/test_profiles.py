"""B3: categories, profile revisions, contacts, location, hours and reviewer approval of material changes."""
import datetime as dt
from datetime import timedelta
from unittest.mock import patch
from uuid import uuid4

from service import hours, limits
from service.models import AuditEvent, Business, BusinessCategory, ProfileRevision, ReviewerGrant
from .support import BusinessTestCase


class ProfileBase(BusinessTestCase):
    def setUp(self):
        super().setUp()
        self.admin, self.reviewer = uuid4(), uuid4()
        self.owner, self.biz = self.register()
        self.bid = self.biz["id"]
        self.put_category("food", "Food and drink")

    def put_category(self, slug, name, **extra):
        return self.call("category_put", {"slug": slug, "name": name, "active": True, **extra}, actor=self.admin,
                         role="administrator", mfa=True)

    def edit(self, owner=None, **fields):
        return self.call("profile_edit", {"business_id": self.bid, **fields}, actor=owner or self.owner)

    def submit(self, owner=None):
        return self.call("profile_submit", {"business_id": self.bid}, actor=owner or self.owner)

    def complete(self, **extra):
        fields = {"category": "food", "county_code": "montserrado", "city": "Monrovia", "description": "Fresh bread daily."}
        return self.edit(**{**fields, **extra})

    def grant(self, reviewer=None, scope="profile_review", target=None):
        data = {"reviewer_account_id": str(reviewer or self.reviewer), "scope": scope, "active": True}
        if target:
            data["target_business_id"] = target
        return self.call("reviewer_grant", data, actor=self.admin, role="administrator", mfa=True)

    def rv(self, operation, data=None, actor=None, role="moderator", mfa=True, **kw):
        return self.call(operation, data or {}, actor=actor or self.reviewer, role=role, mfa=mfa, **kw)

    def approve_first(self):
        self.complete()
        self.assertEqual(self.submit()[1]["state"], "pending_review")
        self.grant()
        rid = str(ProfileRevision.objects.get(state="pending_review").id)
        return self.rv("profile_decide", {"revision_id": rid, "decision": "approve", "reason_code": "looks_correct"})


class CategoryTests(ProfileBase):
    def test_only_an_mfa_administrator_manages_categories_and_depth_is_two(self):
        data = {"slug": "bakery", "name": "Bakery", "active": True, "parent": "food"}
        for role, mfa in (("viewer", True), ("moderator", True), ("administrator", False)):
            self.assertEqual(self.call("category_put", data, actor=self.admin, role=role, mfa=mfa)[0], 403)
        self.assertEqual(self.put_category("bakery", "Bakery", parent="food")[1]["parent"], "food")
        self.assertEqual(self.put_category("pastry", "Pastry", parent="bakery")[1]["code"], "depth_exceeded")
        self.assertEqual(self.put_category("food", "Food", parent="bakery")[1]["code"], "depth_exceeded")
        self.assertEqual(self.put_category("x1", "Odd", parent="missing")[1]["code"], "unknown_parent")
        self.assertEqual(self.put_category("BAD SLUG", "Bad")[0], 400)

    def test_list_shows_only_active_categories(self):
        self.put_category("old", "Old")
        self.call("category_put", {"slug": "old", "name": "Old", "active": False}, actor=self.admin, role="administrator", mfa=True)
        status, body = self.call("category_list", {}, actor=self.owner)
        self.assertEqual([c["slug"] for c in body["items"]], ["food"])
        self.assertEqual(self.call("category_list", {"x": 1}, actor=self.owner)[0], 400)


class EditTests(ProfileBase):
    def test_owner_edits_a_draft_and_it_is_private_until_approved(self):
        status, body = self.complete(display_name="Ma Kolo Bakery", address_line="12 Broad Street",
                                     contacts=[{"kind": "phone", "value": "+231 77 000 0000", "is_public": True},
                                               {"kind": "website", "value": "https://bakery.example/menu"}])
        self.assertEqual(status, 200)
        self.assertEqual((body["state"], body["revision_no"], body["category"]), ("draft", 1, "food"))
        self.assertFalse(body["address_public"])
        self.assertEqual([c["is_public"] for c in body["contacts"]], [True, False])  # private unless opted in
        self.assertEqual(self.call("get_mine", {"business_id": self.bid}, actor=self.owner)[1]["display_name"], "Monrovia Bakery")
        view = self.call("profile_get", {"business_id": self.bid}, actor=self.owner)[1]
        self.assertIsNone(view["approved"])
        self.assertIn("address_line", view["working"]["changed_fields"])

    def test_staff_cannot_edit_or_submit_but_can_read_and_foreign_is_404(self):
        staff = self.add_staff(self.owner, self.bid)
        self.assertEqual(self.edit(owner=staff, city="Paynesville")[0], 404)
        self.assertEqual(self.submit(owner=staff)[0], 404)
        self.assertEqual(self.call("profile_get", {"business_id": self.bid}, actor=staff)[0], 200)
        stranger = uuid4()
        for operation, extra in (("profile_get", {}), ("profile_edit", {"city": "X"}), ("profile_submit", {}),
                                 ("hours_replace", {"rules": []})):
            self.assertEqual(self.call(operation, {"business_id": self.bid, **extra}, actor=stranger)[0], 404, operation)
        self.assertEqual(ProfileRevision.objects.count(), 0)

    def test_inputs_are_validated_and_authority_cannot_be_named(self):
        bad = [{"display_name": "x"}, {"category": "Bad Slug"}, {"county_code": "Mont Serrado"}, {"city": ""},
               {"description": "d" * 2001}, {"address_line": "a" * 201}, {"latitude": 91, "longitude": 0},
               {"latitude": 1.0}, {"latitude": "nan", "longitude": 0}, {"time_zone": "Mars/Base"},
               {"address_public": "yes"}, {"state": "approved"}, {"business_id": str(uuid4())}, {},
               {"contacts": [{"kind": "fax", "value": "123456789"}]},
               {"contacts": [{"kind": "phone", "value": "abc"}]},
               {"contacts": [{"kind": "phone", "value": "12"}]},
               {"contacts": [{"kind": "email", "value": "not-an-email"}]},
               {"contacts": [{"kind": "website", "value": "http://insecure.example"}]},
               {"contacts": [{"kind": "website", "value": "javascript:alert(1)"}]},
               {"contacts": [{"kind": "website", "value": "https://" + "someone" + ":" + "hunter2" + "@evil.example"}]},  # credentials in a URL
               {"contacts": [{"kind": "social", "value": "https://a.example", "is_public": "true"}]},
               {"contacts": [{"kind": "phone", "value": "+231770000000"}] * 2},
               {"contacts": [{"kind": "phone", "value": f"+2317700000{i:02d}"} for i in range(11)]}]
        for fields in bad:
            with patch.dict(limits.BUDGETS, {"profile_edit": (1000, timedelta(hours=1))}):
                status = self.call("profile_edit", {**{"business_id": self.bid}, **fields}, actor=self.owner)[0]
            self.assertEqual(status, 400, fields)
        self.assertEqual(self.edit(category="missing")[1]["code"], "unknown_category")
        self.assertEqual(ProfileRevision.objects.count(), 0)  # every refusal rolled back, nothing half-created

    def test_coordinates_are_paired_and_stored_as_fixed_precision(self):
        status, body = self.edit(latitude=6.3, longitude="-10.8")
        self.assertEqual((status, body["latitude"], body["longitude"]), (200, "6.300000", "-10.800000"))
        self.assertEqual(self.edit(latitude=None)[0], 400)
        self.assertEqual(self.edit(latitude=None, longitude=None)[0], 200)

    def test_edits_are_audited_throttled_and_idempotent(self):
        for _ in range(2):
            self.call("profile_edit", {"business_id": self.bid, "city": "Monrovia"}, actor=self.owner, key="same-key-0123456789")
        self.assertEqual(AuditEvent.objects.filter(kind="business.profile_edited").count(), 1)
        statuses = [self.edit(city=f"City {i}")[0] for i in range(limits.BUDGETS["profile_edit"][0] + 1)]
        self.assertEqual(statuses[-1], 429)


class ApprovalTests(ProfileBase):
    def test_first_submission_needs_a_complete_profile_and_goes_to_review(self):
        self.edit(description="Only a description.")
        status, body = self.submit()
        self.assertEqual((status, body["code"]), (409, "incomplete_profile"))
        self.complete()
        status, body = self.submit()
        self.assertEqual((status, body["state"], body["applied"]), (200, "pending_review", False))
        self.assertEqual(self.edit(city="Other")[1]["code"], "revision_pending")
        self.assertEqual(self.submit()[0], 409)

    def test_reviewer_needs_a_profile_review_grant_and_is_not_the_submitter(self):
        self.complete()
        self.submit()
        rid = str(ProfileRevision.objects.get(state="pending_review").id)
        decide = {"revision_id": rid, "decision": "approve", "reason_code": "looks_correct"}
        self.assertEqual(self.rv("profile_queue")[1]["items"], [])
        self.grant(scope="verification")  # a verification grant is not a profile-review grant
        for operation, data in (("profile_revision", {"revision_id": rid}), ("profile_decide", decide)):
            self.assertEqual(self.rv(operation, data)[0], 404, operation)
        for role, mfa in (("viewer", True), ("moderator", False), ("administrator", False)):
            self.assertEqual(self.rv("profile_decide", decide, role=role, mfa=mfa)[0], 403)
        self.grant()
        self.assertEqual(self.rv("profile_queue")[1]["items"][0]["business_id"], self.bid)
        ProfileRevision.objects.filter(pk=rid).update(submitted_by_account_id=self.reviewer)
        self.assertEqual(self.rv("profile_decide", decide)[0], 404)
        self.assertEqual(ProfileRevision.objects.get(pk=rid).state, "pending_review")

    def test_approval_publishes_the_revision_and_updates_the_display_name(self):
        self.complete(display_name="Ma Kolo Bakery")
        self.submit()
        self.grant()
        rid = str(ProfileRevision.objects.get(state="pending_review").id)
        self.assertEqual(self.rv("profile_revision", {"revision_id": rid})[1]["changed_fields"].count("display_name"), 1)
        status, body = self.rv("profile_decide", {"revision_id": rid, "decision": "approve", "reason_code": "looks_correct"},
                               key="decide-key-0123456789")
        self.assertEqual((status, body["state"]), (200, "approved"))
        self.assertEqual(Business.objects.get(pk=self.bid).display_name, "Ma Kolo Bakery")
        self.assertEqual(self.rv("profile_decide", {"revision_id": rid, "decision": "approve", "reason_code": "looks_correct"},
                                 key="decide-key-0123456789"), (status, body))
        view = self.call("profile_get", {"business_id": self.bid}, actor=self.owner)[1]
        self.assertEqual((view["approved"]["display_name"], view["working"]), ("Ma Kolo Bakery", None))

    def test_rejection_keeps_the_old_public_revision_and_shows_the_reason_to_the_owner(self):
        self.approve_first()
        self.edit(display_name="Misleading Name")
        self.assertEqual(self.submit()[1]["state"], "pending_review")  # display_name is material
        rid = str(ProfileRevision.objects.get(state="pending_review").id)
        self.rv("profile_decide", {"revision_id": rid, "decision": "reject", "reason_code": "name_misleading"})
        view = self.call("profile_get", {"business_id": self.bid}, actor=self.owner)[1]
        self.assertEqual(view["approved"]["display_name"], "Monrovia Bakery")
        self.assertEqual((view["last_rejected"]["reason_code"], view["working"]), ("name_misleading", None))
        self.assertEqual(Business.objects.get(pk=self.bid).display_name, "Monrovia Bakery")

    def test_non_material_edits_apply_without_review_and_material_ones_do_not(self):
        self.approve_first()
        self.edit(description="Now also selling cakes.", time_zone="Africa/Monrovia")
        status, body = self.submit()
        self.assertEqual((status, body["state"], body["applied"]), (200, "approved", True))
        self.assertEqual(AuditEvent.objects.filter(kind="business.profile_applied").count(), 1)
        approved = ProfileRevision.objects.filter(state="approved")
        self.assertEqual((approved.count(), approved.get().revision_no, ProfileRevision.objects.filter(state="superseded").count()), (1, 2, 1))
        self.edit(address_line="5 New Road")
        self.assertEqual(self.submit()[1]["state"], "pending_review")
        self.assertEqual(ProfileRevision.objects.get(state="approved").address_line, "")

    def test_changing_a_live_contact_fails_closed_until_step_up_exists(self):
        self.complete(contacts=[{"kind": "phone", "value": "+231770000000", "is_public": True}])
        self.assertEqual(self.submit()[0], 200)  # before first approval nothing is live
        self.grant()
        rid = str(ProfileRevision.objects.get(state="pending_review").id)
        self.rv("profile_decide", {"revision_id": rid, "decision": "approve", "reason_code": "looks_correct"})
        status, body = self.edit(contacts=[{"kind": "phone", "value": "+231770009999", "is_public": True}])
        self.assertEqual((status, body["code"]), (403, "step_up_unavailable"))
        self.assertEqual(ProfileRevision.objects.filter(state="draft").count(), 0)  # nothing was left behind
        self.assertEqual(self.edit(contacts=[{"kind": "phone", "value": "+231770000000", "is_public": True}])[0], 200)  # unchanged set

    def test_closed_business_cannot_be_edited(self):
        Business.objects.filter(pk=self.bid).update(state="closed")
        for operation, extra in (("profile_edit", {"city": "X"}), ("hours_replace", {"rules": []})):
            self.assertEqual(self.call(operation, {"business_id": self.bid, **extra}, actor=self.owner)[1]["code"], "business_closed")

    def test_profile_review_events_are_audited(self):
        self.approve_first()
        self.rv("profile_queue")
        kinds = set(AuditEvent.objects.values_list("kind", flat=True))
        self.assertTrue({"business.profile_edited", "business.profile_submitted", "business.profile_decided",
                         "business.profile_queue_read", "business.category_changed"} <= kinds)


class HoursTests(ProfileBase):
    def put(self, rules, exceptions=None, owner=None, **extra):
        data = {"business_id": self.bid, "rules": rules, **({"exceptions": exceptions} if exceptions is not None else {}), **extra}
        return self.call("hours_replace", data, actor=owner or self.owner)

    def test_owner_and_staff_replace_hours_atomically(self):
        status, body = self.put([{"weekday": 0, "opens": "08:00", "closes": "17:00"}, {"weekday": 0, "opens": "18:00", "closes": "24:00"}],
                                [{"on_date": "2026-12-25", "closed": True}, {"on_date": "2026-12-31", "closed": False, "opens": "09:00", "closes": "12:00"}])
        self.assertEqual(status, 200)
        self.assertEqual(len(body["rules"]), 2)
        staff = self.add_staff(self.owner, self.bid)
        self.assertEqual(self.put([{"weekday": 1, "opens": "09:00", "closes": "13:00"}], owner=staff)[0], 200)
        view = self.call("profile_get", {"business_id": self.bid}, actor=self.owner)[1]["hours"]
        self.assertEqual((len(view["rules"]), view["exceptions"]), (1, []))  # replaced, not merged

    def test_invalid_hours_are_rejected_and_leave_existing_hours_untouched(self):
        self.put([{"weekday": 2, "opens": "09:00", "closes": "17:00"}])
        good = {"weekday": 3, "opens": "09:00", "closes": "17:00"}
        for rules, exceptions in (
                ([{"weekday": 7, "opens": "09:00", "closes": "17:00"}], None), ([{"weekday": True, "opens": "09:00", "closes": "17:00"}], None),
                ([{"weekday": 1, "opens": "17:00", "closes": "09:00"}], None), ([{"weekday": 1, "opens": "09:00", "closes": "09:00"}], None),
                ([{"weekday": 1, "opens": "24:00", "closes": "24:00"}], None), ([{"weekday": 1, "opens": "9:00", "closes": "17:00"}], None),
                ([{"weekday": 1, "opens": "09:00", "closes": "25:00"}], None),
                ([good, {**good, "opens": "16:00", "closes": "20:00"}], None),
                ([good] * 29, None), ([{**good, "x": 1}], None),
                ([good], [{"on_date": "2026-12-25", "closed": True}, {"on_date": "2026-12-25", "closed": True}]),
                ([good], [{"on_date": "25/12/2026", "closed": True}]), ([good], [{"on_date": "2026-12-25", "closed": True, "opens": "09:00"}]),
                ([good], [{"on_date": "2026-12-25", "closed": False}]), ([good], [{"on_date": "2026-12-25", "closed": "no"}])):
            self.assertEqual(self.put(rules, exceptions)[0], 400, (rules, exceptions))
        view = self.call("profile_get", {"business_id": self.bid}, actor=self.owner)[1]["hours"]
        self.assertEqual([r["weekday"] for r in view["rules"]], [2])

    def test_open_now_uses_the_business_time_zone_exceptions_and_unknown(self):
        rules, exceptions = hours.validate({"rules": [{"weekday": 0, "opens": "08:00", "closes": "17:00"}],
                                            "exceptions": [{"on_date": "2026-12-07", "closed": True}]})
        utc = dt.timezone.utc
        monday = dt.datetime(2026, 11, 30, 9, 0, tzinfo=utc)
        self.assertEqual(dt.date(2026, 11, 30).weekday(), 0)
        self.assertTrue(hours.is_open(rules, exceptions, "Africa/Monrovia", monday))
        self.assertFalse(hours.is_open(rules, exceptions, "Africa/Monrovia", monday.replace(hour=17)))   # closing minute excluded
        self.assertTrue(hours.is_open(rules, exceptions, "Africa/Monrovia", monday.replace(hour=8)))
        self.assertFalse(hours.is_open(rules, exceptions, "Africa/Monrovia", monday + timedelta(days=7)))  # exception day closed
        self.assertTrue(hours.is_open(rules, exceptions, "Africa/Lagos", monday.replace(hour=7)))          # 08:00 local at UTC+1
        self.assertFalse(hours.is_open(rules, exceptions, "Pacific/Auckland", monday))                      # already Tuesday there
        self.assertIsNone(hours.is_open([], [], "Africa/Monrovia", monday))
