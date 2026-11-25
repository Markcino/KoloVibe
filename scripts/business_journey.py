"""The Business end-to-end journey (Phase 6E), run by scripts/verify_local_journeys.py.

Everything here is real HTTP between real processes: the Gateway, Identity (sessions, MFA, verified email), the Business
service and the web console, each with its own disposable TLS PostgreSQL role. Only the mail transport and the account
fixtures are synthetic. Each numbered step of the Phase 6E brief is one block below; a step asserts what the owning
service decided, and every success body is validated against its DOC-205 response schema.

The journey runs as one ordered test because each step depends on the one before it.
"""

from html.parser import HTMLParser
from http.cookies import SimpleCookie
import secrets

from smtp_fixture import mailed_code

NAME = "Journey Bakery"
DAYS = [{"weekday": day, "opens": "00:00", "closes": "24:00"} for day in range(7)]


class Intents(HTMLParser):
    """Every hidden `intent` value in a console page, in document order."""

    def __init__(self):
        super().__init__()
        self.values = []

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == "input" and values.get("name") == "intent":
            self.values.append(values.get("value"))


def intents(page):
    parser = Intents()
    parser.feed(page.decode())
    return parser.values


def run(t, c):
    """`t` is the running unittest case; `c` carries the harness: api, request, contract, ports, base, privileged_fixture,
    fixture_connection."""
    api, contract = c.api, c.contract

    def key():
        return secrets.token_urlsafe(24)

    passwords = {}

    def person(label):
        body = {"email": f"biz-{label}@example.test", "display_name": f"Biz {label}", "password": secrets.token_urlsafe(24)}
        passwords[label] = body["password"]
        t.assertEqual(api("/auth/register", data=body)[0], 201)
        t.assertEqual(api("/auth/verify", data={"email": body["email"], "code": mailed_code(c.base)})[0], 200)
        status, tokens = api("/auth/login", data={name: body[name] for name in ("email", "password")})
        t.assertEqual(status, 200)
        return tokens["user"]["id"], tokens["access_token"]

    def operator(role, suffix):
        actor, body, recovery = c.privileged_fixture(role, suffix)
        status, challenge = api("/auth/login", data={name: body[name] for name in ("email", "password")})
        t.assertEqual(status, 202)
        status, session = api("/auth/mfa/verify", data={"challenge_token": challenge["challenge_token"], "code": recovery})
        t.assertEqual(status, 200)
        return str(actor), session["access_token"], body, role + suffix

    def put(path, token, data):
        return api(path, method="PUT", data=data, token=token, key=key())

    def ok(result, schema=None, method="get", status=200):
        t.assertEqual(result[0], status, result[1])
        if schema:
            contract(schema, method, status, result[1])
        return result[1]

    # ---- 1. a customer account signs in ---------------------------------------------------------------------------
    customer_id, customer = person("customer")
    ok(api("/me", token=customer), "/me")
    t.assertEqual(api("/me/businesses")[0], 401)  # nothing owner-side is anonymous
    t.assertEqual(api("/moderation/business-verifications")[0], 401)

    # ---- 2. a business owner registers: invitation first, then the server decides ownership ------------------------
    admin_id, admin, _, _ = operator("administrator", "-bizadmin")
    reviewer_id, reviewer, reviewer_account, reviewer_label = operator("moderator", "-bizreviewer")
    stranger_id, stranger, _, _ = operator("moderator", "-bizstranger")
    owner_id, owner = person("owner")
    registration = {"display_name": NAME, "legal_name": f"{NAME} Ltd"}
    status, refusal = api("/me/businesses", data=registration, token=owner, key=key())
    t.assertEqual((status, refusal.get("code")), (403, "invitation_required"), refusal)
    ok(put(f"/admin/business-registration-grants/{owner_id}", admin, {"active": True}),
       "/admin/business-registration-grants/{account_id}", "put")
    ok(put("/admin/business-categories/food", admin, {"name": "Food and drink", "active": True}), "/admin/business-categories/{slug}", "put")
    for scope in ("verification", "profile_review", "review_queue"):
        ok(put("/admin/business-reviewer-grants", admin, {"reviewer_account_id": reviewer_id, "scope": scope, "active": True}),
           "/admin/business-reviewer-grants", "put")
    t.assertEqual(put("/admin/business-reviewer-grants", reviewer, {"reviewer_account_id": reviewer_id, "scope": "verification", "active": True})[0], 403)
    sent = key()
    status, business = api("/me/businesses", data=registration, token=owner, key=sent)
    t.assertEqual(status, 201)
    contract("/me/businesses", "post", 201, business)
    bid = business["id"]
    t.assertEqual((business["state"], business["my_role"], business["listed"]), ("draft", "owner", False))
    t.assertEqual(api("/me/businesses", data=registration, token=owner, key=sent)[1]["id"], bid)  # a retry is the same business
    t.assertEqual(api(f"/me/businesses/{bid}", token=customer)[0], 404)  # a stranger cannot even see it exists

    # ---- 3. the owner prepares the profile and submits for verification --------------------------------------------
    ok(api(f"/me/businesses/{bid}/profile", method="PATCH", token=owner, key=key(), data={
        "category": "food", "county_code": "montserrado", "city": "Monrovia", "description": "Fresh bread every morning.",
        "contacts": [{"kind": "phone", "value": "+231770000000", "is_public": True}]}),
       "/me/businesses/{business_id}/profile", "patch")
    ok(api(f"/me/businesses/{bid}/hours", method="PUT", token=owner, key=key(), data={"rules": DAYS, "exceptions": []}),
       "/me/businesses/{business_id}/hours", "put")
    ok(api(f"/me/businesses/{bid}/profile/submit", data={}, token=owner, key=key()), "/me/businesses/{business_id}/profile/submit", "post")
    ok(api(f"/me/businesses/{bid}/verification", data={
        "method": "manual_review", "declaration": True, "evidence": [{"kind": "registration_number", "value": "LBR-2026-1"}]},
        token=owner, key=key()), "/me/businesses/{business_id}/verification", "post", 201)
    t.assertEqual(ok(api(f"/me/businesses/{bid}/verification", token=owner))["state"], "submitted")
    t.assertEqual(api(f"/businesses/{bid}")[0], 404)  # not discoverable yet
    t.assertEqual(api("/businesses?q=Journey")[1]["items"], [])

    # ---- 4. an authorized reviewer inspects the submission; one without a grant sees nothing -----------------------
    queue = ok(api("/moderation/business-verifications", token=reviewer), "/moderation/business-verifications")
    case = next(item for item in queue["items"] if item["business_id"] == bid)["case_id"]
    detail = ok(api(f"/moderation/business-verifications/{case}", token=reviewer), "/moderation/business-verifications/{case_id}")
    t.assertEqual(detail["evidence"][0]["kind"], "registration_number")
    t.assertEqual(ok(api("/moderation/business-verifications", token=stranger))["items"], [])  # no grant: an empty queue
    t.assertEqual(api(f"/moderation/business-verifications/{case}", token=stranger)[0], 404)  # no grant: indistinguishable
    t.assertEqual(api(f"/moderation/business-verifications/{case}/claim", data={}, token=stranger, key=key())[0], 404)
    t.assertEqual(api(f"/moderation/business-verifications/{case}/decision", token=customer, key=key(),
                      data={"decision": "verify", "reason_code": "documents_checked"})[0], 403)
    t.assertEqual(api(f"/moderation/business-verifications/{case}/decision", token=reviewer, key=key(),
                      data={"decision": "verify", "reason_code": "documents_checked"})[0], 409)  # not claimed: no shortcut
    profiles = ok(api("/moderation/business-profile-revisions", token=reviewer), "/moderation/business-profile-revisions")
    revision = next(item for item in profiles["items"] if item["business_id"] == bid)["revision_id"]
    ok(api(f"/moderation/business-profile-revisions/{revision}", token=reviewer), "/moderation/business-profile-revisions/{revision_id}")

    # ---- 5. the reviewer decides, through the real console and the API ---------------------------------------------
    approve = {"decision": "approve", "reason_code": "looks_correct"}
    ok(api(f"/moderation/business-profile-revisions/{revision}/decision", data=approve, token=reviewer, key=key()),
       "/moderation/business-profile-revisions/{revision_id}/decision", "post")
    cookies = SimpleCookie()
    t.assertEqual(c.request(c.ports["web"], "/login/", cookies=cookies)[0], 200)

    def post(path, form):
        return c.request(c.ports["web"], path, method="POST", cookies=cookies, form={"csrfmiddlewaretoken": cookies["csrftoken"].value, **form})

    second_code = (c.base / (reviewer_label + "-recovery")).read_text().splitlines()[1]
    t.assertEqual(post("/login/", {"email": reviewer_account["email"], "password": reviewer_account["password"]})[0], 302)
    t.assertEqual(post("/login/mfa/", {"code": second_code})[0], 302)
    status, page = c.request(c.ports["web"], "/admin/business/verifications/", cookies=cookies)
    t.assertEqual(status, 200)
    t.assertIn(NAME.encode(), page)
    path = f"/admin/business/verifications/{case}/"
    status, page = c.request(c.ports["web"], path, cookies=cookies)
    t.assertEqual(status, 200)
    claim = intents(page)
    t.assertEqual(len(claim), 1)
    for _ in range(2):  # a double submit is one claim
        t.assertEqual(post(path, {"intent": claim[0]})[0], 302)
    status, page = c.request(c.ports["web"], path, cookies=cookies)
    decide = intents(page)
    t.assertEqual(len(decide), 1)
    form = {"intent": decide[0], "decision": "verify", "reason_code": "documents_checked", "note": ""}
    status, page = post(path, form)
    t.assertEqual(status, 200)
    t.assertIn(b"Confirm", page)  # the outcome that cannot be taken back is asked for twice
    with c.fixture_connection("business") as connection:
        t.assertEqual(connection.execute("SELECT count(*) FROM business.service_verificationdecision WHERE case_id=%s", (case,)).fetchone()[0], 0)
    for _ in range(2):  # the confirmed form, replayed, records one decision
        t.assertEqual(post(path, {**form, "confirmed": "1"})[0], 200)
    with c.fixture_connection("business") as connection:
        t.assertEqual(connection.execute("SELECT count(*) FROM business.service_verificationdecision WHERE case_id=%s", (case,)).fetchone()[0], 1)
    t.assertEqual(api(f"/moderation/business-verifications/{case}/decision", token=reviewer, key=key(),
                      data={"decision": "verify", "reason_code": "documents_checked"})[0], 409)  # a new key is a new decision: refused
    t.assertEqual(post("/admin/logout/", {})[0], 302)
    owned = ok(api(f"/me/businesses/{bid}", token=owner), "/me/businesses/{business_id}")
    t.assertEqual((owned["state"], owned["verified"]), ("verified", True))

    # ---- 6. the business becomes eligible, then the owner (only the owner) lists it --------------------------------
    status = ok(api(f"/me/businesses/{bid}/listing", token=owner), "/me/businesses/{business_id}/listing")
    t.assertEqual((status["eligible"], status["listed"]), (True, False))
    ok(api(f"/me/businesses/{bid}/listing/publish", data={}, token=owner, key=key()), "/me/businesses/{business_id}/listing/publish", "post")

    # ---- 7. and 8. a customer searches, then reads the listing -----------------------------------------------------
    found = ok(api("/businesses?q=Journey", token=customer), "/businesses")
    t.assertEqual([item["id"] for item in found["items"]], [bid])
    t.assertEqual([item["id"] for item in ok(api("/businesses?q=Journey"))["items"]], [bid])  # discovery is public
    public = ok(api(f"/businesses/{bid}", token=customer), "/businesses/{business_id}")
    t.assertEqual((public["contacts_access"], public["verified"]), ("available", True))
    t.assertEqual(public["contacts"], [{"kind": "phone", "value": "+231770000000"}])
    anonymous = ok(api(f"/businesses/{bid}"))
    t.assertEqual((anonymous["contacts"], anonymous["contacts_access"]), (None, "sign_in_required"))
    for private in ("legal_name", "owner", "members", "verification", "account_id"):
        t.assertNotIn(private, str(anonymous))

    # ---- 9. and 10. the customer asks, the owner replies ----------------------------------------------------------
    thread = ok(api(f"/businesses/{bid}/inquiries", data={"subject_code": "order_question", "body": "Do you take large orders?"},
                    token=customer, key=key()), "/businesses/{business_id}/inquiries", "post", 201)
    tid = thread["id"]
    inbox = ok(api(f"/me/businesses/{bid}/inquiries", token=owner), "/me/businesses/{business_id}/inquiries")
    t.assertEqual([item["id"] for item in inbox["items"]], [tid])
    t.assertEqual(api(f"/me/businesses/{bid}/inquiries", token=customer)[0], 404)  # the customer is not on the business side
    status, reply = api(f"/me/businesses/{bid}/inquiries/{tid}/messages", data={"body": "Yes, with two days' notice."}, token=owner, key=key())
    t.assertIn(status, (200, 201), reply)
    seen = ok(api(f"/me/inquiries/{tid}", token=customer), "/me/inquiries/{thread_id}")
    t.assertEqual([m["author_kind"] for m in seen["messages"]], ["customer", "business"])

    # ---- 11. both sides confirm the dealing; the customer writes an eligible review -------------------------------
    ok(api(f"/me/inquiries/{tid}/confirm", data={}, token=customer, key=key()), "/me/inquiries/{thread_id}/confirm", "post")
    ok(api(f"/me/businesses/{bid}/inquiries/{tid}/confirm", data={}, token=owner, key=key()),
       "/me/businesses/{business_id}/inquiries/{thread_id}/confirm", "post")
    review = ok(api(f"/businesses/{bid}/reviews", data={"rating": 5, "title": "Great", "body": "Fresh bread and quick, honest replies.",
                                                       "interaction_thread_id": tid}, token=customer, key=key()),
                "/businesses/{business_id}/reviews", "post", 201)
    t.assertEqual((review["state"], review["basis"]), ("published", "interaction_confirmed"))
    rid = review["id"]
    t.assertEqual(api(f"/businesses/{bid}/reviews", data={"rating": 1, "body": "A second review should be refused."},
                      token=customer, key=key())[1]["code"], "already_reviewed")
    t.assertEqual(api(f"/businesses/{bid}/reviews", data={"rating": 5, "body": "The owner reviewing themselves is refused."},
                      token=owner, key=key())[0], 404)
    listed = ok(api(f"/businesses/{bid}/reviews"), "/businesses/{business_id}/reviews")
    t.assertEqual([r["id"] for r in listed["items"]], [rid])
    t.assertNotIn(customer_id, str(listed))  # the author is a pseudonym

    # ---- 12. a second customer reports it; a moderator handles the report ------------------------------------------
    _, reporter = person("reporter")
    report = ok(api("/business-reports", data={"subject_type": "review", "subject_id": rid, "reason_code": "misleading",
                                              "details": "This does not match my experience."}, token=reporter, key=key()),
                "/business-reports", "post", 201)
    t.assertEqual(api("/business-reports", data={"subject_type": "review", "subject_id": rid, "reason_code": "misleading"},
                      token=customer, key=key())[1]["code"], "own_content")
    reports = ok(api("/moderation/business-reports", token=reviewer), "/moderation/business-reports")
    t.assertEqual([item["report_id"] for item in reports["items"]], [report["id"]])
    t.assertEqual(ok(api("/moderation/business-reports", token=stranger))["items"], [])
    t.assertEqual(api(f"/moderation/business-reports/{report['id']}", token=stranger)[0], 404)
    case_view = ok(api(f"/moderation/business-reports/{report['id']}", token=reviewer), "/moderation/business-reports/{report_id}")
    t.assertEqual(case_view["content"]["body"], "Fresh bread and quick, honest replies.")
    removal = {"decision": "remove", "reason_code": "not_a_real_experience"}
    sent = key()
    first = ok(api(f"/moderation/business-reports/{report['id']}/decision", data=removal, token=reviewer, key=sent),
               "/moderation/business-reports/{report_id}/decision", "post")
    t.assertEqual(api(f"/moderation/business-reports/{report['id']}/decision", data=removal, token=reviewer, key=sent)[1], first)  # replay
    t.assertEqual(api(f"/moderation/business-reports/{report['id']}/decision", data=removal, token=reviewer, key=key())[0], 404)
    t.assertEqual(ok(api(f"/businesses/{bid}/reviews"))["items"], [])
    t.assertEqual(ok(api("/me/reviews", token=customer), "/me/reviews")["items"][0]["state"], "removed")

    # ---- 13. staff receive an invitation and exercise only their scope ---------------------------------------------
    invitation = ok(api(f"/me/businesses/{bid}/members/invitations", data={"label": "Cashier"}, token=owner, key=key()),
                    "/me/businesses/{business_id}/members/invitations", "post", 201)
    staff_id, staff = person("staff")
    t.assertEqual(api("/me/business-invitations/redeem", data={"code": "x" * 40}, token=staff, key=key())[0], 404)  # a guess is refused
    joined = ok(api("/me/business-invitations/redeem", data={"code": invitation["code"]}, token=staff, key=key()),
                "/me/business-invitations/redeem", "post")
    t.assertEqual((joined["id"], joined["my_role"]), (bid, "staff"))
    t.assertEqual(api("/me/business-invitations/redeem", data={"code": invitation["code"]}, token=customer, key=key())[0], 404)  # one use
    status, answer = api(f"/me/businesses/{bid}/inquiries/{tid}/messages", data={"body": "Staff here: ready on Friday."}, token=staff, key=key())
    t.assertIn(status, (200, 201), answer)
    ok(api(f"/me/businesses/{bid}/hours", method="PUT", token=staff, key=key(), data={"rules": DAYS[:5], "exceptions": []}),
       "/me/businesses/{business_id}/hours", "put")
    for denied in (api(f"/me/businesses/{bid}/listing/unpublish", data={}, token=staff, key=key()),
                   api(f"/me/businesses/{bid}/verification", token=staff),
                   api(f"/me/businesses/{bid}/members", token=staff),
                   api(f"/me/businesses/{bid}/members/invitations", data={"label": "Friend"}, token=staff, key=key()),
                   api(f"/me/businesses/{bid}/review-invitations", data={}, token=staff, key=key()),
                   api(f"/me/businesses/{bid}/profile", method="PATCH", data={"city": "Paynesville"}, token=staff, key=key())):
        t.assertIn(denied[0], (403, 404), denied)
    t.assertEqual(ok(api(f"/businesses/{bid}"))["rating"]["count"], 0)
    members = ok(api(f"/me/businesses/{bid}/members", token=owner), "/me/businesses/{business_id}/members")
    member = next(m for m in members["members"] if m["role"] == "staff")["id"]
    status, refused = api(f"/me/businesses/{bid}/members/{member}", method="DELETE", token=owner, key=key())
    t.assertEqual((status, refused["code"]), (403, "step_up_required"))  # removal needs an Identity step-up proof
    # Decision G: a purpose-bound proof from Identity, consumed once by the Gateway for this business only.
    t.assertEqual(api("/me/step-up", token=owner, data={"current_password": "wrong-password",
                                                        "purpose": "business.member_remove", "resource_id": bid})[0], 400)
    proof = ok(api("/me/step-up", token=owner, data={"current_password": passwords["owner"],
                                                     "purpose": "business.member_remove", "resource_id": bid}),
               "/me/step-up", "post")["step_up_token"]
    t.assertEqual(api(f"/me/businesses/{bid}/members/{member}", method="DELETE", token=staff, key=key(),
                      headers={"X-Step-Up-Token": proof})[0], 403)  # another person's session cannot use it
    ok(api(f"/me/businesses/{bid}/members/{member}", method="DELETE", token=owner, key=key(),
           headers={"X-Step-Up-Token": proof}), "/me/businesses/{business_id}/members/{member_id}", "delete")
    t.assertEqual(api(f"/me/businesses/{bid}/members/{member}", method="DELETE", token=owner, key=key(),
                      headers={"X-Step-Up-Token": proof})[0], 403)  # a proof is used once

    # ---- 14. revoked staff access is denied -----------------------------------------------------------------------
    for denied in (api(f"/me/businesses/{bid}", token=staff),
                   api(f"/me/businesses/{bid}/inquiries/{tid}/messages", data={"body": "Still here?"}, token=staff, key=key())):
        t.assertEqual(denied[0], 404)
    second_staff_id, second_staff = person("staff-two")
    code = ok(api(f"/me/businesses/{bid}/members/invitations", data={"label": "Weekend"}, token=owner, key=key()), None, status=201)["code"]
    ok(api("/me/business-invitations/redeem", data={"code": code}, token=second_staff, key=key()))
    t.assertEqual(api(f"/me/businesses/{bid}", token=second_staff)[0], 200)
    with c.fixture_connection("business") as connection:  # access removed in the data, as the owner's removal will once step-up exists
        connection.execute("UPDATE business.service_businessmembership SET status='revoked' WHERE account_id=%s", (second_staff_id,))
    t.assertEqual(api(f"/me/businesses/{bid}", token=second_staff)[0], 404)
    t.assertEqual(api(f"/me/businesses/{bid}/inquiries/{tid}/messages", data={"body": "Still here?"}, token=second_staff, key=key())[0], 404)
    t.assertEqual(ok(api("/me/businesses", token=second_staff))["items"], [])
    t.assertEqual(api(f"/me/businesses/{bid}", token=owner)[0], 200)  # the owner is unaffected

    # ---- the service recorded what happened: one audit event per decision, none for a refusal -----------------------------
    with c.fixture_connection("business") as connection:
        kinds = [row[0] for row in connection.execute("SELECT kind FROM business.business_audit_event").fetchall()]
    for kind in ("business.registered", "business.registration_grant_changed", "business.verification_submitted",
                 "business.verification_claimed", "business.verification_decided", "business.profile_decided",
                 "business.listing_published", "business.inquiry_created", "business.inquiry_confirmed", "business.review_created",
                 "business.report_created", "business.report_decided", "business.invitation_created", "business.invitation_redeemed",
                 "business.membership_granted", "business.membership_revoked"):
        t.assertIn(kind, kinds)
    t.assertEqual(kinds.count("business.verification_decided"), 1)  # the replayed and the refused decisions left none
    t.assertEqual(kinds.count("business.report_decided"), 1)
