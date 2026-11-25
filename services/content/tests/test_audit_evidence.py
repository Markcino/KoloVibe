"""D11-007 / FR-015: each video change leaves immutable evidence in its transaction and is delivered to Audit."""

import io
import json
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from django.core.management import CommandError, call_command
from django.db import DatabaseError, transaction
from django.test import RequestFactory, TestCase, TransactionTestCase
from django.utils import timezone

from service import security_audit
from service.media_api import media_api
from service.media_processing import _claim, _finish
from service.models import AuditDelivery, AuditEvent, MediaUpload, Video  # noqa: F401
from service.moderation import moderation_video


class Response:
    status = 201

    def __init__(self, body=b'{"status":"ok"}'):
        self.body = body

    def read(self, size):
        return self.body[:size]

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def kinds(subject):
    # Scoped to one video: the PostgreSQL foundations run shares a database with committed fixtures.
    return list(AuditEvent.objects.filter(subject_id=subject).order_by("occurred_at").values_list("kind", flat=True))


class ContentAuditEvidenceTests(TestCase):
    def setUp(self):
        self.creator, self.account = uuid4(), uuid4()

    def call(self, operation, fields):
        request = RequestFactory().post("/internal/videos/media/" + operation, fields, content_type="application/json")
        request.service_caller = "gateway"
        return media_api(request, operation)

    def owner(self, video_id):
        return {"creator_id": str(self.creator), "video_id": str(video_id)}

    @patch("service.media_api._enqueue")
    @patch("service.media_storage.inspect_upload", return_value=(1234, "video/mp4", '"etag"'))
    @patch("service.media_storage.sign_upload", return_value="https://example.invalid/upload")
    def test_draft_intent_completion_and_processing_each_record_once(self, sign, inspect, enqueue):
        created = self.call("draft", {"creator_id": str(self.creator), "title": "Original", "category": "culture"})
        video_id = json.loads(created.content)["id"]
        intent = self.owner(video_id) | {
            "size_bytes": 1234, "idempotency_key": "audit-test-media-001", "account_id": str(self.account),
            "originality_attestation": {"version": "R1-originality-v1", "accepted": True},
            "review_policy": {"trusted": False, "sample_percent": 100, "policy_version": None}}
        self.assertEqual(self.call("intent", intent).status_code, 200)
        self.assertEqual(self.call("intent", intent).status_code, 200)
        self.assertEqual(self.call("complete", self.owner(video_id)).status_code, 202)
        self.assertEqual(self.call("complete", self.owner(video_id)).status_code, 202)
        claimed, token = _claim(video_id)
        _finish(claimed, token, Video.State.REVIEW, key="playback/x/y.mp4", duration=1000, poster="playback/x/y.jpg")
        self.assertEqual(kinds(video_id), ["video.created", "video.upload_intent_created", "video.upload_completed",
                                   "video.processing_succeeded"])
        intent_event = AuditEvent.objects.get(kind="video.upload_intent_created")
        self.assertEqual((intent_event.actor_id, intent_event.subject_type, str(intent_event.subject_id)),
                         (self.account, "video", video_id))
        self.assertIsNone(AuditEvent.objects.get(kind="video.created").actor_id)
        self.assertEqual(AuditDelivery.objects.filter(event__subject_id=video_id, delivered_at__isnull=True).count(), 4)

    def test_processing_failure_and_transient_outage(self):
        video = Video.objects.create(creator_id=self.creator, title="Original", category="hipco", state="processing")
        MediaUpload.objects.create(id=uuid4(), video=video, expected_bytes=10, expires_at=timezone.now(), source_etag='"e"')
        claimed, token = _claim(video.id)
        _finish(claimed, token, None, failure="processing_unavailable")
        self.assertEqual(kinds(video.id), [])
        claimed, token = _claim(video.id)
        _finish(claimed, token, Video.State.FAILED, failure="invalid_media")
        self.assertEqual(kinds(video.id), ["video.processing_failed"])

    def test_edit_publish_unpublish_and_delete_record_only_real_changes(self):
        now = timezone.now()
        video = Video.objects.create(
            creator_id=self.creator, title="Original", category="hipco", state="published", visibility="private",
            provider_asset_id="playback/a/b.mp4", moderation_approved_at=now, duration_ms=2000)
        self.assertEqual(self.call("edit", self.owner(video.id) | {"title": "Renamed"}).status_code, 200)
        self.assertEqual(self.call("edit", self.owner(video.id) | {"title": "Renamed"}).status_code, 200)
        self.assertEqual(self.call("publish", self.owner(video.id)).status_code, 200)
        self.assertEqual(self.call("unpublish", self.owner(video.id)).status_code, 200)
        self.assertEqual(self.call("unpublish", self.owner(video.id)).status_code, 200)
        self.assertEqual(self.call("delete", self.owner(video.id)).status_code, 200)
        self.assertEqual(kinds(video.id), ["video.edit_submitted", "video.published", "video.unpublished", "video.deleted"])
        self.assertNotIn("Renamed", json.dumps(list(AuditEvent.objects.filter(subject_id=video.id).values()), default=str))

    def test_refused_requests_record_nothing(self):
        before = AuditEvent.objects.count()
        other = Video.objects.create(creator_id=uuid4(), title="Theirs", category="hipco")
        self.assertEqual(self.call("edit", self.owner(other.id) | {"title": "Mine"}).status_code, 404)
        self.assertEqual(self.call("delete", self.owner(other.id)).status_code, 404)
        self.assertEqual(self.call("draft", {"creator_id": str(self.creator), "title": "No category"}).status_code, 400)
        self.assertFalse(AuditEvent.objects.exists())

    def test_moderation_application_records_once_per_action(self):
        video = Video.objects.create(creator_id=self.creator, title="Original", state="review",
                                     provider_asset_id="playback/a/b.mp4")
        action = uuid4()

        def apply():
            request = RequestFactory().post("/internal/videos/moderation/apply", {
                "video_id": str(video.id), "action": "publish", "revision": 0, "action_id": str(action)},
                content_type="application/json")
            request.service_caller = "moderation"
            return moderation_video(request, "apply")
        self.assertEqual(apply().status_code, 200)
        self.assertEqual(apply().status_code, 200)
        self.assertEqual(kinds(video.id), ["video.moderated"])

    def test_events_are_append_only_identifiers_only_and_match_the_audit_vocabulary(self):
        with transaction.atomic():
            event = security_audit.record("video.created", uuid4())
        self.assertEqual({field.name for field in AuditEvent._meta.fields},
                         {"id", "kind", "actor_id", "occurred_at", "subject_type", "subject_id"})
        with self.assertRaises(DatabaseError), transaction.atomic():
            AuditEvent.objects.filter(pk=event.pk).update(kind="video.deleted")
        with self.assertRaises(DatabaseError), transaction.atomic():
            AuditEvent.objects.filter(pk=event.pk)._raw_delete(AuditEvent.objects.db)
        with self.assertRaises(RuntimeError), transaction.atomic():
            security_audit.record("video.viewed", uuid4())
        source = (Path(__file__).resolve().parents[2] / "audit/service/events.py").read_text()
        for kind in security_audit.KINDS:
            self.assertIn(f'"{kind}"', source)


