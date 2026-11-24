"""Audit 0006 (the `business` producer): upgrade, rollback, and the refusal to roll back over data it would orphan."""
from django.db import connection
from django.test import TransactionTestCase

from . import migration_checks as checks


class BusinessProducerMigrationTests(TransactionTestCase):
    def tearDown(self):
        checks.migrate(connection, checks.HEAD)

    def test_rolls_back_and_forward_over_existing_producers(self):
        checks.upgrade_and_rollback_over_existing_producers(self, connection)

    def test_rollback_is_refused_and_loses_nothing_while_a_business_grant_exists(self):
        checks.rollback_refused_and_lossless_while_a_business_grant_exists(self, connection)
