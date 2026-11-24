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
    "verification_submit": (5, timedelta(days=1)),
    "profile_edit": (60, timedelta(hours=1)),
    "listing_change": (30, timedelta(hours=1)),
    "inquiry_create": (10, timedelta(days=1)),       # per customer
    "inquiry_business": (30, timedelta(hours=1)),    # new threads per business, so one business cannot be flooded
    "inquiry_message": (60, timedelta(hours=1)),
    "review_create": (5, timedelta(days=1)),        # per author
    "review_edit": (10, timedelta(days=1)),
    "review_invite": (20, timedelta(days=1)),
    "report_create": (20, timedelta(days=1)),
    "public_read": (1200, timedelta(hours=1)),      # per signed-in account, or per client address
    "contact_reveal": (100, timedelta(days=1)),     # signed-in verified accounts only (DR-BZ-12)
}
PAGE_SIZE = 20
MAX_MESSAGES_PER_THREAD = 100
REVIEW_INVITATION_TTL = timedelta(days=30)
MAX_PENDING_REVIEW_INVITATIONS = 50
# Fraud-hold signals (DR-BZ-16 "hold on fraud signals"; thresholds are DR-BZ-22 starting values).
HOLD_BUSINESS_BURST = (10, timedelta(hours=24))   # this many new reviews for one business inside the window
HOLD_AUTHOR_BURST = (3, timedelta(hours=24))      # this many reviews by one author inside the window
HOLD_DUPLICATE_WINDOW = timedelta(days=30)        # identical text anywhere on the platform inside the window
# Hidden until the owner sets a minimum (DR-BZ-16): with None the average is never shown, only the count.
MIN_REVIEWS_FOR_AVERAGE = None
SEARCH_CHUNK = 50
SEARCH_SCAN_CAP = 500                   # rows examined per request when a filter is applied after the query (open now)
MIN_EVIDENCE_ITEMS = 1                   # technical minimum so a case is never empty; the checklist is the owner's
MAX_EVIDENCE_ITEMS = 5
# DR-BZ-11 (approved: pre-moderate material fields, post-moderate free text). WHICH fields are material is the
# owner's call; these are the register's own examples, recorded as configuration for confirmation.
MATERIAL_FIELDS = ("display_name", "category", "address_line", "contacts")
MAX_CONTACTS = 10
MAX_HOURS_RULES = 28
MAX_HOURS_EXCEPTIONS = 60
REVIEWER_DECISIONS = ("verify", "reject", "request_info", "revoke")
