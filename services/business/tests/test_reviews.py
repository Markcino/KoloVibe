"""B5 part 2: review eligibility, fraud holds, aggregates, responses, reports and reviewer decisions."""
from datetime import timedelta
from unittest.mock import patch
from uuid import uuid4

from service import limits
from service.api import OPERATIONS
from service.models import (AuditEvent, BusinessReport, Review, ReviewAggregate, ReviewInvitation, ReviewResponse,
                            InquiryMessage)
from .test_inquiries import InquiryBase

BODY = "The bread was fresh and the service was friendly."


class ReviewBase(InquiryBase):
    def setUp(self):
        super().setUp()
        self.call("reviewer_grant", {"reviewer_account_id": str(self.reviewer), "scope": "review_queue", "active": True},
                  actor=self.admin, role="administrator", mfa=True)

    def review(self, customer=None, bid=None, rating=5, body=BODY, **extra):
        return self.call("review_create", {"business_id": bid or self.bid, "rating": rating, "body": body, **extra},
                         actor=customer or uuid4())

    def published(self, bid=None, **kw):
        status, body = self.review(bid=bid, **kw)
        assert status == 201, body
        return body

    def reviews(self, bid=None, **params):
        return self.public("review_list_public", {"business_id": bid or self.bid, **params})

    def confirmed_thread(self, customer):
        tid = self.thread(customer)
        self.call("inquiry_reply", {"business_id": self.bid, "thread_id": tid, "body": "Yes."}, actor=self.owner)
        self.call("inquiry_confirm_customer", {"thread_id": tid}, actor=customer)
        self.call("inquiry_confirm_business", {"business_id": self.bid, "thread_id": tid}, actor=self.owner)
        return tid

    def aggregate(self, bid=None):
        row = ReviewAggregate.objects.filter(business_id=bid or self.bid).first()
        return (row.count, row.rating_sum) if row else (0, 0)


class CreateTests(ReviewBase):
    def test_an_open_review_is_published_pseudonymous_and_labelled(self):
        status, body = self.review(rating=4)
        self.assertEqual((status, body["state"], body["basis"]), (201, "published", "open"))
        self.assertEqual(self.aggregate(), (1, 4))
        status, listing = self.reviews()
        item = listing["items"][0]
        self.assertEqual((item["author_label"], item["basis"], item["response"]), ("Reviewer 1", "open", None))
        self.assertEqual(set(item), {"id", "rating", "title", "body", "author_label", "basis", "created_at", "edited_at", "response"})
        self.assertNotIn("author_account", str(listing))
        self.assertEqual(AuditEvent.objects.filter(kind="business.review_created").count(), 1)

    def test_the_average_stays_hidden_until_the_owner_sets_a_minimum(self):
        self.review(rating=5, body="First reviewer says the cakes were lovely.")
        self.review(rating=4, body="Second reviewer says the bread was good.")
        self.assertEqual(self.public("public_detail", {"business_id": self.bid})[1]["rating"], {"count": 2, "average": None})
        with patch.object(limits, "MIN_REVIEWS_FOR_AVERAGE", 2):
            self.assertEqual(self.public("public_detail", {"business_id": self.bid})[1]["rating"], {"count": 2, "average": 4.5})
        with patch.object(limits, "MIN_REVIEWS_FOR_AVERAGE", 3):
            self.assertIsNone(self.public("public_detail", {"business_id": self.bid})[1]["rating"]["average"])

    def test_ineligible_authors_and_businesses_get_one_answer(self):
        unlisted_owner, unlisted = self.make_business("Hidden Co", publish=False)
        staff = self.add_staff(self.owner, self.bid)
        answers = {str(self.review(bid=unlisted)), str(self.review(bid=str(uuid4()))), str(self.review(customer=self.owner)),
                   str(self.review(customer=staff))}
        self.assertEqual(len(answers), 1)
        self.assertEqual(Review.objects.count(), 0)
        self.assertEqual(self.call("review_create", {"business_id": self.bid, "rating": 5, "body": BODY}, actor=uuid4(), verified=False)[0], 403)
        for role in ("moderator", "administrator"):
            self.assertEqual(self.call("review_create", {"business_id": self.bid, "rating": 5, "body": BODY}, actor=uuid4(), role=role, mfa=True)[0], 403)

    def test_one_review_per_author_and_withdrawing_does_not_allow_a_second(self):
        author = uuid4()
        rid = self.review(customer=author)[1]["id"]
        self.assertEqual(self.review(customer=author, body="Another long enough review text.")[1]["code"], "already_reviewed")
        self.call("review_withdraw_mine", {"review_id": rid}, actor=author)
        self.assertEqual(self.review(customer=author, body="Trying again after withdrawing.")[1]["code"], "already_reviewed")

    def test_inputs_are_validated_and_authority_cannot_be_named(self):
        for bad in ({"rating": 0}, {"rating": 6}, {"rating": "5"}, {"rating": True}, {"rating": 4.5}, {"body": "short"},
                    {"body": "x" * 2001}, {"body": "bad\x00text here"}, {"title": "t" * 101}, {"state": "published"},
                    {"basis": "interaction_confirmed"}, {"author_account_id": str(uuid4())}, {"rating_sum": 5},
                    {"author_label": "Admin"}, {"interaction_thread_id": "nope"}):
            self.assertEqual(self.call("review_create", {"business_id": self.bid, "rating": 5, "body": BODY, **bad},
                                       actor=uuid4())[0], 400, bad)
        self.assertEqual(Review.objects.count(), 0)

    def test_creation_is_throttled_per_author_and_idempotent(self):
        author = uuid4()
        data = {"business_id": self.bid, "rating": 5, "body": BODY}
        first = self.call("review_create", data, actor=author, key="rev-key-0123456789")
        again = self.call("review_create", data, actor=author, key="rev-key-0123456789")
        self.assertEqual((first, Review.objects.count()), (again, 1))
        statuses = [self.call("review_create", {"business_id": self.bid, "rating": 5, "body": "x" * 20}, actor=author)[0]
                    for _ in range(limits.BUDGETS["review_create"][0] + 1)]
        self.assertEqual(statuses[-1], 429)


