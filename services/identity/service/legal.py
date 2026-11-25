"""Decision B: versioned terms and privacy notice, acceptance history, and a separate, optional marketing consent.

Each document is a file in `legal_texts/` with a version, an effective date and a review status. Its SHA-256 is
computed from the file when the service starts, and an acceptance records the version and that digest, so it always
points at the exact words the person saw. Acceptance counts only for the same version *and* digest: if a text were
edited without a new version, everyone would be asked to accept it again rather than being bound to words they never
saw. A new version is a new file and a new entry here, never an edit in place.

The terms and the privacy notice are required. Registration is refused unless the caller names their current versions,
and a signed-in person whose last acceptance is older than the current version is told that acceptance is required.
Acceptance is never inferred and never backfilled. Marketing consent is separate, off unless granted, and can be
withdrawn at any time; acknowledging the privacy notice is never consent to marketing, advertising or tracking.

Acceptance and consent rows are append-only (database triggers). Their retention is part of Decision C.

Every text is a draft pending legal review. `status` says so on every response, and the app and the policy page show
it; nothing here marks a text as legally approved.
"""
import hashlib
from dataclasses import dataclass, replace
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
from django.db import transaction
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from .models import LegalAcceptance, MarketingConsentEvent

TEXTS = Path(__file__).resolve().parent / "legal_texts"
PENDING = "pending_legal_review"
APPROVED = "approved"
OUTDATED = "legal_version_outdated"


@dataclass(frozen=True)
class Document:
    kind: str
    title: str
    version: str
    effective_at: str
    status: str
    file: str
    required: bool
    text: str = ""
    sha256: str = ""


def _load(entries):
    """Read each text once; refuse to start on an unknown status, a missing file or a file not named for its version."""
    loaded = {}
    for entry in entries:
        if entry.status not in (PENDING, APPROVED):
            raise ImproperlyConfigured(f"Unknown legal status for {entry.kind}")
        if entry.file != f"{entry.kind}-{entry.version}.md":
            raise ImproperlyConfigured(f"Legal text {entry.file} is not named for its version")
        raw = (TEXTS / entry.file).read_bytes()
        loaded[entry.kind] = replace(entry, text=raw.decode("utf-8"), sha256=hashlib.sha256(raw).hexdigest())
    return loaded


# One entry per document kind.
DOCUMENTS = _load((
    Document("terms", "Terms of Service", "2026-11-25", "2026-11-25", PENDING, "terms-2026-11-25.md", True),
    Document("privacy", "Privacy Notice", "2026-11-25", "2026-11-25", PENDING, "privacy-2026-11-25.md", True),
    Document("marketing", "Marketing messages", "2026-11-25", "2026-11-25", PENDING, "marketing-2026-11-25.md", False),
))
REQUIRED = tuple(kind for kind, d in DOCUMENTS.items() if d.required)


def summary(document):
    return {"kind": document.kind, "title": document.title, "version": document.version,
            "effective_at": document.effective_at, "status": document.status, "sha256": document.sha256}


def check_required(accepted):
    """`accepted` maps each required kind to the version the caller saw. Returns None, or an error response."""
    if not isinstance(accepted, dict) or set(accepted) != set(REQUIRED) or not all(
            isinstance(v, str) and 1 <= len(v) <= 32 for v in accepted.values()):
        raise ValueError
    if any(accepted[kind] != DOCUMENTS[kind].version for kind in REQUIRED):
        return outdated()
    return None


def outdated():
    return JsonResponse({"detail": "A newer version must be accepted", "code": OUTDATED}, status=409)


def record_acceptance(account, kinds, context):
    for kind in kinds:
        document = DOCUMENTS[kind]
        LegalAcceptance.objects.create(account=account, document=kind, version=document.version,
                                       sha256=document.sha256, context=context)


def record_marketing(account, granted):
    document = DOCUMENTS["marketing"]
    MarketingConsentEvent.objects.create(account=account, granted=granted, version=document.version,
                                         sha256=document.sha256)


