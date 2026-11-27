"""Decision C, mandate 3.3: assemble, deliver and retrieve a person's access export.

Approving an access request opens one export with a part per participating service plus Identity's own part, which is
assembled at once. Each service assembles its own records of the person (service-owned assembly) and delivers them
as `privacy.export_delivered`; Identity stores each part once. The export is ready when every part has arrived. Only
the account itself, re-authenticated, can retrieve it, and only until it expires; every retrieval is audited, and
expired data is purged (`purge_expired_exports`).

- The retrieval window is configuration (`KOLOVIBE_EXPORT_RETRIEVAL_SECONDS`), an owner decision with no default:
  without it an access request cannot be approved.
- Moderation and Content key a creator's records by the creator profile id, which only Creators knows. As with
  erasure, they are asked only when Creators delivers its part, with the profile id it reported (null for someone
  who was never a creator).
- A service whose export is not built (`EXPORT_PENDING_SERVICES`, empty since slice 3.3b) would not be asked; its part
  would stay undelivered, so the export never claims to be complete.
"""
import os
import re
import uuid
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from . import events
from .models import (AccessExport, AccessExportPart, Account, LoginSession, NotificationPreferences, PrivacyRequest,
                     SecurityEvent, TotpFactor)
from .security_audit import record

EXPORT_SERVICES = events.ERASURE_SERVICES
EXPORT_PENDING_SERVICES = ()  # every participating service assembles its part (3.3b)
CATEGORY = re.compile(r"[a-z][a-z0-9_]{0,39}")
MAX_ROWS = 5000
MAX_RETRIEVAL_SECONDS = 366 * 24 * 3600  # a sanity bound on configuration, not a policy value


class NotConfigured(Exception):
    pass


def retrieval_window():
    value = os.environ.get("KOLOVIBE_EXPORT_RETRIEVAL_SECONDS", "")
    if not value.isdigit() or not 1 <= int(value) <= MAX_RETRIEVAL_SECONDS:
        raise NotConfigured
    return timedelta(seconds=int(value))


def _iso(value):
    return value.isoformat() if value else None


def identity_part(account):
    """Identity's own records of the person: never a credential, digest, token or secret."""
    preferences = NotificationPreferences.objects.filter(account=account).first()
    return {
        "account": [{"email": account.email, "display_name": account.display_name, "role": account.role,
                     "created_at": _iso(account.created_at), "email_verified_at": _iso(account.email_verified_at)}],
        "notification_preferences": [{"email_notifications": preferences.email_notifications,
                                      "push_notifications": preferences.push_notifications}] if preferences else [],
        "sessions": [{"created_at": _iso(row.created_at), "expires_at": _iso(row.expires_at),
                      "revoked_at": _iso(row.revoked_at)}
                     for row in LoginSession.objects.filter(account=account).order_by("created_at")[:MAX_ROWS]],
        "two_factor_enrolled": [{"enrolled": TotpFactor.objects.filter(account=account).exists()}],
        "privacy_requests": [{"kind": row.kind, "status": row.status, "created_at": _iso(row.created_at)}
                             for row in PrivacyRequest.objects.filter(account=account).order_by("created_at")],
        "security_events": [{"kind": row.kind, "occurred_at": _iso(row.occurred_at)}
                            for row in SecurityEvent.objects.filter(actor_id=account.id)
                            .order_by("occurred_at")[:MAX_ROWS]],
    }


def open_export(item, now):
    """Within the approving transaction: one export, Identity's part, and a request to each service that can answer."""
    export, created = AccessExport.objects.get_or_create(request=item)
    if not created:
        return export
    AccessExportPart.objects.create(export=export, service="identity", delivered_at=now,
                                    data=identity_part(Account.objects.get(pk=item.account_id)))
    for service in EXPORT_SERVICES:
        AccessExportPart.objects.create(export=export, service=service)
        if service not in EXPORT_PENDING_SERVICES and service not in events.AFTER_CREATORS:
            _ask(item, service)
    return export


def _ask(item, service, **extra):
    events.record_event(events.EXPORT_REQUESTED, {"request_id": str(item.id), "account_id": str(item.account_id),
                                                 "service": service, **extra})


def _names(value):
    return (isinstance(value, list) and len(value) <= 40 and len(set(value)) == len(value)
            and all(isinstance(name, str) and CATEGORY.fullmatch(name) for name in value))


