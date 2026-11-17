"""The reviewed R1 capability rollout of the cluster tool: tables, plans, exact deltas and fail-closed guards."""

import copy
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'services'))

from test_cluster_aws_profile import AWS, AwsSwarm, aws  # noqa: E402
from test_cluster_image_update import EVIDENCE, NEW_IMAGE  # noqa: E402
from test_cluster_operations import TARGET_REVISION, cluster  # noqa: E402
from staging_runtime import capabilities as policy  # noqa: E402

R2_ID, R2_BUCKET = '1234abcd' * 4, 'kolovibe-media'
NET_ID = 'msg-net'
PROXY_NET_ID = 'r2-proxy-net'
SET_ENV = ['content:KOLOVIBE_R2_ACCOUNT_ID=' + R2_ID, 'content:KOLOVIBE_R2_MEDIA_BUCKET=' + R2_BUCKET]
ALL_SERVICES = list(cluster.UPDATE_ORDER)


class R1Swarm(AwsSwarm):
    """The AWS fixture plus the R1 secrets the owner would create and the messaging overlay."""

    def __init__(self, secrets=True, network=None, **kw):
        super().__init__(**kw)
        names = set()
        for rollout in cluster.AWS_STAGING.r1_rollout.values():
            names.update(rollout['mounts'].values())
        known = [{'ID': 'id-' + n, 'Spec': {'Name': n}} for n in sorted(names)] if secrets else []
        self.static['/v1.52/secrets'] = self.static['/v1.52/secrets'] + known
        net = {'ID': NET_ID, 'Name': cluster.MESSAGING_NETWORK, 'Driver': 'overlay', 'Internal': True,
               'Options': {'encrypted': ''}}
        net.update(network or {})
        proxy_net = {'ID': PROXY_NET_ID, 'Name': cluster.R2_PROXY_NETWORK, 'Driver': 'overlay', 'Internal': True,
                     'Options': {'encrypted': ''}}
        self.static['/v1.52/networks'] = [
            {'ID': 'services-net', 'Name': 'kolovibe_services'}, {'ID': 'data-net', 'Name': 'kolovibe_data'}, net, proxy_net]


def plan(swarm, services=ALL_SERVICES, **kw):
    kw.setdefault('r1', True)
    kw.setdefault('set_env', SET_ENV)
    with aws(swarm):
        return cluster.update_plan(EVIDENCE, NEW_IMAGE, TARGET_REVISION, services, **kw)


def entry(report, service):
    return next(e for e in report['entries'] if e['service'] == service)


