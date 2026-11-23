from django.core.management.base import BaseCommand, CommandError

from service.retention import BATCH, purge_expired


class Command(BaseCommand):
    help = ("Delete a bounded batch of expired throttle, one-time-code, challenge, replay-marker and finished-session "
            "rows. Prints counts only. Accounts, security events and audit rows are never touched.")

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=BATCH, help="rows per table per run (1-10000)")

    def handle(self, *args, **options):
        try:
            removed = purge_expired(batch=options["limit"])
        except ValueError as error:
            raise CommandError(str(error)) from None
        for name, count in removed.items():
            self.stdout.write(f"{name}: {count}")
