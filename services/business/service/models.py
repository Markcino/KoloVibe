"""Business-owned data. Cross-service identifiers are plain UUID columns with no foreign keys (DOC-204)."""
import uuid

from django.db import models
from django.db.models import Q
from django.utils import timezone


class Business(models.Model):
    class State(models.TextChoices):
        DRAFT = "draft", "Draft"
        SUBMITTED = "submitted", "Submitted"
        UNDER_REVIEW = "under_review", "Under review"
        NEEDS_INFO = "needs_info", "Needs information"
        VERIFIED = "verified", "Verified"
        REJECTED = "rejected", "Rejected"
        SUSPENDED = "suspended", "Suspended"
        REVOKED = "revoked", "Revoked"
        CLOSED = "closed", "Closed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    state = models.CharField(max_length=16, choices=State.choices, default=State.DRAFT)
    display_name = models.CharField(max_length=80)
    legal_name = models.CharField(max_length=160)  # private: owner and assigned reviewers only
    created_by_account_id = models.UUIDField()
    created_at = models.DateTimeField(default=timezone.now)
    closed_at = models.DateTimeField(null=True, blank=True)
    version = models.PositiveIntegerField(default=1)
    owner_listed = models.BooleanField(default=False)  # the owner's intent; the public sees it only while eligible

    class Meta:
        indexes = [models.Index(fields=["created_by_account_id", "created_at"], name="biz_by_creator_idx")]


class BusinessMembership(models.Model):
    """Authority is a per-business relationship, never an Identity role (ADR-BIZ-001 decision 2)."""

    class Role(models.TextChoices):
        OWNER = "owner", "Owner"
        STAFF = "staff", "Staff"

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        REVOKED = "revoked", "Revoked"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    business = models.ForeignKey(Business, on_delete=models.PROTECT, related_name="memberships")
    account_id = models.UUIDField()
    role = models.CharField(max_length=8, choices=Role.choices)
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.ACTIVE)
    granted_by_account_id = models.UUIDField()
    label = models.CharField(max_length=40, blank=True, default="")  # owner-assigned; no account profile data is copied
    created_at = models.DateTimeField(default=timezone.now)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["business", "account_id"], condition=Q(status="active"),
                                    name="biz_one_active_membership"),
            models.CheckConstraint(condition=Q(role__in=["owner", "staff"]), name="biz_membership_role"),
            models.CheckConstraint(condition=Q(status__in=["active", "revoked"]), name="biz_membership_status"),
        ]
        indexes = [models.Index(fields=["account_id", "status"], name="biz_member_by_account_idx")]


