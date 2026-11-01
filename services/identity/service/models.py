"""Identity-owned account data. Public roles are never accepted from a client."""

import uuid

from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.contrib.auth.password_validation import validate_password
from django.core.validators import validate_email
from django.db import models


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


class EmailVerification(models.Model):
    digest = models.CharField(max_length=64, primary_key=True)
    account = models.ForeignKey(Account, on_delete=models.CASCADE)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
