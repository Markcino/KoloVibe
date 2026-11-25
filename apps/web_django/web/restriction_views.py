"""Decision F (D-8): administrators issue, lift and review appeals against measures on creators.

The Gateway and Creators decide who may act and what is allowed (administrator role, a live MFA-verified session,
no self-restriction, a second administrator to lift or decide). This console validates their answers, never echoes
their error text, and carries a signed, session-bound intent for every change.
"""

from datetime import datetime, timezone
import re
import secrets
from urllib.parse import urlencode

from django.core import signing
from django.http import HttpResponseNotAllowed
from django.shortcuts import redirect
from django.urls import reverse

from . import views
from .api_contracts import valid_id

SALT = "admin-creator-measures"
NOTICE = "measure_notice"
KINDS = (("warning", "Warning (blocks nothing)"), ("upload", "No new uploads"), ("publishing", "No publishing"),
         ("monetization", "No future earnings"), ("suspension", "Suspension (uploads, publishing and earnings)"))
KIND_NAMES = {name for name, _ in KINDS}
DECISIONS = ("uphold", "lift")
CODE = re.compile(r"[A-Z][A-Z0-9_]{1,63}")
VERSION = re.compile(r"[A-Za-z0-9._-]{1,32}")
KEY = re.compile(r"[A-Za-z0-9_-]{16,128}")
PUBLIC = {"id", "kind", "reason_code", "policy_version", "issued_at", "expires_at", "lifted_at", "active", "appeal"}
PRIVATE = PUBLIC | {"creator_id", "reason", "issued_by", "lifted_by", "lift_reason"}
# Fixed copy per refusal; the service's own text is never shown.
REFUSED = {
    400: "That request wasn't valid. Check the reason (10 to 2,000 characters), code, policy version and end time.",
    403: "You can't do this. You can't restrict your own creator profile, and a different administrator from the "
         "one who issued a measure must lift it or decide its appeal.",
    404: "That creator or measure wasn't found.",
    409: "This conflicts with an existing record: the creator may already have an active measure of this kind, "
         "or it was already lifted or decided differently.",
}
UNAVAILABLE = "Creator measures are unavailable right now. They may not be enabled in this environment."


def _stamp(value, nullable=False):
    if value is None:
        return nullable
    try:
        return isinstance(value, str) and len(value) <= 64 and datetime.fromisoformat(value).tzinfo is not None
    except ValueError:
        return False


def _text(value):
    return isinstance(value, str) and len(value) <= 2000


def valid_measure(item):
    try:
        appeal = item["appeal"]
        return (isinstance(item, dict) and set(item) == PRIVATE and valid_id(item["id"]) and item["kind"] in KIND_NAMES
                and isinstance(item["reason_code"], str) and CODE.fullmatch(item["reason_code"]) is not None
                and isinstance(item["policy_version"], str) and VERSION.fullmatch(item["policy_version"]) is not None
                and _stamp(item["issued_at"]) and _stamp(item["expires_at"], True) and _stamp(item["lifted_at"], True)
                and type(item["active"]) is bool and not (item["active"] and item["lifted_at"] is not None)
                and (appeal is None or isinstance(appeal, dict) and set(appeal) == {"id", "status"}
                     and valid_id(appeal["id"]) and appeal["status"] in {"open", "upheld", "lifted"})
                and valid_id(item["creator_id"]) and _text(item["reason"]) and valid_id(item["issued_by"])
                and (item["lifted_by"] is None or valid_id(item["lifted_by"])) and _text(item["lift_reason"])
                and (item["lifted_by"] is None) == (item["lifted_at"] is None))
    except (TypeError, KeyError, AttributeError):
        return False


def valid_measures(page, creator_id):
    return (isinstance(page, dict) and set(page) == {"items"} and isinstance(page["items"], list)
            and len(page["items"]) <= 50
            and all(valid_measure(item) and item["creator_id"] == creator_id for item in page["items"]))


def valid_appeal(item):
    try:
        return (isinstance(item, dict)
                and set(item) == {"id", "status", "created_at", "reason", "restriction", "decided_at", "decision_reason"}
                and valid_id(item["id"]) and item["status"] in {"open", "upheld", "lifted"} and _stamp(item["created_at"])
                and _text(item["reason"]) and _text(item["decision_reason"]) and _stamp(item["decided_at"], True)
                and (item["status"] == "open") == (item["decided_at"] is None) and valid_measure(item["restriction"]))
    except (TypeError, KeyError, AttributeError):
        return False


def valid_appeal_page(page, cursor=None):
    if (not isinstance(page, dict) or set(page) != {"items", "next_cursor"} or not isinstance(page["items"], list)
            or len(page["items"]) > 20 or not all(valid_appeal(item) and item["status"] == "open" for item in page["items"])):
        return False
    ids = [item["id"] for item in page["items"]]
    return (len(set(ids)) == len(ids) and cursor not in ids
            and (page["next_cursor"] is None or bool(ids) and page["next_cursor"] == ids[-1] != cursor))


