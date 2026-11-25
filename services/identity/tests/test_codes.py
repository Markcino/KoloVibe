"""Six-digit email verification and password reset codes (ADR-013 amendment A-1)."""

import json
import re
import secrets
import smtplib
from datetime import timedelta
from unittest.mock import patch

from django.core import mail
from django.test import RequestFactory, TestCase, override_settings
from django.utils import timezone

from service import accounts
from service.models import (Account, CodeKind, EmailVerification, LoginSession, LoginThrottle,
                            PasswordReset, SecurityEvent)

EMAIL = "viewer@example.test"


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
                   EMAIL_HOST="smtp.example.test", DEFAULT_FROM_EMAIL="noreply@example.test")
class CodeTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.password = secrets.token_urlsafe(24)

    def post(self, view, body):
        return view(self.factory.post("/internal/auth/test", json.dumps(body),
                                      content_type="application/json"))

    def code_in(self, message):
        found = re.findall(r": ([0-9]{6})\n", message.body)
        self.assertEqual(len(found), 1)
        return found[0]

    def register(self, email=EMAIL):
        self.assertEqual(self.post(accounts.register, {
            "email": email, "password": self.password, "display_name": "Viewer"}).status_code, 201)
        return self.code_in(mail.outbox[-1])

    def verified_account(self, email=EMAIL):
        code = self.register(email)
        self.assertEqual(self.post(accounts.verify_email, {"email": email, "code": code}).status_code, 200)
        return Account.objects.get(email=email)

    def wrong(self, code):
        return "%06d" % ((int(code) + 1) % 1000000)

    def age_rows(self, model, seconds=61):
        model.objects.update(created_at=timezone.now() - timedelta(seconds=seconds))

    # ---- generation and storage --------------------------------------------------------------
    def test_code_is_six_digits_from_the_system_csprng_and_email_says_how_long(self):
        with patch("service.accounts.secrets.randbelow", return_value=42) as source:
            code = self.register()
        source.assert_called_once_with(10 ** 6)
        self.assertEqual(code, "000042")
        self.assertIn("30 minutes", mail.outbox[-1].body)
        self.assertNotIn(self.password, mail.outbox[-1].body)

    def test_codes_are_not_a_fixed_function_of_time_or_account(self):
        codes = {self.register("user%d@example.test" % i) for i in range(12)}
        self.assertGreater(len(codes), 1)
        self.assertTrue(all(re.fullmatch(r"[0-9]{6}", code) for code in codes))

    def test_only_a_keyed_verifier_is_stored_and_it_is_bound_to_account_purpose_and_issue(self):
        code = self.register()
        row = EmailVerification.objects.get()
        self.assertEqual(row.kind, CodeKind.CODE)
        self.assertEqual(len(row.digest), 64)
        self.assertNotIn(code, row.digest)
        same = accounts._code_digest("verify", row.account_id, row.issue_id, code)
        self.assertEqual(row.digest, same)
        self.assertNotEqual(row.digest, accounts._code_digest("reset", row.account_id, row.issue_id, code))
        self.assertNotEqual(row.digest, accounts._code_digest("verify", Account.objects.create_user(
            "other@example.test", self.password, "Other").id, row.issue_id, code))
        import uuid
        self.assertNotEqual(row.digest, accounts._code_digest("verify", row.account_id, uuid.uuid4(), code))
        with override_settings(SECRET_KEY="x" * 50):
            self.assertNotEqual(row.digest, accounts._code_digest("verify", row.account_id, row.issue_id, code))

    def test_codes_never_reach_logs_or_audit_events(self):
        with self.assertNoLogs(level="DEBUG"):
            code = self.register()
            self.post(accounts.verify_email, {"email": EMAIL, "code": self.wrong(code)})
            self.post(accounts.verify_email, {"email": EMAIL, "code": code})
            self.post(accounts.request_password_reset, {"email": EMAIL})
        reset = self.code_in(mail.outbox[-1])
        with patch("service.accounts.send_mail", side_effect=smtplib.SMTPException("boom " + reset)), \
                self.assertLogs("service.accounts", level="ERROR") as logs:
            self.age_rows(PasswordReset)
            self.post(accounts.request_password_reset, {"email": EMAIL})
        self.assertFalse(any(code in line or reset in line for line in logs.output))
        self.assertEqual(SecurityEvent.objects.filter(kind__contains=code).count(), 0)

    # ---- verification ---------------------------------------------------------------------
    def test_valid_code_activates_once_and_is_single_use(self):
        code = self.register()
        account = Account.objects.get()
        self.assertFalse(account.is_active)
        self.assertEqual(self.post(accounts.verify_email, {"email": EMAIL, "code": code}).status_code, 200)
        account.refresh_from_db()
        self.assertTrue(account.is_active and account.email_verified_at is not None)
        self.assertEqual(self.post(accounts.verify_email, {"email": EMAIL, "code": code}).status_code, 400)

    def test_email_verification_grants_no_session(self):
        code = self.register()
        response = self.post(accounts.verify_email, {"email": EMAIL, "code": code})
        self.assertEqual(json.loads(response.content), {"verified": True})
        self.assertFalse(LoginSession.objects.exists())

    def test_expired_code_is_rejected(self):
        code = self.register()
        EmailVerification.objects.update(expires_at=timezone.now() - timedelta(seconds=1))
        response = self.post(accounts.verify_email, {"email": EMAIL, "code": code})
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Account.objects.get().is_active)

    def test_code_expires_in_thirty_minutes(self):
        self.register()
        row = EmailVerification.objects.get()
        lifetime = row.expires_at - row.created_at
        self.assertEqual(lifetime, timedelta(minutes=accounts.VERIFY_MINUTES))
        self.assertEqual(accounts.RESET_MINUTES, 15)

    def test_fifth_wrong_guess_destroys_the_code_even_when_the_sixth_is_right(self):
        code = self.register()
        for _ in range(accounts.CODE_ATTEMPTS):
            self.assertEqual(self.post(accounts.verify_email, {
                "email": EMAIL, "code": self.wrong(code)}).status_code, 400)
        self.assertIsNotNone(EmailVerification.objects.get().used_at)
        self.assertEqual(self.post(accounts.verify_email, {"email": EMAIL, "code": code}).status_code, 400)
        self.assertFalse(Account.objects.get().is_active)
        self.age_rows(EmailVerification)
        self.assertEqual(self.post(accounts.resend_verification, {"email": EMAIL}).status_code, 204)
        fresh = self.code_in(mail.outbox[-1])
        self.assertEqual(self.post(accounts.verify_email, {"email": EMAIL, "code": fresh}).status_code, 200)

    def test_address_budget_blocks_brute_force_across_reissued_codes(self):
        self.register()
        statuses = []
        for round_ in range(4):
            if round_:
                self.age_rows(EmailVerification)
                self.post(accounts.resend_verification, {"email": EMAIL})
            row = EmailVerification.objects.filter(used_at__isnull=True).first()
            guess = "000000" if row is None else self.wrong(self.code_in(mail.outbox[-1]))
            statuses += [self.post(accounts.verify_email, {"email": EMAIL, "code": guess}).status_code
                         for _ in range(accounts.CODE_ATTEMPTS)]
        self.assertIn(429, statuses)
        self.assertLessEqual(statuses.count(400), accounts.CODE_ACCOUNT_FAILURES)
        # Even the right code is refused while the budget is spent: no oracle for the final guess.
        right = self.code_in(mail.outbox[-1])
        self.assertEqual(self.post(accounts.verify_email, {"email": EMAIL, "code": right}).status_code, 429)
        LoginThrottle.objects.update(window_started_at=timezone.now() - timedelta(hours=2))
        # After the window the account may still hold an unspent code or none; either way it is bounded.
        self.assertIn(self.post(accounts.verify_email, {"email": EMAIL, "code": right}).status_code, (200, 400))

    def test_unknown_known_and_wrong_answers_are_indistinguishable(self):
        code = self.register()
        known = self.post(accounts.verify_email, {"email": EMAIL, "code": self.wrong(code)})
        unknown = self.post(accounts.verify_email, {"email": "nobody@example.test", "code": "123456"})
        self.assertEqual((known.status_code, known.content), (unknown.status_code, unknown.content))
        for _ in range(accounts.CODE_ACCOUNT_FAILURES + 2):
            known = self.post(accounts.verify_email, {"email": EMAIL, "code": self.wrong(code)})
            unknown = self.post(accounts.verify_email, {"email": "nobody@example.test", "code": "123456"})
            self.assertEqual((known.status_code, known.content), (unknown.status_code, unknown.content))
        self.assertEqual(known.status_code, 429)

    def test_code_for_one_address_never_verifies_another(self):
        first_code = self.register("first@example.test")
        self.register("second@example.test")
        response = self.post(accounts.verify_email, {"email": "second@example.test", "code": first_code})
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Account.objects.get(email="second@example.test").is_active)
        self.assertEqual(EmailVerification.objects.get(account__email="first@example.test").attempts, 0)

    def test_reset_code_cannot_verify_email_and_verification_code_cannot_reset(self):
        account = self.verified_account()
        self.post(accounts.request_password_reset, {"email": EMAIL})
        reset = self.code_in(mail.outbox[-1])
        pending_code = self.register("pending@example.test")
        self.assertEqual(self.post(accounts.verify_email, {
            "email": "pending@example.test", "code": reset}).status_code, 400)
        new = secrets.token_urlsafe(28)
        self.assertEqual(self.post(accounts.reset_password, {
            "email": EMAIL, "code": pending_code, "new_password": new}).status_code, 400)
        self.assertEqual(self.post(accounts.reset_password, {
            "email": EMAIL, "code": reset, "new_password": new}).status_code, 204)
        account.refresh_from_db()
        self.assertTrue(account.check_password(new))

    def test_malformed_codes_and_unknown_fields_are_rejected_before_any_lookup(self):
        self.register()
        for code in ("12345", "1234567", "12345a", "١٢٣٤٥٦", " 12345", "123 456", "", None, 123456, "x" * 64):
            response = self.post(accounts.verify_email, {"email": EMAIL, "code": code})
            self.assertEqual(response.status_code, 400)
        for extra in ({"role": "administrator"}, {"is_active": True}, {"account_id": "1"}):
            self.assertEqual(self.post(accounts.verify_email, {"email": EMAIL, "code": "123456", **extra}
                                       ).status_code, 400)
        self.assertEqual(EmailVerification.objects.get().attempts, 0)
        self.assertEqual(self.post(accounts.verify_email, {"email": "not an email", "code": "123456"}
                                   ).status_code, 400)
        self.assertEqual(self.post(accounts.verify_email, {"email": EMAIL, "code": "123456",
                                                           "origin": "not-an-ip"}).status_code, 400)

    def test_trusted_origin_budget_applies_across_addresses_and_ignores_untrusted_callers(self):
        self.register()
        for index in range(accounts.CODE_ORIGIN_FAILURES):
            response = self.post(accounts.verify_email, {
                "email": "target%d@example.test" % index, "code": "123456", "origin": "203.0.113.9"})
            self.assertEqual(response.status_code, 400)
        blocked = self.post(accounts.verify_email, {
            "email": "another@example.test", "code": "123456", "origin": "203.0.113.9"})
        self.assertEqual(blocked.status_code, 429)
        other_origin = self.post(accounts.verify_email, {
            "email": "another@example.test", "code": "123456", "origin": "203.0.113.10"})
        self.assertEqual(other_origin.status_code, 400)
        no_origin = self.post(accounts.verify_email, {"email": "another@example.test", "code": "123456"})
        self.assertEqual(no_origin.status_code, 400)

    # ---- resend ----------------------------------------------------------------------------
    def test_resend_has_a_cooldown_an_hourly_cap_and_replaces_the_old_code(self):
        first = self.register()
        self.assertEqual(self.post(accounts.resend_verification, {"email": EMAIL}).status_code, 204)
        self.assertEqual(len(mail.outbox), 1)  # inside the cooldown
        self.age_rows(EmailVerification)
        self.post(accounts.resend_verification, {"email": EMAIL})
        self.assertEqual(len(mail.outbox), 2)
        second = self.code_in(mail.outbox[-1])
        self.age_rows(EmailVerification)
        self.post(accounts.resend_verification, {"email": EMAIL})
        self.assertEqual(len(mail.outbox), 3)
        self.age_rows(EmailVerification)
        self.post(accounts.resend_verification, {"email": EMAIL})
        self.assertEqual(len(mail.outbox), 3)  # a fourth within the hour is silently dropped
        self.assertEqual(self.post(accounts.verify_email, {"email": EMAIL, "code": first}).status_code, 400)
        self.assertEqual(self.post(accounts.verify_email, {"email": EMAIL, "code": second}).status_code, 400)
        third = self.code_in(mail.outbox[-1])
        self.assertEqual(self.post(accounts.verify_email, {"email": EMAIL, "code": third}).status_code, 200)

    def test_resend_and_reset_request_for_unknown_active_and_throttled_accounts_look_identical(self):
        self.register()
        self.verified_account("active@example.test")
        answers = {self.post(accounts.resend_verification, {"email": address}).content
                   for address in (EMAIL, "active@example.test", "none@example.test")}
        answers |= {self.post(accounts.request_password_reset, {"email": address}).content
                    for address in (EMAIL, "active@example.test", "none@example.test")}
        self.assertEqual(answers, {b""})

    def test_trusted_origin_cannot_mass_request_emails(self):
        self.register()
        before = len(mail.outbox)
        for _ in range(accounts.CODE_ORIGIN_SENDS + 5):
            self.age_rows(EmailVerification)
            self.assertEqual(self.post(accounts.resend_verification, {
                "email": EMAIL, "origin": "203.0.113.9"}).status_code, 204)
        self.assertLessEqual(len(mail.outbox) - before, accounts.CODE_SENDS_PER_HOUR)
        spent = {r for r in LoginThrottle.objects.values_list("failures", flat=True)}
        self.assertTrue(spent)

    # ---- D11-004: registration budget ------------------------------------------------------
    def test_registration_is_limited_per_trusted_origin_and_the_limit_does_not_depend_on_the_address(self):
        """T1_94: unbounded registration sent unbounded mail. A spent origin budget answers 429, even for a new address."""
        for index in range(accounts.CODE_ORIGIN_SENDS):
            self.assertEqual(self.post(accounts.register, {
                "email": "flood%d@example.test" % index, "password": self.password, "display_name": "Flood",
                "origin": "203.0.113.9"}).status_code, 201)
        sent = len(mail.outbox)
        refused = self.post(accounts.register, {"email": "flood-late@example.test", "password": self.password,
                                                "display_name": "Flood", "origin": "203.0.113.9"})
        self.assertEqual((refused.status_code, json.loads(refused.content)), (429, {"detail": "Too many attempts"}))
        self.assertFalse(Account.objects.filter(email="flood-late@example.test").exists())
        self.assertEqual(len(mail.outbox), sent)  # a refused request sends nothing
        other = self.post(accounts.register, {"email": "other-network@example.test", "password": self.password,
                                              "display_name": "Other", "origin": "203.0.113.10"})
        self.assertEqual(other.status_code, 201)  # one network does not lock out another

    def test_registration_attempts_for_existing_addresses_count_against_the_same_origin_budget(self):
        self.register()
        statuses = [self.post(accounts.register, {"email": EMAIL, "password": self.password, "display_name": "Probe",
                                                  "origin": "203.0.113.9"}).status_code
                    for _ in range(accounts.CODE_ORIGIN_SENDS + 3)]
        self.assertIn(429, statuses)  # probing addresses through registration is bounded, not only sending mail

    def test_registration_without_a_trusted_origin_is_unchanged_and_a_malformed_origin_is_refused(self):
        self.assertEqual(self.post(accounts.register, {"email": "a@example.test", "password": self.password,
                                                       "display_name": "Viewer"}).status_code, 201)
        self.assertEqual(self.post(accounts.register, {"email": "b@example.test", "password": self.password,
                                                       "display_name": "Viewer", "origin": "not-an-ip"}).status_code, 400)

    # ---- password reset --------------------------------------------------------------------
    def test_reset_code_flow_revokes_sessions_and_is_single_use(self):
        account = self.verified_account()
        session = json.loads(self.post(accounts.login, {"email": EMAIL, "password": self.password}).content)
        self.post(accounts.request_password_reset, {"email": EMAIL})
        code = self.code_in(mail.outbox[-1])
        self.assertIn("15 minutes", mail.outbox[-1].body)
        new = secrets.token_urlsafe(28)
        self.assertEqual(self.post(accounts.reset_password, {
            "email": EMAIL, "code": code, "new_password": new}).status_code, 204)
        self.assertEqual(self.post(accounts.validate_access, {
            "access_token": session["access_token"]}).status_code, 401)
        self.assertEqual(self.post(accounts.reset_password, {
            "email": EMAIL, "code": code, "new_password": secrets.token_urlsafe(28)}).status_code, 400)
        account.refresh_from_db()
        self.assertTrue(account.check_password(new))
        self.assertEqual(self.post(accounts.login, {"email": EMAIL, "password": new}).status_code, 200)

    def test_reset_attempts_are_limited_and_wrong_codes_do_not_change_the_password(self):
        account = self.verified_account()
        self.post(accounts.request_password_reset, {"email": EMAIL})
        code = self.code_in(mail.outbox[-1])
        attacker_password = secrets.token_urlsafe(28)
        for _ in range(accounts.CODE_ATTEMPTS):
            self.assertEqual(self.post(accounts.reset_password, {
                "email": EMAIL, "code": self.wrong(code), "new_password": attacker_password}).status_code, 400)
        self.assertEqual(self.post(accounts.reset_password, {
            "email": EMAIL, "code": code, "new_password": attacker_password}).status_code, 400)
        account.refresh_from_db()
        self.assertTrue(account.check_password(self.password))
        self.assertFalse(account.check_password(attacker_password))
        self.assertTrue(PasswordReset.objects.get().used_at is not None)

    def test_weak_new_password_does_not_burn_a_correct_code(self):
        self.verified_account()
        self.post(accounts.request_password_reset, {"email": EMAIL})
        code = self.code_in(mail.outbox[-1])
        weak = "x" * 5
        self.assertEqual(self.post(accounts.reset_password, {
            "email": EMAIL, "code": code, "new_password": weak}).status_code, 400)
        row = PasswordReset.objects.get()
        self.assertIsNone(row.used_at)
        self.assertEqual(row.attempts, 0)
        self.assertEqual(self.post(accounts.reset_password, {
            "email": EMAIL, "code": code, "new_password": secrets.token_urlsafe(28)}).status_code, 204)

    def test_expired_reset_code_and_unknown_or_privileged_accounts_cannot_reset(self):
        self.verified_account()
        self.post(accounts.request_password_reset, {"email": EMAIL})
        code = self.code_in(mail.outbox[-1])
        PasswordReset.objects.update(expires_at=timezone.now() - timedelta(seconds=1))
        new = secrets.token_urlsafe(28)
        self.assertEqual(self.post(accounts.reset_password, {
            "email": EMAIL, "code": code, "new_password": new}).status_code, 400)
        admin = Account.objects.create_user("admin@example.test", self.password, "Admin")
        Account.objects.filter(pk=admin.pk).update(role=Account.Role.ADMINISTRATOR, email_verified_at=timezone.now())
        self.assertEqual(self.post(accounts.request_password_reset, {"email": admin.email}).status_code, 204)
        self.assertFalse(PasswordReset.objects.filter(account=admin).exists())
        self.assertEqual(self.post(accounts.reset_password, {
            "email": admin.email, "code": "123456", "new_password": new}).status_code, 400)

    def test_reset_request_cooldown_and_hourly_cap(self):
        self.verified_account()
        sent = []
        for _ in range(6):
            self.post(accounts.request_password_reset, {"email": EMAIL})
            sent.append(len(mail.outbox))
            self.age_rows(PasswordReset)
        self.assertEqual(sent, [2, 3, 4, 4, 4, 4])  # one registration email precedes the resets
        self.assertEqual(PasswordReset.objects.count(), accounts.CODE_SENDS_PER_HOUR)

    # ---- migration window ------------------------------------------------------------------
    def make_legacy(self, model, account, expires):
        raw = secrets.token_urlsafe(48)
        model.objects.create(digest=accounts._digest(raw), account=account, expires_at=expires,
                             kind=CodeKind.TOKEN)
        return raw

    def pending(self):
        account = Account.objects.create_user("legacy@example.test", self.password, "Legacy")
        Account.objects.filter(pk=account.pk).update(is_active=False)
        return Account.objects.get(pk=account.pk)

    @override_settings(KOLOVIBE_ACCEPT_LEGACY_LONG_CODES=True)
    def test_pending_long_links_still_verify_and_reset_until_they_expire(self):
        account = self.pending()
        token = self.make_legacy(EmailVerification, account, timezone.now() + timedelta(hours=1))
        self.assertEqual(self.post(accounts.verify_email, {"code": token}).status_code, 200)
        self.assertEqual(self.post(accounts.verify_email, {"code": token}).status_code, 400)
        account.refresh_from_db()
        self.assertTrue(account.is_active)
        reset = self.make_legacy(PasswordReset, account, timezone.now() + timedelta(minutes=5))
        new = secrets.token_urlsafe(28)
        self.assertEqual(self.post(accounts.reset_password, {"code": reset, "new_password": new}).status_code, 204)
        self.assertEqual(self.post(accounts.reset_password, {"code": reset, "new_password": new}).status_code, 400)
        expired = self.make_legacy(PasswordReset, account, timezone.now() - timedelta(seconds=1))
        self.assertEqual(self.post(accounts.reset_password, {"code": expired, "new_password": new}).status_code, 400)

    @override_settings(KOLOVIBE_ACCEPT_LEGACY_LONG_CODES=False)
    def test_legacy_links_are_refused_once_the_window_is_closed(self):
        account = self.pending()
        token = self.make_legacy(EmailVerification, account, timezone.now() + timedelta(hours=1))
        self.assertEqual(self.post(accounts.verify_email, {"code": token}).status_code, 400)
        reset = self.make_legacy(PasswordReset, account, timezone.now() + timedelta(minutes=5))
        self.assertEqual(self.post(accounts.reset_password, {
            "code": reset, "new_password": secrets.token_urlsafe(28)}).status_code, 400)
        self.assertFalse(Account.objects.get(pk=account.pk).is_active)

    @override_settings(KOLOVIBE_ACCEPT_LEGACY_LONG_CODES=True)
    def test_legacy_path_cannot_consume_new_codes_and_new_path_cannot_consume_legacy_tokens(self):
        code = self.register()
        row = EmailVerification.objects.get()
        # The stored verifier of a six-digit row is not a usable long token.
        self.assertEqual(self.post(accounts.verify_email, {"code": row.digest}).status_code, 400)
        self.assertFalse(Account.objects.get().is_active)
        account = self.pending()
        token = self.make_legacy(EmailVerification, account, timezone.now() + timedelta(hours=1))
        self.assertEqual(self.post(accounts.verify_email, {"email": account.email, "code": token[:6]}
                                   ).status_code, 400)
        self.assertEqual(self.post(accounts.verify_email, {"email": EMAIL, "code": code}).status_code, 200)

    @override_settings(KOLOVIBE_ACCEPT_LEGACY_LONG_CODES=True)
    def test_issuing_a_code_retires_any_pending_long_link(self):
        code = self.register()
        account = Account.objects.get()
        token = self.make_legacy(EmailVerification, account, timezone.now() + timedelta(hours=1))
        self.age_rows(EmailVerification)
        self.post(accounts.resend_verification, {"email": EMAIL})
        self.assertEqual(self.post(accounts.verify_email, {"code": token}).status_code, 400)
        self.assertEqual(self.post(accounts.verify_email, {"email": EMAIL, "code": code}).status_code, 400)
        fresh = self.code_in(mail.outbox[-1])
        self.assertEqual(self.post(accounts.verify_email, {"email": EMAIL, "code": fresh}).status_code, 200)
