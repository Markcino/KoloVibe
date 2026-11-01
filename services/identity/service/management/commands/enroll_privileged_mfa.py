"""Offline owner-controlled factor enrollment; never promotes a public account."""

from pathlib import Path
import binascii
import hmac
import os
import secrets

from django.core.management.base import BaseCommand, CommandError
from django.core.exceptions import ValidationError
from django.db import DatabaseError, transaction
from django.utils import timezone
import pyotp

from service.accounts import _digest
from service.mfa import cipher, PRIVILEGED
from service.models import Account, LoginSession, MfaChallenge, RecoveryCode, TotpFactor
from service.security_audit import record
from staging_runtime import file_value


class Command(BaseCommand):
    help = "Enroll an existing privileged account from owner-only factor/code files; output recovery codes privately"

    def add_arguments(self, parser):
        parser.add_argument("--account-id", required=True)
        parser.add_argument("--recovery-file", required=True)
        parser.add_argument("--approval-reference", required=True)

    def handle(self, *args, **options):
        from django.conf import settings
        if not getattr(settings, "STAGING_PRIVILEGED", False):
            raise CommandError("Privileged MFA enrollment is not enabled")
        if not options["approval_reference"].strip():
            raise CommandError("An owner approval reference is required")
        try:
            factor_secret = file_value("KOLOVIBE_ENROLLMENT_SECRET_FILE", private=True)
            code = file_value("KOLOVIBE_ENROLLMENT_CODE_FILE", private=True)
            factor = pyotp.TOTP(factor_secret)
            step = int(timezone.now().timestamp()) // 30
            matched_step = next((candidate for candidate in (step, step - 1, step + 1)
                                 if hmac.compare_digest(factor.at(candidate * 30), code)), None)
            if matched_step is None:
                raise ValueError("Invalid factor")
            encrypted = cipher().encrypt(factor_secret.encode()).decode()
        except (ValueError, RuntimeError, TypeError, binascii.Error):
            raise CommandError("Invalid private MFA enrollment configuration") from None
        output = Path(options["recovery_file"])
        codes = [secrets.token_urlsafe(32) for _ in range(10)]
        # Exclusive creation prevents overwriting another credential file.
        created = False
        try:
            with open(output, "x", opener=lambda path, flags: os.open(path, flags, 0o600)) as stream:
                created = True
                stream.write("\n".join(codes) + "\n")
            with transaction.atomic():
                account = Account.objects.select_for_update().get(id=options["account_id"])
                if not account.is_active or account.role not in PRIVILEGED:
                    raise CommandError("Enrollment requires an existing active privileged account")
                if TotpFactor.objects.filter(account=account).exists():
                    raise CommandError("Factor replacement requires a separately approved recovery procedure")
                TotpFactor.objects.create(account=account, encrypted_secret=encrypted,
                                          last_step=matched_step)
                RecoveryCode.objects.bulk_create([
                    RecoveryCode(account=account, digest=_digest("recovery:" + item)) for item in codes])
                LoginSession.objects.filter(account=account, revoked_at__isnull=True).update(
                    revoked_at=timezone.now())
                MfaChallenge.objects.filter(account=account, used_at__isnull=True).update(
                    used_at=timezone.now())
                record("mfa.enrolled", account.id)
        except (Account.DoesNotExist, ValidationError, DatabaseError,
                ValueError, OSError, CommandError):
            # Remove only the newly created credential file on enrollment rollback.
            if created:
                output.unlink()
            raise CommandError("MFA enrollment failed; check account, approval and output path") from None
        self.stdout.write("MFA enrolled; recovery credentials saved privately, not printed")
