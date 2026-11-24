"""Business administration in the protected console (Phase 6C): scope, decisions, replay, tampering, safe rendering.

The gateway is replaced by a recorder. Each test states what the console may send; the owning services (not these
tests) decide scope and transitions, so what is proved here is that the console never decides from browser state, never
forwards what it did not validate, never trusts a response it did not shape-check and never echoes the gateway.
"""

import re
import time
import uuid
from pathlib import Path
from unittest.mock import patch

from django.test import Client, TestCase
from django.urls import reverse

from tests import test_admin
from web import business_views

HOSTILE = '<script>alert("x")</script><img src=x onerror=alert(1)>'
WHEN = "2026-11-24T10:00:00+00:00"


def uid():
    return str(uuid.uuid4())


class Gateway:
    """Answers by (method, path). Records every call so a test can assert exactly what was, and was not, sent."""

    def __init__(self, test, routes=None, default=(503, {})):
        self.test, self.routes, self.calls, self.default = test, dict(routes or {}), [], default

    def __call__(self, path, **kwargs):
        method = kwargs.get("method", "GET")
        if path == "/me":
            return 200, dict(self.test.account)
        key = kwargs.get("idempotency_key")
        if method != "GET" and path != "/admin/accounts/lookup":   # every Business mutation must be idempotent
            self.test.assertRegex(key or "", r"^[A-Za-z0-9_-]{16,128}$", f"{method} {path} sent without a valid key")
        self.calls.append({"method": method, "path": path, "data": kwargs.get("data"), "key": key})
        answer = self.routes.get((method, path), self.routes.get((method, path.split("?")[0]), self.default))
        return answer(kwargs) if callable(answer) else answer

    def sent(self):
        return [c for c in self.calls if c["method"] != "GET"]


def verification_item(case=None, **changes):
    return {"case_id": case or uid(), "business_id": uid(), "display_name": "Ma Kolo Foods", "state": "submitted",
            "submitted_at": WHEN, "assigned_to_you": False, **changes}


def queue_of(items, key, next_cursor=None):
    return 200, {"items": sorted(items, key=lambda i: i[key]), "next_cursor": next_cursor}


class ConsoleCase(TestCase):
    setUp = test_admin.AdminConsoleTests.setUp
    login = test_admin.AdminConsoleTests.login

    def serve(self, routes=None, default=(503, {})):
        gateway = Gateway(self, routes, default)
        return gateway, patch("web.views._api", side_effect=gateway)

    def case_detail(self, case, **changes):
        return {"case_id": case, "business_id": uid(), "state": "under_review", "method": "manual_review",
                "display_name": "Ma Kolo Foods", "legal_name": "Kolo Foods Ltd", "submitted_at": WHEN,
                "assigned_to_you": True,
                "evidence": [{"id": uid(), "kind": "registration_number", "value": "LBR-2026-1"}],
                "duplicate_candidates": [], **changes}

    def revision(self, rid, **changes):
        return {"business_id": uid(), "id": rid, "revision_no": 2, "state": "pending_review", "display_name": "Kolo Foods",
                "category": "food", "description": "Fresh bread daily.", "county_code": "montserrado", "city": "Monrovia",
                "address_line": "1 Broad St", "address_public": False, "latitude": None, "longitude": None,
                "coordinates_public": False, "time_zone": "Africa/Monrovia",
                "contacts": [{"kind": "phone", "value": "+231770000000", "is_public": True}], "reason_code": None,
                "changed_fields": ["description"], **changes}

    def report(self, rid, subject="review", **changes):
        content = {"review": {"rating": 2, "title": None, "body": "Rude staff and cold food.", "state": "held",
                              "basis": "open", "hold_reasons": ["author_burst"]},
                   "review_response": {"body": "Thank you.", "removed": False},
                   "inquiry_message": {"body": "Call me back.", "author_kind": "customer", "removed": False}}[subject]
        return {"report_id": rid, "subject_type": subject, "subject_id": uid(), "business_id": uid(),
                "reason_code": "misleading", "details": "Looks fake.", "system_hold": False, "content": content, **changes}


