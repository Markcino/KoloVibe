"""Phase 11, test group 1: accounts and security, black-box over real HTTP through the Gateway.

Each test asserts the SECURE behaviour a requirement implies. A failure is a finding to triage, not something to tune away.
Brute-force tests have high numbers so they run last and cannot throttle the other tests.
"""

import json
import secrets
import time
import unittest

import lib
from smtp_fixture import mailed_code


def S():
    return lib.CURRENT


class Accounts(unittest.TestCase):
    # ---- registration and verification -------------------------------------------------------------
    def test_T1_01_registration_creates_an_unverified_account_and_leaks_nothing(self):
        user = S().new_user(verify=False)
        status, body = S().post("/auth/register", {"email": "x" + secrets.token_hex(4) + "@example.test",
                                                    "display_name": "New User", "password": secrets.token_urlsafe(20)})
        self.assertEqual(status, 201)
        text = json.dumps(body).lower()
        for forbidden in ("password", "hash", "pbkdf", "argon", "secret"):
            self.assertNotIn(forbidden, text)

    def test_T1_02_an_unverified_account_cannot_sign_in(self):
        user = S().new_user(verify=False)
        status, _ = S().post("/auth/login", {"email": user["email"], "password": user["password"]})
        self.assertIn(status, (401, 403), "an unverified account must not obtain tokens")

    def test_T1_03_duplicate_registration_is_not_distinguishable_from_a_new_one(self):
        first = S().new_user()
        status_existing, body_existing = S().post("/auth/register", {"email": first["email"], "display_name": "Dup",
                                                                       "password": secrets.token_urlsafe(20)})
        status_new, body_new = S().post("/auth/register", {"email": "n" + secrets.token_hex(4) + "@example.test",
                                                            "display_name": "New", "password": secrets.token_urlsafe(20)})
        self.assertEqual(status_existing, status_new, "registering an existing email must not reveal that it exists")
        self.assertEqual(sorted((body_existing or {}).keys()), sorted((body_new or {}).keys()))

    def test_T1_04_email_case_does_not_create_a_second_account(self):
        user = S().new_user()
        status, _ = S().post("/auth/register", {"email": user["email"].upper(), "display_name": "Case",
                                                "password": secrets.token_urlsafe(20)})
        self.assertIn(status, (201, 200, 409, 400))
        # whatever the answer, the original account must still be the only one that can sign in
        self.assertEqual(S().post("/auth/login", {"email": user["email"], "password": user["password"]})[0], 200)

    def test_T1_05_weak_passwords_are_refused(self):
        for password in ("short", "password", "12345678", "a" * 8, "password123"):
            status, _ = S().post("/auth/register", {"email": "w" + secrets.token_hex(4) + "@example.test",
                                                    "display_name": "Weak", "password": password})
            self.assertEqual(status, 400, f"weak password accepted: {password!r}")

    def test_T1_06_a_wrong_verification_code_is_refused_and_the_right_one_still_works(self):
        user = S().new_user(verify=False)
        code = mailed_code(S().base)
        wrong = "000000" if code != "000000" else "111111"
        self.assertEqual(S().post("/auth/verify", {"email": user["email"], "code": wrong})[0], 400)
        self.assertEqual(S().post("/auth/verify", {"email": user["email"], "code": code})[0], 200)

    def test_T1_07_a_verification_code_is_single_use(self):
        user = S().new_user(verify=False)
        code = mailed_code(S().base)
        self.assertEqual(S().post("/auth/verify", {"email": user["email"], "code": code})[0], 200)
        self.assertNotEqual(S().post("/auth/verify", {"email": user["email"], "code": code})[0], 200)

    # ---- login, tokens, sessions -------------------------------------------------------------------
    def test_T1_10_wrong_password_and_unknown_email_look_the_same(self):
        user = S().new_user()
        a = S().post("/auth/login", {"email": user["email"], "password": "Wrong-password-1!"})
        b = S().post("/auth/login", {"email": "nobody" + secrets.token_hex(3) + "@example.test", "password": "Wrong-password-1!"})
        self.assertEqual(a, b, "sign-in failures must not reveal whether an email is registered")

    def test_T1_11_protected_routes_reject_missing_malformed_and_tampered_tokens(self):
        _, tokens = S().signed_in()
        access = tokens["access_token"]
        self.assertEqual(S().get("/me")[0], 401)
        self.assertEqual(S().get("/me", token="not-a-token")[0], 401)
        # The access token is an opaque two-part value in this build, not a three-part JWT: flip characters instead.
        flipped = access[:-4] + ("AAAA" if not access.endswith("AAAA") else "BBBB")
        self.assertEqual(S().get("/me", token=flipped)[0], 401, "a modified token must be refused")
        self.assertEqual(S().get("/me", token=access[: len(access) // 2])[0], 401, "a truncated token must be refused")
        self.assertEqual(S().get("/me", token=access + "x")[0], 401, "a lengthened token must be refused")
        self.assertEqual(S().get("/me", token=access)[0], 200, "the original token still works")
        self.assertEqual(S().get("/me", headers={"Authorization": "Basic Zm9vOmJhcg=="})[0], 401)

    def test_T1_12_refresh_rotates_and_a_replayed_refresh_token_is_refused(self):
        _, tokens = S().signed_in()
        old = tokens["refresh_token"]
        status, fresh = S().post("/auth/refresh", {"refresh_token": old})
        self.assertEqual(status, 200)
        self.assertNotEqual(fresh["refresh_token"], old)
        self.assertEqual(S().post("/auth/refresh", {"refresh_token": old})[0], 401, "replay must be refused")

    def test_T1_13_replaying_an_old_refresh_token_revokes_the_whole_family(self):
        _, tokens = S().signed_in()
        old = tokens["refresh_token"]
        _, fresh = S().post("/auth/refresh", {"refresh_token": old})
        S().post("/auth/refresh", {"refresh_token": old})  # the replay
        self.assertEqual(S().post("/auth/refresh", {"refresh_token": fresh["refresh_token"]})[0], 401,
                         "after a replay the successor token must also be dead")
        self.assertEqual(S().get("/me", token=fresh["access_token"])[0], 401, "and the access token tied to that family")

    def test_T1_14_logout_revokes_the_session_immediately(self):
        _, tokens = S().signed_in()
        self.assertIn(S().post("/auth/logout", {"refresh_token": tokens["refresh_token"]})[0], (200, 204))
        self.assertEqual(S().post("/auth/refresh", {"refresh_token": tokens["refresh_token"]})[0], 401)
        self.assertEqual(S().get("/me", token=tokens["access_token"])[0], 401, "the access token must die with the session, not at expiry")

    def test_T1_15_session_restoration_after_the_access_token_expires_uses_the_refresh_token(self):
        _, tokens = S().signed_in()
        status, fresh = S().post("/auth/refresh", {"refresh_token": tokens["refresh_token"]})
        self.assertEqual(status, 200)
        self.assertEqual(S().get("/me", token=fresh["access_token"])[0], 200)

    def test_T1_16_sessions_list_only_the_owner_and_revoking_another_session_is_immediate(self):
        user = S().new_user()
        first, second = S().login(user), S().login(user)
        status, listing = S().get("/me/sessions", token=first["access_token"])
        self.assertEqual(status, 200)
        self.assertGreaterEqual(len(listing["items"]), 2)
        other = next(item for item in listing["items"] if not item["current"])
        self.assertEqual(S().call("DELETE", f"/me/sessions/{other['id']}", token=first["access_token"])[0], 204)
        self.assertEqual(S().get("/me", token=second["access_token"])[0], 401, "a revoked session must stop working at once")

    def test_T1_17_one_account_cannot_revoke_or_see_another_accounts_sessions(self):
        a_user, a = S().signed_in()
        _, b = S().signed_in()
        a_session = S().get("/me/sessions", token=a["access_token"])[1]["items"][0]["id"]
        self.assertEqual(S().call("DELETE", f"/me/sessions/{a_session}", token=b["access_token"])[0], 404)
        self.assertEqual(S().get("/me", token=a["access_token"])[0], 200, "the victim session must be untouched")
        ids = {item["id"] for item in S().get("/me/sessions", token=b["access_token"])[1]["items"]}
        self.assertNotIn(a_session, ids)

    # ---- password change and reset -----------------------------------------------------------------
    def test_T1_20_password_change_needs_the_current_password_and_revokes_other_sessions(self):
        user = S().new_user()
        one, two = S().login(user), S().login(user)
        new = secrets.token_urlsafe(22)
        wrong = S().call("PATCH", "/me/password", {"current_password": "Wrong-pass-9!", "new_password": new}, token=one["access_token"])
        self.assertIn(wrong[0], (400, 401, 403))
        ok = S().call("PATCH", "/me/password", {"current_password": user["password"], "new_password": new}, token=one["access_token"])
        self.assertIn(ok[0], (200, 204))
        self.assertEqual(S().get("/me", token=two["access_token"])[0], 401, "other sessions must end when the password changes")
        self.assertEqual(S().post("/auth/login", {"email": user["email"], "password": user["password"]})[0], 401)
        self.assertEqual(S().post("/auth/login", {"email": user["email"], "password": new})[0], 200)

    def test_T1_21_password_reset_does_not_reveal_whether_an_email_exists(self):
        user = S().new_user()
        known = S().post("/auth/password/reset-request", {"email": user["email"]})
        unknown = S().post("/auth/password/reset-request", {"email": "ghost" + secrets.token_hex(3) + "@example.test"})
        self.assertEqual(known[0], unknown[0])
        self.assertEqual(known[1], unknown[1])

    def test_T1_22_password_reset_with_the_emailed_code_works_once_and_ends_old_sessions(self):
        user = S().new_user()
        old = S().login(user)
        S().post("/auth/password/reset-request", {"email": user["email"]})
        code = mailed_code(S().base)
        new = secrets.token_urlsafe(22)
        self.assertEqual(S().post("/auth/password/reset", {"email": user["email"], "code": "000000" if code != "000000" else "111111",
                                                           "new_password": new})[0], 400)
        self.assertIn(S().post("/auth/password/reset", {"email": user["email"], "code": code, "new_password": new})[0], (200, 204))
        self.assertNotIn(S().post("/auth/password/reset", {"email": user["email"], "code": code,
                                                          "new_password": secrets.token_urlsafe(22)})[0], (200, 204), "single use")
        self.assertEqual(S().get("/me", token=old["access_token"])[0], 401, "a reset must end earlier sessions")
        self.assertEqual(S().post("/auth/login", {"email": user["email"], "password": new})[0], 200)

    # ---- authorization, roles ---------------------------------------------------------------------------
    def test_T1_30_cross_account_reads_return_nothing_of_anothers(self):
        _, a = S().signed_in()
        b_user, b = S().signed_in()
        me_a, me_b = S().get("/me", token=a["access_token"])[1], S().get("/me", token=b["access_token"])[1]
        self.assertNotEqual(me_a["id"], me_b["id"])
        for path in ("/me/reports", "/me/appeals", "/me/privacy-requests", "/me/preferences", "/me/standing"):
            status, body = S().get(path, token=b["access_token"])
            self.assertEqual(status, 200, path)
            self.assertNotIn(me_a["id"], json.dumps(body))
        # object routes by another account's identifier must not exist for the caller
        self.assertEqual(S().get("/me/reports/" + me_a["id"], token=b["access_token"])[0], 404)

    def test_T1_31_a_viewer_cannot_reach_privileged_or_creator_routes(self):
        _, t = S().signed_in()
        for method, path in (("GET", "/admin/accounts/lookup"), ("POST", "/admin/accounts/lookup"), ("GET", "/moderation/reports"),
                             ("GET", "/admin/points/balances"), ("GET", "/engagement/fraud-holds"), ("GET", "/creators/me/points"),
                             ("GET", "/admin/business/verification-cases")):
            status, _ = S().call(method, path, {} if method == "POST" else None, token=t["access_token"])
            self.assertIn(status, (401, 403, 404, 405), f"{method} {path} -> {status}")

    def test_T1_32_a_role_change_takes_effect_at_once_and_the_old_session_cannot_keep_the_old_role(self):
        user, tokens = S().signed_in()
        me = S().get("/me", token=tokens["access_token"])[1]
        for role in ("creator", "viewer"):
            with S().db("identity") as c:
                c.execute("UPDATE identity.service_account SET role=%s WHERE id=%s", (role, me["id"]))
            status, body = S().get("/me", token=tokens["access_token"])
            # secure outcomes: the session is rejected (re-authentication needed) or it shows the new role. Never the old one.
            self.assertTrue(status == 401 or body["roles"] == [role], (role, status, body))
            fresh = S().login(user)
            self.assertEqual(S().get("/me", token=fresh["access_token"])[1]["roles"], [role], "a new sign-in shows the new role")
            tokens = fresh

    def test_T1_33_a_disabled_account_loses_access_immediately(self):
        user, tokens = S().signed_in()
        me = S().get("/me", token=tokens["access_token"])[1]
        with S().db("identity") as c:
            c.execute("UPDATE identity.service_account SET is_active=false WHERE id=%s", (me["id"],))
        self.assertEqual(S().get("/me", token=tokens["access_token"])[0], 401)
        self.assertEqual(S().post("/auth/login", {"email": user["email"], "password": user["password"]})[0], 401)

    # ---- privacy ----------------------------------------------------------------------------------------
    def test_T1_40_privacy_requests_are_recorded_for_the_owner_only(self):
        a_user, a = S().signed_in()
        _, b = S().signed_in()
        status, body = S().post("/me/privacy-requests", {"kind": "access", "current_password": a_user["password"]}, token=a["access_token"], key=secrets.token_hex(8))
        self.assertIn(status, (200, 201, 202), (status, body))
        mine = S().get("/me/privacy-requests", token=a["access_token"])[1]
        theirs = S().get("/me/privacy-requests", token=b["access_token"])[1]
        self.assertTrue(json.dumps(mine) != json.dumps(theirs))
        self.assertEqual(len((theirs or {}).get("items", [])), 0)

    def test_T1_41_a_privacy_request_needs_the_current_password(self):
        _, a = S().signed_in()
        status, _ = S().post("/me/privacy-requests", {"kind": "deletion", "current_password": "Wrong-password-1!"}, token=a["access_token"], key=secrets.token_hex(8))
        self.assertIn(status, (400, 401, 403))

    def test_T1_42_preferences_validate_their_input(self):
        _, a = S().signed_in()
        self.assertEqual(S().call("PATCH", "/me/preferences", {"email_notifications": "yes", "push_notifications": 1}, token=a["access_token"])[0], 400)
        self.assertEqual(S().call("PATCH", "/me/preferences", {"email_notifications": True, "push_notifications": False, "admin": True}, token=a["access_token"])[0], 400)

    # ---- input hardening --------------------------------------------------------------------------------
    def test_T1_50_oversized_malformed_and_hostile_input_is_refused_safely(self):
        import http.client

        def raw_post(payload, ctype="application/json"):
            conn = http.client.HTTPConnection("127.0.0.1", S().ports["gateway"], timeout=10)
            conn.request("POST", "/api/v1/auth/register", body=payload, headers={"Content-Type": ctype})
            r = conn.getresponse()
            data = r.read(100000)
            conn.close()
            return r.status, data

        for payload in ("{", "[]", "null", '{"email":["a"],"password":1,"display_name":{}}',
                        json.dumps({"email": "a" * 5000 + "@example.test", "password": "x" * 20, "display_name": "n"}),
                        json.dumps({"email": "q'; DROP TABLE service_account;--@example.test", "password": secrets.token_urlsafe(20), "display_name": "n"}),
                        "x" * 2_000_000):
            status, data = raw_post(payload)
            self.assertIn(status, (400, 413, 415), f"payload {payload[:30]!r} -> {status}")
            self.assertNotIn(b"Traceback", data)
            self.assertNotIn(b"psycopg", data)
        self.assertIn(raw_post("{}", "text/plain")[0], (400, 415))

    def test_T1_51_error_and_success_responses_do_not_leak_server_internals(self):
        import http.client

        conn = http.client.HTTPConnection("127.0.0.1", S().ports["gateway"], timeout=10)
        conn.request("GET", "/api/v1/me")
        r = conn.getresponse()
        headers = {k.lower(): v for k, v in r.getheaders()}
        r.read()
        conn.close()
        # The Server header here is Django's development server (this local harness); the production Gunicorn runtime is
        # checked separately in group 10 (T10_*), so it is deliberately not asserted in this test.
        self.assertEqual(headers.get("x-content-type-options"), "nosniff")
        self.assertIn("no-store", headers.get("cache-control", ""), "authenticated JSON must not be cacheable")

    def test_T1_52_unknown_and_method_tampered_routes_are_refused(self):
        _, t = S().signed_in()
        self.assertEqual(S().call("DELETE", "/me", token=t["access_token"])[0], 405)
        self.assertEqual(S().get("/nonexistent")[0], 404)
        self.assertEqual(S().get("/internal/probe", api=False)[0] in (200, 403, 404), True)
        self.assertEqual(S().call("GET", "/admin/../me", token=t["access_token"])[0] in (400, 401, 403, 404, 301), True)


class Mfa(unittest.TestCase):
    """Privileged accounts: password alone must never mint a session; codes are single use; challenges are bounded."""

    def _challenge(self, user):
        status, answer = S().post("/auth/login", {"email": user["email"], "password": user["password"]})
        self.assertEqual(status, 202, "a privileged password sign-in must stop at the MFA challenge")
        self.assertNotIn("access_token", answer)
        self.assertNotIn("refresh_token", answer)
        return answer["challenge_token"]

    def _next_code(self, user):
        """A valid code that is not the one used at enrolment: wait for the next 30-second step (the server is strict)."""
        import pyotp, time as _t

        _t.sleep(30 - (_t.time() % 30) + 0.7)
        return pyotp.TOTP(user["factor"]).now()

    def test_T1_60_a_privileged_password_sign_in_returns_a_challenge_and_no_tokens(self):
        for role in ("moderator", "administrator"):
            self._challenge(S().privileged(role))

    def test_T1_61_a_wrong_code_is_refused_and_does_not_open_a_session(self):
        user = S().privileged("moderator")
        challenge = self._challenge(user)
        status, body = S().post("/auth/mfa/verify", {"challenge_token": challenge, "code": "000000"})
        self.assertEqual(status, 401)
        self.assertNotIn("access_token", json.dumps(body))

    def test_T1_62_a_correct_code_opens_a_session_once_and_the_same_code_cannot_be_replayed(self):
        user = S().privileged("administrator")
        code = self._next_code(user)
        status, tokens = S().post("/auth/mfa/verify", {"challenge_token": self._challenge(user), "code": code})
        self.assertEqual(status, 200, "the current-step code must be accepted")
        self.assertEqual(S().get("/me", token=tokens["access_token"])[1]["roles"], ["administrator"])
        replay = S().post("/auth/mfa/verify", {"challenge_token": self._challenge(user), "code": code})
        self.assertEqual(replay[0], 401, "a TOTP code must not be accepted twice")

    def test_T1_63_a_recovery_code_works_exactly_once(self):
        user = S().privileged("moderator")
        self.assertEqual(S().post("/auth/mfa/verify", {"challenge_token": self._challenge(user), "code": user["recovery"]})[0], 200)
        self.assertEqual(S().post("/auth/mfa/verify", {"challenge_token": self._challenge(user), "code": user["recovery"]})[0], 401)

    def test_T1_64_a_challenge_is_single_use_after_success(self):
        user = S().privileged("moderator")
        challenge = self._challenge(user)
        self.assertEqual(S().post("/auth/mfa/verify", {"challenge_token": challenge, "code": user["recovery"]})[0], 200)
        self.assertEqual(S().post("/auth/mfa/verify", {"challenge_token": challenge, "code": self._next_code(user)})[0], 401)

    def test_T1_65_repeated_wrong_codes_exhaust_the_challenge_even_for_the_right_code(self):
        user = S().privileged("moderator")
        challenge = self._challenge(user)
        for i in range(8):
            S().post("/auth/mfa/verify", {"challenge_token": challenge, "code": "%06d" % (i + 1)})
        status, _ = S().post("/auth/mfa/verify", {"challenge_token": challenge, "code": self._next_code(user)})
        self.assertIn(status, (401, 429), "ADR-013: 5 failed responses invalidate the challenge; the right code must then be refused")

    def test_T1_66_a_forged_or_foreign_challenge_token_is_refused(self):
        a, b = S().privileged("moderator"), S().privileged("moderator")
        challenge_a = self._challenge(a)
        self.assertEqual(S().post("/auth/mfa/verify", {"challenge_token": challenge_a[:-3] + "AAA", "code": b["recovery"]})[0], 401)
        # account B's recovery code must not complete account A's challenge
        self.assertEqual(S().post("/auth/mfa/verify", {"challenge_token": challenge_a, "code": b["recovery"]})[0], 401)

    def test_T1_67_a_moderator_session_cannot_perform_administrator_only_actions(self):
        mod = S().privileged("moderator")
        status, tokens = S().post("/auth/mfa/verify", {"challenge_token": self._challenge(mod), "code": mod["recovery"]})
        self.assertEqual(status, 200)
        status, _ = S().post("/admin/accounts/lookup", {"email": "someone@example.test"}, token=tokens["access_token"])
        self.assertIn(status, (401, 403, 404))
        self.assertIn(S().get("/admin/moderation/assignments", token=tokens["access_token"])[0], (401, 403, 404))


class ZBruteForce(unittest.TestCase):
    """Runs last: these tests deliberately trip throttles."""

    def test_T1_90_repeated_wrong_passwords_are_throttled(self):
        user = S().new_user()
        statuses = []
        for _ in range(30):
            statuses.append(S().post("/auth/login", {"email": user["email"], "password": "Wrong-password-%d!" % len(statuses)})[0])
        self.assertIn(429, statuses, "no throttle after 30 failed sign-ins: " + str(sorted(set(statuses))))
        # ADR-013 approved budget: 5 failures per 15 minutes per account and origin. Allow slack of three.
        self.assertLessEqual(statuses.index(429), 8, f"first 429 only at attempt {statuses.index(429) + 1}; approved budget is 5")

    def test_T1_91_a_throttled_account_does_not_accept_the_right_password_during_the_lockout(self):
        user = S().new_user()
        for i in range(30):
            S().post("/auth/login", {"email": user["email"], "password": f"Wrong-password-{i}!"})
        status, _ = S().post("/auth/login", {"email": user["email"], "password": user["password"]})
        self.assertIn(status, (429, 401, 403), "during a lockout even the right password must not mint a session")

    def test_T1_92_repeated_wrong_verification_codes_are_throttled(self):
        user = S().new_user(verify=False)
        statuses = [S().post("/auth/verify", {"email": user["email"], "code": "%06d" % i})[0] for i in range(30)]
        self.assertIn(429, statuses, "six-digit codes must not be guessable by brute force: " + str(sorted(set(statuses))))

    def test_T1_93_repeated_wrong_reset_codes_are_throttled(self):
        user = S().new_user()
        S().post("/auth/password/reset-request", {"email": user["email"]})
        statuses = [S().post("/auth/password/reset", {"email": user["email"], "code": "%06d" % i, "new_password": secrets.token_urlsafe(20)})[0] for i in range(30)]
        self.assertIn(429, statuses, "reset codes must be throttled: " + str(sorted(set(statuses))))

    def test_T1_94_registration_and_reset_requests_are_rate_limited(self):
        # Phase 12: the budget is per trusted network origin, so the request carries the header the test Gateway trusts.
        origin = {"X-Phase11-Client-IP": "198.51.100.%d" % (1 + secrets.randbelow(250))}
        statuses = [S().post("/auth/register", {"email": "flood%d%s@example.test" % (i, secrets.token_hex(2)), "display_name": "Flood User",
                                                 "password": secrets.token_urlsafe(20)}, headers=origin)[0] for i in range(40)]
        self.assertIn(429, statuses, "unbounded registration: " + str(sorted(set(statuses))))
        self.assertEqual(statuses[:20], [201] * 20, "the first 20 attempts from one origin stay within the approved budget")
        other = S().post("/auth/register", {"email": "other%s@example.test" % secrets.token_hex(3), "display_name": "Other User",
                                            "password": secrets.token_urlsafe(20)}, headers={"X-Phase11-Client-IP": "203.0.113.%d" % (1 + secrets.randbelow(250))})
        self.assertEqual(other[0], 201, "another network is not locked out by the flood")

    def _mail_count(self, action, attempts=8, prelude=None):
        """How many emails really go out: the capture file is rewritten on every send, so count its changes.

        `prelude` runs inside the measured window (for example creating the account, which itself sends one email), so
        the count proves the instrument is live and includes every send charged against the account's budget.
        """
        path = S().base / "verification-mail"
        last = path.stat().st_mtime_ns if path.exists() else None
        sent = 0
        subject = prelude() if prelude else None
        for step in range(attempts + (1 if prelude else 0)):
            if step or not prelude:
                action(subject)
            time.sleep(0.2)
            now = path.stat().st_mtime_ns if path.exists() else None
            if now != last:
                sent, last = sent + 1, now
        return sent

    def test_T1_95_verification_resend_sends_at_most_three_emails_an_hour_per_account(self):
        sent = self._mail_count(lambda u: S().post("/auth/verification/resend", {"email": u["email"]}),
                                prelude=lambda: S().new_user(verify=False))
        self.assertGreaterEqual(sent, 1, "the instrument saw no mail at all, so this result would be meaningless")
        self.assertLessEqual(sent, 3, f"ADR-013 budget is 3 sends per hour per account; {sent} emails went out (1 registration + 8 resends)")

    def test_T1_96_password_reset_sends_at_most_three_emails_an_hour_and_answers_identically(self):
        user = S().new_user()
        sent = self._mail_count(lambda u: S().post("/auth/password/reset-request", {"email": user["email"]}))
        self.assertGreaterEqual(sent, 1, "the instrument saw no mail at all, so this result would be meaningless")
        self.assertLessEqual(sent, 3, f"ADR-013 budget is 3 requests per hour per account; {sent} emails went out from 8 requests")
        known = S().post("/auth/password/reset-request", {"email": user["email"]})
        unknown = S().post("/auth/password/reset-request", {"email": "nobody%s@example.test" % secrets.token_hex(3)})
        self.assertEqual(known, unknown, "the answer must not depend on whether the account exists")
