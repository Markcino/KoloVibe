"""Business migrations: tested upgrade and rollback (disposable database only; never applied to a shared one)."""
from django.db import connection
from django.test import TransactionTestCase

from . import migration_checks as checks


class MigrationRoundTripTests(TransactionTestCase):
    def tearDown(self):
        # Whatever happened, leave the shared test database at the head migration for the next test.
        checks.migrate_to(connection, (checks.APP, checks.head(connection)[1]))

    def test_every_migration_applies_and_reverses_in_order_and_the_schema_round_trips(self):
        order = checks.round_trip(self, connection)
        self.assertEqual(order[0][1], "0001_initial")

    def test_rows_survive_an_upgrade_and_a_rollback_of_later_migrations(self):
        checks.data_survives(self, connection)
