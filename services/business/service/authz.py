"""The ONE entitlement module (BZ-R-033). Other modules never query BusinessMembership directly.

Non-entitlement is always 404, identical to an unknown id, so object existence is never disclosed (BZ-R-034).
"""
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from .errors import not_found
from .models import Business, BusinessMembership

OWNER, STAFF = BusinessMembership.Role.OWNER, BusinessMembership.Role.STAFF
ACTIVE = BusinessMembership.Status.ACTIVE
ANY = (OWNER, STAFF)

# The identity roles an operation may name. Moderators and administrators can never hold a membership (conflict of interest).
CUSTOMER = ("viewer", "creator")
REVIEWERS = ("moderator", "administrator")
EVERYONE = ("anonymous",) + CUSTOMER + REVIEWERS


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


# ---- reviewer authority (explicit scoped grants; administrators need one too) -------------------------------------
from .models import ReviewerGrant  # noqa: E402


def has_grant(reviewer_id, scope, business_id=None):
    grants = ReviewerGrant.objects.filter(reviewer_account_id=reviewer_id, scope=scope, active=True)
    return grants.filter(Q(target_business_id__isnull=True) | Q(target_business_id=business_id)).exists()


def granted_targets(reviewer_id, scope):
    """(all_businesses, set_of_business_ids) the reviewer may act on."""
    rows = list(ReviewerGrant.objects.filter(reviewer_account_id=reviewer_id, scope=scope, active=True)
                .values_list("target_business_id", flat=True))
    return (None in rows, {r for r in rows if r is not None})


def put_grant(reviewer_id, scope, target_business_id, active, granted_by):
    grant, created = ReviewerGrant.objects.select_for_update().get_or_create(
        reviewer_account_id=reviewer_id, scope=scope, target_business_id=target_business_id,
        defaults={"active": active, "granted_by_account_id": granted_by})
    if not created and (grant.active != active):
        grant.active, grant.granted_by_account_id = active, granted_by
        grant.save(update_fields=["active", "granted_by_account_id"])
    return grant


def is_affiliated(account_id, business):
    """A reviewer is affiliated if they created the business or hold/held any membership of it."""
    return (business.created_by_account_id == account_id
            or BusinessMembership.objects.filter(business=business, account_id=account_id).exists())
