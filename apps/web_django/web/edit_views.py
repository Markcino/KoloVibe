"""Decision A (RV2-01): reviewing held edits to published videos.

The Gateway and Moderation decide who may see and decide each edit; this console only validates their answers,
shows the live and proposed text side by side, and carries a signed, session-bound intent for each decision.
"""

import re
import secrets
from urllib.parse import urlencode

from django.core import signing
from django.http import HttpResponseNotAllowed
from django.views.decorators.http import require_GET

from . import views
from .api_contracts import valid_id
from .reviewer_contracts import valid_edit_detail

SALT = "admin-edit-decision"
ACTIONS = ("approve", "reject")
FIELDS = (("title", "Title"), ("description", "Description"), ("category", "Category"), ("tags", "Tags"))


def valid_edit_page(page, cursor=None):
    if not isinstance(page, dict) or set(page) != {"items", "next_cursor"} or not isinstance(page["items"], list):
        return False
    items = page["items"]
    if len(items) > 20 or not all(
            isinstance(item, dict) and set(item) == {"id", "video_id", "title", "submitted_at"}
            and valid_id(item["id"]) and valid_id(item["video_id"])
            and isinstance(item["title"], str) and 1 <= len(item["title"]) <= 160
            and isinstance(item["submitted_at"], str) and len(item["submitted_at"]) <= 64 for item in items):
        return False
    ids = [item["id"] for item in items]
    if ids != sorted(set(ids)) or cursor is not None and any(item_id <= cursor for item_id in ids):
        return False
    return page["next_cursor"] is None or len(items) == 20 and page["next_cursor"] == ids[-1]


def _proof(request, target_id):
    return views._intent(request, "edits", target_id)


@views.privileged
@require_GET
def queue(request):
    if set(request.GET) - {"cursor"} or any(len(request.GET.getlist(key)) != 1 for key in request.GET):
        return views.error_page(request, status=400)
    cursor = request.GET.get("cursor")
    if cursor is not None and not valid_id(cursor):
        return views.error_page(request, status=400)
    status, page = views._api("/moderation/edits" + ("?" + urlencode({"cursor": cursor}) if cursor else ""),
                              token=request.gateway_token, response_limit=524288)
    if status != 200:
        return views._gateway_error(request, status)
    if not valid_edit_page(page, cursor):
        return views.error_page(request)
    return views._render(request, "edit_list.html", {
        "title": "Video edits", "items": page["items"],
        "next_query": urlencode({"cursor": page["next_cursor"]}) if page["next_cursor"] else None})


def _rows(edit):
    rows = []
    for name, label in FIELDS:
        live, proposed = edit["live"][name], edit["proposed"][name]
        if name == "tags":
            live, proposed = " ".join("#" + tag for tag in live), " ".join("#" + tag for tag in proposed)
        rows.append({"label": label, "live": live or "", "proposed": proposed or "", "changed": live != proposed})
    return rows


@views.privileged
def detail(request, target_id):
    if request.method not in ("GET", "POST"):
        return HttpResponseNotAllowed(["GET", "POST"])
    if request.GET:
        return views.error_page(request, status=400)
    if request.method == "POST":
        try:
            intent = signing.loads(request.POST.get("intent", ""), salt=SALT, max_age=900)
            key, video_id = intent.pop("key"), intent.pop("video")
            if (intent != _proof(request, target_id) or not valid_id(video_id)
                    or not re.fullmatch(r"[A-Za-z0-9_-]{16,128}", key)):
                raise ValueError
        except (signing.BadSignature, ValueError, TypeError, AttributeError, KeyError):
            return views.error_page(request, status=400)
        action, reason = request.POST.get("action", ""), request.POST.get("reason", "")
        if action not in ACTIONS or not 10 <= len(reason.strip()) <= len(reason) <= 2000:
            return views.error_page(request, status=400)
        status, result = views._api(f"/moderation/edits/{target_id}/decisions", method="POST",
                                    token=request.gateway_token, data={"action": action, "reason": reason.strip()},
                                    idempotency_key=key)
        if status not in (200, 201):
            return views._gateway_error(request, status)
        if not views.valid_decision(result, video_id, action):
            return views.error_page(request)
        return views._render(request, "edit_result.html", {"title": "Decision recorded", "action": action})
    status, data = views._api(f"/moderation/edits/{target_id}", token=request.gateway_token, response_limit=524288)
    if status != 200:
        return views._gateway_error(request, status)
    if not valid_edit_detail(data) or data["edit"]["id"] != str(target_id):
        return views.error_page(request)
    edit = data["edit"]
    intent = signing.dumps({**_proof(request, target_id), "key": secrets.token_urlsafe(32), "video": edit["video_id"]},
                           salt=SALT)
    return views._render(request, "edit_detail.html", {
        "title": "Video edit review", "edit": edit, "rows": _rows(edit), "decisions": data["decisions"],
        "intent": intent if edit["status"] == "pending" else None, "actions": ACTIONS})
