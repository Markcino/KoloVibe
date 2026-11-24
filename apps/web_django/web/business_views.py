"""Business administration in the protected console (DR-BZ-21): moderators and administrators only.

Everything is decided by the Gateway and the Business service: scope (reviewer grants), conflicts of interest,
state transitions and idempotency. This module presents their answers and carries a signed, session-bound,
expiring intent for each mutation. It never decides from browser state, never forwards a field it did not
validate, never echoes a gateway body, and puts only ids (never names, evidence or reasons) in URLs.

Not here, because no approved backend contract exists yet: suspension and restoration, appeals, listing and
impersonation complaints, ownership or staff disputes, moderation metrics, a business list or status endpoint.
"""

import re
import secrets
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlencode

from django.core import signing
from django.http import HttpResponseNotAllowed
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET

from . import account_lookup, assignment_views, views
from . import business_contracts as contracts
from .api_contracts import valid_id

SALT = "admin-business"
INTENT_MAX_AGE = 900
KEY = re.compile(r"[A-Za-z0-9_-]{16,128}")
CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
NOTICE = "business_notice"
REASON_HELP = "Lower-case letters and underscores, 3 to 40 characters, starting with a letter (for example documents_checked)."

# Outcomes a reviewer cannot take back from the console get a second, explicit step; nothing is sent until it.
CONFIRMED = {"verify", "reject", "revoke", "approve", "remove", "keep"}

QUEUES = {
    "verifications": {"path": "/moderation/business-verifications", "valid": contracts.valid_verification_queue,
                      "id": "case_id", "title": "Verification requests", "noun": "verification case"},
    "profiles": {"path": "/moderation/business-profile-revisions", "valid": contracts.valid_profile_queue,
                 "id": "revision_id", "title": "Profile reviews", "noun": "profile revision"},
    "reports": {"path": "/moderation/business-reports", "valid": contracts.valid_report_queue,
                "id": "report_id", "title": "Business reports", "noun": "report"},
}

# What each detail page can POST. `path` is appended to the item's gateway path.
OPERATIONS = {
    "verifications": {"claim": {"path": "/claim", "decisions": ()},
                      "decision": {"path": "/decision", "decisions": contracts.VERIFICATION_DECISIONS}},
    "profiles": {"decision": {"path": "/decision", "decisions": tuple(contracts.PROFILE_DECISIONS)}},
    "reports": {"decision": {"path": "/decision", "decisions": contracts.REPORT_DECISIONS}},
}

# Fixed copy for the business refusals a person can act on. Never the gateway's own words.
REFUSALS = {
    "claim_required": ("Claim the case first", "A case must be claimed by you before you can decide it."),
    "invalid_transition": ("That change isn't allowed now", "The item is no longer in a state that allows this decision. Reopen it to see its current state."),
    "idempotency_conflict": ("This request was already used", "That submission was already recorded with different details. Reopen the item and decide again."),
    "self_grant": ("You can't grant yourself access", "Ask another administrator to make this change."),
    "unknown_parent": ("Unknown parent category", "Choose a parent from the current list."),
    "depth_exceeded": ("Categories have two levels at most", "A category with children can't become a child, and a child can't have children."),
}


# ---- shared plumbing ------------------------------------------------------------------------------------------

def _refusal(request, title, message, status):
    account = getattr(request, "admin_account", None)
    return render(request, "status.html", {"title": title, "message": message, "code": status, "signed_in": True,
                                           "role": account["roles"][0]}, status=status)


def _failure(request, status, payload):
    """A gateway refusal as fixed copy: a known business code becomes specific advice, anything else a generic page."""
    if status == 409 and isinstance(payload, dict) and payload.get("code") in REFUSALS:
        title, message = REFUSALS[payload["code"]]
        return _refusal(request, title, message, 409)
    return views._gateway_error(request, status)


def _administrator_only(request):
    if request.admin_account["roles"] != ["administrator"]:
        return views.error_page(request, status=403)
    return None


def _proof(request, kind, target):
    return views._intent(request, "business-" + kind, target)


def _sign(request, kind, target, op):
    """An expiring token bound to this actor, this session, this item and this one operation, carrying the key
    that makes the decision idempotent. A replay of the same form reuses the key and so cannot apply twice."""
    return signing.dumps({**_proof(request, kind, target), "op": op, "key": secrets.token_urlsafe(32)}, salt=SALT)