class StaffInvitation(models.Model):
    """Single-use, expiring code shared by the owner out of band (DR-BZ-08 option A). Only a keyed digest is stored."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    business = models.ForeignKey(Business, on_delete=models.PROTECT, related_name="invitations")
    code_digest = models.CharField(max_length=64, unique=True)
    label = models.CharField(max_length=40)
    created_by_account_id = models.UUIDField()
    created_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField()
    redeemed_by_account_id = models.UUIDField(null=True, blank=True)
    redeemed_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)


class RegistrationGrant(models.Model):
    """Pilot-cohort invitation to register businesses (DR-BZ-03); administrator-managed."""
    account_id = models.UUIDField(primary_key=True)
    granted_by_account_id = models.UUIDField()
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)


class IdempotencyRecord(models.Model):
    """Replays the recorded result for a repeated key and payload; a different payload conflicts."""
    id = models.BigAutoField(primary_key=True)
    actor_id = models.UUIDField()
    operation = models.CharField(max_length=40)
    key_digest = models.CharField(max_length=64)
    payload_digest = models.CharField(max_length=64)
    status = models.PositiveSmallIntegerField()
    body = models.JSONField()
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["actor_id", "operation", "key_digest"],
                                               name="biz_idempotency_unique")]


class ThrottleCounter(models.Model):
    """Hashed key and a window; raw account or address values are never stored."""
    key = models.CharField(max_length=64, primary_key=True)
    count = models.PositiveIntegerField(default=0)
    window_started_at = models.DateTimeField()


class AuditEvent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    actor_id = models.UUIDField()
    kind = models.CharField(max_length=64)
    occurred_at = models.DateTimeField(default=timezone.now)
    subject_type = models.CharField(max_length=32)
    subject_id = models.UUIDField()

    class Meta:
        db_table = "business_audit_event"


class AuditDelivery(models.Model):
    event = models.OneToOneField(AuditEvent, primary_key=True, on_delete=models.PROTECT)
    attempts = models.PositiveIntegerField(default=0)
    delivered_at = models.DateTimeField(null=True)
    next_attempt_at = models.DateTimeField(default=timezone.now)


class ReviewerGrant(models.Model):
    """Explicit, scoped reviewer authority (pattern: Moderation's ModeratorAssignment). A null target means all businesses."""

    class Scope(models.TextChoices):
        VERIFICATION = "verification", "Verification"
        REVIEW_QUEUE = "review_queue", "Review queue"
        PROFILE_REVIEW = "profile_review", "Profile review"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    reviewer_account_id = models.UUIDField()
    scope = models.CharField(max_length=16, choices=Scope.choices)
    target_business_id = models.UUIDField(null=True, blank=True)
    active = models.BooleanField(default=True)
    granted_by_account_id = models.UUIDField()
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["reviewer_account_id", "scope", "target_business_id"],
                                    condition=Q(target_business_id__isnull=False), name="biz_grant_unique_target"),
            models.UniqueConstraint(fields=["reviewer_account_id", "scope"],
                                    condition=Q(target_business_id__isnull=True), name="biz_grant_unique_all"),
            models.CheckConstraint(condition=Q(scope__in=["verification", "review_queue", "profile_review"]), name="biz_grant_scope"),
        ]
        indexes = [models.Index(fields=["reviewer_account_id", "scope", "active"], name="biz_grant_lookup_idx")]


class VerificationCase(models.Model):
    class State(models.TextChoices):
        SUBMITTED = "submitted", "Submitted"
        UNDER_REVIEW = "under_review", "Under review"
        NEEDS_INFO = "needs_info", "Needs information"
        VERIFIED = "verified", "Verified"
        REJECTED = "rejected", "Rejected"
        REVOKED = "revoked", "Revoked"

    OPEN = ("submitted", "under_review")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    business = models.ForeignKey(Business, on_delete=models.PROTECT, related_name="verification_cases")
    state = models.CharField(max_length=16, choices=State.choices, default=State.SUBMITTED)
    method = models.CharField(max_length=40)
    submitted_by_account_id = models.UUIDField()
    submitted_at = models.DateTimeField(default=timezone.now)
    assigned_reviewer_account_id = models.UUIDField(null=True, blank=True)
    decided_at = models.DateTimeField(null=True, blank=True)
    reason_code = models.CharField(max_length=40, blank=True, default="")
    duplicate_candidates = models.JSONField(default=list)  # business ids only; shown to the assigned reviewer

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["business"], condition=Q(state__in=["submitted", "under_review"]),
                                    name="biz_one_open_case"),
            models.CheckConstraint(condition=Q(state__in=["submitted", "under_review", "needs_info", "verified",
                                                           "rejected", "revoked"]), name="biz_case_state"),
        ]
        indexes = [models.Index(fields=["state", "submitted_at", "id"], name="biz_case_queue_idx")]


class VerificationEvidence(models.Model):
    """Text-only evidence (for example a registration number or a page to check). File evidence waits for the
    owner's checklist and approved private storage (DR-BZ-04, DR-BZ-19)."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    case = models.ForeignKey(VerificationCase, on_delete=models.PROTECT, related_name="evidence")
    kind = models.CharField(max_length=40)
    value = models.CharField(max_length=300)
    created_at = models.DateTimeField(default=timezone.now)


class VerificationDecision(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    case = models.ForeignKey(VerificationCase, on_delete=models.PROTECT, related_name="decisions")
    decided_by_account_id = models.UUIDField()
    decision = models.CharField(max_length=16)
    reason_code = models.CharField(max_length=40)
    note = models.CharField(max_length=500, blank=True, default="")
    created_at = models.DateTimeField(default=timezone.now)


class BusinessCategory(models.Model):
    """Administrator-managed controlled vocabulary, at most two levels (DR-BZ-10). Owners cannot create categories."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    slug = models.SlugField(max_length=60, unique=True)
    name = models.CharField(max_length=80)
    parent = models.ForeignKey("self", null=True, blank=True, on_delete=models.PROTECT, related_name="children")
    active = models.BooleanField(default=True)