class OverviewAndQueueTests(ConsoleCase):
    def queues(self, extra=None):
        v, p, r = verification_item(), {"revision_id": uid(), "business_id": uid(), "display_name": "Beta Cafe",
                                        "submitted_at": WHEN}, {"report_id": uid(), "subject_type": "review",
                                                                "business_id": uid(), "reason_code": "misleading",
                                                                "system_hold": True, "created_at": WHEN}
        routes = {**(extra or {}),("GET", "/moderation/business-verifications"): queue_of([v], "case_id"),
                  ("GET", "/moderation/business-profile-revisions"): queue_of([p], "revision_id"),
                  ("GET", "/moderation/business-reports"): queue_of([r], "report_id")}
        routes.update(extra or {})
        return routes, v, p, r

    def test_overview_summarises_each_queue_and_lists_businesses_in_scope(self):
        self.login("moderator")
        routes, v, p, r = self.queues()
        gateway, api = self.serve(routes)
        with api:
            response = self.client.get(reverse("business"))
        self.assertContains(response, "Queue summary")
        self.assertContains(response, "Ma Kolo Foods")
        self.assertContains(response, "Beta Cafe")
        self.assertContains(response, "1 automatic hold")
        self.assertContains(response, reverse("business-verifications-detail", args=[v["case_id"]]))
        self.assertEqual([c["method"] for c in gateway.calls], ["GET", "GET", "GET"])
        self.assertNotContains(response, "Categories")        # administrator-only tabs are not offered to a moderator
        with self.serve(routes)[1]:
            filtered = self.client.get(reverse("business"), {"q": "beta", "queue": "profiles"})
        self.assertContains(filtered, "Beta Cafe")
        self.assertNotContains(filtered, "Ma Kolo Foods")

    def test_one_failing_queue_does_not_hide_the_others_and_total_failure_is_explained(self):
        self.login()
        routes, *_ = self.queues({("GET", "/moderation/business-reports"): (503, {})})
        with self.serve(routes)[1]:
            page = self.client.get(reverse("business"))
        self.assertContains(page, "Unavailable right now")
        self.assertContains(page, "Ma Kolo Foods")
        closed = {("GET", path): (404, {"detail": "Not found"}) for path in
                  ("/moderation/business-verifications", "/moderation/business-profile-revisions", "/moderation/business-reports")}
        with self.serve(closed)[1]:
            page = self.client.get(reverse("business"))
        self.assertContains(page, "may not be enabled in this environment")
        self.assertNotContains(page, "Not found")
        expired = {key: (401, {}) for key in closed}
        with self.serve(expired)[1]:
            self.assertEqual(self.client.get(reverse("business"))["Location"].split("?")[0], "/login/")

    def test_a_reviewer_with_nothing_in_scope_sees_an_empty_state_not_an_error(self):
        self.login("moderator")
        empty = {("GET", path): queue_of([], "case_id") for path in
                 ("/moderation/business-verifications", "/moderation/business-profile-revisions", "/moderation/business-reports")}
        with self.serve(empty)[1]:
            page = self.client.get(reverse("business"))
        self.assertContains(page, "Nothing is waiting for you right now.")

    def test_queue_lists_filters_pages_and_jumps_to_an_item(self):
        self.login("moderator")
        mine = verification_item(state="under_review", assigned_to_you=True, display_name="Mine Co")
        other = verification_item(display_name="Other Co")
        route = {("GET", "/moderation/business-verifications"): queue_of([mine, other], "case_id", next_cursor=None)}
        with self.serve(route)[1]:
            page = self.client.get(reverse("business-verifications"))
            claimed = self.client.get(reverse("business-verifications"), {"mine": "1"})
            named = self.client.get(reverse("business-verifications"), {"q": "other"})
        self.assertContains(page, "Mine Co")
        self.assertContains(page, "Other Co")
        self.assertContains(claimed, "Mine Co")
        self.assertNotContains(claimed, "Other Co")
        self.assertContains(named, "Other Co")
        self.assertNotContains(named, "Mine Co")
        target = uid()
        gateway, api = self.serve()
        with api:
            jump = self.client.get(reverse("business-reports"), {"find": f" {target.upper()} "})
        self.assertEqual(jump["Location"], reverse("business-reports-detail", args=[target]))
        self.assertEqual(gateway.sent() + [c for c in gateway.calls], [])   # the jump asks nobody; the detail authorises

    def test_the_cursor_is_passed_on_and_the_next_page_link_carries_only_ids_and_filters(self):
        self.login()
        first, second = sorted((verification_item(), verification_item()), key=lambda i: i["case_id"])
        route = {("GET", "/moderation/business-verifications"): queue_of([first], "case_id", next_cursor=first["case_id"])}
        with self.serve(route)[1]:
            page = self.client.get(reverse("business-verifications"), {"q": "Ma"})
        self.assertContains(page, f"cursor={first['case_id']}")
        self.assertContains(page, "q=Ma")
        gateway, api = self.serve({("GET", f"/moderation/business-verifications?cursor={first['case_id']}"):
                                   queue_of([second], "case_id")})
        with api:
            self.assertEqual(self.client.get(reverse("business-verifications"), {"cursor": first["case_id"]}).status_code, 200)
        self.assertEqual(gateway.calls[0]["path"], f"/moderation/business-verifications?cursor={first['case_id']}")

    def test_invalid_queue_input_is_refused_before_any_gateway_call(self):
        self.login()
        gateway, api = self.serve()
        bad = [{"cursor": "x"}, {"cursor": uid(), "extra": "1"}, {"q": "a" * 81}, {"q": "tab\x07bell"}, {"mine": "yes"},
               {"find": "nope"}, {"find": uid(), "q": "x"}]
        with api:
            for params in bad:
                self.assertEqual(self.client.get(reverse("business-verifications"), params).status_code, 400, params)
            self.assertEqual(self.client.get(reverse("business-reports"), {"mine": "1"}).status_code, 400)
            self.assertEqual(self.client.get(f"{reverse('business-profiles')}?q=a&q=b").status_code, 400)
        self.assertEqual(gateway.calls, [])

    def test_a_malformed_or_mismatched_queue_answer_fails_closed(self):
        self.login()
        item = verification_item()
        bad_pages = [(200, {"items": [{**item, "extra": 1}], "next_cursor": None}),
                     (200, {"items": [{**item, "state": "verified"}], "next_cursor": None}),
                     (200, {"items": [item], "next_cursor": None, "total": 5}),
                     (200, {"items": [item, item], "next_cursor": None}),
                     (200, {"items": [item], "next_cursor": "bad"}),
                     (200, {"items": [], "next_cursor": None, "x": 1}), (200, [])]
        for answer in bad_pages:
            with self.serve({("GET", "/moderation/business-verifications"): answer})[1]:
                self.assertEqual(self.client.get(reverse("business-verifications")).status_code, 503, answer)

    def test_gateway_refusals_become_fixed_copy_that_never_echoes_the_gateway(self):
        self.login()
        for code, text in ((403, "Access denied"), (404, "may not be enabled"), (503, "Something went wrong")):
            with self.serve({("GET", "/moderation/business-profile-revisions"): (code, {"detail": "LEAK-secret-detail"})})[1]:
                page = self.client.get(reverse("business-profiles"))
            self.assertContains(page, text, status_code=code if code != 404 else 200)
            self.assertNotContains(page, "LEAK-secret-detail", status_code=code if code != 404 else 200)