class R1TableTests(unittest.TestCase):
    def test_tool_tables_mirror_the_runtime_capability_policy(self):
        self.assertEqual(cluster.R1_CAPABILITIES, frozenset(policy.CAPABILITIES))
        self.assertEqual(cluster.R1_APPLICABLE, {s: frozenset(c) for s, c in policy.APPLICABLE.items()})
        self.assertEqual(cluster.R1_REQUIRES, {c: frozenset(r) for c, r in policy.REQUIRES.items()})

    def test_every_r1_row_is_exactly_what_the_runtime_accepts(self):
        rows = cluster.AWS_STAGING.r1_flags
        gateway = policy.parse(rows['gateway'][cluster.FLAG_CAPABILITIES])
        for service, row in rows.items():
            caps = policy.parse(row[cluster.FLAG_CAPABILITIES])
            policy.check(service, caps, accounts=row[cluster.FLAG_ACCOUNTS] == '1',
                         privileged=row[cluster.FLAG_PRIVILEGED] == '1')
            self.assertEqual(caps, policy.slice_for(service, gateway), service)

    def test_the_full_r1_set_is_on_the_gateway_and_the_audit_service_stays_off(self):
        rows = cluster.AWS_STAGING.r1_flags
        self.assertEqual(set(rows['gateway'][cluster.FLAG_CAPABILITIES].split(',')), set(policy.CAPABILITIES))
        self.assertEqual(rows['audit'], {cluster.FLAG_ACCOUNTS: '0', cluster.FLAG_PRIVILEGED: '0',
                                         cluster.FLAG_ONBOARDING: '0', cluster.FLAG_CAPABILITIES: ''})
        self.assertEqual(rows['gateway'][cluster.FLAG_PRIVILEGED], '1')  # reviewer routes stay behind MFA

    def test_oracle_has_no_r1_rollout(self):
        self.assertIsNone(cluster.ORACLE_STAGING.r1_flags)
        with patch.object(cluster, 'PROFILE', cluster.ORACLE_STAGING), self.assertRaisesRegex(RuntimeError, 'not defined'):
            cluster.update_plan(EVIDENCE, NEW_IMAGE, TARGET_REVISION, ['audit'], r1=True)

    def test_broken_r1_tables_are_refused_at_review_time(self):
        good = cluster.r1_flag_table()
        bad = {
            'unsorted': dict(good, content=dict(good['content'], **{cluster.FLAG_CAPABILITIES: 'media,analytics'})),
            'inapplicable': dict(good, audit=dict(good['audit'], **{cluster.FLAG_CAPABILITIES: 'media'})),
            'accounts on a receiver': dict(good, content=dict(good['content'], **{cluster.FLAG_ACCOUNTS: '1'})),
            'moderation without mfa': dict(good, gateway=dict(good['gateway'], **{cluster.FLAG_PRIVILEGED: '0'}),
                                           identity=dict(good['identity'], **{cluster.FLAG_PRIVILEGED: '0'})),
            'onboarding mismatch': dict(good, creators=dict(good['creators'], **{cluster.FLAG_ONBOARDING: '0'})),
            'receiver differs from gateway': dict(good, points=dict(good['points'], **{cluster.FLAG_CAPABILITIES: ''})),
            'unknown capability': dict(good, gateway=dict(good['gateway'], **{cluster.FLAG_CAPABILITIES: 'x'})),
        }
        cluster.check_flag_table(AWS._replace(r1_flags=good))
        for label, table in bad.items():
            with self.subTest(label), self.assertRaises(ValueError):
                cluster.check_flag_table(AWS._replace(r1_flags=table))

    def test_every_r1_secret_a_service_mounts_is_allowed_for_that_service_only(self):
        for service, rollout in cluster.AWS_STAGING.r1_rollout.items():
            for name in rollout['mounts'].values():
                self.assertIn(name, AWS.service_allowed_secrets[service])
        self.assertNotIn('kolovibe_content_r2_access_key_r1_v1', AWS.service_allowed_secrets['points'])
        self.assertNotIn('kolovibe_content_r2_access_key_r1_v1', AWS.service_allowed_secrets['gateway'])


class DatabaseCaNameTests(unittest.TestCase):
    """Live AWS mounts the database CA from `kolovibe_pg_ca_v1` at target `db_ca` (read-only inspection)."""

    def spec(self, name, target='db_ca'):
        return {'TaskTemplate': {'ContainerSpec': {'Secrets': [
            {'SecretName': name, 'SecretID': 'x', 'File': {'Name': target}}]}}}

    def test_aws_accepts_only_its_recorded_database_ca_name_at_the_db_ca_target(self):
        with patch.object(cluster, 'PROFILE', AWS):
            cluster.require_secrets_belong('audit', self.spec('kolovibe_pg_ca_v1'))
            for name, target in (('db_ca', 'db_ca'), ('kolovibe_pg_ca_v1', 'internal_ca'), ('kolovibe_rmq_ca', 'db_ca'),
                                 ('audit_db_ca', 'db_ca'), ('kolovibe_pg_ca_v2', 'db_ca')):
                with self.subTest(name, target=target), self.assertRaisesRegex(RuntimeError, 'does not belong to it'):
                    cluster.require_secrets_belong('audit', self.spec(name, target))
            self.assertEqual(cluster.convention_secrets('audit')['db_ca'], 'kolovibe_pg_ca_v1')
            self.assertEqual(cluster.convention_secrets('audit')['internal_ca'], 'internal_ca')

    def test_oracle_still_demands_the_cluster_ca_under_its_own_name(self):
        with patch.object(cluster, 'PROFILE', cluster.ORACLE_STAGING):
            cluster.require_secrets_belong('audit', self.spec('db_ca'))
            with self.assertRaisesRegex(RuntimeError, 'does not belong to it'):
                cluster.require_secrets_belong('audit', self.spec('kolovibe_pg_ca_v1'))
            self.assertEqual(cluster.convention_secrets('audit')['db_ca'], 'db_ca')


