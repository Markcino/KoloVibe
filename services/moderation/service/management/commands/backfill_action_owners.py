"""Bounded recovery of legacy ownership from the authoritative Content snapshot."""
from uuid import UUID
from django.core.management.base import BaseCommand, CommandError
from service.models import ModerationAction
from service.workflow import ContentUnavailable, _content


class Command(BaseCommand):
    help = "Backfill up to 100 legacy moderation action owners; no new decisions or audit events"

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=100)

    def handle(self, *args, **options):
        if not 1 <= options["limit"] <= 1000:
            raise CommandError("Backfill batch must be between 1 and 1000")
        actions = ModerationAction.objects.filter(creator_id__isnull=True, owner_lookup_completed=False).order_by("id")[:options["limit"]]
        count = 0
        for action in actions:
            try:
                snapshot = _content("inspect", {"video_id": str(action.video_id)})
            except ContentUnavailable:
                raise CommandError("Content unavailable; rerun bounded ownership backfill") from None
            count += ModerationAction.objects.filter(pk=action.pk, creator_id__isnull=True).update(
                creator_id=UUID(snapshot["creator_id"]) if snapshot is not None else None, owner_lookup_completed=True)
        self.stdout.write(f"Checked {count} legacy actions; unavailable/deleted content remains unknown")