class BasisTests(ReviewBase):
    def test_a_confirmed_conversation_gives_the_interaction_basis(self):
        customer = uuid4()
        tid = self.confirmed_thread(customer)
        status, body = self.review(customer=customer, interaction_thread_id=tid)
        self.assertEqual((status, body["basis"]), (201, "interaction_confirmed"))

    def test_unconfirmed_foreign_and_cross_business_conversations_are_refused_alike(self):
        customer, other = uuid4(), uuid4()
        mine = self.thread(customer)  # not confirmed
        foreign = self.confirmed_thread(other)
        cross = self.ask(customer=customer, bid=self.other)[1]["id"]
        self.call("inquiry_reply", {"business_id": self.other, "thread_id": cross, "body": "ok"}, actor=self.other_owner)
        self.call("inquiry_confirm_customer", {"thread_id": cross}, actor=customer)
        self.call("inquiry_confirm_business", {"business_id": self.other, "thread_id": cross}, actor=self.other_owner)
        answers = {str(self.review(customer=customer, interaction_thread_id=t)[1]) for t in (mine, foreign, cross, str(uuid4()))}
        self.assertEqual(answers, {str({"detail": "That conversation is not confirmed by both sides", "code": "interaction_not_confirmed"})})
        self.assertEqual(Review.objects.count(), 0)

    def test_invitation_codes_give_the_invited_basis_once(self):
        status, invite = self.call("review_invite_create", {"business_id": self.bid}, actor=self.owner)
        self.assertEqual(status, 201)
        code = invite["code"]
        self.assertNotIn(code, str(list(ReviewInvitation.objects.values())))
        status, body = self.review(invitation_code=code)
        self.assertEqual((status, body["basis"]), (201, "invited"))
        self.assertEqual(self.review(invitation_code=code)[0], 404)  # single use
        revoked = self.call("review_invite_create", {"business_id": self.bid}, actor=self.owner)[1]
        self.call("review_invite_revoke", {"business_id": self.bid, "invitation_id": revoked["id"]}, actor=self.owner)
        expired = self.call("review_invite_create", {"business_id": self.bid}, actor=self.owner)[1]
        ReviewInvitation.objects.filter(pk=expired["id"]).update(expires_at=self.now_minus())
        other_code = self.call("review_invite_create", {"business_id": self.other}, actor=self.other_owner)[1]["code"]
        answers = {str(self.review(invitation_code=c)) for c in (revoked["code"], expired["code"], other_code, "z" * 32)}
        self.assertEqual(answers, {str((404, {"detail": "Invitation unavailable"}))})
        self.assertEqual(self.review(invitation_code=code, interaction_thread_id=str(uuid4()))[0], 400)

    def now_minus(self):
        from django.utils import timezone
        return timezone.now() - timedelta(seconds=1)

    def test_only_the_owner_issues_review_invitations(self):
        staff = self.add_staff(self.owner, self.bid)
        for actor in (staff, uuid4(), self.other_owner):
            self.assertEqual(self.call("review_invite_create", {"business_id": self.bid}, actor=actor)[0], 404)
        self.assertEqual(ReviewInvitation.objects.count(), 0)