class LiveShapeTests(unittest.TestCase):
    """AWS constants read from the live services on 14 November 2026 (read-only inspection), names only."""

    def test_database_host_and_logins_match_the_live_services(self):
        with patch.object(cluster, 'PROFILE', AWS):
            self.assertTrue(cluster.db_host_ok('kolovibe-postgres'))
            self.assertTrue(cluster.db_host_ok('172.31.16.20'))  # the earlier address form stays accepted
            for bad in ('postgres', 'kolovibe-postgres.evil.test', 'kolovibe-postgres ', '', 'vm-swarm-worker', '172.32.0.1'):
                self.assertFalse(cluster.db_host_ok(bad), bad)
            self.assertEqual(cluster.db_user('gateway'), 'kolovibe_gateway_app')
            self.assertEqual(cluster.db_user('audit'), 'kolovibe_audit_app')
        with patch.object(cluster, 'PROFILE', cluster.ORACLE_STAGING):
            self.assertEqual(cluster.db_user('gateway'), 'kv_gateway_run')
            self.assertFalse(cluster.db_host_ok('kolovibe-postgres'))

    def test_a_service_name_database_is_guarded_by_a_running_task_not_a_host_probe(self):
        with patch.object(cluster, 'PROFILE', AWS), \
                patch.object(cluster, 'gateway_database_endpoint', return_value=('kolovibe-postgres', '5432')), \
                patch.object(cluster, 'probe_database') as probe:
            with patch.object(cluster, 'run', return_value='abc123\n') as run:
                self.assertEqual(cluster.database_guard(), {'guard': True, 'db': 'kolovibe-postgres'})
            self.assertIn('label=com.docker.swarm.service.name=kolovibe-postgres', run.call_args[0][0])
            probe.assert_not_called()
            with patch.object(cluster, 'run', return_value=''), self.assertRaisesRegex(RuntimeError, 'not running'):
                cluster.database_guard()
        with patch.object(cluster, 'PROFILE', AWS), \
                patch.object(cluster, 'gateway_database_endpoint', return_value=('172.31.16.20', '5432')), \
                patch.object(cluster, 'probe_database', return_value={'guard': True, 'db': '172.31.16.20'}) as probe:
            cluster.database_guard()
            probe.assert_called_once_with('172.31.16.20', '5432')