class VerificationDecisionTests(ConsoleCase):
    def open_case(self, case, **changes):
        gateway, api = self.serve({("GET", f"/moderation/business-verifications/{case}"): (200, self.case_detail(case, **changes))})
        with api:
            response = self.client.get(reverse("business-verifications-detail", args=[case]))
        return response

    def post(self, case, data, routes=None, client=None):
        gateway, api = self.serve(routes)
        with api:
            response = (client or self.client).post(reverse("business-verifications-detail", args=[case]), data)
        return response, gateway

    def test_the_case_page_shows_private_evidence_with_the_right_actions_for_each_state(self):
        self.login("moderator")
        case = uid()
        submitted = self.open_case(case, state="submitted", assigned_to_you=False)
        self.assertContains(submitted, "LBR-2026-1")
        self.assertContains(submitted, "Kolo Foods Ltd")
        self.assertContains(submitted, "Claim case")
        self.assertNotContains(submitted, "Record a decision")
        claimed = self.open_case(case, state="under_review", assigned_to_you=True)
        self.assertContains(claimed, "Record a decision")
        self.assertNotContains(claimed, "Claim case")
        self.assertEqual(claimed.context["offered"]["decisions"], ("verify", "reject", "request_info"))
        someone_elses = self.open_case(case, state="under_review", assigned_to_you=False)
        self.assertContains(someone_elses, "No decision is available")
        verified = self.open_case(case, state="verified")
        self.assertEqual(verified.context["offered"]["decisions"], ("revoke",))
        self.assertEqual(self.open_case(case, state="rejected").context["offered"]["decisions"], ())
        self.assertIn("no-store", claimed["Cache-Control"])

    def test_hostile_business_text_is_escaped_and_no_private_value_reaches_a_url(self):
        self.login()
        case = uid()
        page = self.open_case(case, display_name=HOSTILE, legal_name=HOSTILE,
                              evidence=[{"id": uid(), "kind": "note", "value": HOSTILE}],
                              duplicate_candidates=[{"business_id": uid(), "display_name": HOSTILE, "state": "draft"}])
        html = page.content.decode()
        self.assertNotIn("<script>alert", html)
        self.assertNotIn("<img src=x", html)
        self.assertIn("&lt;script&gt;", html)
        for target in re.findall(r'(?:href|action|src)="([^"]*)"', html):
            self.assertNotIn("Kolo Foods", target)
            self.assertNotIn("LBR-2026", target)
            self.assertNotIn("script", target)

    def test_a_case_outside_the_reviewers_scope_is_the_same_page_as_an_unknown_case(self):
        self.login("moderator")
        with self.serve(default=(404, {"detail": "Not found"}))[1]:     # the service answers 404 for both
            out_of_scope = self.client.get(reverse("business-verifications-detail", args=[uid()]))
            unknown = self.client.get(reverse("business-verifications-detail", args=[uid()]))
        self.assertEqual(out_of_scope.status_code, 404)
        self.assertEqual(out_of_scope.content, unknown.content)
        self.assertNotContains(out_of_scope, "Ma Kolo Foods", status_code=404)

    def test_a_case_answer_for_a_different_case_or_with_extra_fields_is_never_rendered(self):
        self.login()
        case = uid()
        for answer in (self.case_detail(uid()), {**self.case_detail(case), "assigned_reviewer": uid()},
                       self.case_detail(case, state="approved"), self.case_detail(case, evidence=[{"id": uid(), "kind": "x", "value": "v"}])):
            with self.serve({("GET", f"/moderation/business-verifications/{case}"): (200, answer)})[1]:
                self.assertEqual(self.client.get(reverse("business-verifications-detail", args=[case])).status_code, 503)

    def test_claiming_sends_only_the_idempotency_key_and_returns_to_the_case(self):
        self.login("moderator")
        case = uid()
        page = self.open_case(case, state="submitted", assigned_to_you=False)
        intent = page.context["claim_intent"]
        path = f"/moderation/business-verifications/{case}/claim"
        response, gateway = self.post(case, {"intent": intent}, {("POST", path): (200, {"case_id": case, "state": "under_review"})})
        self.assertRedirects(response, reverse("business-verifications-detail", args=[case]), fetch_redirect_response=False)
        self.assertEqual([(c["method"], c["path"], c["data"]) for c in gateway.calls], [("POST", path, {})])
        self.assertRegex(gateway.calls[0]["key"], r"^[A-Za-z0-9_-]{16,128}$")

    def test_a_verifying_decision_needs_confirmation_then_sends_exactly_the_validated_fields(self):
        self.login("moderator")
        case = uid()
        intent = self.open_case(case).context["decision_intent"]
        form = {"intent": intent, "decision": "verify", "reason_code": "documents_checked", "note": "  Licence matches.  "}
        asked, gateway = self.post(case, form)
        self.assertContains(asked, "Confirm your decision")
        self.assertContains(asked, "documents_checked")
        self.assertEqual(gateway.calls, [], "the confirmation step must not reach the gateway")
        path = f"/moderation/business-verifications/{case}/decision"
        answer = (200, {"case_id": case, "state": "verified", "business_state": "verified"})
        done, gateway = self.post(case, {**form, "confirmed": "1"}, {("POST", path): answer})
        self.assertContains(done, "Decision recorded")
        self.assertEqual([(c["method"], c["path"], c["data"]) for c in gateway.calls],
                         [("POST", path, {"decision": "verify", "reason_code": "documents_checked", "note": "Licence matches."})])

    def test_requesting_information_needs_no_confirmation(self):
        self.login()
        case = uid()
        intent = self.open_case(case).context["decision_intent"]
        path = f"/moderation/business-verifications/{case}/decision"
        done, gateway = self.post(case, {"intent": intent, "decision": "request_info", "reason_code": "need_licence"},
                                  {("POST", path): (200, {"case_id": case, "state": "needs_info", "business_state": "needs_info"})})
        self.assertContains(done, "Decision recorded")
        self.assertEqual(gateway.calls[0]["data"], {"decision": "request_info", "reason_code": "need_licence"})

    def test_a_replayed_form_reuses_the_same_key_and_body_so_it_cannot_apply_twice(self):
        self.login()
        case = uid()
        intent = self.open_case(case).context["decision_intent"]
        path = f"/moderation/business-verifications/{case}/decision"
        answer = (200, {"case_id": case, "state": "rejected", "business_state": "rejected"})
        form = {"intent": intent, "decision": "reject", "reason_code": "evidence_unclear", "confirmed": "1"}
        first, gateway = self.post(case, form, {("POST", path): answer})
        second, again = self.post(case, form, {("POST", path): answer})
        self.assertContains(first, "Decision recorded")
        self.assertContains(second, "Decision recorded")
        self.assertEqual(gateway.calls[0]["key"], again.calls[0]["key"])
        self.assertEqual(gateway.calls[0]["data"], again.calls[0]["data"])
        # The service answers a changed body under the same key with 409: shown as fixed copy, never as success.
        conflict = (409, {"detail": "Idempotency-Key was used with a different request", "code": "idempotency_conflict"})
        changed, _ = self.post(case, {**form, "decision": "reject", "reason_code": "something_else"}, {("POST", path): conflict})
        self.assertContains(changed, "already used", status_code=409)
        self.assertNotContains(changed, "different request", status_code=409)

    def test_a_forged_foreign_wrong_operation_expired_or_missing_intent_is_refused_without_a_gateway_call(self):
        self.login()
        case = uid()
        page = self.open_case(case, state="submitted", assigned_to_you=False)
        claim_intent = page.context["claim_intent"]
        decision_intent = self.open_case(case).context["decision_intent"]
        decision = {"decision": "verify", "reason_code": "documents_checked", "confirmed": "1"}
        other_case = uid()
        foreign = self.open_case(other_case).context["decision_intent"]
        attempts = [({"intent": "forged", **decision}, case), ({**decision}, case), ({"intent": decision_intent, **decision}, other_case),
                    ({"intent": foreign, **decision}, case), ({"intent": claim_intent, **decision}, case),
                    ({"intent": decision_intent}, case)]          # a decision intent cannot claim
        for form, target in attempts:
            response, gateway = self.post(target, form)
            self.assertEqual(response.status_code, 400, form)
            self.assertEqual(gateway.calls, [], "a refused intent must not reach the gateway")
        with patch.object(business_views, "INTENT_MAX_AGE", -1):
            expired, gateway = self.post(case, {"intent": decision_intent, **decision})
        self.assertEqual((expired.status_code, gateway.calls), (400, []))

    def test_an_intent_lives_fifteen_minutes_and_not_a_second_longer(self):
        self.login()
        case = uid()
        intent = self.open_case(case).context["decision_intent"]
        form = {"intent": intent, "decision": "request_info", "reason_code": "need_licence"}
        path = f"/moderation/business-verifications/{case}/decision"
        ok = (200, {"case_id": case, "state": "needs_info", "business_state": "needs_info"})
        real = time.time()
        with patch("django.core.signing.time.time", return_value=real + 14 * 60):
            fresh, _ = self.post(case, form, {("POST", path): ok})
        self.assertContains(fresh, "Decision recorded")
        with patch("django.core.signing.time.time", return_value=real + 16 * 60):
            late, gateway = self.post(case, form, {("POST", path): ok})
        self.assertEqual((late.status_code, gateway.calls), (400, []))

    def test_an_intent_issued_to_one_session_does_not_work_in_another(self):
        self.login()
        case = uid()
        intent = self.open_case(case).context["decision_intent"]
        other = Client()
        self.login(client=other)
        response, gateway = self.post(case, {"intent": intent, "decision": "verify", "reason_code": "documents_checked",
                                             "confirmed": "1"}, client=other)
        self.assertEqual((response.status_code, gateway.calls), (400, []))

    def test_invalid_decision_input_is_refused_before_the_gateway(self):
        self.login()
        case = uid()
        intent = self.open_case(case).context["decision_intent"]
        good = {"intent": intent, "decision": "reject", "reason_code": "evidence_unclear", "confirmed": "1"}
        for change in ({"decision": "approve"}, {"decision": "REJECT"}, {"decision": ""}, {"reason_code": "Bad Code"},
                       {"reason_code": "ab"}, {"reason_code": "a" * 41}, {"reason_code": "1abc"}, {"reason_code": ""},
                       {"note": "x" * 501}, {"note": "bell\x07"}, {"business_state": "verified"}, {"state": "verified"},
                       {"reviewer": uid()}):
            response, gateway = self.post(case, {**good, **change})
            self.assertEqual(response.status_code, 400, change)
            self.assertEqual(gateway.calls, [], change)
        body = "&".join(f"{k}={v}" for k, v in good.items()) + "&decision=verify"
        gateway, api = self.serve()
        with api:
            duplicate = self.client.post(reverse("business-verifications-detail", args=[case]), body,
                                         content_type="application/x-www-form-urlencoded")
        self.assertEqual((duplicate.status_code, gateway.calls), (400, []))

    def test_a_response_that_does_not_match_the_decision_is_never_shown_as_success(self):
        self.login()
        case = uid()
        intent = self.open_case(case).context["decision_intent"]
        path = f"/moderation/business-verifications/{case}/decision"
        form = {"intent": intent, "decision": "reject", "reason_code": "evidence_unclear", "confirmed": "1"}
        for answer in ({"case_id": case, "state": "verified", "business_state": "verified"},
                       {"case_id": uid(), "state": "rejected", "business_state": "rejected"},
                       {"case_id": case, "state": "rejected", "business_state": "verified"},
                       {"case_id": case, "state": "rejected", "business_state": "rejected", "extra": 1}):
            response, _ = self.post(case, form, {("POST", path): (200, answer)})
            self.assertEqual(response.status_code, 503, answer)
            self.assertNotContains(response, "Decision recorded", status_code=503)

    def test_business_refusals_become_specific_fixed_copy_and_expired_sessions_sign_out(self):
        self.login()
        case = uid()
        intent = self.open_case(case).context["decision_intent"]
        path = f"/moderation/business-verifications/{case}/decision"
        form = {"intent": intent, "decision": "verify", "reason_code": "documents_checked", "confirmed": "1"}
        claim = (409, {"detail": "Claim the case before deciding it", "code": "claim_required"})
        page, _ = self.post(case, form, {("POST", path): claim})
        self.assertContains(page, "Claim the case first", status_code=409)
        self.assertNotContains(page, "before deciding it", status_code=409)
        for status, text in ((404, "Page not found"), (403, "Access denied"), (503, "Something went wrong")):
            page, _ = self.post(case, form, {("POST", path): (status, {"detail": "LEAK"})})
            self.assertContains(page, text, status_code=status)
            self.assertNotContains(page, "LEAK", status_code=status)
        expired, _ = self.post(case, form, {("POST", path): (401, {})})
        self.assertEqual(expired["Location"].split("?")[0], "/login/")

    def test_a_successful_decision_logs_nothing_sensitive(self):
        self.login()
        case = uid()
        intent = self.open_case(case).context["decision_intent"]
        path = f"/moderation/business-verifications/{case}/decision"
        with self.assertNoLogs(level="INFO"):
            self.post(case, {"intent": intent, "decision": "reject", "reason_code": "evidence_unclear", "confirmed": "1",
                             "note": "private note"},
                      {("POST", path): (200, {"case_id": case, "state": "rejected", "business_state": "rejected"})})