def _open(request, kind, target, token):
    """The (operation, idempotency key) a valid intent authorises, or None."""
    try:
        data = signing.loads(token, salt=SALT, max_age=INTENT_MAX_AGE)
        op, key = data.pop("op"), data.pop("key")
        if data != _proof(request, kind, target) or not KEY.fullmatch(key) or not isinstance(op, str):
            return None
        return op, key
    except (signing.BadSignature, TypeError, ValueError, AttributeError, KeyError):
        return None


def _only_params(request, allowed):
    """Query parameters must be exactly the expected names, once each."""
    return not set(request.GET) - allowed and all(len(request.GET.getlist(key)) == 1 for key in request.GET)


def _search_text(raw):
    return raw is not None and len(raw) <= 80 and not CONTROL.search(raw)


def _context(request, section, **extra):
    return {"section": section, "is_administrator": request.admin_account["roles"] == ["administrator"], **extra}


def _queue_status(request, status):
    if status == 404:  # the route is closed (capability off) or absent in this environment
        return views._unavailable(request, "Business administration",
                                  "Business administration may not be enabled in this environment, or you have no access to it.")
    return views._gateway_error(request, status)


# ---- overview (C1) --------------------------------------------------------------------------------------------

@views.privileged
@require_GET
def overview(request):
    if not _only_params(request, {"q", "queue"}):
        return views.error_page(request, status=400)
    needle = request.GET.get("q", "")
    queue = request.GET.get("queue", "all")
    if not _search_text(needle) or queue not in {"all", *QUEUES}:
        return views.error_page(request, status=400)
    with ThreadPoolExecutor(max_workers=len(QUEUES)) as pool:
        calls = {kind: pool.submit(views._api, spec["path"], token=request.gateway_token, response_limit=131072)
                 for kind, spec in QUEUES.items()}
        answers = {kind: call.result() for kind, call in calls.items()}
    if any(status == 401 for status, _ in answers.values()):
        return views._expired(request)
    summaries, businesses = {}, {}
    for kind, (status, page) in answers.items():
        spec = QUEUES[kind]
        if status == 200 and spec["valid"](page):
            items = page["items"]
            summaries[kind] = {"kind": kind, "title": spec["title"], "available": True, "count": len(items), "more": page["next_cursor"] is not None,
                               "mine": sum(1 for i in items if i.get("assigned_to_you")),
                               "holds": sum(1 for i in items if i.get("system_hold")),
                               "oldest": min((i.get("submitted_at") or i.get("created_at") for i in items), default=None)}
            if queue in ("all", kind):
                for item in items:
                    row = businesses.setdefault(item["business_id"], {"id": item["business_id"], "name": None, "links": []})
                    row["name"] = row["name"] or item.get("display_name")
                    row["links"].append({"label": spec["title"], "url": reverse(f"business-{kind}-detail", args=[item[spec["id"]]])})
        else:
            summaries[kind] = {"kind": kind, "title": spec["title"], "available": False, "status": status}
    # (summaries is still a dict here)
    if all(not s["available"] and s["status"] == 404 for s in summaries.values()):
        return _queue_status(request, 404)
    if all(not s["available"] for s in summaries.values()):
        return views._gateway_error(request, next(s["status"] for s in summaries.values()))
    rows = sorted((r for r in businesses.values() if needle.casefold() in (r["name"] or "").casefold()),
                  key=lambda r: ((r["name"] or "~").casefold(), r["id"]))
    return views._render(request, "business_overview.html", _context(
        request, "overview", title="Business administration", summaries=list(summaries.values()), businesses=rows, needle=needle,
        selected_queue=queue, queues=QUEUES, notice=request.session.pop(NOTICE, None)))


# ---- queues (C2, C3) ------------------------------------------------------------------------------------------