class R1PlanTests(unittest.TestCase):
    def test_plan_adds_exactly_the_reviewed_flags_mounts_and_network_as_names(self):
        report = plan(R1Swarm())
        content = entry(report, 'content')
        self.assertEqual(content['action'], 'update')
        self.assertEqual(content['r1_changes']['secret_mounts'],
                         ['r2_access_key', 'r2_secret_key', 'rabbitmq_ca', 'rabbitmq_url'])
        self.assertEqual(content['r1_changes']['networks'], [cluster.MESSAGING_NETWORK, cluster.R2_PROXY_NETWORK])
        self.assertIn('KOLOVIBE_R2_HTTPS_PROXY', content['r1_changes']['env'])
        self.assertIn('KOLOVIBE_STAGING_CAPABILITIES', content['r1_changes']['env'])
        self.assertEqual(entry(report, 'audit')['r1_changes'], {'env': sorted(
            k for k, v in cluster.AWS_STAGING.r1_flags['audit'].items() if v != ''), 'secret_mounts': [], 'networks': []})
        text = repr(cluster.public_plan(report))
        for needle in (R2_ID, R2_BUCKET, 'id-kolovibe_', 'update_spec'):
            self.assertNotIn(needle, text)

    def test_the_planned_spec_differs_from_the_live_spec_only_by_the_reviewed_additions(self):
        swarm = R1Swarm()
        report = plan(swarm)
        for e in report['entries']:
            live = swarm.services['kolovibe-' + e['service']]['Spec']
            new = e['update_spec']
            c_new, c_live = new['TaskTemplate']['ContainerSpec'], live['TaskTemplate']['ContainerSpec']
            env_new, env_live = cluster.env_dict(c_new), cluster.env_dict(c_live)
            changed = {k for k in env_new if env_new[k] != env_live.get(k)} | (set(env_live) - set(env_new))
            self.assertTrue(changed <= set(e['r1_changes']['env']), e['service'])
            self.assertEqual(set(cluster.secret_refs(new)) - set(cluster.secret_refs(live)),
                             set(e['r1_changes']['secret_mounts']))
            for key in ('Image', 'Hostname', 'User', 'ReadOnly', 'Healthcheck'):
                if key != 'Image':
                    self.assertEqual(c_new.get(key), c_live.get(key), key)
            self.assertEqual(new['TaskTemplate']['Placement'], live['TaskTemplate']['Placement'])
            self.assertEqual(new['TaskTemplate'].get('Resources'), live['TaskTemplate'].get('Resources'))
            self.assertEqual(new.get('EndpointSpec'), live.get('EndpointSpec'))
        content = cluster.env_dict(entry(report, 'content')['update_spec']['TaskTemplate']['ContainerSpec'])
        self.assertEqual(content['KOLOVIBE_R2_ACCOUNT_ID'], R2_ID)
        self.assertEqual(content['KOLOVIBE_STAGING_CAPABILITIES'], 'analytics,engagement,media,moderation')

    def test_identity_without_mfa_and_audit_mounts_gets_them_before_privileged_is_enabled(self):
        swarm = R1Swarm()
        container = swarm.services['kolovibe-identity']['Spec']['TaskTemplate']['ContainerSpec']
        gone = {'mfa_encryption_key', 'audit_signing_key', 'audit_peers'}  # absent on the live AWS identity
        container['Secrets'] = [r for r in container['Secrets'] if r['File']['Name'] not in gone]
        container['Env'] = [e for e in container['Env'] if e.split('=', 1)[0] not in (
            'KOLOVIBE_MFA_ENCRYPTION_KEY_FILE', 'KOLOVIBE_OUTBOUND_KEY_FILE', 'KOLOVIBE_TRUSTED_PEERS_FILE')]
        report = plan(swarm, ['identity'], set_env=None)
        self.assertEqual(entry(report, 'identity')['r1_changes']['secret_mounts'], sorted(gone))
        env = cluster.env_dict(entry(report, 'identity')['update_spec']['TaskTemplate']['ContainerSpec'])
        self.assertEqual(env['KOLOVIBE_STAGING_PRIVILEGED'], '1')
        self.assertEqual(env['KOLOVIBE_MFA_ENCRYPTION_KEY_FILE'], '/run/secrets/mfa_encryption_key')
        # Without the secret objects the plan stops: privileged is never switched on first.
        swarm.static['/v1.52/secrets'] = [x for x in swarm.static['/v1.52/secrets']
                                          if x['Spec']['Name'] != 'identity_mfa_encryption']
        with self.assertRaisesRegex(RuntimeError, 'identity_mfa_encryption'):
            plan(swarm, ['identity'], set_env=None)

    def test_a_missing_r1_secret_stops_the_plan_naming_only_the_secret(self):
        with self.assertRaisesRegex(RuntimeError, 'R1 secret does not exist in Swarm.*kolovibe_content_'):
            plan(R1Swarm(secrets=False), ['content'])

    def test_r2_identifiers_are_required_validated_and_never_secrets(self):
        with self.assertRaisesRegex(RuntimeError, '--set-env content:KOLOVIBE_R2_ACCOUNT_ID'):
            plan(R1Swarm(), ['content'], set_env=None)
        for bad in ('content:KOLOVIBE_R2_ACCOUNT_ID=short', 'content:KOLOVIBE_R2_MEDIA_BUCKET=Bad_Bucket',
                    'content:KOLOVIBE_R2_SECRET_KEY=abcdefghijklmnop', 'points:KOLOVIBE_R2_ACCOUNT_ID=' + R2_ID,
                    'content:KOLOVIBE_R2_ACCOUNT_ID=' + R2_ID + ' x', 'nonsense'):
            with self.subTest(bad), self.assertRaises(RuntimeError):
                plan(R1Swarm(), ['content'], set_env=[bad, SET_ENV[1]])
        with self.assertRaisesRegex(RuntimeError, 'twice'):
            plan(R1Swarm(), ['content'], set_env=SET_ENV + [SET_ENV[0]])
        with self.assertRaisesRegex(RuntimeError, 'only valid with --enable-r1-capabilities'):
            plan(R1Swarm(), ['content'], r1=False, set_env=SET_ENV)

    def test_a_missing_or_exposed_messaging_network_stops_the_plan(self):
        for label, network in (('plain', {'Options': {}}), ('not internal', {'Internal': False}),
                               ('not overlay', {'Driver': 'bridge'})):
            with self.subTest(label), self.assertRaisesRegex(RuntimeError, 'internal encrypted overlay'):
                plan(R1Swarm(network=network), ['content'])
        swarm = R1Swarm()
        swarm.static['/v1.52/networks'] = swarm.static['/v1.52/networks'][:2]
        with self.assertRaisesRegex(RuntimeError, 'R1 network is missing'):
            plan(swarm, ['content'])

    def test_a_different_secret_already_at_a_new_mount_target_is_refused(self):
        swarm = R1Swarm()
        container = swarm.services['kolovibe-content']['Spec']['TaskTemplate']['ContainerSpec']
        container['Secrets'].append({'SecretName': 'content_other', 'SecretID': 'x', 'File': {'Name': 'rabbitmq_url'}})  # pragma: allowlist secret
        swarm.static['/v1.52/secrets'].append({'ID': 'x', 'Spec': {'Name': 'content_other'}})
        with self.assertRaisesRegex(RuntimeError, 'already mounts a different secret at rabbitmq_url'):
            plan(swarm, ['content'])

    def test_a_foreign_secret_in_the_rollout_table_is_refused_by_the_ownership_rule(self):
        rollout = copy.deepcopy(cluster.AWS_STAGING.r1_rollout)
        rollout['content']['mounts']['r2_access_key'] = 'points_callers'
        swarm = R1Swarm()
        swarm.static['/v1.52/secrets'].append({'ID': 'id-points_callers', 'Spec': {'Name': 'points_callers'}})
        with patch.object(cluster, 'AWS_STAGING', AWS._replace(r1_rollout=rollout)), \
                patch.object(cluster, 'PROFILES', {'aws-staging': AWS._replace(r1_rollout=rollout)}):
            with patch.object(cluster, 'PROFILE', AWS._replace(r1_rollout=rollout)), \
                    patch.object(cluster, 'root'), patch.object(cluster, 'docker', side_effect=swarm), patch('sys.stderr'):
                with self.assertRaisesRegex(RuntimeError, 'does not belong to it'):
                    cluster.update_plan(EVIDENCE, NEW_IMAGE, TARGET_REVISION, ['content'], r1=True, set_env=SET_ENV)

    def test_unknown_live_flags_stop_an_r1_plan_naming_only_variables(self):
        swarm = R1Swarm()
        env = swarm.services['kolovibe-points']['Spec']['TaskTemplate']['ContainerSpec']['Env']
        env.append('KOLOVIBE_STAGING_CAPABILITIES=media')
        with self.assertRaises(RuntimeError) as raised:
            plan(swarm, ['points'], set_env=None)
        self.assertIn('KOLOVIBE_STAGING_CAPABILITIES', str(raised.exception))
        self.assertNotIn('media', str(raised.exception).replace('KOLOVIBE_STAGING_CAPABILITIES', ''))

    def test_a_service_already_on_r1_is_unchanged_and_plain_image_updates_still_pass_the_guard(self):
        swarm = R1Swarm()
        report = plan(swarm, ['content'])
        done = report['entries'][0]['update_spec']
        swarm.services['kolovibe-content']['Spec'] = cluster.pinned(done, cluster.BASELINE_IMAGE, cluster.BASELINE_REVISION)
        again = plan(swarm, ['content'], set_env=None)  # identifiers are read back from the live service
        self.assertEqual(again['entries'][0]['r1_changes'], None)
        self.assertEqual(again['entries'][0]['action'], 'update')  # the image still moves
        swarm.services['kolovibe-content']['Spec'] = cluster.pinned(done, NEW_IMAGE, TARGET_REVISION)
        self.assertEqual(plan(swarm, ['content'], set_env=None)['entries'][0]['action'], 'unchanged')
        plain = plan(swarm, ['content'], r1=False, set_env=None)  # no flag: image-only plan keeps R1 env and mounts
        self.assertEqual(plain['entries'][0]['action'], 'unchanged')

    def test_without_the_flag_nothing_r1_is_ever_added(self):
        report = plan(R1Swarm(), ALL_SERVICES, r1=False, set_env=None)
        for e in report['entries']:
            self.assertIsNone(e['r1_changes'])
            self.assertEqual(cluster.env_dict(e['update_spec']['TaskTemplate']['ContainerSpec']).get(
                'KOLOVIBE_STAGING_CAPABILITIES'), None)

    def test_the_reviewed_delta_cannot_smuggle_another_change(self):
        swarm = R1Swarm()
        live = swarm.services['kolovibe-content']['Spec']
        with aws(swarm):
            delta = cluster.r1_delta('content', live, {n: 'id-' + n for n in AWS.service_allowed_secrets['content']},
                                     {cluster.MESSAGING_NETWORK: {'ID': NET_ID, 'Name': cluster.MESSAGING_NETWORK, 'Driver': 'overlay',
                                              'Internal': True, 'Options': {'encrypted': ''}},
                                      cluster.R2_PROXY_NETWORK: {'ID': PROXY_NET_ID, 'Name': cluster.R2_PROXY_NETWORK,
                                              'Driver': 'overlay', 'Internal': True, 'Options': {'encrypted': ''}}},
                                     {'KOLOVIBE_R2_ACCOUNT_ID': R2_ID, 'KOLOVIBE_R2_MEDIA_BUCKET': R2_BUCKET})
            tampered = copy.deepcopy(live)
            tampered['TaskTemplate']['Placement']['Constraints'] = ['node.role == worker']
            expected = cluster.apply_r1(live, delta)
            expected['TaskTemplate']['Placement']['Constraints'] = ['node.role == manager']
            self.assertNotEqual(cluster.release_neutral(cluster.r1_strip(expected, 'content', delta)),
                                cluster.release_neutral(cluster.r1_strip(live, 'content', delta)))
            self.assertEqual(cluster.release_neutral(cluster.r1_strip(cluster.apply_r1(live, delta), 'content', delta)),
                             cluster.release_neutral(cluster.r1_strip(live, 'content', delta)))