def valid_search(page):
    return (isinstance(page, dict) and set(page) == {"items", "next_cursor"} and isinstance(page["items"], list)
            and len(page["items"]) <= 20
            and all(isinstance(item, dict) and set(item) == {"id", "handle", "bio", "status", "display_name", "location"}
                    and valid_id(item["id"]) and isinstance(item["handle"], str)
                    and re.fullmatch(r"[a-z0-9_]{3,40}", item["handle"]) is not None
                    and isinstance(item["display_name"], str) and len(item["display_name"]) <= 100
                    for item in page["items"]))


def _proof(request, operation, target_id):
    return views._intent(request, "measure-" + operation, target_id)


def _intent(request, operation, target_id, **extra):
    return signing.dumps({**_proof(request, operation, target_id), **extra}, salt=SALT)


def _checked_intent(request, operation, target_id):
    """The signed intent's extra fields, or None when it is missing, expired or bound to something else."""
    try:
        intent = signing.loads(request.POST.get("intent", ""), salt=SALT, max_age=900)
        proof = _proof(request, operation, target_id)
        if not isinstance(intent, dict) or {name: intent.get(name) for name in proof} != proof:
            return None
        return {name: value for name, value in intent.items() if name not in proof}
    except (signing.BadSignature, TypeError, ValueError):
        return None


def _administrator(request):
    return request.admin_account["roles"] == ["administrator"]


def _reason(request, name="reason"):
    reason = request.POST.get(name, "")
    return reason.strip() if 10 <= len(reason.strip()) <= len(reason) <= 2000 else None


@views.privileged
def find(request):
    """Find a creator by handle, or open one by creator ID."""
    if request.method != "GET":
        return HttpResponseNotAllowed(["GET"])
    if not _administrator(request):
        return views.error_page(request, status=403)
    if set(request.GET) - {"q", "creator"} or any(len(request.GET.getlist(k)) != 1 for k in request.GET):
        return views.error_page(request, status=400)
    creator = request.GET.get("creator", "").strip()
    if creator:
        if not valid_id(creator):
            return views._render(request, "measures_find.html", {
                "title": "Creator measures", "error": "Enter a creator ID in the form 8-4-4-4-12."}, status=400)
        return redirect(reverse("creator-measures", args=[creator.lower()]))
    query, results, error = request.GET.get("q", "").strip(), None, None
    if query:
        if len(query) > 100 or any(ord(char) < 32 for char in query):
            return views.error_page(request, status=400)
        status, page = views._api("/creators/search?" + urlencode({"q": query}), token=request.gateway_token,
                                  response_limit=262144)
        if status == 401:
            return views._expired(request)
        if status == 200 and valid_search(page):
            results = page["items"]
        else:
            error = UNAVAILABLE
    return views._render(request, "measures_find.html", {"title": "Creator measures", "query": query,
                                                         "results": results, "error": error})


def _creator_page(request, creator_id, *, error=None, status=200):
    code, page = views._api(f"/admin/creators/{creator_id}/restrictions", token=request.gateway_token,
                            response_limit=262144)
    if code == 401:
        return views._expired(request)
    available = code == 200 and valid_measures(page, str(creator_id))
    items = [{**item, "lift_intent": _intent(request, "lift", item["id"], creator=str(creator_id))
              if item["active"] else None} for item in page["items"]] if available else []
    return views._render(request, "measures_creator.html", {
        "title": "Creator measures", "creator_id": str(creator_id), "items": items, "available": available,
        "kinds": KINDS, "issue_intent": _intent(request, "issue", creator_id, key=secrets.token_urlsafe(32)),
        "error": error or (None if available else UNAVAILABLE), "notice": request.session.pop(NOTICE, None)},
        status=status)


def _expires(value):
    """A `datetime-local` value read as UTC, or None when left blank."""
    if not value:
        return None
    stamp = datetime.strptime(value, "%Y-%m-%dT%H:%M").replace(tzinfo=timezone.utc)
    if stamp <= datetime.now(timezone.utc):
        raise ValueError("The end time must be in the future")
    return stamp.isoformat()


