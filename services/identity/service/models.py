"""Identity-owned account data. Public roles are never accepted from a client."""

import uuid

from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.contrib.auth.password_validation import validate_password
from django.core.validators import validate_email
from django.db import models
from django.utils import timezone


class AccountManager(BaseUserManager):
    def create_user(self, email, password, display_name):
        if not email:
            raise ValueError("An email address is required")
        if not password:
            raise ValueError("A password is required")
        if len(password) > 128:
            raise ValueError("Password exceeds the allowed length")
        display_name = display_name.strip()
        if not 2 <= len(display_name) <= 80:
            raise ValueError("Display name must be between 2 and 80 characters")
        normalized = email.strip().casefold()
        validate_email(normalized)
        account = self.model(email=normalized, display_name=display_name)
        validate_password(password, user=account)
        account.set_password(password)
        account.save(using=self._db)
        return account

    def create_superuser(self, *args, **kwargs):
        raise RuntimeError("Privileged account creation requires approved MFA and audit controls")


class Account(AbstractBaseUser, PermissionsMixin):
    class Role(models.TextChoices):
        VIEWER = "viewer", "Viewer"
        CREATOR = "creator", "Creator"
        MODERATOR = "moderator", "Moderator"
        ADMINISTRATOR = "administrator", "Administrator"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(max_length=254, unique=True)
    display_name = models.CharField(max_length=80)
    role = models.CharField(max_length=16, choices=Role.choices, default=Role.VIEWER)
    is_active = models.BooleanField(default=True)
    email_verified_at = models.DateTimeField(null=True, blank=True)
    is_staff = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["display_name"]
    objects = AccountManager()

    def __str__(self):
        return str(self.id)