class ProfileAndReportDecisionTests(ConsoleCase):
    def test_a_profile_revision_shows_what_changed_and_approval_is_confirmed_then_validated(self):
        self.login("moderator")
        rid = uid()
        with self.serve({("GET", f"/moderation/business-profile-revisions/{rid}"): (200, self.revision(rid, description=HOSTILE))})[1]:
            page = self.client.get(reverse("business-profiles-detail", args=[rid]))
        self.assertContains(page, "Description")
        self.assertContains(page, "&lt;script&gt;")
        self.assertNotContains(page, "<script>alert")
        intent = page.context["decision_intent"]
        path = f"/moderation/business-profile-revisions/{rid}/decision"
        form = {"intent": intent, "decision": "approve", "reason_code": "looks_correct"}
        gateway, api = self.serve()
        with api:
            asked = self.client.post(reverse("business-profiles-detail", args=[rid]), form)
        self.assertContains(asked, "Confirm your decision")
        self.assertEqual(gateway.calls, [])
        gateway, api = self.serve({("POST", path): (200, {"revision_id": rid, "state": "approved"})})
        with api:
            done = self.client.post(reverse("business-profiles-detail", args=[rid]), {**form, "confirmed": "1"})
        self.assertContains(done, "Decision recorded")
        self.assertEqual(gateway.calls[0]["data"], {"decision": "approve", "reason_code": "looks_correct"})
        with self.serve({("POST", path): (200, {"revision_id": rid, "state": "rejected"})})[1]:
            wrong = self.client.post(reverse("business-profiles-detail", args=[rid]), {**form, "confirmed": "1"})
        self.assertEqual(wrong.status_code, 503)
        with self.serve()[1]:     # a note is not part of a profile decision
            self.assertEqual(self.client.post(reverse("business-profiles-detail", args=[rid]),
                                              {**form, "confirmed": "1", "note": "x"}).status_code, 400)

    def test_each_report_subject_renders_safely_and_removal_needs_confirmation(self):
        self.login("moderator")
        for subject in ("review", "review_response", "inquiry_message"):
            rid = uid()
            data = self.report(rid, subject)
            data["content"] = {**data["content"], "body": HOSTILE}
            data["details"] = HOSTILE
            with self.serve({("GET", f"/moderation/business-reports/{rid}"): (200, data)})[1]:
                page = self.client.get(reverse("business-reports-detail", args=[rid]))
            self.assertContains(page, "&lt;script&gt;")
            self.assertNotContains(page, "<script>alert")
            self.assertEqual(page.context["offered"]["decisions"], ("keep", "remove"))
        rid = uid()
        intent = page.context["decision_intent"]
        # The intent belongs to the last report opened; use it only for that item.
        path = f"/moderation/business-reports/{rid}/decision"
        with self.serve()[1]:
            self.assertEqual(self.client.post(reverse("business-reports-detail", args=[rid]),
                                              {"intent": intent, "decision": "remove", "reason_code": "misleading"}).status_code, 400)
        rid = uid()
        with self.serve({("GET", f"/moderation/business-reports/{rid}"): (200, self.report(rid))})[1]:
            intent = self.client.get(reverse("business-reports-detail", args=[rid])).context["decision_intent"]
        path = f"/moderation/business-reports/{rid}/decision"
        form = {"intent": intent, "decision": "remove", "reason_code": "misleading"}
        gateway, api = self.serve({("POST", path): (200, {"report_id": rid, "state": "decided", "decision": "remove"})})
        with api:
            asked = self.client.post(reverse("business-reports-detail", args=[rid]), form)
            self.assertContains(asked, "Confirm your decision")
            self.assertEqual(gateway.calls, [])
            done = self.client.post(reverse("business-reports-detail", args=[rid]), {**form, "confirmed": "1"})
        self.assertContains(done, "Decision recorded")
        self.assertEqual(gateway.calls[0]["data"], {"decision": "remove", "reason_code": "misleading"})
        with self.serve({("POST", path): (200, {"report_id": rid, "state": "decided", "decision": "keep"})})[1]:
            self.assertEqual(self.client.post(reverse("business-reports-detail", args=[rid]), {**form, "confirmed": "1"}).status_code, 503)

    def test_a_reviewer_cannot_reach_another_businesss_item_and_the_gateway_answer_decides(self):
        self.login("moderator")
        rid = uid()
        refused = {("GET", f"/moderation/business-reports/{rid}"): (404, {"detail": "Not found"}),
                   ("GET", f"/moderation/business-profile-revisions/{rid}"): (404, {"detail": "Not found"})}
        with self.serve(refused)[1]:
            for name in ("business-reports-detail", "business-profiles-detail"):
                page = self.client.get(reverse(name, args=[rid]))
                self.assertEqual(page.status_code, 404)
                self.assertNotContains(page, "Looks fake", status_code=404)


