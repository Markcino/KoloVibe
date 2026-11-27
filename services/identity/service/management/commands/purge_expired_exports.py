from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from ...access_export import purge
from ...models import AccessExport
from ...security_audit import record


class Command(BaseCommand):
    help = ("Remove the assembled data of every access export whose retrieval window has passed (mandate 3.3). The "
            "export row and its dates stay as the record. Idempotent; run it on a schedule.")

    def handle(self, *args, **options):
        purged = 0
        rows = AccessExport.objects.filter(purged_at__isnull=True, expires_at__lte=timezone.now()).order_by("expires_at")
        for export in rows.select_related("request").iterator():
            with transaction.atomic():
                purge(export)
                record("account.privacy_export_purged", export.request.account_id)
                purged += 1
        # A count only: no account or request detail is printed.
        self.stdout.write(f"Purged {purged} expired exports")
