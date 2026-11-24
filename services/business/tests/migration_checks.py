"""Shared migration round-trip checks: one implementation for the SQLite suite and the PostgreSQL integration script.

Exercises what a rollout and a rollback actually do to a database: every migration applies and reverses in order, the
head schema after a full round trip equals the original, and rows written before later migrations survive both an
upgrade and a rollback of those later migrations (rollback drops only what the later migrations created).
"""
from uuid import uuid4

from django.db.migrations.executor import MigrationExecutor

APP = "service"


def _executor(connection):
    return MigrationExecutor(connection)


def head(connection):
    return _executor(connection).loader.graph.leaf_nodes(APP)[0]


def migrations_in_order(connection):
    """The Business migration nodes from the first to the head, in apply order."""
    loader = _executor(connection).loader
    return [node for node in loader.graph.forwards_plan((APP, head(connection)[1])) if node[0] == APP]


def migrate_to(connection, target):
    executor = _executor(connection)
    executor.migrate([target])
    return _executor(connection)


def business_tables(connection):
    return {t for t in connection.introspection.table_names() if t.startswith("service_") or t == "business_audit_event"}


def schema(connection):
    """Table name -> sorted column names, for the Business-owned tables."""
    with connection.cursor() as cursor:
        return {table: sorted(col.name for col in connection.introspection.get_table_description(cursor, table))
                for table in sorted(business_tables(connection))}


def applied(connection):
    return {name for app, name in _executor(connection).loader.applied_migrations if app == APP}


def round_trip(test, connection):
    """Roll back every migration one at a time, then apply them one at a time; the schema must come back identical."""
    order = migrations_in_order(connection)
    test.assertGreaterEqual(len(order), 7)
    original = schema(connection)
    sizes = [len(business_tables(connection))]
    for (_, name), previous in zip(reversed(order), list(reversed(order[:-1])) + [None]):
        target = (APP, previous[1]) if previous else (APP, None)
        migrate_to(connection, target)
        test.assertNotIn(name, applied(connection), f"{name} did not reverse")
        sizes.append(len(business_tables(connection)))
    test.assertEqual(business_tables(connection), set(), "Rolling back to zero must leave no Business-owned table")
    test.assertTrue(all(a >= b for a, b in zip(sizes, sizes[1:])), f"a rollback step added tables: {sizes}")
    for node in order:
        migrate_to(connection, node)
        test.assertIn(node[1], applied(connection), f"{node[1]} did not apply")
    test.assertEqual(schema(connection), original, "Schema after a full round trip differs from the original")
    return order


def data_survives(test, connection):
    """Rows written at the profiles migration survive upgrade to head and rollback to that migration."""
    order = migrations_in_order(connection)
    profiles = next(node for node in order if node[1].startswith("0004"))
    state_apps = migrate_to(connection, profiles).loader.project_state([profiles]).apps
    Business = state_apps.get_model(APP, "Business")
    Membership = state_apps.get_model(APP, "BusinessMembership")
    account = uuid4()
    business = Business.objects.create(display_name="Migration Shop", legal_name="Migration Shop Ltd",
                                       created_by_account_id=account)
    Membership.objects.create(business=business, account_id=account, role="owner", granted_by_account_id=account)
    try:
        migrate_to(connection, order[-1])
        head_apps = _executor(connection).loader.project_state([order[-1]]).apps
        test.assertEqual(head_apps.get_model(APP, "Business").objects.filter(pk=business.pk).count(), 1)
        test.assertFalse(head_apps.get_model(APP, "Business").objects.get(pk=business.pk).owner_listed)
        test.assertEqual(head_apps.get_model(APP, "BusinessMembership").objects.filter(account_id=account).count(), 1)
        migrate_to(connection, profiles)
        back_apps = _executor(connection).loader.project_state([profiles]).apps
        test.assertEqual(back_apps.get_model(APP, "Business").objects.filter(pk=business.pk).count(), 1)
        test.assertEqual(back_apps.get_model(APP, "BusinessMembership").objects.filter(account_id=account).count(), 1)
        test.assertNotIn("service_businesslisting", business_tables(connection))
        test.assertNotIn("service_review", business_tables(connection))
    finally:
        migrate_to(connection, order[-1])
        head_apps = _executor(connection).loader.project_state([order[-1]]).apps
        head_apps.get_model(APP, "BusinessMembership").objects.filter(account_id=account).delete()
        head_apps.get_model(APP, "Business").objects.filter(pk=business.pk).delete()
