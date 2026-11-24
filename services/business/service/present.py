"""Response shapes. Each is an explicit allowlist; role decides which private fields appear (matrix section 5)."""
from .models import Business, BusinessMembership


def business_view(business, role):
    data = {"id": str(business.id), "state": business.state, "my_role": role,
            "verified": business.state == Business.State.VERIFIED, "listed": False,
            "display_name": business.display_name, "created_at": business.created_at.isoformat()}
    if role == BusinessMembership.Role.OWNER:
        data["legal_name"] = business.legal_name  # private: never shown to staff
    return data


def member_view(membership, actor_id):
    return {"id": str(membership.id), "role": membership.role, "label": membership.label,
            "since": membership.created_at.isoformat(), "is_you": membership.account_id == actor_id}


def invitation_view(invitation, now):
    state = ("redeemed" if invitation.redeemed_at else "revoked" if invitation.revoked_at
             else "expired" if invitation.expires_at <= now else "pending")
    return {"id": str(invitation.id), "label": invitation.label, "state": state,
            "expires_at": invitation.expires_at.isoformat()}
