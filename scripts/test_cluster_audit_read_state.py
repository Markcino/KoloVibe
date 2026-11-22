"""Recognize the existing AWS audit-read state without enabling it or widening drift guards."""
import copy
import unittest
from unittest.mock import patch

from test_cluster_r1_rollout import R1Swarm, plan
from test_cluster_aws_profile import aws
from test_cluster_image_update import EVIDENCE, NEW_IMAGE
from test_cluster_operations import TARGET_REVISION, cluster


class AuditReadStateTests(unittest.TestCase):
    def live(self):
        swarm = R1Swarm()
        report = plan(swarm)
        for entry in report['entries']:
            swarm.services['kolovibe-' + entry['service']]['Spec'] = copy.deepcopy(entry['update_spec'])
        for service, flags in cluster.AWS_STAGING.audit_read_flags.items():
            container = swarm.services['kolovibe-' + service]['Spec']['TaskTemplate']['ContainerSpec']
            env = cluster.env_dict(container)
            env.update(flags)
            container['Env'] = [key + '=' + value for key, value in env.items()]
        return swarm

    def test_readback_row_is_exact_and_does_not_change_the_r1_activation_target(self):
        aws_profile = cluster.AWS_STAGING
        self.assertNotIn('audit_read', aws_profile.r1_flags['gateway'][cluster.FLAG_CAPABILITIES])
        self.assertEqual(aws_profile.r1_flags['audit'][cluster.FLAG_CAPABILITIES], '')
        with patch.object(cluster, 'PROFILE', aws_profile):
            for service, row in aws_profile.audit_read_flags.items():
                expected = 'audit-read' if service in ('audit', 'gateway') else 'r1'
                self.assertEqual(cluster.flag_state(service, row), expected)
            changed = dict(aws_profile.audit_read_flags['gateway'])
            for value in (changed[cluster.FLAG_CAPABILITIES] + ',unknown', 'audit_read', 'media,audit_read'):
                self.assertIsNone(cluster.flag_state('gateway', dict(changed, **{cluster.FLAG_CAPABILITIES: value})))

    def test_image_only_plan_preserves_capabilities_secrets_and_every_nonrelease_field(self):
        swarm = self.live()
        before = copy.deepcopy(swarm.services)
        with aws(swarm):
            report = cluster.update_plan(EVIDENCE, NEW_IMAGE, TARGET_REVISION, list(cluster.UPDATE_ORDER))
        for entry in report['entries']:
            original = before['kolovibe-' + entry['service']]['Spec']
            self.assertEqual(cluster.release_neutral(entry['update_spec']), cluster.release_neutral(original))
            self.assertEqual(cluster.secret_refs(entry['update_spec']), cluster.secret_refs(original))
        self.assertEqual(swarm.posts, [])

    def test_legacy_activation_cannot_silently_disable_active_audit_reads(self):
        swarm = self.live()
        with aws(swarm), self.assertRaisesRegex(RuntimeError, 'remove active audit reads'):
            cluster.update_plan(EVIDENCE, NEW_IMAGE, TARGET_REVISION, ['audit'], r1=True)
        self.assertEqual(swarm.posts, [])

    def test_only_the_recorded_service_can_mount_each_recorded_secret_name(self):
        pairs = [('gateway', 'outbound_key', 'kolovibe_gateway_audit_outbound_20261122_v1'),
                 ('gateway', 'trusted_peers', 'kolovibe_gateway_audit_peers_20261122_v1'),
                 ('audit', 'caller_keys', 'kolovibe_audit_callers_auditread_20261122_v1')]
        with patch.object(cluster, 'PROFILE', cluster.AWS_STAGING):
            for service, target, name in pairs:
                spec = {'TaskTemplate': {'ContainerSpec': {'Secrets': [{'SecretName': name, 'File': {'Name': target}}]}}}
                cluster.require_secrets_belong(service, spec)
                for other in set(cluster.SERVICES) - {service}:
                    with self.assertRaises(RuntimeError):
                        cluster.require_secrets_belong(other, spec)
                spec['TaskTemplate']['ContainerSpec']['Secrets'][0]['SecretName'] = name.replace('_v1', '_v2')
                with self.assertRaises(RuntimeError):
                    cluster.require_secrets_belong(service, spec)

    def test_unrecorded_profile_rows_and_oracle_are_rejected(self):
        bad = copy.deepcopy(cluster.AWS_STAGING.audit_read_flags)
        bad['identity'][cluster.FLAG_CAPABILITIES] += ',audit_read'
        with self.assertRaises(ValueError):
            cluster.check_flag_table(cluster.AWS_STAGING._replace(audit_read_flags=bad))
        self.assertIsNone(cluster.ORACLE_STAGING.audit_read_flags)
        with self.assertRaises(ValueError):
            cluster.check_flag_table(cluster.ORACLE_STAGING._replace(audit_read_flags=bad))
