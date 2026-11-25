"""Decision F (D-8): creator measures, enforcement, expiry, appeals and reinstatement."""

import json
from datetime import timedelta
from uuid import uuid4

from django.db import IntegrityError, transaction
from django.test import RequestFactory, TestCase
from django.utils import timezone

from service.models import AuditEvent, CreatorApplication, CreatorProfile, CreatorRestriction, RestrictionAppeal
from service.onboarding import POLICY_VERSION, onboarding
from service.restrictions import restrictions

REASON = "Repeated spam uploads after a warning"


class RestrictionTests(TestCase):
    def setUp(self):
        self.account, self.admin, self.other_admin = uuid4(), uuid4(), uuid4()
        self.profile = CreatorProfile.objects.create(user_id=self.account, handle="restricted_creator",
                                                     status="active", reviewed_at=timezone.now())
        CreatorApplication.objects.create(account_id=self.account, invited_by=uuid4(), profile=self.profile,
                                          status="approved", attestation_version=POLICY_VERSION)

    def call(self, operation, data, actor=None, role="administrator", caller="gateway"):
        request = RequestFactory().post("/internal/creators/restrictions/" + operation, {
            "actor_id": str(actor or self.admin), "role": role, "data": data}, content_type="application/json")
        request.service_caller = caller
        return restrictions(request, operation)

    def own(self, operation, data=None):
        return self.call(operation, data or {}, actor=self.account, role="creator")

    def onboarding(self, operation):
        request = RequestFactory().post("/internal/creators/onboarding/" + operation, {
            "actor_id": str(self.account), "role": "creator", "data": {}}, content_type="application/json")
        request.service_caller = "gateway"
        return json.loads(onboarding(request, operation).content)

    def issue(self, kind, key="restriction-key-0001", expires_at=None, actor=None):
        return self.call("issue", {"creator_id": str(self.profile.id), "kind": kind, "reason_code": "SPAM_REPEAT",
                                   "policy_version": "creator-enforcement-v1", "reason": REASON,
                                   "expires_at": expires_at, "key": key}, actor=actor)

    def capabilities(self):
        return json.loads(self.own("capabilities").content)

    def kinds(self):
        return list(AuditEvent.objects.order_by("occurred_at").values_list("kind", flat=True))

    def test_each_kind_blocks_only_what_it_names(self):
        expected = {"warning": (True, True, True), "upload": (False, True, True), "publishing": (True, False, True),
                    "monetization": (True, True, False), "suspension": (False, False, False)}
        for index, (kind, (upload, publish, money)) in enumerate(expected.items()):
            with self.subTest(kind):
                result = self.issue(kind, key=f"restriction-key-{index:04d}")
                self.assertEqual(result.status_code, 201)
                caps = self.capabilities()
                self.assertEqual((caps["upload"], caps["publish"], caps["monetization"]), (upload, publish, money))
                self.assertEqual(self.onboarding("eligibility")["upload_eligible"], upload)
                self.assertEqual(self.onboarding("standing")["publishing_allowed"], publish)
                CreatorRestriction.objects.filter(pk=json.loads(result.content)["id"]).update(
                    lifted_at=timezone.now(), lifted_by=self.other_admin)
        self.assertEqual(self.kinds(), ["creator.warned", "creator.restricted", "creator.restricted",
                                        "creator.restricted", "creator.suspended"])

    def test_standing_shows_the_derived_status(self):
        upload = json.loads(self.issue("upload").content)["id"]
        self.assertEqual(self.onboarding("standing")["creator_status"], "active")  # publishing still allowed
        CreatorRestriction.objects.filter(pk=upload).update(lifted_at=timezone.now(), lifted_by=self.other_admin)
        self.issue("publishing", key="restriction-key-0002")
        self.assertEqual(self.onboarding("standing")["creator_status"], "restricted")
        self.issue("suspension", key="restriction-key-0003")
        self.assertEqual(self.onboarding("standing")["creator_status"], "suspended")

    def test_capabilities_need_an_approved_creator(self):
        CreatorApplication.objects.filter(account_id=self.account).update(status="revoked")
        caps = self.capabilities()
        self.assertEqual((caps["creator_id"], caps["upload"], caps["publish"], caps["monetization"]),
                         (str(self.profile.id), False, False, False))

    def test_a_temporary_measure_expires_without_a_scheduler(self):
        expires = (timezone.now() + timedelta(hours=1)).isoformat()
        restriction = json.loads(self.issue("upload", expires_at=expires).content)
        self.assertFalse(self.capabilities()["upload"])
        CreatorRestriction.objects.filter(pk=restriction["id"]).update(
            issued_at=timezone.now() - timedelta(hours=3), expires_at=timezone.now() - timedelta(seconds=1))
        self.assertTrue(self.capabilities()["upload"])
        mine = json.loads(self.own("mine").content)["items"]
        self.assertFalse(mine[0]["active"])
        self.assertEqual(self.issue("upload", key="restriction-key-past", expires_at=timezone.now().isoformat()).status_code, 400)

    def test_issue_is_idempotent_validated_and_never_self_applied(self):
        first = self.issue("upload")
        self.assertEqual(self.issue("upload").status_code, 200)
        self.assertEqual(self.issue("publishing").status_code, 409)
        self.assertEqual(CreatorRestriction.objects.count(), 1)
        self.assertEqual(self.issue("upload", key="restriction-key-self", actor=self.account).status_code, 403)
        for bad in ({"kind": "ban"}, {"reason_code": "lower"}, {"reason": "short"}, {"key": "x"}):
            data = {"creator_id": str(self.profile.id), "kind": "upload", "reason_code": "SPAM_REPEAT",
                    "policy_version": "v1", "reason": REASON, "expires_at": None, "key": "restriction-key-bad1"} | bad
            self.assertEqual(self.call("issue", data).status_code, 400)
        self.assertEqual(json.loads(first.content)["reason"], REASON)

    def test_only_administrators_manage_and_creators_see_no_private_detail(self):
        self.issue("upload")
        for role in ("moderator", "creator", "viewer"):
            self.assertEqual(self.call("list", {"creator_id": str(self.profile.id)}, role=role).status_code, 403)
        self.assertEqual(self.call("list", {"creator_id": str(self.profile.id)}, caller="moderation").status_code, 403)
        self.assertEqual(self.call("mine", {}, role="administrator").status_code, 403)
        mine = json.loads(self.own("mine").content)
        item = mine["items"][0]
        self.assertEqual((item["kind"], item["reason_code"], item["active"]), ("upload", "SPAM_REPEAT", True))
        for private in ("reason", "issued_by", "lifted_by", "lift_reason", "creator_id"):
            self.assertNotIn(private, item)
        self.assertNotIn(REASON, json.dumps(mine))
        self.assertNotIn(REASON, json.dumps(list(AuditEvent.objects.values()), default=str))

    def test_lift_needs_a_different_administrator_and_replays(self):
        restriction = json.loads(self.issue("suspension").content)["id"]
        lift = {"restriction_id": restriction, "reason": "Reviewed and reinstated"}
        self.assertEqual(self.call("lift", lift).status_code, 403)
        self.assertEqual(self.call("lift", lift, actor=self.other_admin).status_code, 200)
        self.assertEqual(self.call("lift", lift, actor=self.other_admin).status_code, 200)
        self.assertEqual(self.call("lift", lift | {"reason": "Another reason given"}, actor=uuid4()).status_code, 409)
        self.assertTrue(self.capabilities()["upload"])
        self.assertEqual(self.kinds()[-1], "creator.restored")

    def test_appeal_is_decided_by_an_independent_administrator(self):
        restriction = json.loads(self.issue("publishing").content)["id"]
        appeal = self.own("appeal", {"restriction_id": restriction, "reason": "These were my own original videos"})
        self.assertEqual(appeal.status_code, 201)
        appeal_id = json.loads(appeal.content)["id"]
        self.assertEqual(self.own("appeal", {"restriction_id": restriction, "reason": "These were my own original videos"}).status_code, 200)
        self.assertEqual(self.own("appeal", {"restriction_id": restriction, "reason": "A second, different appeal"}).status_code, 409)
        queue = json.loads(self.call("appeals", {"cursor": None}).content)["items"]
        self.assertEqual([item["id"] for item in queue], [appeal_id])
        decide = {"appeal_id": appeal_id, "decision": "lift", "reason": "Evidence shows original work"}
        self.assertEqual(self.call("decide", decide).status_code, 403)  # the issuer
        self.assertEqual(self.call("decide", decide | {"decision": "pardon"}, actor=self.other_admin).status_code, 400)
        self.assertEqual(self.call("decide", decide, actor=self.other_admin).status_code, 200)
        self.assertEqual(self.call("decide", decide, actor=self.other_admin).status_code, 200)
        self.assertEqual(self.call("decide", decide | {"decision": "uphold"}, actor=self.other_admin).status_code, 409)
        self.assertTrue(self.capabilities()["publish"])
        self.assertEqual(json.loads(self.own("mine").content)["items"][0]["appeal"]["status"], "lifted")
        self.assertEqual(json.loads(self.call("appeals", {"cursor": None}).content)["items"], [])
        self.assertIn("creator.restriction_appealed", self.kinds())
        self.assertIn("creator.restriction_appeal_decided", self.kinds())

    def test_upheld_appeal_keeps_the_measure_and_a_lift_closes_an_open_appeal(self):
        first = json.loads(self.issue("upload").content)["id"]
        appeal = json.loads(self.own("appeal", {"restriction_id": first, "reason": "Please look at this again"}).content)["id"]
        self.assertEqual(self.call("decide", {"appeal_id": appeal, "decision": "uphold", "reason": "The evidence stands"},
                                   actor=self.other_admin).status_code, 200)
        self.assertFalse(self.capabilities()["upload"])
        second = json.loads(self.issue("monetization", key="restriction-key-0002").content)["id"]
        self.own("appeal", {"restriction_id": second, "reason": "Please look at this again"})
        self.call("lift", {"restriction_id": second, "reason": "Lifted after a fresh review"}, actor=self.other_admin)
        self.assertEqual(RestrictionAppeal.objects.get(restriction_id=second).status, "lifted")

    def test_appeals_need_an_owned_active_measure(self):
        restriction = json.loads(self.issue("upload").content)["id"]
        self.assertEqual(self.call("appeal", {"restriction_id": restriction, "reason": "Not my restriction"},
                                   actor=uuid4(), role="creator").status_code, 404)
        self.call("lift", {"restriction_id": restriction, "reason": "Lifted after a fresh review"}, actor=self.other_admin)
        self.assertEqual(self.own("appeal", {"restriction_id": restriction, "reason": "Too late for this one"}).status_code, 409)

    def test_database_guards(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            CreatorRestriction.objects.create(id=uuid4(), creator=self.profile, kind="ban", reason_code="X1",
                                              policy_version="v1", reason=REASON, issued_by=self.admin)
        with self.assertRaises(IntegrityError), transaction.atomic():
            now = timezone.now()
            CreatorRestriction.objects.create(id=uuid4(), creator=self.profile, kind="upload", reason_code="X1",
                                              policy_version="v1", reason=REASON, issued_by=self.admin,
                                              issued_at=now, expires_at=now - timedelta(seconds=1))

    def test_unknown_account_has_no_capabilities(self):
        result = json.loads(self.call("capabilities", {}, actor=uuid4(), role="viewer").content)
        self.assertEqual(result, {"creator_id": None, "upload": False, "publish": False, "monetization": False})