class ProfileRevision(models.Model):
    """What the owner edits. The public sees only the last approved revision (BZ-R-010)."""

    class State(models.TextChoices):
        DRAFT = "draft", "Draft"
        PENDING_REVIEW = "pending_review", "Pending review"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        SUPERSEDED = "superseded", "Superseded"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    business = models.ForeignKey(Business, on_delete=models.PROTECT, related_name="revisions")
    revision_no = models.PositiveIntegerField()
    state = models.CharField(max_length=16, choices=State.choices, default=State.DRAFT)
    display_name = models.CharField(max_length=80)
    category = models.ForeignKey(BusinessCategory, null=True, blank=True, on_delete=models.PROTECT)
    description = models.TextField(max_length=2000, blank=True, default="")
    county_code = models.CharField(max_length=40, blank=True, default="")
    city = models.CharField(max_length=80, blank=True, default="")
    address_line = models.CharField(max_length=200, blank=True, default="")
    address_public = models.BooleanField(default=False)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    coordinates_public = models.BooleanField(default=False)
    time_zone = models.CharField(max_length=64, default="Africa/Monrovia")
    submitted_at = models.DateTimeField(null=True, blank=True)
    reviewed_by_account_id = models.UUIDField(null=True, blank=True)
    submitted_by_account_id = models.UUIDField(null=True, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reason_code = models.CharField(max_length=40, blank=True, default="")
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["business", "revision_no"], name="biz_revision_no_unique"),
            models.UniqueConstraint(fields=["business"], condition=Q(state__in=["draft", "pending_review"]),
                                    name="biz_one_working_revision"),
            models.UniqueConstraint(fields=["business"], condition=Q(state="approved"), name="biz_one_approved_revision"),
            models.CheckConstraint(condition=Q(state__in=["draft", "pending_review", "approved", "rejected",
                                                           "superseded"]), name="biz_revision_state"),
            models.CheckConstraint(condition=(Q(latitude__isnull=True, longitude__isnull=True)
                                              | Q(latitude__isnull=False, longitude__isnull=False)),
                                   name="biz_revision_coordinates_paired"),
        ]
        indexes = [models.Index(fields=["state", "submitted_at", "id"], name="biz_revision_queue_idx")]


class ContactChannel(models.Model):
    class Kind(models.TextChoices):
        PHONE = "phone", "Phone"
        EMAIL = "email", "Email"
        WEBSITE = "website", "Website"
        SOCIAL = "social", "Social"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    revision = models.ForeignKey(ProfileRevision, on_delete=models.CASCADE, related_name="contacts")
    kind = models.CharField(max_length=8, choices=Kind.choices)
    value = models.CharField(max_length=300)
    is_public = models.BooleanField(default=False)  # private unless the owner opts in (DR-BZ-09)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["revision", "kind", "value"], name="biz_contact_unique")]