@views.privileged
@require_GET
def queue(request, kind):
    spec = QUEUES[kind]
    if "find" in request.GET:  # jump to an item by id; the detail page and the owning service still authorise it
        target = request.GET["find"].strip().lower()
        if set(request.GET) != {"find"} or not valid_id(target):
            return views.error_page(request, status=400)
        return redirect(reverse(f"business-{kind}-detail", args=[target]))
    if not _only_params(request, {"cursor", "q", "mine"}):
        return views.error_page(request, status=400)
    cursor, needle, mine = request.GET.get("cursor"), request.GET.get("q", ""), request.GET.get("mine")
    if (cursor is not None and not valid_id(cursor) or not _search_text(needle)
            or mine not in (None, "1") or mine and kind != "verifications"):
        return views.error_page(request, status=400)
    status, page = views._api(spec["path"] + ("?" + urlencode({"cursor": cursor}) if cursor else ""),
                              token=request.gateway_token, response_limit=131072)
    if status != 200:
        return _queue_status(request, status)
    if not spec["valid"](page, cursor):
        return views.error_page(request)
    items = [{**i, "item_id": i[spec["id"]]} for i in page["items"]
             if needle.casefold() in (i.get("display_name") or "").casefold() and (not mine or i["assigned_to_you"])]
    keep = {key: value for key, value in (("q", needle), ("mine", mine)) if value}
    return views._render(request, "business_queue.html", _context(
        request, kind, title=spec["title"], kind=kind, items=items, needle=needle, mine=mine,
        next_query=urlencode({**keep, "cursor": page["next_cursor"]}) if page["next_cursor"] else None,
        first_query=urlencode(keep), shown=len(page["items"])))


# ---- item detail and decisions (C2, C3) -------------------------------------------------------------------------

def _fetch_detail(request, kind, target):
    path = QUEUES[kind]["path"] + "/" + str(target)
    status, detail = views._api(path, token=request.gateway_token, response_limit=131072)
    if status != 200:
        return status, None
    valid = {"verifications": contracts.valid_verification_case, "profiles": contracts.valid_profile_revision,
             "reports": contracts.valid_report_case}[kind]
    return 200, detail if valid(detail, str(target)) else False


def _offered(kind, detail):
    """What the page offers, derived from the server's current answer only. The service re-decides on every POST."""
    if kind == "verifications":
        state = detail["state"]
        if state == "submitted":
            return {"claim": True, "decisions": ()}
        if state == "under_review" and detail["assigned_to_you"]:
            return {"claim": False, "decisions": ("verify", "reject", "request_info")}
        if state == "verified":
            return {"claim": False, "decisions": ("revoke",)}
        return {"claim": False, "decisions": ()}
    if kind == "profiles":
        return {"claim": False, "decisions": tuple(contracts.PROFILE_DECISIONS) if detail["state"] == "pending_review" else ()}
    return {"claim": False, "decisions": contracts.REPORT_DECISIONS}


@views.privileged
def detail(request, kind, target_id):
    if request.method not in ("GET", "POST"):
        return HttpResponseNotAllowed(["GET", "POST"])
    if not _only_params(request, set()):
        return views.error_page(request, status=400)
    if request.method == "POST":
        return _decide(request, kind, target_id)
    status, item = _fetch_detail(request, kind, target_id)
    if status != 200:
        return views._gateway_error(request, status)
    if item is False:
        return views.error_page(request)
    offered = _offered(kind, item)
    return views._render(request, f"business_{kind[:-1]}.html", _context(
        request, kind, title=QUEUES[kind]["title"], kind=kind, item=item, offered=offered, target_id=str(target_id),
        claim_intent=_sign(request, kind, target_id, "claim") if offered["claim"] else None,
        decision_intent=_sign(request, kind, target_id, "decision") if offered["decisions"] else None,
        reason_help=REASON_HELP))


