"""B5 part 1: inquiries — ownership, isolation, privacy of the customer, blocking, throttles and confirmation."""
from datetime import timedelta
from unittest.mock import patch
from uuid import uuid4

from service import limits
from service.models import AuditEvent, InquiryBlock, InquiryMessage, InquiryThread
from .test_listings import ListingBase


class InquiryBase(ListingBase):
    def setUp(self):
        super().setUp()
        self.owner, self.bid = self.make_business("Alpha Bakery")
        self.other_owner, self.other = self.make_business("Beta Cafe")
        self.customer = uuid4()

    def ask(self, customer=None, bid=None, body="Do you take large orders?", **kw):
        return self.call("inquiry_create", {"business_id": bid or self.bid, "subject_code": "order_question", "body": body},
                         actor=customer or self.customer, **kw)

    def thread(self, customer=None):
        status, body = self.ask(customer)
        assert status == 201, body
        return body["id"]


class CustomerTests(InquiryBase):
    def test_a_verified_customer_opens_one_thread_with_a_listed_business(self):
        status, body = self.ask()
        self.assertEqual(status, 201)
        self.assertEqual((body["state"], body["business_name"], len(body["messages"])), ("open", "Alpha Bakery", 1))
        self.assertEqual(self.ask()[1]["code"], "thread_exists")
        self.assertEqual(self.ask(verified=False)[0], 403)
        self.assertEqual(AuditEvent.objects.filter(kind="business.inquiry_created").count(), 1)

    def test_unlisted_unknown_own_and_blocked_are_one_indistinguishable_answer(self):
        unlisted_owner, unlisted = self.make_business("Hidden Co", publish=False)
        answers = {str(self.ask(bid=b)) for b in (unlisted, str(uuid4()))}
        self.assertEqual(len(answers), 1)
        self.assertEqual(self.ask(customer=self.owner)[0], 404)  # own business
        staff = self.add_staff(self.owner, self.bid)
        self.assertEqual(self.ask(customer=staff)[0], 404)       # staff of the business
        tid = self.thread()
        self.call("inquiry_block", {"business_id": self.bid, "thread_id": tid}, actor=self.owner)
        self.assertEqual(str(self.ask()), str(self.ask(bid=unlisted)))  # blocked looks like unlisted

    def test_roles_and_inputs_are_enforced(self):
        for role in ("moderator", "administrator"):
            self.assertEqual(self.ask(role=role, mfa=True)[0], 403)
        for bad in ({"body": ""}, {"body": "x" * 1001}, {"body": "a\x00b"}, {"subject_code": "Bad Code"}, {"account_id": str(uuid4())},
                    {"customer_label": "Admin"}, {"attachment": "x"}):
            data = {"business_id": self.bid, "subject_code": "order_question", "body": "hello", **bad}
            self.assertEqual(self.call("inquiry_create", data, actor=uuid4())[0], 400, bad)
        self.assertEqual(InquiryThread.objects.count(), 0)

    def test_customers_see_only_their_own_threads(self):
        tid = self.thread()
        stranger = uuid4()
        self.assertEqual(self.call("inquiry_get_mine", {"thread_id": tid}, actor=stranger)[0], 404)
        self.assertEqual(self.call("inquiry_message_customer", {"thread_id": tid, "body": "hi"}, actor=stranger)[0], 404)
        self.assertEqual(self.call("inquiry_close_customer", {"thread_id": tid}, actor=stranger)[0], 404)
        self.assertEqual(self.call("inquiry_confirm_customer", {"thread_id": tid}, actor=stranger)[0], 404)
        self.assertEqual(self.call("inquiry_list_mine", {}, actor=stranger)[1]["items"], [])
        self.assertEqual([t["id"] for t in self.call("inquiry_list_mine", {}, actor=self.customer)[1]["items"]], [tid])
        self.assertNotIn("messages", self.call("inquiry_list_mine", {}, actor=self.customer)[1]["items"][0])

    def test_messages_are_bounded_and_a_closed_thread_stays_closed(self):
        tid = self.thread()
        self.assertEqual(self.call("inquiry_message_customer", {"thread_id": tid, "body": "More detail."}, actor=self.customer)[0], 201)
        self.assertEqual(self.call("inquiry_close_customer", {"thread_id": tid}, actor=self.customer)[0], 200)
        self.assertEqual(self.call("inquiry_message_customer", {"thread_id": tid, "body": "again"}, actor=self.customer)[1]["code"], "thread_closed")
        self.assertEqual(self.call("inquiry_reply", {"business_id": self.bid, "thread_id": tid, "body": "x"}, actor=self.owner)[1]["code"], "thread_closed")
        self.assertEqual(self.ask()[0], 201)  # a new conversation may follow a closed one
        with patch.object(limits, "MAX_MESSAGES_PER_THREAD", 2):
            tid = InquiryThread.objects.filter(state="open").get().id
            self.call("inquiry_message_customer", {"thread_id": str(tid), "body": "second"}, actor=self.customer)
            self.assertEqual(self.call("inquiry_message_customer", {"thread_id": str(tid), "body": "third"}, actor=self.customer)[1]["code"], "thread_full")

    def test_throttles_apply_per_customer_and_per_business(self):
        with patch.dict(limits.BUDGETS, {"inquiry_create": (2, timedelta(days=1))}):
            statuses = [self.ask(customer=self.customer, bid=b)[0] for b in (self.bid, self.other, self.bid)]
        self.assertEqual(statuses, [201, 201, 429])
        with patch.dict(limits.BUDGETS, {"inquiry_business": (2, timedelta(hours=1))}):
            statuses = [self.ask(customer=uuid4())[0] for _ in range(3)]
        self.assertEqual(statuses[-1], 429)

    def test_probing_unlisted_ids_cannot_spend_a_businesss_budget(self):
        with patch.dict(limits.BUDGETS, {"inquiry_business": (1, timedelta(hours=1))}):
            for _ in range(5):
                self.assertEqual(self.ask(customer=uuid4(), bid=str(uuid4()))[0], 404)
            self.assertEqual(self.ask(customer=uuid4())[0], 201)


