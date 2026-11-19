"""Remove expired web credentials and Django browser sessions in bounded batches."""

from django.contrib.sessions.models import Session
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from web.models import WebCredential


class Command(BaseCommand):
    help = "Delete at most 500 expired web credentials and 500 expired browser sessions"

    def handle(self, *args, **options):
        now = timezone.now()
        with transaction.atomic():
            keys = list(WebCredential.objects.filter(absolute_expires_at__lte=now)
                        .order_by("absolute_expires_at").values_list("pk", flat=True)[:500])
            count, _ = WebCredential.objects.filter(pk__in=keys).delete()
        session_keys = list(Session.objects.filter(expire_date__lte=now)
                            .order_by("expire_date").values_list("pk", flat=True)[:500])
        Session.objects.filter(pk__in=session_keys).delete()
        self.stdout.write(f"Expired web credential rows removed: {count}")
