"""Report (and with --apply repair) drift between the listing projection and the eligibility predicate."""
from django.core.management.base import BaseCommand, CommandError

from service import listings


class Command(BaseCommand):
    help = "Compare the public listing projection with the eligibility predicate"

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="repair drift instead of only reporting it")

    def handle(self, *args, **options):
        drift = listings.reconcile(apply=options["apply"])
        self.stdout.write(f"missing={drift['missing']} orphaned={drift['orphaned']} applied={options['apply']}")
        if not options["apply"] and any(drift.values()):
            raise CommandError("Listing projection has drifted")
