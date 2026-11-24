"""Audit 0006 round-trip checks, shared by the SQLite suite and the PostgreSQL integration script."""
from uuid import uuid4

from django.db import DatabaseError
from django.db.migrations.executor import MigrationExecutor

PREVIOUS, HEAD = ("service", "0005_audit_read_grants"), ("service", "0006_business_producer")


def migrate(connection, target):
    MigrationExecutor(connection).migrate([target])
    return MigrationExecutor(connection).loader.project_state([target]).apps


def grants(apps):
    return apps.get_model("service", "AuditReadGrant").objects


def upgrade_and_rollback_over_existing_producers(test, connection):
    test.assertEqual(MigrationExecutor(connection).loader.graph.leaf_nodes("service")[0], HEAD)
    apps = migrate(connection, HEAD)
    kept = grants(apps).create(administrator_id=uuid4(), producer="moderation")
    try:
        apps = migrate(connection, PREVIOUS)
        test.assertEqual(grants(apps).filter(pk=kept.pk).count(), 1)
        apps = migrate(connection, HEAD)
        test.assertEqual(grants(apps).filter(pk=kept.pk).count(), 1)
        extra = grants(apps).create(administrator_id=uuid4(), producer="business")  # accepted again after the upgrade
        extra.delete()
    finally:
        grants(migrate(connection, HEAD)).filter(pk=kept.pk).delete()


def rollback_refused_and_lossless_while_a_business_grant_exists(test, connection):
    apps = migrate(connection, HEAD)
    grant = grants(apps).create(administrator_id=uuid4(), producer="business")
    try:
        with test.assertRaises(DatabaseError):
            migrate(connection, PREVIOUS)
        test.assertIn(HEAD, MigrationExecutor(connection).loader.applied_migrations)
        apps = MigrationExecutor(connection).loader.project_state([HEAD]).apps
        test.assertEqual(grants(apps).filter(pk=grant.pk, producer="business").count(), 1)
    finally:
        grants(migrate(connection, HEAD)).filter(pk=grant.pk).delete()
    migrate(connection, PREVIOUS)   # with the grant gone the rollback is clean
    migrate(connection, HEAD)
