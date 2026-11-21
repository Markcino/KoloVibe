"""Add a taken-down video's fingerprints to the blocklist so re-uploads are caught by automated screening."""

from uuid import UUID

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from service.models import Fingerprint, ScreeningRecord, Video


class Command(BaseCommand):
    help = "Mark all stored fingerprints of a confirmed copyright takedown as blocked"

    def add_arguments(self, parser):
        parser.add_argument("video_id")

    def handle(self, *args, **options):
        try:
            video_id = UUID(options["video_id"])
        except ValueError:
            raise CommandError("A video UUID is required") from None
        with transaction.atomic():
            video = Video.objects.select_for_update().filter(pk=video_id).first()
            if video is None:
                raise CommandError("Video not found")
            count = Fingerprint.objects.filter(video=video).update(blocked=True)
            ScreeningRecord.objects.create(video=video, provider="blocklist", kind="decision", score=1.0,
                                           action="block", reason=f"fingerprints_blocked:{count}")
        self.stdout.write(f"Blocked {count} fingerprints")
