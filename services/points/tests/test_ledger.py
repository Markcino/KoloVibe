import uuid

from django.db import DatabaseError, IntegrityError, connection, transaction
from django.test import TestCase

from service.models import PointsEntry


class LedgerTests(TestCase):
    def award(self):
        return PointsEntry.objects.create(
            creator_user_id=uuid.uuid4(), source_decision_id=uuid.uuid4(),
            delta=1, entry_type=PointsEntry.Type.AWARD,
            rule_version="approved-rules-only", reason_code="qualified",
        )

    def test_award_and_compensating_reversal_preserve_history(self):
        award = self.award()
        reversal = PointsEntry.objects.create(
            creator_user_id=award.creator_user_id, delta=-award.delta,
            entry_type=PointsEntry.Type.REVERSAL, reversal_of=award,
            rule_version=award.rule_version, reason_code="reviewed-reversal",
        )
        self.assertEqual(PointsEntry.objects.count(), 2)
        self.assertEqual(sum(PointsEntry.objects.values_list("delta", flat=True)), 0)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                PointsEntry.objects.create(
                    creator_user_id=award.creator_user_id, delta=-1,
                    entry_type=PointsEntry.Type.REVERSAL, reversal_of=award,
                    rule_version=award.rule_version, reason_code="duplicate")
        self.assertNotEqual(award.entry_id, reversal.entry_id)

    def test_database_rejects_mutation_even_if_orm_is_bypassed(self):
        award = self.award()
        with self.assertRaises(DatabaseError):
            with transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute("UPDATE points_entries SET delta=99")
        with self.assertRaises(DatabaseError):
            with transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute("DELETE FROM points_entries")
        self.assertEqual(PointsEntry.objects.count(), 1)

    def test_invalid_award_has_no_points(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                PointsEntry.objects.create(
                    creator_user_id=uuid.uuid4(), delta=1,
                    entry_type=PointsEntry.Type.AWARD,
                    rule_version="unapproved", reason_code="missing-decision")
        self.assertFalse(PointsEntry.objects.exists())

    def test_no_public_award_endpoint(self):
        self.assertEqual(self.client.post("/points", data={}).status_code, 404)

    def test_source_decision_cannot_be_awarded_twice(self):
        award = self.award()
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                PointsEntry.objects.create(
                    creator_user_id=award.creator_user_id,
                    source_decision_id=award.source_decision_id,
                    delta=1, entry_type=PointsEntry.Type.AWARD,
                    rule_version=award.rule_version, reason_code="duplicate",
                )
        self.assertEqual(PointsEntry.objects.count(), 1)

    def test_orm_save_and_delete_cannot_mutate_entries(self):
        award = self.award()
        award.delta = 99
        with self.assertRaises(ValueError):
            award.save()
        with self.assertRaises(ValueError):
            award.delete()
        award.refresh_from_db()
        self.assertEqual(award.delta, 1)