def _decide(request, kind, target_id):
    opened = _open(request, kind, target_id, request.POST.get("intent", ""))
    if opened is None:
        return views.error_page(request, status=400)
    op, key = opened
    spec = OPERATIONS[kind].get(op)
    fields = set(request.POST) - {"csrfmiddlewaretoken"}
    allowed = {"intent"} if op == "claim" else {"intent", "decision", "reason_code", "confirmed"} | (
        {"note"} if kind == "verifications" else set())
    if spec is None or not fields <= allowed or any(len(request.POST.getlist(name)) != 1 for name in fields):
        return views.error_page(request, status=400)
    path = f"{QUEUES[kind]['path']}/{target_id}{spec['path']}"
    if op == "claim":
        status, result = views._api(path, method="POST", token=request.gateway_token, data={}, idempotency_key=key)
        if status not in (200, 201):
            return _failure(request, status, result)
        if not contracts.valid_claim(result, str(target_id)):
            return views.error_page(request)
        return redirect(reverse(f"business-{kind}-detail", args=[target_id]))
    decision, reason = request.POST.get("decision", ""), request.POST.get("reason_code", "")
    note = request.POST.get("note", "").strip()
    if (decision not in spec["decisions"] or not contracts.CODE.fullmatch(reason) or len(note) > 500 or CONTROL.search(note)):
        return views.error_page(request, status=400)
    if decision in CONFIRMED and request.POST.get("confirmed") != "1":
        return views._render(request, "business_confirm.html", _context(
            request, kind, title="Confirm your decision", kind=kind, target_id=str(target_id), decision=decision,
            reason_code=reason, note=note, intent=request.POST["intent"]))
    data = {"decision": decision, "reason_code": reason}
    if note:
        data["note"] = note
    status, result = views._api(path, method="POST", token=request.gateway_token, data=data, idempotency_key=key)
    if status not in (200, 201):
        return _failure(request, status, result)
    valid = {"verifications": lambda: contracts.valid_verification_decision(result, str(target_id), decision),
             "profiles": lambda: contracts.valid_profile_decision(result, str(target_id), decision),
             "reports": lambda: contracts.valid_report_decision(result, str(target_id), decision)}[kind]
    if not valid():
        return views.error_page(request)
    return views._render(request, "business_result.html", _context(
        request, kind, title="Decision recorded", kind=kind, decision=decision, target_id=str(target_id)))


# ---- categories (C4, administrators) ----------------------------------------------------------------------------

def _categories(request):
    status, listing = views._api("/business-categories", token=request.gateway_token, response_limit=262144)
    if status != 200:
        return status, None
    return 200, listing["items"] if contracts.valid_category_list(listing) else False


def _category_page(request, *, error=None, status=200):
    code, items = _categories(request)
    if code == 401:
        return views._expired(request)
    return views._render(request, "business_categories.html", _context(
        request, "categories", title="Business categories", categories=items if code == 200 else None,
        available=code == 200 and items is not False, error=error, notice=request.session.pop(NOTICE, None),
        intent=_sign(request, "categories", "categories", "upsert"), reason_help=None), status=status)


@views.privileged
def categories(request):
    if request.method not in ("GET", "POST"):
        return HttpResponseNotAllowed(["GET", "POST"])
    denied = _administrator_only(request)
    if denied:
        return denied
    if not _only_params(request, set()):
        return views.error_page(request, status=400)
    if request.method == "GET":
        return _category_page(request)
    opened = _open(request, "categories", "categories", request.POST.get("intent", ""))
    fields = set(request.POST) - {"csrfmiddlewaretoken"}
    if opened is None or opened[0] != "upsert" or not fields <= {"intent", "slug", "name", "parent", "active"} or any(
            len(request.POST.getlist(name)) != 1 for name in fields):
        return views.error_page(request, status=400)
    slug, name = request.POST.get("slug", ""), request.POST.get("name", "").strip()
    parent, active = request.POST.get("parent", ""), request.POST.get("active", "")
    if (not contracts.SLUG.fullmatch(slug) or not 2 <= len(name) <= 80 or CONTROL.search(name)
            or parent and not contracts.SLUG.fullmatch(parent) or active not in ("0", "1")):
        return _category_page(request, error="Enter a slug (lower-case letters, digits and hyphens), a name of 2 to 80 characters, "
                                              "and choose whether the category is active.", status=400)
    code, items = _categories(request)
    if code == 401:
        return views._expired(request)
    if code != 200 or items is False:
        return views.error_page(request)
    if parent and parent not in {item["slug"] for item in items}:
        return _category_page(request, error="Choose a parent from the current list.", status=400)
    data = {"name": name, "parent": parent or None, "active": active == "1"}
    status, result = views._api(f"/admin/business-categories/{slug}", method="PUT", token=request.gateway_token,
                                data=data, idempotency_key=opened[1])
    if status != 200:
        return _failure(request, status, result)
    if not contracts.valid_category(result) or (result["slug"], result["name"], result["active"], result["parent"]) != (
            slug, name, data["active"], parent or None):
        return views.error_page(request)
    request.session[NOTICE] = "Category saved."
    return redirect(reverse("business-categories"))


# ---- access: reviewer and registration grants (C4, administrators) -------------------------------------------------

