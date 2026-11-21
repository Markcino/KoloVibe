import hashlib
import hmac
import json
import os
from pathlib import Path
import tempfile
import time
from unittest.mock import patch
from uuid import uuid4

from django.http import JsonResponse
from django.test import RequestFactory, TestCase
from django.utils import timezone

from service.events import ingest, PRODUCER_KINDS
from service.models import SecurityEvent
from service.service_auth import ServiceAuthMiddleware


class ProducerTests(TestCase):
    def send(self, caller, kind, **extra):
        payload = {"id": str(uuid4()), "actor_id": str(uuid4()), "kind": kind,
                   "occurred_at": timezone.now().isoformat(), **extra}
        request = RequestFactory().post("/internal/security-events", payload, content_type="application/json")
        request.service_caller = caller
        return ingest(request), payload

    def test_each_producer_has_own_allow_list_and_subject_attribution(self):
        for producer, kinds in PRODUCER_KINDS.items():
            for kind in kinds:
                response, payload = self.send(producer, kind, subject_type="video", subject_id=str(uuid4()))
                self.assertEqual(response.status_code, 201)
                event = SecurityEvent.objects.get(pk=payload["id"])
                self.assertEqual((event.producer, str(event.subject_id)), (producer, payload["subject_id"]))
            other = "moderation.report_created" if producer == "identity" else "account.registered"
            self.assertEqual(self.send(producer, other)[0].status_code, 400)
        self.assertEqual(self.send("gateway", "account.registered")[0].status_code, 403)

    def test_points_ledger_decision_payload_is_ingested_with_null_actor_and_is_producer_bound(self):
        # Exact shape emitted by the Points deliver_audit_events command.
        for kind in ("points.awarded", "points.withheld"):
            payload = {"id": str(uuid4()), "actor_id": None, "kind": kind,
                       "occurred_at": timezone.now().isoformat(),
                       "subject_type": "points_entry", "subject_id": str(uuid4())}
            request = RequestFactory().post("/internal/security-events", payload, content_type="application/json")
            request.service_caller = "points"
            self.assertEqual(ingest(request).status_code, 201)
            self.assertEqual(ingest(request).status_code, 200)
            event = SecurityEvent.objects.get(pk=payload["id"])
            self.assertEqual((event.producer, event.actor_id, event.subject_type), ("points", None, "points_entry"))
            request.service_caller = "moderation"
            self.assertEqual(ingest(request).status_code, 400)

    def test_optional_subject_is_paired_strict_and_producer_cannot_be_spoofed(self):
        for extra in ({"subject_type": "video"}, {"subject_id": str(uuid4())},
                      {"subject_type": "video", "subject_id": "bad"},
                      {"subject_type": "password", "subject_id": str(uuid4())}, {"producer": "identity"}):
            self.assertEqual(self.send("moderation", "moderation.report_created", **extra)[0].status_code, 400)
        response, payload = self.send("identity", "account.registered")
        self.assertEqual(response.status_code, 201)
        event = SecurityEvent.objects.get(pk=payload["id"])
        self.assertIsNone(event.subject_id)
        request = RequestFactory().post("/internal/security-events", payload | {"kind": "points.awarded"}, content_type="application/json")
        request.service_caller = "points"
        self.assertEqual(ingest(request).status_code, 409)

    def test_distinct_signing_keys_required_and_wrong_producer_key_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            keyfile = Path(directory) / "keys.json"
            keys = {name: name.ljust(40, "x") for name in PRODUCER_KINDS}
            keyfile.write_text(json.dumps(keys))
            middleware = ServiceAuthMiddleware(lambda req: JsonResponse({"caller": req.service_caller}))
            def signed(caller, key, path="/internal/security-events"):
                stamp, nonce = str(int(time.time())), str(uuid4())
                digest = hashlib.sha256(b"{}").hexdigest()
                canonical = "\n".join((caller, "audit", stamp, nonce, "POST", path, digest))
                signature = hmac.new(key.encode(), canonical.encode(), hashlib.sha256).hexdigest()
                return RequestFactory().post(path, b"{}", content_type="application/json",
                    HTTP_X_KOLOVIBE_CALLER=caller, HTTP_X_KOLOVIBE_TIMESTAMP=stamp,
                    HTTP_X_KOLOVIBE_NONCE=nonce, HTTP_X_KOLOVIBE_SIGNATURE=signature)
            with patch.dict(os.environ, {"KOLOVIBE_CALLER_KEYS_FILE": str(keyfile), "KOLOVIBE_SERVICE_NAME": "audit", "KOLOVIBE_CALLER_GATEWAY_KEY": ""}):
                for caller, key in keys.items():
                    self.assertEqual(middleware(signed(caller, key)).status_code, 200)
                    wrong = keys["identity"] if caller != "identity" else keys["moderation"]
                    self.assertEqual(middleware(signed(caller, wrong)).status_code, 403)
                # Preserve the existing diagnostic caller while keeping it unable
                # to publish events or access any other internal route.
                keys["gateway"] = "gateway-probe".ljust(40, "x")
                keyfile.write_text(json.dumps(keys))
                self.assertEqual(middleware(signed("gateway", keys["gateway"], "/internal/probe")).status_code, 200)
                self.assertEqual(middleware(signed("gateway", keys["gateway"])).status_code, 403)
                self.assertEqual(middleware(signed("gateway", keys["gateway"], "/internal/other")).status_code, 403)
                keyfile.write_text(json.dumps({"identity": keys["identity"], "moderation": keys["identity"]}))
                self.assertEqual(middleware(signed("identity", keys["identity"])).status_code, 403)