class HoursRule(models.Model):
    """Minutes since local midnight so that 24:00 (closing at midnight) is representable."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name="hours_rules")
    weekday = models.PositiveSmallIntegerField()
    opens_minute = models.PositiveSmallIntegerField()
    closes_minute = models.PositiveSmallIntegerField()

    class Meta:
        constraints = [
            models.CheckConstraint(condition=Q(weekday__lte=6), name="biz_hours_weekday"),
            models.CheckConstraint(condition=Q(opens_minute__lt=models.F("closes_minute"), closes_minute__lte=1440),
                                   name="biz_hours_interval"),
        ]


class HoursException(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name="hours_exceptions")
    on_date = models.DateField()
    closed = models.BooleanField(default=True)
    opens_minute = models.PositiveSmallIntegerField(null=True, blank=True)
    closes_minute = models.PositiveSmallIntegerField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["business", "on_date"], name="biz_hours_exception_unique"),
            models.CheckConstraint(condition=(Q(closed=True, opens_minute__isnull=True, closes_minute__isnull=True)
                                              | Q(closed=False, opens_minute__isnull=False, closes_minute__isnull=False,
                                                  opens_minute__lt=models.F("closes_minute"), closes_minute__lte=1440)),
                                   name="biz_hours_exception_shape"),
        ]


class BusinessListing(models.Model):
    """The public read model: public columns ONLY, one row while a business is listed (ADR-BIZ-001 decision 4).

    Every public query reads this table and nothing else, so a private column cannot leak by omission. A row exists
    exactly while the eligibility predicate holds and the owner wants to be listed (see listings.py)."""
    business = models.OneToOneField(Business, primary_key=True, on_delete=models.CASCADE, related_name="listing")
    display_name = models.CharField(max_length=80)
    name_sort = models.CharField(max_length=80)
    category_slug = models.CharField(max_length=60)
    category_name = models.CharField(max_length=80)
    county_code = models.CharField(max_length=40)
    city = models.CharField(max_length=80)
    summary = models.CharField(max_length=200, blank=True, default="")
    description = models.TextField(max_length=2000, blank=True, default="")
    address_line = models.CharField(max_length=200, blank=True, default="")  # empty unless the owner made it public
    time_zone = models.CharField(max_length=64)
    hours = models.JSONField(default=dict)
    contacts = models.JSONField(default=list)  # only channels the owner marked public
    verified = models.BooleanField(default=True)
    updated_at = models.DateTimeField(default=timezone.now)

    class Meta:
        indexes = [models.Index(fields=["name_sort", "business"], name="biz_listing_order_idx"),
                   models.Index(fields=["county_code", "category_slug"], name="biz_listing_filter_idx")]


class InquiryThread(models.Model):
    """A customer-opened conversation with a listed business. The business never receives the customer's account id."""

    class State(models.TextChoices):
        OPEN = "open", "Open"
        CLOSED_BY_CUSTOMER = "closed_by_customer", "Closed by customer"
        CLOSED_BY_BUSINESS = "closed_by_business", "Closed by business"
        BLOCKED = "blocked", "Blocked"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    business = models.ForeignKey(Business, on_delete=models.PROTECT, related_name="inquiry_threads")
    customer_account_id = models.UUIDField()  # private to the service; never serialized to the business
    customer_label = models.CharField(max_length=40)  # pseudonymous ("Customer 7"); no profile data is copied
    subject_code = models.CharField(max_length=40)
    state = models.CharField(max_length=24, choices=State.choices, default=State.OPEN)
    created_at = models.DateTimeField(default=timezone.now)
    last_message_at = models.DateTimeField(default=timezone.now)
    message_count = models.PositiveIntegerField(default=0)
    customer_confirmed_at = models.DateTimeField(null=True, blank=True)
    business_confirmed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["business", "customer_account_id"], condition=Q(state="open"),
                                    name="biz_one_open_thread"),
            models.CheckConstraint(condition=Q(state__in=["open", "closed_by_customer", "closed_by_business",
                                                           "blocked"]), name="biz_thread_state"),
        ]
        indexes = [models.Index(fields=["customer_account_id", "id"], name="biz_thread_customer_idx"),
                   models.Index(fields=["business", "last_message_at", "id"], name="biz_thread_inbox_idx")]


class InquiryMessage(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    thread = models.ForeignKey(InquiryThread, on_delete=models.PROTECT, related_name="messages")
    author_kind = models.CharField(max_length=8)
    author_account_id = models.UUIDField()
    body = models.CharField(max_length=1000)
    removed = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [models.CheckConstraint(condition=Q(author_kind__in=["customer", "business"]),
                                              name="biz_message_author_kind")]
        indexes = [models.Index(fields=["thread", "created_at", "id"], name="biz_message_order_idx")]


class InquiryBlock(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    business = models.ForeignKey(Business, on_delete=models.PROTECT, related_name="inquiry_blocks")
    customer_account_id = models.UUIDField()
    blocked_by_account_id = models.UUIDField()
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["business", "customer_account_id"], name="biz_one_block")]
