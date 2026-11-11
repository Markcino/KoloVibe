"""Exercise BE-TR upgrade/rollback guards against disposable SQLite only.

Run with local Django dependencies: python scripts/check_be_tr_migrations.py points|moderation|audit
No service database is opened: its settings connection is replaced before setup.
"""
import os
from pathlib import Path
import sys
import tempfile
from uuid import uuid4


def main():
    service = sys.argv[1] if len(sys.argv) == 2 else ""
    targets = {
        "points": ("0003_dailyawardcount", "0004_pointsentry_video_id_qualificationreceipt"),
        "moderation": ("0002_internal_nonce", "0003_auditevent_moderationaction_creator_id_and_more"),
        "audit": ("0003_internal_nonce", "0004_securityevent_producer_securityevent_subject_id_and_more"),
    }
    if service not in targets or os.environ.get("KOLOVIBE_ENV") != "local":
        raise SystemExit("Explicit local environment and points|moderation|audit argument required")
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "services" / service))
    os.environ["DJANGO_SETTINGS_MODULE"] = "service.settings"
    import django
    from django.conf import settings
    from django.db import connection, DatabaseError, transaction
    from django.db.migrations.executor import MigrationExecutor
    from django.utils import timezone

    with tempfile.TemporaryDirectory(prefix="be-tr-migrations-") as directory:
        settings.DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": str(Path(directory) / "fixture.sqlite3")}}
        django.setup()
        old, new = ([('service', name)] for name in targets[service])
        def migrate(target):
            executor = MigrationExecutor(connection)
            executor.migrate(target)
            return executor.loader.project_state(target).apps
        apps = migrate(old)
        ident = uuid4()
        if service == "points":
            apps.get_model("service", "PointsEntry").objects.create(entry_id=ident, creator_user_id=uuid4(),
                source_decision_id=uuid4(), delta=1, entry_type="AWARD", rule_version="DEC-003-v1", reason_code="QUALIFIED_VIEW")
        elif service == "moderation":
            apps.get_model("service", "ModerationAction").objects.create(id=ident, video_id=uuid4(),
                reviewer_id=uuid4(), action="reject", reason="Retained historical review", status="applied", revision=1)
        else:
            apps.get_model("service", "SecurityEvent").objects.create(id=ident, actor_id=uuid4(), kind="mfa.succeeded",
                occurred_at=timezone.now(), payload_digest="a" * 64)
        for target in (new, old, new):
            apps = migrate(target)
            if service == "moderation":
                action = apps.get_model("service", "ModerationAction").objects.get(pk=ident)
                if target == new:
                    assert action.reason_code is None and action.creator_id is None and not action.owner_lookup_completed
                    event = apps.get_model("service", "AuditEvent").objects.create(actor_id=uuid4(), kind="moderation.decision_recorded",
                        subject_type="moderation_action", subject_id=ident)
                    query = apps.get_model("service", "AuditEvent").objects.filter(pk=event.pk)
                else:
                    continue
            elif service == "points":
                query = apps.get_model("service", "PointsEntry").objects.filter(pk=ident)
                assert query.get().delta == 1
                if target == new: assert query.get().video_id is None
            else:
                query = apps.get_model("service", "SecurityEvent").objects.filter(pk=ident)
                assert query.get().payload_digest == "a" * 64
                if target == new: assert query.get().producer == "identity" and query.get().subject_id is None
            field = "delta" if service == "points" else "kind"
            for mutate in (lambda: query.update(**{field: 2 if service == "points" else "changed"}), query.delete):
                try:
                    with transaction.atomic(): mutate()
                except DatabaseError:
                    pass
                else:
                    raise AssertionError("Append-only guard missing after migration")
        connection.close()
    print(f"{service}: upgrade/rollback/re-upgrade retained legacy facts and append-only guards")


if __name__ == "__main__":
    main()