class BusinessSideTests(InquiryBase):
    def setUp(self):
        super().setUp()
        self.tid = self.thread()

    def test_the_inbox_shows_a_pseudonymous_label_and_never_an_account_id(self):
        status, body = self.call("inquiry_inbox", {"business_id": self.bid}, actor=self.owner)
        self.assertEqual(status, 200)
        self.assertEqual(body["items"][0]["customer_label"], "Customer 1")
        status, full = self.call("inquiry_inbox_get", {"business_id": self.bid, "thread_id": self.tid}, actor=self.owner)
        self.assertEqual(set(full), {"id", "customer_label", "state", "subject_code", "created_at", "confirmed", "messages"})
        self.assertNotIn(str(self.customer), str(body) + str(full))
        self.assertNotIn("account", str(full))

    def test_staff_work_the_inbox_but_cannot_block_and_others_are_isolated(self):
        staff = self.add_staff(self.owner, self.bid)
        self.assertEqual(self.call("inquiry_reply", {"business_id": self.bid, "thread_id": self.tid, "body": "Yes we do."}, actor=staff)[0], 201)
        self.assertEqual(self.call("inquiry_block", {"business_id": self.bid, "thread_id": self.tid}, actor=staff)[0], 404)
        for actor, bid in ((self.other_owner, self.bid), (self.customer, self.bid), (uuid4(), self.bid)):
            for operation, extra in (("inquiry_inbox", {}), ("inquiry_inbox_get", {"thread_id": self.tid}),
                                     ("inquiry_reply", {"thread_id": self.tid, "body": "x"}),
                                     ("inquiry_close_business", {"thread_id": self.tid}),
                                     ("inquiry_confirm_business", {"thread_id": self.tid}),
                                     ("inquiry_block", {"thread_id": self.tid})):
                self.assertEqual(self.call(operation, {"business_id": bid, **extra}, actor=actor)[0], 404, (operation, actor))

    def test_a_thread_id_from_another_business_does_not_work_under_my_business_path(self):
        other_thread = self.thread(customer=uuid4()) if False else None
        status, body = self.ask(customer=uuid4(), bid=self.other)
        for operation, extra in (("inquiry_inbox_get", {}), ("inquiry_reply", {"body": "x"}), ("inquiry_close_business", {}),
                                 ("inquiry_confirm_business", {}), ("inquiry_block", {})):
            self.assertEqual(self.call(operation, {"business_id": self.bid, "thread_id": body["id"], **extra}, actor=self.owner)[0], 404, operation)
        self.assertEqual(InquiryBlock.objects.count(), 0)

    def test_blocking_closes_the_conversation_and_prevents_new_ones_silently(self):
        status, body = self.call("inquiry_block", {"business_id": self.bid, "thread_id": self.tid}, actor=self.owner)
        self.assertEqual((status, body["state"]), (200, "blocked"))
        self.assertEqual(InquiryBlock.objects.count(), 1)
        self.assertEqual(self.call("inquiry_message_customer", {"thread_id": self.tid, "body": "hello?"}, actor=self.customer)[1]["code"], "thread_closed")
        self.assertEqual(self.ask()[0], 404)
        self.assertEqual(self.ask(customer=uuid4())[0], 201)  # other customers are unaffected
        self.assertEqual(AuditEvent.objects.filter(kind="business.inquiry_blocked").count(), 1)

    def test_replies_are_idempotent(self):
        for _ in range(2):
            self.call("inquiry_reply", {"business_id": self.bid, "thread_id": self.tid, "body": "Same."}, actor=self.owner, key="reply-key-0123456789")
        self.assertEqual(InquiryMessage.objects.filter(author_kind="business").count(), 1)

    def test_a_business_cannot_start_conversations(self):
        self.assertEqual(self.call("inquiry_create", {"business_id": self.other, "subject_code": "order_question", "body": "x"},
                                   actor=self.owner)[0], 201)  # an owner is a customer of OTHER businesses
        self.assertEqual(self.call("inquiry_create", {"business_id": self.bid, "subject_code": "order_question", "body": "x"},
                                   actor=self.owner)[0], 404)

    def test_completion_needs_both_sides_to_have_written_and_both_to_confirm(self):
        self.assertEqual(self.call("inquiry_confirm_customer", {"thread_id": self.tid}, actor=self.customer)[1]["code"], "no_exchange")
        self.call("inquiry_reply", {"business_id": self.bid, "thread_id": self.tid, "body": "Done."}, actor=self.owner)
        status, body = self.call("inquiry_confirm_customer", {"thread_id": self.tid}, actor=self.customer)
        self.assertEqual((status, body["confirmed"]), (200, {"customer": True, "business": False}))
        status, body = self.call("inquiry_confirm_business", {"business_id": self.bid, "thread_id": self.tid}, actor=self.owner)
        self.assertEqual(body["confirmed"], {"customer": True, "business": True})
        self.assertEqual(AuditEvent.objects.filter(kind="business.inquiry_confirmed").count(), 2)