class LoginSession(models.Model):
    """A revocable device session; raw refresh credentials never enter the database."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name="login_sessions")
    family_id = models.UUIDField(default=uuid.uuid4, db_index=True)
    refresh_digest = models.CharField(max_length=64, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    rotated_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField()
    revoked_at = models.DateTimeField(null=True, blank=True)
    authenticated_role = models.CharField(max_length=16, default="viewer")
    mfa_verified_at = models.DateTimeField(null=True, blank=True)


class UsedRefreshToken(models.Model):
    """Retains consumed digests until expiry so replay revokes the token family."""

    digest = models.CharField(max_length=64, primary_key=True)
    family_id = models.UUIDField(db_index=True)
    expires_at = models.DateTimeField()


class LoginThrottle(models.Model):
    """A bounded, hashed account-and-origin key for local login throttling."""

    key = models.CharField(max_length=64, primary_key=True)
    failures = models.PositiveSmallIntegerField(default=0)
    window_started_at = models.DateTimeField()


class CodeKind(models.TextChoices):
    """`token` rows are the retired 64-character links; `code` rows are six digits (ADR-013 A-1)."""

    TOKEN = "token", "Legacy long token"
    CODE = "code", "Six-digit code"


class EmailVerification(models.Model):
    """Single-use email proof. Only a keyed verifier is stored, never the raw code."""

    digest = models.CharField(max_length=64, primary_key=True)
    account = models.ForeignKey(Account, on_delete=models.CASCADE)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
    kind = models.CharField(max_length=5, choices=CodeKind.choices, default=CodeKind.CODE)
    issue_id = models.UUIDField(default=uuid.uuid4, editable=False)
    attempts = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(default=timezone.now)


class PasswordReset(models.Model):
    """Single-use password reset proof. Raw codes are delivered by mail only."""

    digest = models.CharField(max_length=64, primary_key=True)
    account = models.ForeignKey(Account, on_delete=models.CASCADE)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
    kind = models.CharField(max_length=5, choices=CodeKind.choices, default=CodeKind.CODE)
    issue_id = models.UUIDField(default=uuid.uuid4, editable=False)
    attempts = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(default=timezone.now)


class ReauthenticationToken(models.Model):
    """Short-lived, single-use proof bound to one account and login session."""

    digest = models.CharField(max_length=64, primary_key=True)
    account = models.ForeignKey(Account, on_delete=models.CASCADE)
    session = models.ForeignKey(LoginSession, on_delete=models.CASCADE)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)


class StepUpProof(models.Model):
    """Decision G: a short-lived, single-use proof of fresh reauthentication for one purpose.

    Bound to the account and login session that obtained it, the purpose, the service that may accept it
    (audience) and, where the purpose names one, the resource it was obtained for. Only a digest is stored.
    """

    digest = models.CharField(max_length=64, primary_key=True)
    account = models.ForeignKey(Account, on_delete=models.CASCADE)
    session = models.ForeignKey(LoginSession, on_delete=models.CASCADE)
    purpose = models.CharField(max_length=64)
    audience = models.CharField(max_length=32)
    resource_id = models.UUIDField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=["expires_at"], name="step_up_expiry")]


class NotificationPreferences(models.Model):
    """Account-owned delivery choices; no delivery is enabled by this record."""

    account = models.OneToOneField(Account, on_delete=models.CASCADE, primary_key=True)
    email_notifications = models.BooleanField(default=False)
    push_notifications = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)


class PrivacyRequest(models.Model):
    """Receipt only. Processing awaits the approved retention/deletion policy."""

    class Kind(models.TextChoices):
        ACCESS = "access", "Access"
        DELETION = "deletion", "Deletion"

    class Status(models.TextChoices):
        RECEIVED = "received", "Received"
        IN_REVIEW = "in_review", "In review"
        COMPLETED = "completed", "Completed"
        DECLINED = "declined", "Declined"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    account = models.ForeignKey(Account, on_delete=models.PROTECT)
    kind = models.CharField(max_length=8, choices=Kind.choices)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.RECEIVED, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(
            fields=["account", "kind"], condition=models.Q(status__in=["received", "in_review"]),
            name="unique_open_privacy_request_kind")]


class TotpFactor(models.Model):
    account = models.OneToOneField(Account, on_delete=models.CASCADE)
    encrypted_secret = models.TextField()
    last_step = models.BigIntegerField(default=-1)
    created_at = models.DateTimeField(auto_now_add=True)


class RecoveryCode(models.Model):
    account = models.ForeignKey(Account, on_delete=models.CASCADE)
    digest = models.CharField(max_length=64, unique=True)
    used_at = models.DateTimeField(null=True, blank=True)


class MfaChallenge(models.Model):
    digest = models.CharField(max_length=64, primary_key=True)
    account = models.ForeignKey(Account, on_delete=models.CASCADE)
    role = models.CharField(max_length=16)
    throttle_key = models.CharField(max_length=64)
    expires_at = models.DateTimeField()
    failures = models.PositiveSmallIntegerField(default=0)
    used_at = models.DateTimeField(null=True, blank=True)


class SecurityEvent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    actor_id = models.UUIDField(null=True)
    kind = models.CharField(max_length=64)
    occurred_at = models.DateTimeField(default=timezone.now)


class AuditDelivery(models.Model):
    event = models.OneToOneField(SecurityEvent, on_delete=models.PROTECT, primary_key=True)
    attempts = models.PositiveIntegerField(default=0)
    delivered_at = models.DateTimeField(null=True)


class ModeratorInvitation(models.Model):
    """Mailbox-bound invitation; no account exists until TOTP enrollment succeeds."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_by = models.ForeignKey(Account, on_delete=models.PROTECT, related_name="moderator_invitations")
    email = models.EmailField(max_length=254)
    display_name = models.CharField(max_length=80)
    reason = models.CharField(max_length=500)
    token_digest = models.CharField(max_length=64, unique=True)
    idempotency_digest = models.CharField(max_length=64)
    payload_digest = models.CharField(max_length=64)
    created_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField()
    closed = models.BooleanField(default=False)
    revoked_at = models.DateTimeField(null=True)
    revocation_reason = models.CharField(max_length=500, blank=True)
    accepted_at = models.DateTimeField(null=True)
    accepted_account = models.OneToOneField(Account, on_delete=models.PROTECT, null=True, related_name="moderator_invitation")
    encrypted_secret = models.TextField(blank=True)
    password_hash = models.CharField(max_length=128, blank=True)
    setup_expires_at = models.DateTimeField(null=True)
    failures = models.PositiveSmallIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["created_by", "idempotency_digest"], name="moderator_invite_actor_key"),
            models.UniqueConstraint(fields=["email"], condition=models.Q(closed=False), name="moderator_invite_pending_email"),
        ]


class ModeratorInvitationEvent(models.Model):
    """Owning-service correlation; sensitive invitation data is never sent to Audit."""

    event = models.OneToOneField(SecurityEvent, primary_key=True, on_delete=models.PROTECT)
    invitation = models.ForeignKey(ModeratorInvitation, on_delete=models.PROTECT)


class LegalAcceptance(models.Model):
    """Decision B: one row per accepted version of a required legal document. Append-only (database trigger)."""

    class Context(models.TextChoices):
        REGISTRATION = "registration", "Registration"
        UPDATE = "update", "Update"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name="legal_acceptances")
    document = models.CharField(max_length=16)
    version = models.CharField(max_length=32)
    sha256 = models.CharField(max_length=64)
    context = models.CharField(max_length=16, choices=Context.choices)
    accepted_at = models.DateTimeField(default=timezone.now)

    class Meta:
        indexes = [models.Index(fields=["account", "document", "accepted_at"], name="legal_acceptance_lookup")]


class MarketingConsentEvent(models.Model):
    """Decision B: each grant or withdrawal of the optional marketing consent. The latest row is the current state.
    Append-only (database trigger)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name="marketing_consents")
    granted = models.BooleanField()
    version = models.CharField(max_length=32)
    sha256 = models.CharField(max_length=64)
    recorded_at = models.DateTimeField(default=timezone.now)

    class Meta:
        indexes = [models.Index(fields=["account", "recorded_at"], name="marketing_consent_lookup")]