class FraudTests(ReviewBase):
    def reports(self):
        return self.rv("report_queue", {})[1]["items"]

    def test_a_burst_for_one_business_is_held_not_published_nor_counted(self):
        with patch.object(limits, "HOLD_BUSINESS_BURST", (2, timedelta(hours=24))):
            states = [self.review(body=f"Distinct review text number {i} here.")[1]["state"] for i in range(3)]
        self.assertEqual(states, ["published", "published", "held"])
        self.assertEqual(self.aggregate(), (2, 10))
        self.assertEqual(len(self.reviews()[1]["items"]), 2)
        self.assertEqual([(r["reason_code"], r["system_hold"]) for r in self.reports()], [("fraud_hold", True)])
        self.assertEqual(AuditEvent.objects.filter(kind="business.review_held").count(), 1)

    def test_identical_text_is_held_wherever_it_appears_and_one_author_bursting_is_held(self):
        self.published(body="Great place to buy bread every morning.")
        status, body = self.review(bid=self.other, body="great   place to BUY bread every morning.")
        self.assertEqual(body["state"], "held")
        author = uuid4()
        with patch.object(limits, "HOLD_AUTHOR_BURST", (1, timedelta(hours=24))):
            self.assertEqual(self.review(customer=author, body="First honest review of this shop.")[1]["state"], "published")
            self.assertEqual(self.review(customer=author, bid=self.other, body="Second honest review of another shop.")[1]["state"], "held")

    def test_a_reviewer_releases_or_removes_a_held_review(self):
        self.published(body="Original words for this particular review.")
        held = self.review(body="Original words for this particular review.")[1]["id"]
        report = self.reports()[0]["report_id"]
        case = self.rv("report_case", {"report_id": report})[1]
        self.assertEqual((case["system_hold"], case["content"]["hold_reasons"]), (True, ["duplicate_text"]))
        status, body = self.rv("report_decide", {"report_id": report, "decision": "keep", "reason_code": "genuine_customer"})
        self.assertEqual((status, body["decision"]), (200, "keep"))
        self.assertEqual((Review.objects.get(pk=held).state, self.aggregate()), ("published", (2, 10)))
        self.published(bid=self.other, body="A different shop gets a different review.")
        again = self.review(bid=self.other, body="A different shop gets a different review.")[1]["id"]
        report = self.reports()[0]["report_id"]
        self.rv("report_decide", {"report_id": report, "decision": "remove", "reason_code": "copied_text"})
        self.assertEqual((Review.objects.get(pk=again).state, self.aggregate(self.other)), ("removed", (1, 5)))

    def test_edits_re_enter_the_checks(self):
        self.published(body="Somebody else wrote this exact sentence first.")
        author = uuid4()
        rid = self.review(customer=author, body="My own and entirely original review text.")[1]["id"]
        status, body = self.call("review_edit_mine", {"review_id": rid, "body": "Somebody else wrote this exact sentence first."}, actor=author)
        self.assertEqual((status, body["state"]), (200, "held"))
        self.assertEqual(self.aggregate(), (1, 5))
        self.assertEqual(self.call("review_edit_mine", {"review_id": rid, "rating": 2}, actor=author)[1]["state"], "held")