class R1ApplyTests(unittest.TestCase):
    def apply(self, swarm, services, **kw):
        with aws(swarm), tempfile.TemporaryDirectory() as directory, patch('sys.stderr'):
            record = str(Path(directory) / 'r.json')
            cluster.update('e.json', 'operator', NEW_IMAGE, TARGET_REVISION, services, 'WAIVED-R1-STAGING-20261114',
                           NEW_IMAGE, record, True, None, True, SET_ENV if 'content' in services else None, **kw)
            return record

    def test_apply_then_roll_back_restores_flags_mounts_and_networks_per_service(self):
        swarm = R1Swarm()
        before = copy.deepcopy(swarm.services['kolovibe-points']['Spec'])
        self.apply(swarm, ['points'])
        live = swarm.services['kolovibe-points']['Spec']
        with patch.object(cluster, 'PROFILE', AWS):
            self.assertEqual(cluster.flag_state('points', cluster.env_dict(live['TaskTemplate']['ContainerSpec'])), 'r1')
        self.assertIn('rabbitmq_url', cluster.secret_refs(live))
        self.assertEqual([p[0] for p in swarm.posts], ['kolovibe-points'])
        with aws(swarm), patch('sys.stderr'):
            cluster.rollback(['points'], 'points')
        self.assertEqual(swarm.services['kolovibe-points']['Spec'], before)

    def test_the_restore_point_reference_may_name_the_owner_waiver(self):
        self.assertTrue(cluster.REF_RE.fullmatch(cluster.RESTORE_WAIVER))
        swarm = R1Swarm()
        self.apply(swarm, ['audit'])  # accepted: nothing about a restore is verified by the tool either way

    def test_a_dry_run_changes_nothing(self):
        swarm = R1Swarm()
        with aws(swarm), patch('sys.stderr'):
            cluster.update('e.json', 'operator', NEW_IMAGE, TARGET_REVISION, ALL_SERVICES, None, None, 'x.json', False,
                           None, True, SET_ENV)
        self.assertEqual(swarm.posts, [])


if __name__ == '__main__':
    unittest.main()
