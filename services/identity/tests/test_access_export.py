"""Mandate 3.3: an access request is approved, each service delivers its own part, and only the account retrieves the
assembled export, re-authenticated, until it expires. Unauthorized, unready and expired retrieval is denied."""
import json
import os
import secrets
import uuid
from datetime import timedelta
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.db import connection
from django.test import TestCase, override_settings

from service import access_export, erasure, events, preferences_privacy
from service.models import AccessExport, AccessExportPart, Account, PrivacyRequest, SecurityEvent
from . import test_privacy_review

WINDOW = {"KOLOVIBE_EXPORT_RETRIEVAL_SECONDS": "3600"}  # a test value; the real window is an owner decision


@override_settings(STAGING_PRIVILEGED=True, PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class AccessExportTests(TestCase):
    setUp = test_privacy_review.PrivacyReviewTests.setUp
    token = test_privacy_review.PrivacyReviewTests.token
    call = test_privacy_review.PrivacyReviewTests.call

    def password(self, account):
        value = secrets.token_urlsafe(24)
        account.set_password(value)
        account.save(update_fields=["password"])
        return value

    def retrieve(self, account, password, request_id=None, role="viewer"):
        mfa = self.now if role == "administrator" else None
        body = {"access_token": self.token(account, role, mfa=mfa), "operation": "export",
                "id": request_id or str(self.access_request.id), "current_password": password}
        response = preferences_privacy.privacy_requests(self.factory.post(
            "/internal/auth/privacy-requests", json.dumps(body), content_type="application/json"))
        return response.status_code, json.loads(response.content)

    def approve(self):
        target = str(self.access_request.id)
        self.call("start-review", id=target)
        with patch.dict(os.environ, WINDOW):
            status, row = self.call("approve-access", id=target)
        self.assertEqual((status, row["status"]), (200, "processing"))
        return row

    def outbox(self):
        with connection.cursor() as cur:
            cur.execute("SELECT event_type, payload FROM event_outbox ORDER BY created_at")
            return [(kind, json.loads(payload)) for kind, payload in cur.fetchall()]

    def part(self, service="engagement", **changes):
        extra = {"creator_id": None} if service == "creators" else {}
        return {"request_id": str(self.access_request.id), "account_id": str(self.person.id), "service": service,
                "data": {"likes": [{"video_id": str(uuid.uuid4()), "created_at": "2026-11-20T10:00:00+00:00"}]},
                "withheld": ["fraud_holds"], "truncated": []} | extra | changes

    def deliver_all(self):
        with patch.dict(os.environ, WINDOW):
            for service in access_export.EXPORT_SERVICES:
                self.assertTrue(access_export.deliver(str(uuid.uuid4()), self.part(service=service)))

    def test_approval_needs_the_configured_retrieval_window(self):
        target = str(self.access_request.id)
        self.call("start-review", id=target)
        with patch.dict(os.environ, {"KOLOVIBE_EXPORT_RETRIEVAL_SECONDS": ""}):
            status, body = self.call("approve-access", id=target)
        self.assertEqual((status, body["code"]), (409, "export_window_not_configured"))
        for bad in ("0", "-5", "1h", str(400 * 24 * 3600)):
            with self.subTest(bad=bad), patch.dict(os.environ, {"KOLOVIBE_EXPORT_RETRIEVAL_SECONDS": bad}):
                self.assertEqual(self.call("approve-access", id=target)[1]["code"], "export_window_not_configured")
        self.access_request.refresh_from_db()
        self.assertEqual((self.access_request.status, AccessExport.objects.count()), ("in_review", 0))

    def test_approval_assembles_identity_and_asks_the_services_that_need_no_creator_id(self):
        self.assertEqual(self.call("approve-access", id=str(self.access_request.id))[0], 409, "review first")
        row = self.approve()
        self.assertEqual(row["export"], {"waiting_on": sorted(access_export.EXPORT_SERVICES), "ready_at": None,
                                         "expires_at": None, "purged": False, "retrievals": 0})
        self.assertEqual(sorted(self.outbox(), key=lambda row: row[1]["service"]), [
            ("privacy.export_requested", {"request_id": str(self.access_request.id),
                                          "account_id": str(self.person.id), "service": service})
            for service in ("business", "creators", "engagement")], "Moderation and Content wait for Creators")
        identity = AccessExportPart.objects.get(service="identity")
        self.assertEqual(identity.data["account"][0]["email"], "person@example.test")
        text = json.dumps(identity.data)
        for secret in ("password", "digest", "token", "secret", self.person.password):
            self.assertNotIn(secret, text)
        with patch.dict(os.environ, WINDOW):
            self.assertEqual(self.call("approve-access", id=str(self.access_request.id))[0], 200)
        self.assertEqual((AccessExport.objects.count(), len(self.outbox())), (1, 3), "a repeat opens nothing more")
        self.assertEqual(SecurityEvent.objects.filter(kind="account.privacy_access_approved").count(), 1)

    def test_a_part_is_stored_once_and_the_export_waits_for_every_service(self):
        self.approve()
        event, first = str(uuid.uuid4()), self.part()
        self.assertTrue(access_export.deliver(event, first))
        self.assertFalse(access_export.deliver(event, first), "the same event is applied once")
        self.assertTrue(access_export.deliver(str(uuid.uuid4()), self.part(data={})), "a re-sent part is accepted")
        self.assertEqual(AccessExportPart.objects.get(service="engagement").data, first["data"],
                         "the first part stands")
        self.assertEqual(access_export.waiting_on(self.access_request), ["business", "content", "creators",
                                                                         "moderation"])
        self.access_request.refresh_from_db()
        self.assertEqual(self.access_request.status, "processing", "never ready while a service has not answered")

    def test_the_creators_part_releases_moderation_and_content_with_the_profile_id(self):
        self.approve()
        profile = str(uuid.uuid4())
        self.assertFalse(access_export.valid_delivery(self.part(service="creators") | {"creator_id": "nope"}))
        creators = self.part(service="creators", creator_id=profile)
        del creators["creator_id"]
        self.assertFalse(access_export.valid_delivery(creators), "Creators must say which profile it holds")
        self.assertFalse(access_export.valid_delivery(self.part(creator_id=profile)), "only Creators reports one")
        event = str(uuid.uuid4())
        self.assertTrue(access_export.deliver(event, self.part(service="creators", creator_id=profile)))
        self.assertEqual(sorted(self.outbox()[3:], key=lambda row: row[1]["service"]), [
            ("privacy.export_requested", {"request_id": str(self.access_request.id),
                                          "account_id": str(self.person.id), "service": service,
                                          "creator_id": profile})
            for service in ("content", "moderation")])
        self.assertFalse(access_export.deliver(event, self.part(service="creators", creator_id=profile)))
        self.assertTrue(access_export.deliver(str(uuid.uuid4()), self.part(service="creators", creator_id=profile)))
        self.assertEqual(len(self.outbox()), 5, "a repeated part asks nothing more")
        self.assertNotIn("creator_id", AccessExportPart.objects.get(service="creators").data)

    def test_malformed_or_foreign_deliveries_are_refused(self):
        self.approve()
        for bad in (self.part(service="points"), self.part(extra=1), self.part(withheld=["A"]),
                    self.part(truncated=["x", "x"]), self.part(data={"Likes": []}), self.part(data={"likes": [1]}),
                    self.part(data=[]), self.part(request_id="nope")):
            with self.subTest(bad=bad):
                self.assertFalse(access_export.valid_delivery(bad))
        for bad in (self.part(account_id=str(uuid.uuid4())), self.part(request_id=str(uuid.uuid4()))):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                access_export.deliver(str(uuid.uuid4()), bad)
        self.assertIsNone(AccessExportPart.objects.get(service="engagement").delivered_at)

    def test_request_to_retrieval_then_expiry(self):
        password = self.password(self.person)
        self.approve()
        self.assertEqual(self.retrieve(self.person, password)[1]["code"], "export_not_ready")
        self.deliver_all()
        self.access_request.refresh_from_db()
        self.assertEqual(self.access_request.status, "completed")
        export = AccessExport.objects.get()
        self.assertEqual(export.expires_at - export.ready_at, timedelta(seconds=3600))
        status, body = self.retrieve(self.person, password)
        self.assertEqual(status, 200)
        self.assertEqual(set(body["services"]), {"identity", *access_export.EXPORT_SERVICES})
        self.assertEqual(body["services"]["engagement"]["withheld"], ["fraud_holds"])
        self.assertEqual(body["services"]["identity"]["data"]["account"][0]["email"], "person@example.test")
        self.assertEqual(self.retrieve(self.person, password)[0], 200, "retrievable again until it expires")
        _, listed = self.call("list")
        row = next(item for item in listed["items"] if item["id"] == str(self.access_request.id))
        self.assertEqual((row["export"]["waiting_on"], row["export"]["retrievals"]), ([], 2))
        self.assertNotIn("person@example.test", json.dumps(listed), "the console never sees the data")
        self.assertEqual(SecurityEvent.objects.filter(kind="account.privacy_export_retrieved").count(), 2)

        AccessExport.objects.filter(pk=export.pk).update(expires_at=self.now)
        self.assertEqual(self.retrieve(self.person, password), (410, {"detail": "The export has expired",
                                                                      "code": "export_expired"}))
        export.refresh_from_db()
        self.assertIsNotNone(export.purged_at)
        self.assertFalse(AccessExportPart.objects.exclude(data={}).exists(), "expired data is removed")
        self.assertEqual(self.retrieve(self.person, password)[0], 410)
        self.assertEqual(AccessExportPart.objects.count(), 6, "the dated record stays")

    def test_only_the_account_itself_freshly_reauthenticated_retrieves(self):
        password = self.password(self.person)
        self.approve()
        self.deliver_all()
        other = Account.objects.create_user("other@example.test", secrets.token_urlsafe(32), "Other")
        self.assertEqual(self.retrieve(other, self.password(other))[0], 404, "another account cannot see it")
        self.assertEqual(self.retrieve(self.admin, self.password(self.admin), role="administrator")[0], 404,
                         "nor can an administrator")
        self.assertEqual(self.retrieve(self.person, password + "!")[0], 400, "a wrong password is refused")
        self.assertEqual(self.retrieve(self.person, password, str(self.deletion.id))[0], 404, "a deletion has none")
        self.assertEqual(self.retrieve(self.person, password, str(uuid.uuid4()))[0], 404)
        for body in ({"operation": "export", "id": str(self.access_request.id)},
                     {"operation": "export", "id": "nope", "current_password": password},
                     {"operation": "export", "id": str(self.access_request.id), "current_password": password,
                      "kind": "access"}):
            with self.subTest(body=body):
                response = preferences_privacy.privacy_requests(self.factory.post(
                    "/internal/auth/privacy-requests",
                    json.dumps({"access_token": self.token(self.person, "viewer"), **body}),
                    content_type="application/json"))
                self.assertEqual(response.status_code, 400)
        response = preferences_privacy.privacy_requests(self.factory.post(
            "/internal/auth/privacy-requests", json.dumps({"access_token": "x" * 40, "operation": "export",
                                                           "id": str(self.access_request.id),
                                                           "current_password": password}),
            content_type="application/json"))
        self.assertEqual(response.status_code, 401)
        self.assertEqual(AccessExport.objects.get().retrievals, 0)
        self.assertTrue(SecurityEvent.objects.filter(kind="account.privacy_export_denied").exists())

    def test_the_purge_command_removes_expired_exports_only(self):
        self.approve()
        self.deliver_all()
        out = StringIO()
        call_command("purge_expired_exports", stdout=out)
        self.assertIn("Purged 0 expired exports", out.getvalue())
        AccessExport.objects.update(expires_at=self.now - timedelta(seconds=1))
        call_command("purge_expired_exports", stdout=out)
        self.assertIn("Purged 1 expired exports", out.getvalue())
        self.assertNotIn(str(self.person.id), out.getvalue())
        self.assertFalse(AccessExportPart.objects.exclude(data={}).exists())
        call_command("purge_expired_exports", stdout=out)
        self.assertEqual(SecurityEvent.objects.filter(kind="account.privacy_export_purged").count(), 1)

    def test_a_completed_erasure_also_removes_an_earlier_export(self):
        self.approve()
        self.deliver_all()
        erasure.deidentify(Account.objects.get(pk=self.person.pk))
        self.assertIsNotNone(AccessExport.objects.get().purged_at)
        self.assertFalse(AccessExportPart.objects.exclude(data={}).exists())

    def test_the_identity_worker_routes_export_parts(self):
        with patch.dict("os.environ", {"KOLOVIBE_ENV": "local",
                                       "KOLOVIBE_RABBITMQ_URL": "amqps://u:p@localhost:5671/kv"}):
            from service import celery_app
        with patch("service.access_export.deliver", return_value=True) as deliver:
            self.assertTrue(celery_app.receive_event.run("e", events.EXPORT_DELIVERED, {"a": 1}))
        deliver.assert_called_once_with("e", {"a": 1})
        with self.assertRaises(ValueError):
            celery_app.receive_event.run("e", events.EXPORT_REQUESTED, {})

    def test_requests_and_parts_are_distinct_outbox_kinds(self):
        from django.db import transaction
        with transaction.atomic():
            events.record_event(events.EXPORT_REQUESTED, {"service": "engagement"})
            with self.assertRaises(ValueError):
                events.record_event(events.EXPORT_DELIVERED, {"service": "engagement"})
        self.assertEqual(PrivacyRequest.objects.filter(status="completed").count(), 0)
