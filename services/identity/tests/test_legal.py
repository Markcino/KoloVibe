"""Decision B: versioned legal documents, mandatory acceptance at registration, re-acceptance and marketing consent."""
import hashlib
import json
import secrets
from dataclasses import replace
from datetime import timedelta
from unittest.mock import patch

from django.core import mail
from django.db import IntegrityError, transaction
from django.test import RequestFactory, TestCase, override_settings
from django.utils import timezone

from service import accounts, legal
from service.models import Account, LegalAcceptance, LoginSession, MarketingConsentEvent, SecurityEvent

CURRENT = {kind: legal.DOCUMENTS[kind].version for kind in legal.REQUIRED}


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
                   EMAIL_HOST="smtp.example.test", DEFAULT_FROM_EMAIL="noreply@example.test")
class LegalTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.password = secrets.token_urlsafe(24)

    def post(self, view, body):
        return view(self.factory.post("/internal/auth/test", json.dumps(body), content_type="application/json"))

    def register(self, email="new@example.test", **extra):
        body = {"email": email, "password": self.password, "display_name": "New", "accepted": CURRENT, **extra}
        return self.post(accounts.register, body)

    def signed_in(self, account=None):
        account = account or Account.objects.create_user("signed@example.test", self.password, "Signed")
        session = LoginSession.objects.create(account=account, refresh_digest=secrets.token_hex(32),
                                              expires_at=timezone.now() + timedelta(days=1))
        return account, accounts._issue(session)["access_token"]

    def manage(self, token, **body):
        return self.post(legal.manage, {"access_token": token, **body})

    # documents
    def test_every_document_is_versioned_dated_digested_and_marked_pending_legal_review(self):
        for kind, document in legal.DOCUMENTS.items():
            with self.subTest(kind):
                raw = (legal.TEXTS / document.file).read_bytes()
                self.assertEqual(hashlib.sha256(raw).hexdigest(), document.sha256)
                self.assertEqual(document.file, f"{kind}-{document.version}.md")
                self.assertEqual(document.status, legal.PENDING)
                self.assertRegex(document.version, r"^\d{4}-\d{2}-\d{2}$")
                self.assertRegex(document.effective_at, r"^\d{4}-\d{2}-\d{2}$")
                self.assertIn("PENDING LEGAL REVIEW", raw.decode())
        self.assertEqual(set(legal.REQUIRED), {"terms", "privacy"})
        self.assertFalse(legal.DOCUMENTS["marketing"].required)

    def test_a_misnamed_file_or_an_unknown_status_stops_the_service(self):
        terms = legal.DOCUMENTS["terms"]
        for broken in (replace(terms, file="terms-draft.md"), replace(terms, status="final")):
            with self.subTest(broken.file + broken.status), self.assertRaises(Exception):
                legal._load([broken])

    def test_a_text_edited_under_the_same_version_must_be_accepted_again(self):
        self.assertEqual(self.register().status_code, 201)
        account = Account.objects.get(email="new@example.test")
        self.assertFalse(legal.state(account.id)["acceptance_required"])
        edited = {**legal.DOCUMENTS, "privacy": replace(legal.DOCUMENTS["privacy"], sha256="e" * 64)}
        with patch.object(legal, "DOCUMENTS", edited):
            self.assertTrue(legal.state(account.id)["acceptance_required"])

    def test_the_current_text_is_readable_without_an_account(self):
        for kind in legal.DOCUMENTS:
            response = self.post(legal.document, {"kind": kind})
            self.assertEqual(response.status_code, 200)
            body = json.loads(response.content)
            self.assertEqual(set(body), {"kind", "title", "version", "effective_at", "status", "sha256", "text"})
            self.assertEqual(body["status"], "pending_legal_review")
            self.assertEqual(hashlib.sha256(body["text"].encode()).hexdigest(), body["sha256"])
        for bad in ({"kind": "cookies"}, {"kind": "terms", "version": "x"}, {}):
            self.assertEqual(self.post(legal.document, bad).status_code, 404)

    # registration
    def test_registration_records_the_exact_versions_and_digests_accepted(self):
        self.assertEqual(self.register().status_code, 201)
        account = Account.objects.get(email="new@example.test")
        rows = {row.document: row for row in LegalAcceptance.objects.filter(account=account)}
        self.assertEqual(set(rows), {"terms", "privacy"})
        for kind, row in rows.items():
            self.assertEqual((row.version, row.sha256, row.context),
                             (legal.DOCUMENTS[kind].version, legal.DOCUMENTS[kind].sha256, "registration"))
        self.assertFalse(MarketingConsentEvent.objects.filter(account=account).exists(),
                         "accepting the terms and the privacy notice is never marketing consent")
        self.assertIn("account.legal_accepted", SecurityEvent.objects.values_list("kind", flat=True))

    def test_registration_without_or_with_partial_or_malformed_acceptance_creates_nothing(self):
        for accepted in (None, {}, {"terms": CURRENT["terms"]}, {**CURRENT, "marketing": "2026-11-25"},
                         {"terms": 1, "privacy": CURRENT["privacy"]}, ["terms", "privacy"], {**CURRENT, "terms": ""}):
            with self.subTest(accepted):
                body = {"email": "x@example.test", "password": self.password, "display_name": "X"}
                if accepted is not None:
                    body["accepted"] = accepted
                self.assertEqual(self.post(accounts.register, body).status_code, 400)
        self.assertFalse(Account.objects.exists())
        self.assertEqual(len(mail.outbox), 0)

    def test_an_outdated_version_is_refused_with_a_code_and_sends_nothing(self):
        response = self.register(accepted={**CURRENT, "privacy": "2020-01-01"})
        self.assertEqual(response.status_code, 409)
        self.assertEqual(json.loads(response.content)["code"], "legal_version_outdated")
        self.assertFalse(Account.objects.exists())
        self.assertEqual(len(mail.outbox), 0)

    def test_marketing_consent_at_registration_is_optional_strict_and_recorded_separately(self):
        self.assertEqual(self.register("a@example.test", marketing_consent=True).status_code, 201)
        row = MarketingConsentEvent.objects.get(account__email="a@example.test")
        self.assertEqual((row.granted, row.version), (True, legal.DOCUMENTS["marketing"].version))
        self.assertEqual(self.register("b@example.test", marketing_consent=False).status_code, 201)
        self.assertFalse(MarketingConsentEvent.objects.filter(account__email="b@example.test").exists())
        self.assertEqual(self.register("c@example.test", marketing_consent="yes").status_code, 400)

    def test_registering_a_taken_address_records_nothing_for_the_existing_account(self):
        self.assertEqual(self.register().status_code, 201)
        before = LegalAcceptance.objects.count()
        self.assertEqual(self.register(marketing_consent=True).status_code, 201)
        self.assertEqual(LegalAcceptance.objects.count(), before)
        self.assertFalse(MarketingConsentEvent.objects.exists())

    # signed in
    def test_state_reports_acceptance_and_marketing_off_by_default(self):
        account, token = self.signed_in()
        state = json.loads(self.manage(token, operation="get").content)
        self.assertTrue(state["acceptance_required"])
        self.assertEqual([d["kind"] for d in state["documents"]], ["terms", "privacy"])
        self.assertTrue(all(d["accepted_version"] is None and d["status"] == "pending_legal_review"
                            for d in state["documents"]))
        self.assertEqual(state["marketing"], {"granted": False, "version": legal.DOCUMENTS["marketing"].version,
                                              "updated_at": None})

    def test_accepting_current_versions_is_recorded_once_and_clears_the_requirement(self):
        account, token = self.signed_in()
        state = json.loads(self.manage(token, operation="accept", accepted=CURRENT).content)
        self.assertFalse(state["acceptance_required"])
        self.manage(token, operation="accept", accepted=CURRENT)
        self.assertEqual(LegalAcceptance.objects.filter(account=account, context="update").count(), 2)

    def test_a_new_version_requires_acceptance_again_and_keeps_the_history(self):
        self.assertEqual(self.register().status_code, 201)
        account = Account.objects.get(email="new@example.test")
        newer = {**legal.DOCUMENTS, "terms": replace(legal.DOCUMENTS["terms"], version="2027-01-01")}
        with patch.object(legal, "DOCUMENTS", newer):
            state = legal.state(account.id)
            self.assertTrue(state["acceptance_required"])
            self.assertEqual(state["documents"][0]["accepted_version"], CURRENT["terms"])
            account.is_active = True
            account.save(update_fields=["is_active"])
            _, token = self.signed_in(account)
            stale = self.manage(token, operation="accept", accepted={"terms": CURRENT["terms"]})
            self.assertEqual(json.loads(stale.content)["code"], "legal_version_outdated")
            fresh = json.loads(self.manage(token, operation="accept", accepted={"terms": "2027-01-01"}).content)
            self.assertFalse(fresh["acceptance_required"])
        versions = list(LegalAcceptance.objects.filter(account=account, document="terms")
                        .order_by("accepted_at").values_list("version", flat=True))
        self.assertEqual(versions, [CURRENT["terms"], "2027-01-01"])

    def test_marketing_consent_can_be_granted_and_withdrawn_and_only_changes_are_recorded(self):
        account, token = self.signed_in()
        version = legal.DOCUMENTS["marketing"].version
        self.assertTrue(json.loads(self.manage(token, operation="marketing", granted=True, version=version).content)
                        ["marketing"]["granted"])
        self.manage(token, operation="marketing", granted=True, version=version)
        self.assertFalse(json.loads(self.manage(token, operation="marketing", granted=False, version=version).content)
                         ["marketing"]["granted"])
        self.assertEqual(list(MarketingConsentEvent.objects.filter(account=account).order_by("recorded_at")
                              .values_list("granted", flat=True)), [True, False])
        self.assertEqual(self.manage(token, operation="marketing", granted=True, version="1999-01-01").status_code, 409)

    def test_requests_are_strict_and_need_a_session(self):
        account, token = self.signed_in()
        for body in ({"operation": "delete"}, {"operation": "get", "accepted": CURRENT},
                     {"operation": "accept", "accepted": {}}, {"operation": "accept", "accepted": {"marketing": "x"}},
                     {"operation": "accept", "accepted": {"terms": 5}},
                     {"operation": "marketing", "granted": "true", "version": "2026-11-25"},
                     {"operation": "marketing", "granted": True}):
            with self.subTest(body):
                self.assertEqual(self.manage(token, **body).status_code, 400)
        self.assertEqual(self.manage("nope" * 10, operation="get").status_code, 401)

    def test_acceptance_and_consent_rows_are_append_only(self):
        account, token = self.signed_in()
        self.manage(token, operation="accept", accepted=CURRENT)
        self.manage(token, operation="marketing", granted=True, version=legal.DOCUMENTS["marketing"].version)
        for model in (LegalAcceptance, MarketingConsentEvent):
            with self.subTest(model.__name__):
                for change in (lambda: model.objects.update(version="x"), lambda: model.objects.all().delete()):
                    with self.assertRaises(IntegrityError), transaction.atomic():
                        change()
