"""Decision E (D11-008): verified rights holders and the reviewer's copyright signals."""
import json
from unittest.mock import patch
from uuid import uuid4

from django.db import IntegrityError, transaction
from django.test import RequestFactory, TestCase

from service.models import AuditEvent, CopyrightNotice, CopyrightStrike, ModeratorAssignment, Report, RightsHolder
from service.workflow import moderation_workflow

EVIDENCE = "Signed letter from the label confirming authority"


class RightsHolderTests(TestCase):
    def setUp(self):
        self.video, self.creator, self.claimant, self.admin, self.other, self.reviewer = (uuid4() for _ in range(6))
        self.snapshot = {"creator_id": str(self.creator), "state": "published", "visibility": "public", "revision": 1}
        self.video_row = {"id": str(self.video), "title": "Song", "description": "", "state": "published",
                          "duration_seconds": 30, "rights_status": "claimed", "preview_available": False}
        self.content = self.enterContext(patch("service.workflow._content", side_effect=self.answer))

    def answer(self, operation, data):
        if operation == "inspect":
            return dict(self.snapshot)
        if operation == "detail":
            return dict(self.video_row)
        return {"applied": True}

    def call(self, op, data, actor=None, role="administrator", mfa=True):
        request = RequestFactory().post("/internal/", {"actor_id": str(actor or self.admin), "role": role,
                                                       "data": data, "mfa_verified": mfa}, content_type="application/json")
        request.service_caller = "gateway"
        return moderation_workflow(request, op)

    def verify(self, actor=None, **extra):
        return self.call("rights-holder-verify", {"account_id": str(self.claimant), "organisation": "Monrovia Records",
                                                  "evidence": EVIDENCE} | extra, actor=actor)

    def claim(self, key="copyright-notice-001", actor=None):
        return self.call("copyright_report", {
            "video_id": str(self.video), "work_reference": "Original recording, 2025",
            "details": "This upload uses our recording without a licence.", "authority_attested": True, "key": key},
            actor=actor or self.claimant, role="viewer")

    def test_only_mfa_administrators_verify_and_never_themselves(self):
        for role, mfa in (("moderator", True), ("viewer", True), ("administrator", False)):
            self.assertEqual(self.call("rights-holder-verify", {"account_id": str(self.claimant), "organisation": "Label",
                                                                "evidence": EVIDENCE}, role=role, mfa=mfa).status_code, 403)
        self.assertEqual(self.verify(actor=self.claimant).status_code, 403)
        self.assertEqual(self.verify(evidence="short").status_code, 400)
        self.assertFalse(RightsHolder.objects.exists())
        self.assertEqual(self.verify().status_code, 201)
        self.assertEqual(self.verify().status_code, 200)
        self.assertEqual(self.verify(organisation="Another label").status_code, 409)
        self.assertEqual(AuditEvent.objects.filter(kind="moderation.rights_holder_verified").count(), 1)
        with self.assertRaises(IntegrityError), transaction.atomic():
            RightsHolder.objects.create(account_id=self.other, organisation="Self", evidence=EVIDENCE, verified_by=self.other)

    def test_revoke_and_reverify_and_list(self):
        self.verify()
        revoke = {"account_id": str(self.claimant)}
        self.assertEqual(self.call("rights-holder-revoke", {"account_id": str(uuid4())}).status_code, 404)
        result = json.loads(self.call("rights-holder-revoke", revoke).content)
        self.assertFalse(result["active"])
        self.assertEqual(self.call("rights-holder-revoke", revoke).status_code, 200)
        self.assertEqual(AuditEvent.objects.filter(kind="moderation.rights_holder_revoked").count(), 1)
        self.assertEqual(self.verify(organisation="Monrovia Records Ltd").status_code, 201)
        page = json.loads(self.call("rights-holders", {"cursor": None}).content)
        self.assertEqual([(item["account_id"], item["active"]) for item in page["items"]], [(str(self.claimant), True)])
        self.assertIsNone(page["next_cursor"])

    def test_claim_records_verification_at_submission(self):
        self.verify()
        self.assertEqual(self.claim().status_code, 201)
        notice = CopyrightNotice.objects.get()
        self.assertEqual((notice.claimant_verified, notice.organisation), (True, "Monrovia Records"))
        stranger = uuid4()
        self.assertEqual(self.claim(key="copyright-notice-002", actor=stranger).status_code, 201)
        self.assertFalse(CopyrightNotice.objects.get(report__reporter_id=stranger).claimant_verified)

    def test_reviewer_sees_signals_but_not_the_claimant(self):
        self.verify()
        report = json.loads(self.claim().content)["id"]
        Report.objects.create(id=uuid4(), video_id=uuid4(), reporter_id=self.claimant, reason="copyright", status="dismissed")
        ModeratorAssignment.objects.create(moderator_id=self.reviewer, queue_scope="reports", target_id=report)
        detail = self.call("report_detail", {"target_id": report}, actor=self.reviewer, role="moderator")
        self.assertEqual(detail.status_code, 200)
        data = json.loads(detail.content)
        self.assertEqual(data["copyright"], {"work_reference": "Original recording, 2025", "claimant_verified": True,
                                             "organisation": "Monrovia Records", "claimant_claims": 2,
                                             "claimant_dismissed": 1, "creator_active_strikes": 0})
        self.assertNotIn(str(self.claimant), json.dumps(data))
        decision = {"target_id": report, "action": "remove", "reason": "Rights evidence confirms this takedown.",
                    "key": "copyright-remove-001"}
        self.assertEqual(self.call("report_decision", decision, actor=self.reviewer, role="moderator").status_code, 200)
        self.assertEqual(CopyrightStrike.objects.filter(creator_id=self.creator).count(), 1)
        data = json.loads(self.call("report_detail", {"target_id": report}, actor=self.reviewer, role="moderator").content)
        self.assertEqual(data["copyright"]["creator_active_strikes"], 1)

    def test_other_reports_carry_no_copyright_context(self):
        report = self.call("report", {"video_id": str(self.video), "reason": "spam", "details": "", "key": "spam-report-0001"},
                           actor=self.claimant, role="viewer")
        target = json.loads(report.content)["id"]
        data = json.loads(self.call("report_detail", {"target_id": target}).content)
        self.assertIsNone(data["copyright"])
        self.assertIsNone(json.loads(self.call("video_detail", {"target_id": str(self.video)}).content)["copyright"])
