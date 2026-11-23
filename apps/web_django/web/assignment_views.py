"""Administrator-only explicit grants: which moderator may review one video, report or appeal."""

from urllib.parse import urlencode

from django.core import signing
from django.http import HttpResponseNotAllowed
from django.shortcuts import redirect
from django.urls import reverse

from . import views
from .admin_contracts import valid_assignment, valid_assignment_list
from .api_contracts import valid_id
from .invitation_contracts import valid_page

SALT = "admin-assignment"
NOTICE = "assignment_notice"
ROSTER_PAGES = 4


def _proof(request, kind, target_id):
    return views._intent(request, "assignment-" + kind, target_id)


def roster(request):
    """Accepted moderators as {account id: display name}, or None when Identity cannot answer."""
    people, cursor = {}, None
    for _ in range(ROSTER_PAGES):
        status, page = views._api("/admin/moderator-invitations" + ("?" + urlencode({"cursor": cursor}) if cursor else ""),
                                  token=request.gateway_token)
        if status != 200 or not valid_page(page) or page["next_cursor"] is not None and page["next_cursor"] == cursor:
            return None
        people.update({row["account_id"]: row["display_name"] for row in page["items"] if row["status"] == "accepted"})
        cursor = page["next_cursor"]
        if cursor is None:
            break
    return people


def panel(request, kind, target_id):
    """Template context for the detail page. Failure degrades to an explicit unavailable state."""
    status, listing = views._api("/admin/moderation/assignments?" + urlencode({"scope": kind, "target": str(target_id)}),
                                 token=request.gateway_token)
    people = roster(request) if status == 200 else None
    if people is None or not valid_assignment_list(listing, kind, str(target_id)):
        return {"available": False}
    assigned = [row["moderator_id"] for row in listing["items"]]
    return {
        "available": True,
        "assigned": [{"id": account, "name": people.get(account)} for account in assigned],
        "candidates": [{"id": account, "name": name} for account, name in
                       sorted(people.items(), key=lambda item: (item[1].casefold(), item[0])) if account not in assigned],
        "intent": signing.dumps(_proof(request, kind, target_id), salt=SALT),
        "action": reverse(f"moderation-{kind}-assign", args=[target_id])
                  + ("?" + urlencode({"cursor": request.GET["cursor"]}) if "cursor" in request.GET else ""),
        "notice": request.session.pop(NOTICE, None),
    }


@views.privileged
def assign(request, kind, target_id):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    if request.admin_account["roles"] != ["administrator"]:
        return views.error_page(request, status=403)
    if views._queue_query(request, kind) is None:
        return views.error_page(request, status=400)
    try:
        if signing.loads(request.POST.get("intent", ""), salt=SALT, max_age=900) != _proof(request, kind, target_id):
            raise ValueError
    except (signing.BadSignature, ValueError, TypeError):
        return views.error_page(request, status=400)
    moderator, active = request.POST.get("moderator_id", ""), request.POST.get("active")
    if not valid_id(moderator) or active not in ("0", "1"):
        return views.error_page(request, status=400)
    if active == "1":
        people = roster(request)
        if people is None:
            return views.error_page(request)
        if moderator not in people:
            return views.error_page(request, status=400)
    data = {"scope": kind, "target_id": str(target_id), "moderator_id": moderator, "active": active == "1"}
    status, result = views._api("/admin/moderation/assignments", method="POST", data=data, token=request.gateway_token)
    if status != 200:
        return views._gateway_error(request, status)
    if not valid_assignment(result, data):
        return views.error_page(request)
    request.session[NOTICE] = "assigned" if data["active"] else "revoked"
    cursor = request.GET.get("cursor")
    return redirect(reverse(f"moderation-{kind}-detail", args=[target_id]) + ("?" + urlencode({"cursor": cursor}) if cursor else ""))