def valid_delivery(payload):
    try:
        data = payload["data"]
        keys = {"request_id", "account_id", "service", "data", "withheld", "truncated"}
        if payload.get("service") == "creators":
            keys.add("creator_id")
            creator = payload["creator_id"]
            if creator is not None and str(uuid.UUID(creator)) != creator:
                return False
        return (isinstance(payload, dict) and set(payload) == keys
                and str(uuid.UUID(payload["request_id"])) == payload["request_id"]
                and str(uuid.UUID(payload["account_id"])) == payload["account_id"]
                and payload["service"] in EXPORT_SERVICES and payload["service"] not in EXPORT_PENDING_SERVICES
                and isinstance(data, dict) and len(data) <= 40
                and all(isinstance(name, str) and CATEGORY.fullmatch(name) and isinstance(rows, list)
                        and len(rows) <= MAX_ROWS and all(isinstance(row, dict) for row in rows)
                        for name, rows in data.items())
                and _names(payload["withheld"]) and _names(payload["truncated"]))
    except (KeyError, TypeError, ValueError, AttributeError):
        return False


def deliver(event_id, payload):
    """Store one service's part exactly once; the export becomes ready when the last part arrives."""
    if not valid_delivery(payload):
        raise ValueError("Invalid export delivery")
    with transaction.atomic():
        if not events.accept_once(event_id, events.EXPORT_DELIVERED):
            return False
        part = (AccessExportPart.objects.select_for_update().select_related("export__request")
                .filter(export__request_id=payload["request_id"], service=payload["service"]).first())
        if (part is None or str(part.export.request.account_id) != payload["account_id"]
                or part.export.request.status != PrivacyRequest.Status.PROCESSING):
            raise ValueError("No open export for this delivery")
        if part.delivered_at is not None:
            return True  # a re-sent part after a retry: the first one stands
        now = timezone.now()
        part.delivered_at, part.data = now, payload["data"]
        part.withheld, part.truncated = payload["withheld"], payload["truncated"]
        part.save(update_fields=["delivered_at", "data", "withheld", "truncated"])
        record("account.privacy_export_part_received", part.export.request.account_id)
        if part.service == "creators":  # releases the parts keyed by the creator profile id
            for service in events.AFTER_CREATORS:
                if service not in EXPORT_PENDING_SERVICES:
                    _ask(part.export.request, service, creator_id=payload["creator_id"])
        _ready_if_complete(part.export, now)
        return True


def _ready_if_complete(export, now):
    if AccessExportPart.objects.filter(export=export, delivered_at__isnull=True).exists():
        return False
    try:
        window = retrieval_window()
    except NotConfigured:
        return False  # stays processing; approval already required the window, so this means it was removed
    AccessExport.objects.filter(pk=export.pk).update(ready_at=now, expires_at=now + window)
    PrivacyRequest.objects.filter(pk=export.request_id).update(status=PrivacyRequest.Status.COMPLETED)
    record("account.privacy_export_ready", export.request.account_id)
    return True


def waiting_on(item):
    """Services whose part has not arrived, for the console (names only)."""
    export = AccessExport.objects.filter(request=item).first()
    if export is None:
        return []
    return sorted(AccessExportPart.objects.filter(export=export, delivered_at__isnull=True)
                  .values_list("service", flat=True))


def purge(export):
    """Remove the assembled data once; the export row and its dates stay as the record of what happened."""
    AccessExportPart.objects.filter(export=export).update(data={}, withheld=[], truncated=[])
    AccessExport.objects.filter(pk=export.pk, purged_at__isnull=True).update(purged_at=timezone.now())


def retrieve(account, request_id, now):
    """(status, body) for the account's own ready export; expired data is purged on the spot."""
    export = (AccessExport.objects.select_for_update().select_related("request")
              .filter(request_id=request_id, request__account=account, request__kind=PrivacyRequest.Kind.ACCESS)
              .first())
    if export is None:
        return 404, {"detail": "Export not found"}
    if export.ready_at is None:
        return 409, {"detail": "The export is not ready yet", "code": "export_not_ready"}
    if export.purged_at is not None or export.expires_at <= now:
        if export.purged_at is None:
            purge(export)
            record("account.privacy_export_purged", account.id)
        return 410, {"detail": "The export has expired", "code": "export_expired"}
    parts = AccessExportPart.objects.filter(export=export).order_by("service")
    AccessExport.objects.filter(pk=export.pk).update(retrievals=export.retrievals + 1)
    record("account.privacy_export_retrieved", account.id)
    return 200, {"request_id": str(export.request_id), "generated_at": export.ready_at.isoformat(),
                 "expires_at": export.expires_at.isoformat(),
                 "services": {part.service: {"data": part.data, "withheld": part.withheld, "truncated": part.truncated}
                              for part in parts}}
