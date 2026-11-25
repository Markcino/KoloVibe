"""Administrator-only exact-email lookup, used to invite an existing account as a creator.

Returns only what the administrator needs to confirm they have the right person. Privileged and
inactive accounts answer exactly like unknown addresses, and each lookup is rate-limited and audited,
so this cannot be used to enumerate accounts.
"""

from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST

from .accounts import _body, _email_field, _error
from .models import Account
from .moderator_invitations import actor, budget
from .security_audit import record

LOOKUPS_PER_HOUR = 30
UNAVAILABLE = "Account unavailable"


@never_cache
@require_POST
def lookup(request):
    try:
        data = _body(request, {"access_token", "email"})
        if "access_token" not in data:
            raise ValueError
    except (ValueError, TypeError, UnicodeError):
        return _error("Invalid email address")
    with transaction.atomic():
        # Authority is decided before the body is judged, so a caller without it learns nothing about the request schema.
        administrator, error = actor(data)
        if error is not None:
            return error
        try:
            email = _email_field(data)
        except (KeyError, ValueError, TypeError, UnicodeError, ValidationError):
            return _error("Invalid email address")
        if not budget("lookup:" + str(administrator.id), LOOKUPS_PER_HOUR, timezone.now(), timedelta(hours=1)):
            return _error("Too many lookups", 429)
        record("account.creator_candidate_looked_up", administrator.id)
        account = Account.objects.filter(email=email, is_active=True,
                                         role__in=(Account.Role.VIEWER, Account.Role.CREATOR)).first()
        if account is None:
            return _error(UNAVAILABLE, 404)
        return JsonResponse({"account_id": str(account.id), "display_name": account.display_name,
                             "role": account.role, "email_verified": account.email_verified_at is not None})