class AdministrationTests(ConsoleCase):
    def categories(self, *slugs):
        return 200, {"items": [{"slug": s, "name": s.title(), "active": True, "parent": None} for s in sorted(slugs)]}

    def test_categories_are_listed_and_saved_with_exactly_the_validated_fields(self):
        self.login()
        routes = {("GET", "/business-categories"): self.categories("food", "fabric")}
        with self.serve(routes)[1]:
            page = self.client.get(reverse("business-categories"))
        self.assertContains(page, "Current list")
        self.assertContains(page, "fabric")
        intent = page.context["intent"]
        saved = (200, {"slug": "bakery", "name": "Bakery", "active": True, "parent": "food"})
        routes[("PUT", "/admin/business-categories/bakery")] = saved
        gateway, api = self.serve(routes)
        with api:
            response = self.client.post(reverse("business-categories"), {"intent": intent, "slug": "bakery", "name": " Bakery ",
                                                                         "parent": "food", "active": "1"})
        self.assertRedirects(response, reverse("business-categories"), fetch_redirect_response=False)
        put = [c for c in gateway.calls if c["method"] == "PUT"]
        self.assertEqual([(c["path"], c["data"]) for c in put],
                         [("/admin/business-categories/bakery", {"name": "Bakery", "parent": "food", "active": True})])
        self.assertRegex(put[0]["key"], r"^[A-Za-z0-9_-]{16,128}$")
        with self.serve(routes)[1]:
            self.assertContains(self.client.get(reverse("business-categories")), "Category saved.")

    def test_category_input_is_validated_and_the_service_answer_is_checked(self):
        self.login()
        routes = {("GET", "/business-categories"): self.categories("food")}
        with self.serve(routes)[1]:
            intent = self.client.get(reverse("business-categories")).context["intent"]
        good = {"intent": intent, "slug": "bakery", "name": "Bakery", "parent": "food", "active": "1"}
        for change in ({"slug": "Bad Slug"}, {"slug": "a"}, {"name": "x"}, {"name": "n" * 81}, {"name": "bell\x07x"},
                       {"parent": "ghost"}, {"parent": "Bad Parent"}, {"active": "yes"}):
            gateway, api = self.serve(routes)
            with api:
                response = self.client.post(reverse("business-categories"), {**good, **change})
            self.assertEqual(response.status_code, 400, change)
            self.assertEqual(gateway.sent(), [], change)
        for extra in ({"intent": "forged"}, {"role": "administrator"}):
            with self.serve(routes)[1]:
                self.assertEqual(self.client.post(reverse("business-categories"), {**good, **extra}).status_code, 400)
        put = ("PUT", "/admin/business-categories/bakery")
        for answer in ({"slug": "bakery", "name": "Other", "active": True, "parent": "food"},
                       {"slug": "bakery", "name": "Bakery", "active": False, "parent": "food"},
                       {"slug": "bakery", "name": "Bakery", "active": True, "parent": None},
                       {"slug": "bakery", "name": "Bakery", "active": True, "parent": "food", "extra": 1}):
            with self.serve({**routes, put: (200, answer)})[1]:
                self.assertEqual(self.client.post(reverse("business-categories"), good).status_code, 503, answer)
        with self.serve({**routes, put: (409, {"detail": "LEAK", "code": "depth_exceeded"})})[1]:
            page = self.client.post(reverse("business-categories"), good)
        self.assertContains(page, "two levels at most", status_code=409)
        self.assertNotContains(page, "LEAK", status_code=409)

    def test_a_moderator_can_use_the_review_pages_but_not_categories_or_access(self):
        self.login("moderator")
        for name in ("business-categories", "business-grants"):
            gateway, api = self.serve()
            with api:
                self.assertEqual(self.client.get(reverse(name)).status_code, 403)
                self.assertEqual(self.client.post(reverse(name), {"form": "reviewer"}).status_code, 403)
            self.assertEqual(gateway.calls, [])

    def test_reviewer_access_is_granted_only_to_a_known_moderator_and_never_to_self(self):
        self.login()
        moderator = uid()
        with patch("web.assignment_views.roster", return_value={moderator: "Ada Moderator"}):
            with self.serve()[1]:
                page = self.client.get(reverse("business-grants"))
            self.assertContains(page, "Ada Moderator")
            intent = page.context["reviewer_intent"]
            target = uid()
            form = {"form": "reviewer", "intent": intent, "reviewer": moderator, "scope": "verification", "target": target, "active": "1"}
            path = "/admin/business-reviewer-grants"
            gateway, api = self.serve({("PUT", path): (200, {"id": uid(), "scope": "verification", "active": True})})
            with api:
                done = self.client.post(reverse("business-grants"), form)
            self.assertRedirects(done, reverse("business-grants"), fetch_redirect_response=False)
            self.assertEqual([(c["path"], c["data"]) for c in gateway.sent()],
                             [(path, {"reviewer_account_id": moderator, "scope": "verification", "active": True,
                                      "target_business_id": target})])
            for change in ({"reviewer": uid()}, {"scope": "everything"}, {"target": "x"}, {"active": "2"}, {"reviewer": "x"}):
                gateway, api = self.serve()
                with api:
                    self.assertEqual(self.client.post(reverse("business-grants"), {**form, **change}).status_code, 400, change)
                self.assertEqual(gateway.sent(), [], change)
            with self.serve({("PUT", path): (409, {"detail": "LEAK", "code": "self_grant"})})[1]:
                page = self.client.post(reverse("business-grants"), form)
            self.assertContains(page, "grant yourself", status_code=409)
            self.assertNotContains(page, "LEAK", status_code=409)
            with self.serve({("PUT", path): (200, {"id": uid(), "scope": "review_queue", "active": True})})[1]:
                self.assertEqual(self.client.post(reverse("business-grants"), form).status_code, 503)
            revoke = {**form, "reviewer": uid(), "active": "0"}     # revoking never needs the roster
            gateway, api = self.serve({("PUT", path): (200, {"id": uid(), "scope": "verification", "active": False})})
            with api:
                self.assertEqual(self.client.post(reverse("business-grants"), revoke).status_code, 302)
            self.assertEqual(len(gateway.sent()), 1)

    def test_registration_access_is_looked_up_then_granted_by_the_confirmed_account_only(self):
        self.login()
        person = uid()
        found = (200, {"account_id": person, "display_name": "Ada Eze", "role": "viewer", "email_verified": True})
        with patch("web.assignment_views.roster", return_value={}):
            with self.serve()[1]:
                lookup = self.client.get(reverse("business-grants")).context["lookup_intent"]
            with self.serve({("POST", "/admin/accounts/lookup"): found})[1]:
                page = self.client.post(reverse("business-grants"), {"form": "lookup", "intent": lookup, "email": "ada@example.test"})
            self.assertContains(page, "Ada Eze")
            intent = page.context["registration_intent"]
            path = f"/admin/business-registration-grants/{person}"
            form = {"form": "registration", "intent": intent, "account_id": person, "active": "1"}
            gateway, api = self.serve({("PUT", path): (200, {"account_id": person, "active": True})})
            with api:
                self.assertEqual(self.client.post(reverse("business-grants"), form).status_code, 302)
            self.assertEqual([(c["path"], c["data"]) for c in gateway.sent()], [(path, {"active": True})])
            for change in ({"account_id": uid()}, {"intent": "forged"}, {"active": "maybe"}, {"extra": "1"}):
                gateway, api = self.serve()
                with api:
                    self.assertEqual(self.client.post(reverse("business-grants"), {**form, **change}).status_code, 400, change)
                self.assertEqual(gateway.sent(), [], change)
            with self.serve({("PUT", path): (200, {"account_id": uid(), "active": True})})[1]:
                self.assertEqual(self.client.post(reverse("business-grants"), form).status_code, 503)
            with self.serve({("POST", "/admin/accounts/lookup"): (404, {"detail": "LEAK"})})[1]:
                missing = self.client.post(reverse("business-grants"), {"form": "lookup", "intent": lookup, "email": "x@example.test"})
            self.assertContains(missing, "must register in the app first", status_code=404)
            self.assertNotContains(missing, "LEAK", status_code=404)
            gateway, api = self.serve()
            with api:
                self.assertEqual(self.client.post(reverse("business-grants"), {"form": "lookup", "intent": lookup, "email": "nope"}).status_code, 400)
            self.assertEqual(gateway.calls, [])

    def test_the_audit_page_accepts_business_events_and_offers_the_business_filter(self):
        self.login()
        event = {"id": uid(), "kind": "business.verification_decided", "occurred_at": WHEN, "producer": "business",
                 "subject_type": "business"}
        with self.serve({("GET", "/admin/audit?producer=business&kind=business.verification_decided"): (200, {"items": [event], "next_cursor": None})})[1]:
            page = self.client.get(reverse("audit"), {"producer": "business", "kind": "business.verification_decided"})
        self.assertContains(page, "business.verification_decided")
        self.assertContains(page, 'value="business"')