class OutsideTransactionTests(TransactionTestCase):
    def test_evidence_is_refused_outside_its_owning_transaction(self):
        with self.assertRaises(RuntimeError):
            security_audit.record("video.created", uuid4())


class ContentAuditDeliveryTests(TestCase):
    def setUp(self):
        AuditDelivery.objects.update(delivered_at=timezone.now())  # isolate from committed fixtures (rolled back)
        with transaction.atomic():
            self.event = security_audit.record("video.created", uuid4())

    def run_command(self, **options):
        out = io.StringIO()
        call_command("deliver_audit_events", stdout=out, **options)
        return out.getvalue()

    def test_delivers_the_exact_signed_payload_with_a_null_actor_once(self):
        calls = []

        def send(audience, path, **kwargs):
            calls.append((audience, path, kwargs))
            return Response()
        with patch("service.management.commands.deliver_audit_events.signed_internal_request", side_effect=send):
            self.assertIn("acknowledged", self.run_command())
            self.run_command()
        self.assertEqual(len(calls), 1)
        audience, path, kwargs = calls[0]
        self.assertEqual((audience, path, kwargs["method"]), ("audit", "/internal/security-events", "POST"))
        payload = json.loads(kwargs["payload"])
        self.assertEqual(set(payload), {"id", "actor_id", "kind", "occurred_at", "subject_type", "subject_id"})
        self.assertEqual((payload["actor_id"], payload["kind"], payload["subject_type"]),
                         (None, "video.created", "video"))

    def test_failure_keeps_the_evidence_and_backs_off(self):
        with patch("service.management.commands.deliver_audit_events.signed_internal_request", side_effect=OSError):
            with self.assertRaises(CommandError):
                self.run_command()
        delivery = AuditDelivery.objects.get(event=self.event)
        self.assertEqual((delivery.delivered_at, delivery.attempts), (None, 1))
        self.assertGreater(delivery.next_attempt_at, timezone.now())