def _grants_page(request, *, candidate=None, error=None, status=200, lookup_error=None):
    people = assignment_views.roster(request)
    return views._render(request, "business_grants.html", _context(
        request, "grants", title="Business access", people=sorted((people or {}).items(), key=lambda p: (p[1].casefold(), p[0])),
        people_available=people is not None, scopes=sorted(contracts.SCOPES), candidate=candidate, error=error,
        lookup_error=lookup_error, notice=request.session.pop(NOTICE, None),
        reviewer_intent=_sign(request, "reviewer-grants", "reviewer", "reviewer"),
        lookup_intent=_sign(request, "registration-grants", "lookup", "lookup"),
        registration_intent=_sign(request, "registration-grants", candidate["account_id"], "registration") if candidate else None),
        status=status)


@views.privileged
def grants(request):
    if request.method not in ("GET", "POST"):
        return HttpResponseNotAllowed(["GET", "POST"])
    denied = _administrator_only(request)
    if denied:
        return denied
    if not _only_params(request, set()):
        return views.error_page(request, status=400)
    if request.method == "GET":
        return _grants_page(request)
    form = request.POST.get("form")
    if form == "reviewer":
        return _reviewer_grant(request)
    if form == "lookup":
        return _lookup(request)
    if form == "registration":
        return _registration_grant(request)
    return views.error_page(request, status=400)


def _strict(request, opened, allowed):
    fields = set(request.POST) - {"csrfmiddlewaretoken"}
    return opened is not None and fields <= allowed | {"form"} and all(len(request.POST.getlist(n)) == 1 for n in fields)


def _reviewer_grant(request):
    opened = _open(request, "reviewer-grants", "reviewer", request.POST.get("intent", ""))
    if not _strict(request, opened, {"intent", "reviewer", "scope", "target", "active"}) or opened[0] != "reviewer":
        return views.error_page(request, status=400)
    reviewer, scope = request.POST.get("reviewer", ""), request.POST.get("scope", "")
    target, active = request.POST.get("target", "").strip().lower(), request.POST.get("active", "")
    if not valid_id(reviewer) or scope not in contracts.SCOPES or target and not valid_id(target) or active not in ("0", "1"):
        return _grants_page(request, error="Choose a reviewer, a scope and whether to grant or revoke. A target business must be a valid id.", status=400)
    if active == "1":  # the person must be an accepted moderator the service knows about; revoking never needs the roster
        people = assignment_views.roster(request)
        if people is not None and reviewer not in people:
            people = assignment_views.roster(request, fresh=True)
        if people is None:
            return views.error_page(request)
        if reviewer not in people:
            return _grants_page(request, error="Choose a reviewer from the list.", status=400)
    data = {"reviewer_account_id": reviewer, "scope": scope, "active": active == "1"}
    if target:
        data["target_business_id"] = target
    status, result = views._api("/admin/business-reviewer-grants", method="PUT", token=request.gateway_token, data=data,
                                idempotency_key=opened[1])
    if status != 200:
        return _failure(request, status, result)
    if not contracts.valid_reviewer_grant(result, scope, data["active"]):
        return views.error_page(request)
    request.session[NOTICE] = "Reviewer access granted." if data["active"] else "Reviewer access revoked."
    return redirect(reverse("business-grants"))


def _lookup(request):
    opened = _open(request, "registration-grants", "lookup", request.POST.get("intent", ""))
    if not _strict(request, opened, {"intent", "email"}) or opened[0] != "lookup":
        return views.error_page(request, status=400)
    outcome, value, status = account_lookup.find(request, request.POST.get("email", ""), verb="given registration access")
    if outcome == "expired":
        return views._expired(request)
    if outcome == "found":
        return _grants_page(request, candidate=value)
    return _grants_page(request, lookup_error=value, status=status)


def _registration_grant(request):
    account = request.POST.get("account_id", "")
    opened = _open(request, "registration-grants", account, request.POST.get("intent", ""))
    if not _strict(request, opened, {"intent", "account_id", "active"}) or opened[0] != "registration" or not valid_id(account):
        return views.error_page(request, status=400)
    active = request.POST.get("active", "")
    if active not in ("0", "1"):
        return views.error_page(request, status=400)
    status, result = views._api(f"/admin/business-registration-grants/{account}", method="PUT", token=request.gateway_token,
                                data={"active": active == "1"}, idempotency_key=opened[1])
    if status != 200:
        return _failure(request, status, result)
    if not contracts.valid_registration_grant(result, account, active == "1"):
        return views.error_page(request)
    request.session[NOTICE] = ("Registration access granted. The person can now register a business in the app." if active == "1"
                               else "Registration access revoked.")
    return redirect(reverse("business-grants"))