class AuthorTests(ReviewBase):
    def test_edit_updates_the_aggregate_and_stranger_edits_are_404(self):
        author = uuid4()
        rid = self.review(customer=author, rating=5)[1]["id"]
        status, body = self.call("review_edit_mine", {"review_id": rid, "rating": 2, "title": "Changed my mind"}, actor=author)
        self.assertEqual((status, body["rating"], body["edited_at"] is not None), (200, 2, True))
        self.assertEqual(self.aggregate(), (1, 2))
        for operation, extra in (("review_edit_mine", {"rating": 1}), ("review_withdraw_mine", {})):
            self.assertEqual(self.call(operation, {"review_id": rid, **extra}, actor=uuid4())[0], 404)
        self.assertEqual(self.call("review_edit_mine", {"review_id": rid}, actor=author)[0], 400)
        self.assertEqual(self.call("review_edit_mine", {"review_id": rid, "state": "published"}, actor=author)[0], 400)
        self.assertEqual([r["id"] for r in self.call("review_list_mine", {}, actor=author)[1]["items"]], [rid])
        self.assertEqual(self.call("review_list_mine", {}, actor=uuid4())[1]["items"], [])

    def test_withdrawal_blanks_the_text_removes_the_response_and_the_rating(self):
        author = uuid4()
        rid = self.review(customer=author)[1]["id"]
        self.call("review_respond", {"business_id": self.bid, "review_id": rid, "body": "Thank you!"}, actor=self.owner)
        status, body = self.call("review_withdraw_mine", {"review_id": rid}, actor=author)
        review = Review.objects.get(pk=rid)
        self.assertEqual((status, body["state"], review.body, review.title, review.body_digest), (200, "withdrawn", "", "", ""))
        self.assertEqual((self.aggregate(), ReviewResponse.objects.count(), self.reviews()[1]["items"]), ((0, 0), 0, []))
        self.assertEqual(self.call("review_edit_mine", {"review_id": rid, "rating": 1}, actor=author)[1]["code"], "not_editable")
        self.assertEqual(self.call("review_withdraw_mine", {"review_id": rid}, actor=author)[0], 200)  # idempotent


class ResponseTests(ReviewBase):
    def setUp(self):
        super().setUp()
        self.rid = self.review()[1]["id"]

    def respond(self, actor=None, bid=None, rid=None, body="Thank you for the kind words."):
        return self.call("review_respond", {"business_id": bid or self.bid, "review_id": rid or self.rid, "body": body}, actor=actor or self.owner)

    def test_the_owner_answers_once_and_the_answer_is_public(self):
        self.assertEqual(self.respond()[0], 200)
        self.assertEqual(self.respond(body="Updated answer text.")[0], 200)
        self.assertEqual(ReviewResponse.objects.count(), 1)
        self.assertEqual(self.reviews()[1]["items"][0]["response"]["body"], "Updated answer text.")
        self.assertEqual(self.call("review_response_delete", {"business_id": self.bid, "review_id": self.rid}, actor=self.owner)[0], 200)
        self.assertIsNone(self.reviews()[1]["items"][0]["response"])

    def test_only_the_owner_of_that_business_may_answer(self):
        staff = self.add_staff(self.owner, self.bid)
        for actor, bid in ((staff, self.bid), (uuid4(), self.bid), (self.other_owner, self.bid), (self.other_owner, self.other)):
            self.assertEqual(self.respond(actor=actor, bid=bid)[0], 404, (actor, bid))
        self.assertEqual(ReviewResponse.objects.count(), 0)
        self.assertEqual(self.respond(body="x")[0], 400)

    def test_a_business_has_no_operation_that_hides_edits_or_removes_a_review(self):
        names = set(OPERATIONS)
        self.assertFalse({n for n in names if "review" in n and any(w in n for w in ("hide", "remove", "edit_business", "delete"))
                          and n != "review_response_delete"})
        self.assertEqual({n for n in names if n.startswith("review_")} & {"review_edit_mine", "review_withdraw_mine"},
                         {"review_edit_mine", "review_withdraw_mine"})  # author-scoped only

    def test_a_held_review_cannot_be_answered(self):
        Review.objects.filter(pk=self.rid).update(state="held")
        self.assertEqual(self.respond()[1]["code"], "not_published")


