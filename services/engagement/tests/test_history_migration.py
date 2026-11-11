from datetime import timedelta
from uuid import uuid4

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase
from django.utils import timezone


class QualificationHistoryMigrationTests(TransactionTestCase):
    def test_backfill_preserves_only_known_facts_and_does_not_date_old_likes(self):
        executor = MigrationExecutor(connection)
        old_target = [('service', '0004_watch_video_qualification_index')]
        new_target = [('service', '0005_discovery_shares_and_qualified_history')]
        executor.migrate(old_target)
        try:
            apps = executor.loader.project_state(old_target).apps
            likes, watches = apps.get_model('service', 'VideoLike'), apps.get_model('service', 'WatchSession')
            now = timezone.now()
            like = likes.objects.create(account_id=uuid4(), video_id=uuid4())
            for renewed in (False, True):
                watches.objects.create(account_id=uuid4(), video_id=uuid4(), creator_user_id=uuid4(),
                    duration_ms=2501, revision=1, started_at=now-timedelta(seconds=2) if renewed else now-timedelta(seconds=5),
                    last_sample_at=now, expires_at=now+timedelta(seconds=90), qualified_at=now-timedelta(seconds=3), position_ms=0 if renewed else 2501)
            executor = MigrationExecutor(connection); executor.migrate(new_target)
            apps = executor.loader.project_state(new_target).apps
            self.assertIsNone(apps.get_model('service', 'VideoLike').objects.get(pk=like.pk).created_at)
            records = apps.get_model('service', 'QualifiedWatch').objects.all()
            self.assertEqual(records.count(), 2)
            self.assertEqual(set(records.values_list('watched_ms', flat=True)), {None, 2501})
        finally:
            MigrationExecutor(connection).migrate(new_target)
