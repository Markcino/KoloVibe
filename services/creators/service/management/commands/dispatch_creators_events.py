from django.core.management.base import BaseCommand, CommandError

from ...events import dispatch_one


class Command(BaseCommand):
    help = "Dispatch a batch of erasure confirmations from the Creators outbox to RabbitMQ (Decision C)."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=100)

    def handle(self, *args, **options):
        limit = options["limit"]
        if not 1 <= limit <= 1000:
            raise CommandError("Use a batch limit from 1 to 1000")
        from ...celery_app import app

        sent = 0
        while sent < limit and dispatch_one(app):
            sent += 1
        self.stdout.write(f"Dispatched {sent} creators events")