class ReportTests(ReviewBase):
    def setUp(self):
        super().setUp()
        self.author = uuid4()
        self.rid = self.review(customer=self.author)[1]["id"]
        self.reporter = uuid4()

    def report(self, subject="review", sid=None, actor=None, code="misleading", **kw):
        return self.call("report_create", {"subject_type": subject, "subject_id": sid or self.rid, "reason_code": code},
                         actor=actor or self.reporter, **kw)

    def test_reporting_is_limited_to_what_the_reporter_can_see(self):
        self.assertEqual(self.report()[0], 201)
        self.assertEqual(self.report()[1]["code"], "already_reported")
        self.assertEqual(self.report(actor=self.author)[1]["code"], "own_content")
        Review.objects.filter(pk=self.rid).update(state="held")
        self.assertEqual(self.report(actor=uuid4())[0], 404)       # held reviews are not visible
        self.assertEqual(self.report(sid=str(uuid4()), actor=uuid4())[0], 404)
        for bad in ({"subject_type": "listing"}, {"reason_code": "BAD CODE"}, {"extra": 1}):
            data = {"subject_type": "review", "subject_id": self.rid, "reason_code": "misleading", **bad}
            self.assertEqual(self.call("report_create", data, actor=uuid4())[0], 400, bad)
        self.assertEqual(self.report(actor=uuid4(), verified=False)[0], 403)

    def test_inquiry_messages_can_only_be_reported_by_participants(self):
        customer = uuid4()
        tid = self.thread(customer)
        mid = str(InquiryMessage.objects.get(thread_id=tid).id)
        self.assertEqual(self.report("inquiry_message", mid, actor=uuid4())[0], 404)
        self.assertEqual(self.report("inquiry_message", mid, actor=self.owner)[0], 201)   # the business, a participant
        self.assertEqual(self.report("inquiry_message", mid, actor=self.other_owner)[0], 404)
        self.assertEqual(self.report("inquiry_message", mid, actor=customer)[1]["code"], "own_content")

    def test_reports_are_throttled(self):
        statuses = [self.report(actor=self.reporter, sid=str(uuid4()))[0] for _ in range(limits.BUDGETS["report_create"][0] + 1)]
        self.assertEqual(statuses[-1], 429)

    def test_reviewer_routes_need_role_mfa_and_a_review_queue_grant(self):
        self.report()
        report = BusinessReport.objects.get().id
        for operation, data in (("report_queue", {}), ("report_case", {"report_id": str(report)}),
                                ("report_decide", {"report_id": str(report), "decision": "remove", "reason_code": "misleading"})):
            for role, mfa in (("viewer", True), ("creator", True), ("moderator", False), ("administrator", False)):
                self.assertEqual(self.call(operation, data, actor=self.reviewer, role=role, mfa=mfa)[0], 403)
        stranger = uuid4()
        self.call("reviewer_grant", {"reviewer_account_id": str(stranger), "scope": "verification", "active": True}, actor=self.admin, role="administrator", mfa=True)
        self.assertEqual(self.call("report_queue", {}, actor=stranger, role="moderator", mfa=True)[1]["items"], [])
        self.assertEqual(self.call("report_case", {"report_id": str(report)}, actor=stranger, role="moderator", mfa=True)[0], 404)
        self.assertEqual(Review.objects.get(pk=self.rid).state, "published")

    def test_removing_a_review_updates_public_views_and_the_aggregate(self):
        self.report()
        report = str(BusinessReport.objects.get().id)
        status, case = self.rv("report_case", {"report_id": report})
        self.assertEqual((status, case["content"]["body"], case["system_hold"]), (200, BODY, False))
        self.assertNotIn(str(self.reporter), str(case))
        self.assertEqual(self.rv("report_decide", {"report_id": report, "decision": "remove", "reason_code": "misleading"}, key="decide-key-0123456789")[0], 200)
        self.assertEqual((Review.objects.get(pk=self.rid).state, self.aggregate(), self.reviews()[1]["items"]), ("removed", (0, 0), []))
        self.assertEqual(self.rv("report_decide", {"report_id": report, "decision": "remove", "reason_code": "misleading"})[0], 404)  # already decided
        self.assertEqual(AuditEvent.objects.filter(kind="business.report_decided").count(), 1)

    def test_removing_a_response_or_a_message_hides_only_that_content(self):
        self.call("review_respond", {"business_id": self.bid, "review_id": self.rid, "body": "Our reply to you."}, actor=self.owner)
        response_id = str(ReviewResponse.objects.get().id)
        self.report("review_response", response_id)
        self.rv("report_decide", {"report_id": str(BusinessReport.objects.get().id), "decision": "remove", "reason_code": "abusive"})
        self.assertIsNone(self.reviews()[1]["items"][0]["response"])
        self.assertEqual(self.respondable(), "response_removed")  # the owner cannot put it back
        tid = self.thread(uuid4())
        mid = str(InquiryMessage.objects.get(thread_id=tid).id)
        self.report("inquiry_message", mid, actor=self.owner)
        self.rv("report_decide", {"report_id": str(BusinessReport.objects.get(subject_id=mid).id), "decision": "remove", "reason_code": "abusive"})
        view = self.call("inquiry_inbox_get", {"business_id": self.bid, "thread_id": tid}, actor=self.owner)[1]
        self.assertEqual((view["messages"][0]["body"], view["messages"][0]["removed"]), (None, True))

    def respondable(self):
        return self.call("review_respond", {"business_id": self.bid, "review_id": self.rid, "body": "Replacement text"}, actor=self.owner)[1]["code"]

    def test_keep_changes_nothing_and_conflicted_reviewers_cannot_decide(self):
        self.report()
        report = str(BusinessReport.objects.get().id)
        BusinessReport.objects.update(reporter_account_id=self.reviewer)
        self.assertEqual(self.rv("report_case", {"report_id": report})[0], 404)  # a reviewer cannot judge their own report
        BusinessReport.objects.update(reporter_account_id=self.reporter)
        self.assertEqual(self.rv("report_decide", {"report_id": report, "decision": "keep", "reason_code": "no_violation"})[0], 200)
        self.assertEqual((Review.objects.get(pk=self.rid).state, self.aggregate()), ("published", (1, 5)))
        self.assertEqual(self.report(actor=self.reporter)[0], 201)  # a decided report no longer blocks a new one

    def test_decisions_are_validated(self):
        self.report()
        report = str(BusinessReport.objects.get().id)
        for bad in ({"decision": "restore", "reason_code": "misleading"}, {"decision": "ban", "reason_code": "misleading"},
                    {"decision": "remove"}, {"decision": "remove", "reason_code": "BAD"},
                    {"decision": "remove", "reason_code": "misleading", "state": "removed"}):
            self.assertEqual(self.rv("report_decide", {"report_id": report, **bad})[0], 400, bad)
        self.assertEqual(Review.objects.get(pk=self.rid).state, "published")


