"""B1 — business identity, ownership and staff. Every state change is audited in its own transaction."""
import hashlib
import hmac
import secrets

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from . import authz, limits, security_audit, step_up
from .api import Result, operation
from .errors import ApiError, not_found
from .models import Business, RegistrationGrant, StaffInvitation
from .present import business_view, invitation_view, member_view
from .validation import PAGE, boolean, clean_text, page_params, parse, uuid_text

CUSTOMER = authz.CUSTOMER  # moderators and administrators can never hold a membership (conflict of interest)
OWNER, STAFF = authz.OWNER, authz.STAFF


def _digest(code):
    return hmac.new(settings.SECRET_KEY.encode(), ("staff-invite:" + code).encode(), hashlib.sha256).hexdigest()


@operation("register", roles=CUSTOMER, verified_email=True, idempotent=True, budget="register")
def register(ctx, data):
    fields = parse(data, {"display_name": (lambda v: clean_text(v, 2, 80), True),
                          "legal_name": (lambda v: clean_text(v, 2, 160), True)})
    with transaction.atomic():
        if limits.REGISTRATION_INVITE_ONLY:
            grant = RegistrationGrant.objects.select_for_update().filter(account_id=ctx.actor_id, active=True).first()
            if grant is None:
                raise ApiError(403, "Business registration is by invitation during the pilot", "invitation_required")
        open_count = Business.objects.filter(created_by_account_id=ctx.actor_id).exclude(
            state=Business.State.CLOSED).count()
        if open_count >= limits.MAX_BUSINESSES_PER_ACCOUNT:
            raise ApiError(409, "Business limit reached", "business_limit")
        business = Business.objects.create(created_by_account_id=ctx.actor_id, **fields)
        authz.grant(business, ctx.actor_id, OWNER, ctx.actor_id)
        security_audit.record("business.registered", ctx.actor_id, "business", business.id)
        security_audit.record("business.membership_granted", ctx.actor_id, "business", business.id)
    return Result(201, business_view(business, OWNER))


@operation("list_mine", roles=CUSTOMER, budget="read")
def list_mine(ctx, data):
    cursor, limit = page_params(parse(data, PAGE),
                                limits.PAGE_SIZE)
    query = authz.memberships_of(ctx.actor_id).order_by("id")
    if cursor is not None:
        query = query.filter(id__gt=cursor)
    page = list(query[:limit + 1])
    items = [business_view(m.business, m.role) for m in page[:limit]]
    return Result(200, {"items": items, "next_cursor": str(page[limit - 1].id) if len(page) > limit else None})


@operation("get_mine", roles=CUSTOMER, budget="read", member_roles=authz.ANY)
def get_mine(ctx, data):
    fields = parse(data, {"business_id": (uuid_text, True)})
    business, membership = authz.require_member(ctx.actor_id, fields["business_id"])
    return Result(200, business_view(business, membership.role))


@operation("staff_invite", roles=CUSTOMER, idempotent=True, budget="staff_invite", member_roles=(OWNER,))
def staff_invite(ctx, data):
    fields = parse(data, {"business_id": (uuid_text, True), "label": (lambda v: clean_text(v, 1, 40), True)})
    now = timezone.now()
    with transaction.atomic():
        authz.lock_business(fields["business_id"])
        business, _ = authz.require_member(ctx.actor_id, fields["business_id"], (OWNER,), lock=True)
        if business.state == Business.State.CLOSED:
            raise ApiError(409, "Business is closed", "business_closed")
        pending = business.invitations.filter(redeemed_at__isnull=True, revoked_at__isnull=True,
                                              expires_at__gt=now).count()
        if pending >= limits.MAX_PENDING_INVITATIONS_PER_BUSINESS or (
                pending + authz.active_count(business, STAFF) >= limits.MAX_ACTIVE_STAFF_PER_BUSINESS):
            raise ApiError(409, "Staff limit reached", "staff_limit")
        code = secrets.token_urlsafe(24)
        invitation = StaffInvitation.objects.create(
            business=business, code_digest=_digest(code), label=fields["label"],
            created_by_account_id=ctx.actor_id, expires_at=now + limits.STAFF_INVITATION_TTL)
        security_audit.record("business.invitation_created", ctx.actor_id, "business", business.id)
    # The code is returned once and is never stored or replayed; a lost code needs a new invitation.
    return Result(201, invitation_view(invitation, now), secret={"code": code})


@operation("staff_invitation_revoke", roles=CUSTOMER, idempotent=True, member_roles=(OWNER,))
def staff_invitation_revoke(ctx, data):
    fields = parse(data, {"business_id": (uuid_text, True), "invitation_id": (uuid_text, True)})
    with transaction.atomic():
        business, _ = authz.require_member(ctx.actor_id, fields["business_id"], (OWNER,))
        invitation = business.invitations.select_for_update().filter(pk=fields["invitation_id"]).first()
        if invitation is None:
            raise not_found()
        if invitation.redeemed_at is not None:
            raise ApiError(409, "Invitation already redeemed", "invitation_redeemed")
        if invitation.revoked_at is None:
            invitation.revoked_at = timezone.now()
            invitation.save(update_fields=["revoked_at"])
            security_audit.record("business.invitation_revoked", ctx.actor_id, "business", business.id)
    return Result(200, invitation_view(invitation, timezone.now()))