def _latest(account_id):
    latest = {}
    for row in LegalAcceptance.objects.filter(account_id=account_id).order_by("accepted_at", "id"):
        latest[row.document] = row
    return latest


def _accepted(row, kind):
    """An acceptance counts only for the current version and the exact text (digest) of that version."""
    return row is not None and (row.version, row.sha256) == (DOCUMENTS[kind].version, DOCUMENTS[kind].sha256)


def _marketing(account_id):
    return MarketingConsentEvent.objects.filter(account_id=account_id).order_by("-recorded_at", "-id").first()


def state(account_id):
    latest = _latest(account_id)
    documents, missing = [], []
    for kind in REQUIRED:
        row = latest.get(kind)
        documents.append({**summary(DOCUMENTS[kind]),
                          "accepted_version": row.version if row else None,
                          "accepted_at": row.accepted_at.isoformat() if row else None})
        missing.append(not _accepted(row, kind))
    consent = _marketing(account_id)
    return {
        "documents": documents,
        "acceptance_required": any(missing),
        "marketing": {"granted": bool(consent and consent.granted), "version": DOCUMENTS["marketing"].version,
                      "updated_at": consent.recorded_at.isoformat() if consent else None},
    }


@require_POST
def document(request):
    """The current text of one document. Public through the Gateway: it must be readable before registration."""
    from .accounts import _body, _error
    try:
        data = _body(request, {"kind"})
        if set(data) != {"kind"} or data["kind"] not in DOCUMENTS:
            raise ValueError
    except (ValueError, TypeError, UnicodeError):
        return _error("Unknown document", 404)
    current = DOCUMENTS[data["kind"]]
    return JsonResponse({**summary(current), "text": current.text})


@require_POST
def manage(request):
    """Signed-in: read the acceptance state, accept the current required versions, or set marketing consent."""
    from .accounts import _body, _error, _locked_account, _session_for_access
    from .security_audit import record
    try:
        data = _body(request, {"access_token", "operation", "accepted", "granted", "version"})
        operation = data.get("operation")
        expected = {"get": {"access_token", "operation"},
                    "accept": {"access_token", "operation", "accepted"},
                    "marketing": {"access_token", "operation", "granted", "version"}}.get(operation)
        if expected is None or set(data) != expected or not isinstance(data["access_token"], str):
            raise ValueError
        if operation == "accept":
            accepted = data["accepted"]
            if (not isinstance(accepted, dict) or not accepted or not set(accepted) <= set(REQUIRED)
                    or not all(isinstance(v, str) and 1 <= len(v) <= 32 for v in accepted.values())):
                raise ValueError
        if operation == "marketing" and (type(data["granted"]) is not bool or not isinstance(data["version"], str)):
            raise ValueError
        session = _session_for_access(data["access_token"])
    except (ValueError, KeyError, TypeError, UnicodeError):
        return _error("Invalid legal request")
    if session is None:
        return _error("Unauthorized", 401)
    if operation == "get":
        return JsonResponse(state(session.account_id))
    with transaction.atomic():
        account = _locked_account(session)
        if account is None:
            return _error("Unauthorized", 401)
        if operation == "accept":
            if any(version != DOCUMENTS[kind].version for kind, version in accepted.items()):
                return outdated()
            latest = _latest(account.id)
            fresh = [kind for kind in REQUIRED if kind in accepted and not _accepted(latest.get(kind), kind)]
            if fresh:
                record_acceptance(account, fresh, LegalAcceptance.Context.UPDATE)
                record("account.legal_accepted", account.id)
        else:
            if data["version"] != DOCUMENTS["marketing"].version:
                return outdated()
            current = _marketing(account.id)
            if bool(current and current.granted) != data["granted"]:
                record_marketing(account, data["granted"])
                record("account.marketing_consent_changed", account.id)
    return JsonResponse(state(session.account_id))
