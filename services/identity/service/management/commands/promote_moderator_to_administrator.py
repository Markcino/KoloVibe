"""Owner-controlled promotion preserving the existing MFA enrollment."""

import json
import re

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.core.validators import validate_email
from django.db import DatabaseError, transaction
from django.utils import timezone
from cryptography.fernet import InvalidToken
import pyotp

from service.mfa import cipher
from service.models import Account, LoginSession, MfaChallenge, ReauthenticationToken, TotpFactor
from service.security_audit import record


class Command(BaseCommand):
    help = "Plan or apply an approved moderator-to-administrator promotion without changing MFA credentials"

    def add_arguments(self, parser):
        parser.add_argument("--email", required=True)
        parser.add_argument("--approval-reference", required=True)
        parser.add_argument("--apply", action="store_true")

    def handle(self, *args, **options):
        if not getattr(settings, "STAGING_PRIVILEGED", False):
            raise CommandError("Privileged access must be enabled")
        approval = options["approval_reference"]
        if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/-]{3,127}", approval) is None:
            raise CommandError("A bounded owner approval reference is required")
        email = options["email"].strip().casefold()
        try:
            validate_email(email)
            with transaction.atomic():
                account = Account.objects.select_for_update().get(email=email)
                if (not account.is_active or account.email_verified_at is None
                        or account.role not in (Account.Role.MODERATOR, Account.Role.ADMINISTRATOR)):
                    raise CommandError("Requires an active, verified moderator or existing administrator")
                factor = TotpFactor.objects.select_for_update().filter(account=account).first()
                if factor is None:
                    raise CommandError("Existing MFA enrollment is required")
                # Check the existing encrypted enrollment is usable; do not consume or print a code.
                secret = cipher().decrypt(factor.encrypted_secret.encode()).decode()
                pyotp.TOTP(secret).at(timezone.now())
                del secret
                result = {"account_id": str(account.id), "previous_role": account.role,
                          "target_role": Account.Role.ADMINISTRATOR, "mfa_preserved": True,
                          "approval_reference": approval}
                if account.role == Account.Role.ADMINISTRATOR:
                    result["status"] = "already-administrator"
                elif not options["apply"]:
                    result["status"] = "dry-run"
                else:
                    now = timezone.now()
                    account.role = Account.Role.ADMINISTRATOR
                    account.save(update_fields=["role"])
                    result["sessions_revoked"] = LoginSession.objects.filter(
                        account=account, revoked_at__isnull=True).update(revoked_at=now)
                    result["challenges_invalidated"] = MfaChallenge.objects.filter(
                        account=account, used_at__isnull=True).update(used_at=now)
                    ReauthenticationToken.objects.filter(
                        account=account, used_at__isnull=True).update(used_at=now)
                    event = record("account.administrator_role_granted", account.id)
                    result.update(status="promoted", audit_event_id=str(event.id))
        except Account.DoesNotExist:
            raise CommandError("Account not found") from None
        except (ValidationError, InvalidToken, UnicodeError, ValueError, TypeError,
                RuntimeError, DatabaseError):
            raise CommandError("Promotion failed; no role change committed") from None
        self.stdout.write(json.dumps(result, sort_keys=True))