@operation("staff_redeem", roles=CUSTOMER, verified_email=True, idempotent=True, budget="staff_redeem")
def staff_redeem(ctx, data):
    fields = parse(data, {"code": (lambda v: clean_text(v, 16, 64), True)})
    now = timezone.now()
    with transaction.atomic():
        invitation = StaffInvitation.objects.select_for_update().select_related("business").filter(
            code_digest=_digest(fields["code"])).first()
        # One answer for unknown, used, revoked and expired codes: nothing is learned by guessing.
        if (invitation is None or invitation.redeemed_at or invitation.revoked_at or invitation.expires_at <= now
                or invitation.business.state == Business.State.CLOSED):
            raise ApiError(404, "Invitation unavailable")
        business = authz.lock_business(invitation.business_id)
        if authz.is_member(ctx.actor_id, business.id):
            raise ApiError(409, "Already a member of this business", "already_member")
        if authz.active_count(business, STAFF) >= limits.MAX_ACTIVE_STAFF_PER_BUSINESS:
            raise ApiError(409, "Staff limit reached", "staff_limit")
        membership = authz.grant(business, ctx.actor_id, STAFF, invitation.created_by_account_id)
        membership.label = invitation.label
        membership.save(update_fields=["label"])
        invitation.redeemed_by_account_id, invitation.redeemed_at = ctx.actor_id, now
        invitation.save(update_fields=["redeemed_by_account_id", "redeemed_at"])
        security_audit.record("business.invitation_redeemed", ctx.actor_id, "business", business.id)
        security_audit.record("business.membership_granted", ctx.actor_id, "business", business.id)
    return Result(200, business_view(business, STAFF))


@operation("member_list", roles=CUSTOMER, budget="read", member_roles=(OWNER,))
def member_list(ctx, data):
    fields = parse(data, {"business_id": (uuid_text, True)})
    business, _ = authz.require_member(ctx.actor_id, fields["business_id"], (OWNER,))
    now = timezone.now()
    members = [member_view(m, ctx.actor_id) for m in authz.members_of(business).order_by("created_at", "id")]
    invitations = [invitation_view(i, now) for i in business.invitations.filter(
        redeemed_at__isnull=True, revoked_at__isnull=True, expires_at__gt=now).order_by("created_at", "id")]
    return Result(200, {"members": members, "invitations": invitations})


@operation("member_remove", roles=CUSTOMER, idempotent=True, member_roles=(OWNER,))
def member_remove(ctx, data):
    """Owner removes a staff member. Needs a step-up proof for this business (BZ-R-036, Decision G)."""
    fields = parse(data, {"business_id": (uuid_text, True), "member_id": (uuid_text, True)})
    authz.require_member(ctx.actor_id, fields["business_id"], (OWNER,))
    step_up.require(ctx, "business.member_remove", fields["business_id"])
    with transaction.atomic():
        business = authz.lock_business(fields["business_id"])
        target = authz.members_of(business).filter(pk=fields["member_id"]).first()
        if target is None:
            raise not_found()
        if target.role != STAFF:
            raise ApiError(409, "Owners cannot be removed", "owner_protected")
        authz.revoke(target)
        security_audit.record("business.membership_revoked", ctx.actor_id, "business", business.id)
    return Result(200, {"status": "ok"})


@operation("member_leave", roles=CUSTOMER, idempotent=True, member_roles=authz.ANY)
def member_leave(ctx, data):
    """A staff member ends their own membership. Owners cannot leave: the last-owner rule and transfer are not enabled."""
    fields = parse(data, {"business_id": (uuid_text, True)})
    with transaction.atomic():
        business, membership = authz.require_member(ctx.actor_id, fields["business_id"], (STAFF, OWNER), lock=True)
        if membership.role == OWNER:
            raise ApiError(409, "An owner cannot leave the business", "owner_protected")
        authz.revoke(membership)
        security_audit.record("business.membership_revoked", ctx.actor_id, "business", business.id)
    return Result(200, {"status": "ok"})


@operation("registration_grant", roles=("administrator",), mfa=True, idempotent=True)
def registration_grant(ctx, data):
    fields = parse(data, {"account_id": (uuid_text, True), "active": (boolean, True)})
    with transaction.atomic():
        if fields["account_id"] == ctx.actor_id:
            raise ApiError(409, "Administrators cannot grant themselves", "self_grant")
        grant, _ = RegistrationGrant.objects.select_for_update().get_or_create(
            account_id=fields["account_id"], defaults={"granted_by_account_id": ctx.actor_id,
                                                       "active": fields["active"]})
        if grant.active != fields["active"]:
            grant.active, grant.granted_by_account_id = fields["active"], ctx.actor_id
            grant.save(update_fields=["active", "granted_by_account_id"])
        security_audit.record("business.registration_grant_changed", ctx.actor_id, "account", fields["account_id"])
    return Result(200, {"account_id": str(fields["account_id"]), "active": grant.active})