class PublicListTests(ReviewBase):
    def test_pagination_is_newest_first_complete_and_cursors_are_bound(self):
        for index in range(5):
            self.review(body=f"Review number {index} with enough words.")
        seen, cursor = [], None
        for _ in range(5):
            status, body = self.reviews(limit=2, **({"cursor": cursor} if cursor else {}))
            self.assertEqual(status, 200)
            seen += [i["body"] for i in body["items"]]
            cursor = body["next_cursor"]
            if not cursor:
                break
        self.assertEqual(len(seen), 5)
        self.assertEqual(len(set(seen)), 5)
        _, first = self.reviews(limit=2)
        for bad in ("garbage", first["next_cursor"][:-2] + "zz"):
            self.assertEqual(self.reviews(limit=2, cursor=bad)[0], 400)
        self.assertEqual(self.reviews(bid=self.other, limit=2, cursor=first["next_cursor"])[0], 400)  # another business's cursor

    def test_unlisted_businesses_have_no_public_reviews(self):
        self.review()
        self.call("listing_unpublish", {"business_id": self.bid}, actor=self.owner)
        self.assertEqual(self.reviews()[0], 404)
        self.assertEqual(self.reviews(bid=str(uuid4()))[0], 404)

    def test_the_aggregate_always_equals_a_recomputation(self):
        authors = [uuid4() for _ in range(4)]
        ids = [self.review(customer=a, rating=r, body=f"Independent review text number {r} here.")[1]["id"]
               for a, r in zip(authors, (5, 3, 1, 4))]
        self.call("review_edit_mine", {"review_id": ids[0], "rating": 2}, actor=authors[0])
        self.call("review_withdraw_mine", {"review_id": ids[1]}, actor=authors[1])
        Review.objects.filter(pk=ids[3]).update(state="held")
        from service.reviews import recompute
        from service.models import Business
        recompute(Business.objects.get(pk=self.bid))
        published = list(Review.objects.filter(business_id=self.bid, state="published").values_list("rating", flat=True))
        self.assertEqual(self.aggregate(), (len(published), sum(published)))
        self.assertEqual(self.aggregate(), (2, 3))
