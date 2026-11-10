"""Run the opt-in local media worker without adding it to the shared image."""

from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Run one local R2 media worker process"

    def handle(self, *args, **options):
        try:
            from service.media_tasks import app, QUEUE
        except RuntimeError as error:
            raise CommandError(str(error)) from None
        app.worker_main(["worker", "-Q", QUEUE, "--concurrency=1", "--loglevel=WARNING"])
