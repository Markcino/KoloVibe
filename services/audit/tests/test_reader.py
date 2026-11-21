import json
from datetime import timedelta
from uuid import uuid4
from django.test import TestCase, RequestFactory
from django.utils import timezone
from service.models import SecurityEvent, AuditReadGrant
from service.reader import read_events


class AuditReadTests(TestCase):
    def setUp(self):
        self.actor, self.other = uuid4(), uuid4()
        for index in range(22):
            SecurityEvent.objects.create(actor_id=self.actor, kind="moderation.reviewer_read", producer="moderation",
                occurred_at=timezone.now() - timedelta(minutes=index), subject_type="video", subject_id=uuid4(),
                payload_digest="never-expose-digest")
        self.other_event = SecurityEvent.objects.create(actor_id=self.other, kind="login.succeeded", producer="identity",
            occurred_at=timezone.now(), subject_type="account", subject_id=self.other, payload_digest="private")

    def call(self, data=None, role="moderator", mfa=True, caller="gateway"):
        request = RequestFactory().post("/internal/audit/read", {"actor_id": str(self.actor), "role": role,
            "mfa_verified": mfa, "data": data or {}}, content_type="application/json")
        request.service_caller = caller
        return read_events(request)

    def test_moderator_own_actions_paginate_and_redact_sensitive_fields(self):
        result = self.call({"producer": "moderation"})
        self.assertEqual(result.status_code, 200)
        page = json.loads(result.content)
        self.assertEqual(len(page["items"]), 20)
        self.assertEqual(page["next_cursor"], page["items"][-1]["id"])
        next_page = json.loads(self.call({"producer": "moderation", "cursor": page["next_cursor"]}).content)
        self.assertEqual(len(next_page["items"]), 2)
        for value in ("actor_id", "subject_id", "payload_digest", "never-expose-digest", str(self.other)):
            self.assertNotIn(value.encode(), result.content)
        self.assertTrue(SecurityEvent.objects.filter(actor_id=self.actor, kind="audit.read").exists())
        self.assertEqual(self.call({"cursor": str(self.other_event.id)}).status_code, 400)

    def test_admin_requires_explicit_producer_grants_and_filters_cannot_expand_scope(self):
        self.assertEqual(self.call(role="administrator").status_code, 403)
        grant = AuditReadGrant.objects.create(administrator_id=self.actor, producer="moderation")
        page = json.loads(self.call({"producer": "identity"}, role="administrator").content)
        self.assertEqual(page["items"], [])
        self.assertEqual(len(json.loads(self.call(role="administrator").content)["items"]), 20)
        grant.active = False
        grant.save()
        self.assertEqual(self.call(role="administrator").status_code, 403)
        self.assertTrue(SecurityEvent.objects.filter(kind="audit.read_denied").exists())

    def test_roles_mfa_caller_and_filters_fail_closed(self):
        for role in ("viewer", "creator", "support", "finance"):
            self.assertEqual(self.call(role=role).status_code, 403)
        self.assertEqual(self.call(mfa=False).status_code, 403)
        self.assertEqual(self.call(caller="content").status_code, 403)
        for query in ({"actor_id": str(self.other)}, {"cursor": "bad"}, {"producer": "unknown"},
                      {"kind": "unknown"}, {"since": "not-a-date"}, {"since": "2026-11-21"},
                      {"since": "2026-11-22T00:00:00Z", "until": "2026-11-21T00:00:00Z"}):
            self.assertEqual(self.call(query).status_code, 400)
        self.assertEqual(self.client.get("/internal/audit/read").status_code, 403)