@views.privileged
def creator(request, target_id):
    creator_id = target_id
    if request.method not in ("GET", "POST"):
        return HttpResponseNotAllowed(["GET", "POST"])
    if not _administrator(request):
        return views.error_page(request, status=403)
    if request.GET:
        return views.error_page(request, status=400)
    if request.method == "GET":
        return _creator_page(request, creator_id)
    operation = request.POST.get("operation")
    if operation == "issue":
        extra = _checked_intent(request, "issue", creator_id)
        if extra is None or set(extra) != {"key"} or not KEY.fullmatch(str(extra["key"])):
            return views.error_page(request, status=400)
        kind, code, version = (request.POST.get(name, "").strip() for name in ("kind", "reason_code", "policy_version"))
        reason = _reason(request)
        try:
            expires_at = _expires(request.POST.get("expires_at", "").strip())
        except ValueError:
            return _creator_page(request, creator_id, error=REFUSED[400], status=400)
        if kind not in KIND_NAMES or not CODE.fullmatch(code) or not VERSION.fullmatch(version) or reason is None:
            return _creator_page(request, creator_id, error=REFUSED[400], status=400)
        status, result = views._api(f"/admin/creators/{creator_id}/restrictions", method="POST",
                                    token=request.gateway_token, idempotency_key=extra["key"],
                                    data={"kind": kind, "reason_code": code, "policy_version": version,
                                          "reason": reason, "expires_at": expires_at})
        valid = status in (200, 201) and valid_measure(result) and result["creator_id"] == str(creator_id) \
            and result["kind"] == kind
        notice = ("Measure issued. The creator sees it in the app." if status == 201
                  else "This measure was already recorded.")
    elif operation == "lift":
        target = request.POST.get("restriction_id", "")
        extra = _checked_intent(request, "lift", target) if valid_id(target) else None
        if extra != {"creator": str(creator_id)}:
            return views.error_page(request, status=400)
        reason = _reason(request, "lift_reason")
        if reason is None:
            return _creator_page(request, creator_id, error=REFUSED[400], status=400)
        status, result = views._api(f"/admin/creator-restrictions/{target}/lift", method="POST",
                                    token=request.gateway_token, data={"reason": reason})
        valid = status == 200 and valid_measure(result) and result["id"] == target and result["lifted_at"] is not None
        notice = "Measure lifted. The creator is reinstated for what it blocked."
    else:
        return views.error_page(request, status=400)
    if status == 401:
        return views._expired(request)
    if valid:
        request.session[NOTICE] = notice
        return redirect(reverse("creator-measures", args=[creator_id]))
    if status in REFUSED:
        return _creator_page(request, creator_id, error=REFUSED[status], status=status)
    return _creator_page(request, creator_id, error=UNAVAILABLE, status=503)


def _appeals_page(request, cursor, *, error=None, status=200):
    path = "/admin/creator-restriction-appeals" + ("?" + urlencode({"cursor": cursor}) if cursor else "")
    code, page = views._api(path, token=request.gateway_token, response_limit=524288)
    if code == 401:
        return views._expired(request)
    available = code == 200 and valid_appeal_page(page, cursor)
    items = [{**item, "intent": _intent(request, "decide", item["id"])} for item in page["items"]] if available else []
    return views._render(request, "measures_appeals.html", {
        "title": "Measure appeals", "items": items, "available": available, "decisions": DECISIONS,
        "next_query": urlencode({"cursor": page["next_cursor"]}) if available and page["next_cursor"] else None,
        "error": error or (None if available else UNAVAILABLE), "notice": request.session.pop(NOTICE, None)},
        status=status)


@views.privileged
def appeals(request):
    if request.method not in ("GET", "POST"):
        return HttpResponseNotAllowed(["GET", "POST"])
    if not _administrator(request):
        return views.error_page(request, status=403)
    if set(request.GET) - {"cursor"} or any(len(request.GET.getlist(k)) != 1 for k in request.GET):
        return views.error_page(request, status=400)
    cursor = request.GET.get("cursor")
    if cursor is not None and not valid_id(cursor):
        return views.error_page(request, status=400)
    if request.method == "GET":
        return _appeals_page(request, cursor)
    target = request.POST.get("appeal_id", "")
    if not valid_id(target) or _checked_intent(request, "decide", target) != {}:
        return views.error_page(request, status=400)
    decision, reason = request.POST.get("decision", ""), _reason(request)
    if decision not in DECISIONS or reason is None:
        return _appeals_page(request, cursor, error=REFUSED[400], status=400)
    status, result = views._api(f"/admin/creator-restriction-appeals/{target}/decision", method="POST",
                                token=request.gateway_token, data={"decision": decision, "reason": reason})
    if status == 401:
        return views._expired(request)
    if status == 200 and valid_appeal(result) and result["id"] == target and result["status"] != "open":
        request.session[NOTICE] = ("Appeal decided: the measure was lifted." if decision == "lift"
                                   else "Appeal decided: the measure stays in place.")
        return redirect(reverse("creator-measure-appeals"))
    return _appeals_page(request, cursor, error=REFUSED.get(status, UNAVAILABLE), status=status if status in REFUSED else 503)
