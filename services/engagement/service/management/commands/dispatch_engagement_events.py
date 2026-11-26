from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from ...events import dispatch_one


class Command(BaseCommand):
    help = "Dispatch a batch from the Engagement outbox to RabbitMQ."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=100)

    def handle(self, *args, **options):
        limit = options["limit"]
        if not 1 <= limit <= 1000:
            raise CommandError("Use a batch limit from 1 to 1000")
        from ...celery_app import app

        # Without local points only erasure confirmations (Decision C) are sent; points events stay in the outbox.
        privacy_only = not settings.LOCAL_POINTS_ENABLED
        sent = 0
        while sent < limit and dispatch_one(app, privacy_only=privacy_only):
            sent += 1
        self.stdout.write(f"Dispatched {sent} engagement events")
