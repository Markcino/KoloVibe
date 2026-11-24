"""The ONE entitlement module (BZ-R-033). Other modules never query BusinessMembership directly.

Non-entitlement is always 404, identical to an unknown id, so object existence is never disclosed (BZ-R-034).
"""
from django.db import transaction
from django.utils import timezone

from .errors import not_found
from .models import Business, BusinessMembership

OWNER, STAFF = BusinessMembership.Role.OWNER, BusinessMembership.Role.STAFF
ACTIVE = BusinessMembership.Status.ACTIVE
ANY = (OWNER, STAFF)


def require_member(actor_id, business_id, roles=ANY, *, lock=False):
    """Return (business, membership) for an active membership with an allowed role, else 404."""
    query = BusinessMembership.objects.select_related("business").filter(
        business_id=business_id, account_id=actor_id, status=ACTIVE, role__in=roles)
    if lock:
        query = query.select_for_update(of=("self",))
    membership = query.first()
    if membership is None:
        raise not_found()
    return membership.business, membership


def memberships_of(actor_id):
    """Active memberships of exactly this account (query is scoped by the authenticated actor)."""
    return BusinessMembership.objects.select_related("business").filter(account_id=actor_id, status=ACTIVE)


def members_of(business):
    return BusinessMembership.objects.filter(business=business, status=ACTIVE)


def grant(business, account_id, role, granted_by):
    return BusinessMembership.objects.create(business=business, account_id=account_id, role=role,
                                             granted_by_account_id=granted_by)


def revoke(membership):
    membership.status = BusinessMembership.Status.REVOKED
    membership.revoked_at = timezone.now()
    membership.save(update_fields=["status", "revoked_at"])


def active_count(business, role):
    return members_of(business).filter(role=role).count()


def is_member(actor_id, business_id):
    return BusinessMembership.objects.filter(business_id=business_id, account_id=actor_id, status=ACTIVE).exists()


def lock_business(business_id):
    """Serialize membership changes on one business (last-owner and cap invariants)."""
    with transaction.atomic():
        return Business.objects.select_for_update().filter(pk=business_id).first()