class RenderingAndStructureTests(ConsoleCase):
    def test_the_business_templates_and_views_never_disable_auto_escaping(self):
        root = Path(__file__).resolve().parents[1]
        for path in [*root.glob("templates/business_*.html"), root / "web" / "business_views.py", root / "web" / "business_contracts.py"]:
            text = path.read_text()
            for forbidden in ("|safe", "mark_safe", "autoescape off", "format_html", "SafeString"):
                self.assertNotIn(forbidden, text, f"{path.name} uses {forbidden}")

    def test_the_business_navigation_shows_administrator_tabs_only_to_administrators(self):
        for role, expect in (("administrator", True), ("moderator", False)):
            self.client = Client()
            self.login(role)
            routes = {("GET", p): queue_of([], "case_id") for p in
                      ("/moderation/business-verifications", "/moderation/business-profile-revisions", "/moderation/business-reports")}
            with self.serve(routes)[1]:
                page = self.client.get(reverse("business"))
            self.assertEqual(reverse("business-grants") in page.content.decode(), expect, role)
            self.assertContains(page, reverse("business"))          # the sidebar entry is for both roles

    def test_no_business_page_offers_a_web_surface_for_business_users(self):
        """DR-BZ-21: the console routes for Business are all under /admin/ and none is for owners, staff or customers."""
        from tests.test_route_security_matrix import PUBLIC, ROUTES
        business = {name: path for name, path in ROUTES.items() if "business" in name}
        self.assertGreaterEqual(len(business), 9)
        for name, path in business.items():
            self.assertTrue(path.startswith("/admin/business/"), f"{name}: {path}")
            self.assertNotIn(name, PUBLIC)
