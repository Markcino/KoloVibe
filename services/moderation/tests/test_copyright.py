import json
from unittest.mock import patch
from uuid import UUID, uuid4
from django.test import RequestFactory, TestCase
from django.db import DatabaseError, transaction
from service.models import (Appeal, AuditEvent, CopyrightNotice, CopyrightStrike, CounterNotice,
                            ModeratorAssignment, ModerationAction, Report)
from service.workflow import moderation_workflow, ContentUnavailable


class CopyrightWorkflowTests(TestCase):
    def setUp(self):
        self.video, self.creator, self.owner, self.viewer, self.reviewer, self.second = [uuid4() for _ in range(6)]
        self.snapshot = {'creator_id': str(self.creator), 'state': 'published', 'visibility': 'public', 'revision': 1}
        self.content = self.enterContext(patch('service.workflow._content'))
        self.content.side_effect = lambda op, data: dict(self.snapshot) if op == 'inspect' else {'applied': True}
        self.intake = {'video_id': str(self.video), 'work_reference': 'Original performance reference',
            'details': 'Identified use of my original work without permission.', 'authority_attested': True, 'key': 'copyright-notice-001'}

    def call(self, op, actor, role, data, mfa=True):
        request = RequestFactory().post('/internal/', {'actor_id': str(actor), 'role': role, 'data': data, 'mfa_verified': mfa}, content_type='application/json')
        request.service_caller = 'gateway'
        return moderation_workflow(request, op)

    def report(self):
        result = self.call('copyright_report', self.viewer, 'viewer', self.intake)
        self.assertEqual(result.status_code, 201)
        return json.loads(result.content)['id']

    def remove(self):
        report = self.report()
        decision = {'target_id': report, 'action': 'remove', 'reason': 'Rights evidence confirms this takedown.', 'key': 'copyright-remove-001'}
        ModeratorAssignment.objects.create(moderator_id=self.reviewer, queue_scope='reports', target_id=report)
        self.assertEqual(self.call('report_decision', self.reviewer, 'moderator', decision).status_code, 200)
        self.snapshot.update(state='removed', visibility='private', revision=2)
        return decision

    def test_intake_records_reason_work_reference_audit_and_replays_without_duplicates(self):
        report = self.report()
        self.assertEqual(CopyrightNotice.objects.get().work_reference, self.intake['work_reference'])
        self.assertEqual(self.call('copyright_report', self.viewer, 'viewer', self.intake).status_code, 200)
        self.assertEqual(Report.objects.count(), 1)
        self.assertEqual(AuditEvent.objects.filter(kind='moderation.report_created').count(), 1)
        with self.assertRaises(DatabaseError), transaction.atomic():
            CopyrightNotice.objects.filter(report_id=report).update(work_reference='rewritten')
        self.assertEqual(self.call('copyright_report', self.viewer, 'viewer', self.intake | {'work_reference': 'Different work'}).status_code, 409)
        self.assertEqual(self.call('copyright_report', self.viewer, 'viewer', self.intake | {'authority_attested': False}).status_code, 400)

    def test_durable_report_survives_lost_content_result(self):
        self.content.side_effect = [dict(self.snapshot), ContentUnavailable, {'applied': True}]
        self.assertEqual(self.call('copyright_report', self.viewer, 'viewer', self.intake).status_code, 503)
        self.assertEqual(Report.objects.count(), 1)
        self.assertEqual(self.call('copyright_report', self.viewer, 'viewer', self.intake).status_code, 200)
        self.assertEqual(self.content.call_args_list[1], self.content.call_args_list[2])

    def test_takedown_requires_assignment_mfa_and_counts_only_applied_copyright_actions(self):
        report = self.report()
        decision = {'target_id': report, 'action': 'remove', 'reason': 'Copyright evidence checked by reviewer.', 'key': 'copyright-remove-001'}
        self.assertEqual(self.call('report_decision', self.reviewer, 'moderator', decision).status_code, 403)
        ModeratorAssignment.objects.create(moderator_id=self.reviewer, queue_scope='reports', target_id=report)
        self.assertEqual(self.call('report_decision', self.reviewer, 'moderator', decision, mfa=False).status_code, 403)
        self.assertFalse(CopyrightStrike.objects.exists())
        self.assertEqual(self.call('report_decision', self.reviewer, 'moderator', decision).status_code, 200)
        self.assertEqual(self.call('report_decision', self.reviewer, 'moderator', decision).status_code, 200)
        self.assertEqual(CopyrightStrike.objects.count(), 1)
        self.assertEqual(CopyrightStrike.objects.get().creator_id, self.creator)
        self.assertTrue(ModerationAction.objects.get().copyright)
        self.assertEqual(AuditEvent.objects.filter(kind='moderation.decision_applied').count(), 1)
        self.assertEqual(json.loads(self.call('copyright_status', self.owner, 'creator', {'creator_id': str(self.creator)}).content)['strike_count'], 1)

    def test_counter_notice_is_owner_bound_independent_and_reverses_strike_only_on_restoration(self):
        decision = self.remove()
        counter = {'video_id': str(self.video), 'creator_id': str(self.creator),
            'reason': 'I hold the rights and provide evidence for restoration.', 'accuracy_attested': True, 'key': 'copyright-counter-001'}
        self.assertEqual(self.call('counter_notice', self.owner, 'creator', counter | {'creator_id': str(uuid4())}).status_code, 404)
        result = self.call('counter_notice', self.owner, 'creator', counter)
        self.assertEqual(result.status_code, 201)
        self.assertEqual(self.call('counter_notice', self.owner, 'creator', counter).status_code, 200)
        self.assertEqual(CounterNotice.objects.count(), 1)
        self.assertEqual(AuditEvent.objects.filter(kind='moderation.counter_notice_created').count(), 1)
        self.assertEqual(CopyrightStrike.objects.filter(reversed_by__isnull=True).count(), 1)
        appeal = json.loads(result.content)['id']
        restore = {'target_id': appeal, 'action': 'restore', 'reason': 'Independent review accepted the rights evidence.', 'key': 'copyright-restore-001'}
        ModeratorAssignment.objects.create(moderator_id=self.reviewer, queue_scope='appeals', target_id=appeal)
        self.assertEqual(self.call('appeal_decision', self.reviewer, 'moderator', restore).status_code, 403)
        self.assertEqual(self.call('appeal_decision', self.second, 'administrator', restore, mfa=False).status_code, 403)
        self.assertEqual(self.call('appeal_decision', self.second, 'administrator', restore).status_code, 200)
        self.assertEqual(self.call('appeal_decision', self.second, 'administrator', restore).status_code, 200)
        self.assertEqual(CopyrightStrike.objects.filter(reversed_by__isnull=True).count(), 0)
        self.assertEqual(self.call('counter_notice', uuid4(), 'creator', counter).status_code, 409)

    def test_non_copyright_removal_cannot_create_counter_notice_or_strike(self):
        self.snapshot.update(state='removed', visibility='private', revision=2)
        ModerationAction.objects.create(id=uuid4(), video_id=self.video, reviewer_id=self.reviewer, creator_id=self.creator,
            action='remove', reason='Safety policy decision', revision=1, status='applied')
        data = {'video_id': str(self.video), 'creator_id': str(self.creator), 'reason': 'This is a safety policy appeal.',
                'accuracy_attested': True, 'key': 'wrong-counter-001'}
        self.assertEqual(self.call('counter_notice', self.owner, 'creator', data).status_code, 409)
        self.assertFalse(Appeal.objects.exists())
        self.assertFalse(CopyrightStrike.objects.exists())

    def test_historical_projection_uses_applied_evidence_and_known_owners_only(self):
        from importlib import import_module
        from django.apps import apps
        report = Report.objects.create(id=uuid4(), video_id=self.video, reporter_id=self.viewer,
                                       reason='copyright', details='Historical copyright evidence')
        removal = ModerationAction.objects.create(id=uuid4(), video_id=self.video, reviewer_id=self.reviewer,
            creator_id=self.creator, action='remove', reason='Applied historical copyright takedown',
            revision=1, status='applied', report=report)
        appeal = Appeal.objects.create(removal=removal, appellant_id=self.owner, reason='Historical rights evidence')
        restore = ModerationAction.objects.create(id=uuid4(), video_id=self.video, reviewer_id=self.second,
            creator_id=self.creator, action='restore', reason='Independently restored historical takedown',
            revision=2, status='applied', appeal=appeal)
        unknown = ModerationAction.objects.create(id=uuid4(), video_id=uuid4(), reviewer_id=self.reviewer,
            action='remove', reason='Historical unknown owner', revision=1, status='applied', reason_code='COPYRIGHT_TAKEDOWN')
        project = import_module('service.migrations.0006_copyright_notices').project_legacy_copyright
        project(apps, None); project(apps, None)
        self.assertEqual(CopyrightStrike.objects.count(), 1)
        self.assertEqual(CopyrightStrike.objects.get().reversed_by_id, restore.id)
        unknown.refresh_from_db()
        self.assertIsNone(unknown.creator_id)
