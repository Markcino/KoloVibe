import uuid

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from ...erasure import reapply
from ...models import PrivacyRequest
from ...security_audit import record


class Command(BaseCommand):
    help = ("Ask every participating service to erase approved deletions again (Decision C). Run after restoring a "
            "service database, so a restore cannot bring an erased account's data back. Idempotent.")

    def add_arguments(self, parser):
        target = parser.add_mutually_exclusive_group(required=True)
        target.add_argument("--request", help="one privacy request id")
        target.add_argument("--all", action="store_true", help="every approved deletion")

    def handle(self, *args, **options):
        rows = PrivacyRequest.objects.filter(kind=PrivacyRequest.Kind.DELETION,
                                             status__in=(PrivacyRequest.Status.PROCESSING,
                                                         PrivacyRequest.Status.COMPLETED)).order_by("created_at", "id")
        if options["request"]:
            try:
                rows = rows.filter(pk=uuid.UUID(options["request"]))
            except ValueError:
                raise CommandError("Use a privacy request id") from None
        requests = sent = 0
        for item in rows.iterator():
            with transaction.atomic():
                count = reapply(item)
                if count:
                    record("account.privacy_erasure_reapplied", item.account_id)
                    requests, sent = requests + 1, sent + count
        # Counts only: no account, email or request detail is printed.
        self.stdout.write(f"Re-applied {requests} erasures ({sent} service requests); run the Identity dispatcher next")
