"""Initial abuse-control parameters (DR-BZ-22, approved "start conservative, record as configuration").

These are starting values for the restricted pilot, not tuned policy. Change them only by owner decision; every
value is read from here so a change is one reviewed edit.
"""
from datetime import timedelta

REGISTRATION_INVITE_ONLY = True          # DR-BZ-03: pilot cohort is invitation-only first
MAX_BUSINESSES_PER_ACCOUNT = 3           # open (not closed) businesses an account may have created
MAX_ACTIVE_STAFF_PER_BUSINESS = 10
MAX_PENDING_INVITATIONS_PER_BUSINESS = 10
STAFF_INVITATION_TTL = timedelta(hours=72)

# (limit, window) per actor. Attempts count, successful or not.
BUDGETS = {
    "register": (5, timedelta(days=1)),
    "staff_invite": (20, timedelta(days=1)),
    "staff_redeem": (10, timedelta(hours=1)),
    "read": (600, timedelta(hours=1)),
}
PAGE_SIZE = 20
