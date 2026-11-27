"""Mandate 3.3b: Business assembles one account's own business records for an access export, once."""
import json
import uuid

from django.db import connection, transaction

from service import privacy
from service.models import StaffInvitation
from .support import BusinessTestCase


def delivered(self):
    with connection.cursor() as cur:
        cur.execute("SELECT event_type, payload FROM event_outbox")
        rows = cur.fetchall()
    self.assertEqual(len(rows), 1)
    self.assertEqual(rows[0][0], "privacy.export_delivered")
    part = json.loads(rows[0][1])
    json.dumps(part, allow_nan=False)
    return part


def export_twice(self, payload):
    event = str(uuid.uuid4())
    with transaction.atomic():
        self.assertTrue(privacy.export(event, payload))
    with transaction.atomic():
        self.assertFalse(privacy.export(event, payload), "a repeat delivery sends nothing more")
    return delivered(self)


class BusinessExportTests(BusinessTestCase):
    def setUp(self):
        super().setUp()
        self.owner, business = self.register()
        self.business_id = business["id"]
        self.person = self.add_staff(self.owner, self.business_id)
        self.request_id = str(uuid.uuid4())

    def payload(self, account=None, **changes):
        return {"request_id": self.request_id, "account_id": str(account or self.person),
                "service": "business"} | changes

    def test_a_staff_member_gets_their_membership_and_nothing_of_the_owner(self):
        part = export_twice(self, self.payload())
        self.assertEqual(len(part["data"]["memberships"]), 1)
        self.assertEqual(part["data"]["memberships"][0]["business_id"], self.business_id)
        self.assertEqual(part["data"]["businesses_created"], [])
        self.assertNotIn(str(self.owner), json.dumps(part))

    def test_the_owner_gets_the_business_they_created_and_invitation_codes_never_leave(self):
        part = export_twice(self, self.payload(account=self.owner))
        self.assertEqual(len(part["data"]["businesses_created"]), 1)
        self.assertIn("staff_invitations", part["withheld"])
        text = json.dumps(part)
        for digest in StaffInvitation.objects.values_list("code_digest", flat=True):
            self.assertNotIn(digest, text)

    def test_malformed_requests_are_refused(self):
        for bad in (self.payload(service="creators"), self.payload(extra=1)):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                privacy.export(str(uuid.uuid4()), bad)
