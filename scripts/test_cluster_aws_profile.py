"""Offline tests for the explicit AWS staging profile of the cluster tool.

No Docker, AWS, registry or VM is contacted. Fixtures carry secret *names* only; the AWS names
below are the ones observed read-only on the AWS staging (docs/operations R1 dry run, 4.2).
"""
import contextlib
import copy
import json
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent))
from test_cluster_image_update import EVIDENCE, FakeSwarm, NEW_IMAGE, manager  # noqa: E402
from test_cluster_operations import TARGET, TARGET_REVISION, all_secrets, cluster, gateway_fixture  # noqa: E402

AWS = cluster.AWS_STAGING
MANAGER, WORKER = 'ip-172-31-30-236', 'ip-172-31-16-154'
PIN = 'node.hostname==' + WORKER
DB = '172.31.16.20'
APPROVAL = 'kolovibe_account_uat_approval_20261110_v1'
SMTP_USER = 'kolovibe_identity_smtp_user_20261110_v1'
SMTP_PASSWORD = 'kolovibe_identity_smtp_password_20261110_v1'  # pragma: allowlist secret
PEERS = 'kolovibe_gateway_trusted_peers_accounts_20261110_v1'
AWS_ONLY = (APPROVAL, SMTP_USER, SMTP_PASSWORD, PEERS)


def mount(target, name):
    # Offline fixture: a Swarm secret *name* and a placeholder id; no value exists here.
    return {'SecretName': name, 'SecretID': 'id-' + name, 'File': {'Name': target}}  # pragma: allowlist secret


def aws_gateway(constraint=PIN, db_host=DB, networks=('services-net', 'data-net'), extra_mounts=()):
    gateway = gateway_fixture()
    spec = gateway['Spec']
    spec['Name'] = 'kolovibe-gateway'
    container = spec['TaskTemplate']['ContainerSpec']
    container['Hosts'] = []
    container['Env'] = [('KOLOVIBE_DB_HOST=' + db_host) if e.startswith('KOLOVIBE_DB_HOST=') else e
                        for e in container['Env']]
    container['Secrets'] = [mount('django_key', 'gateway_django'), mount('internal_ca', 'internal_ca'),
                            mount('db_ca', 'db_ca'), mount('trusted_peers', PEERS),
                            mount('account_approvals', APPROVAL), *extra_mounts]
    spec['TaskTemplate']['Networks'] = [{'Target': n} for n in networks]
    spec['TaskTemplate']['Placement'] = {'Constraints': [constraint]}
    return gateway


def aws_names(service):
    names = cluster.convention_secrets(service)
    if service == 'identity':
        names.update(smtp_user=SMTP_USER, smtp_password=SMTP_PASSWORD, account_approvals=APPROVAL)
    return names


class AwsSwarm(FakeSwarm):
    """Eight `kolovibe-<service>` services on the AWS node; the node has no labels."""

    def __init__(self, gateway=None, node=None, **kw):
        super().__init__(**kw)
        gateway = gateway or aws_gateway()
        gateway['Version'] = {'Index': 7}
        known = {**all_secrets(), **{n: 'id-' + n for n in AWS_ONLY}}
        with patch.object(cluster, 'PROFILE', AWS):
            self.services = {'kolovibe-gateway': gateway}
            for service in cluster.SERVICES[1:]:
                spec = cluster.api_spec(gateway, service, known, cluster.BASELINE_IMAGE, cluster.BASELINE_REVISION,
                                        names=aws_names(service))
                self.services[spec['Name']] = {'ID': 'id-' + service, 'Version': {'Index': 3}, 'Spec': spec}
        self.static['/v1.52/secrets'] = [{'ID': 'id-' + n, 'Spec': {'Name': n}} for n in known]
        self.static['/v1.52/nodes'] = [node or {'Description': {'Hostname': WORKER}, 'Status': {'State': 'ready'},
                                                 'Spec': {'Availability': 'active', 'Labels': {}}}]


@contextlib.contextmanager
def aws(swarm):
    with patch.object(cluster, 'PROFILE', AWS), manager(swarm):
        yield


class ProfileSelectionTests(unittest.TestCase):
    def test_profiles_are_a_fixed_reviewed_table_chosen_by_name_only(self):
        self.assertEqual(sorted(cluster.PROFILES), ['aws-staging', 'oracle-staging'])
        with patch.object(cluster, 'PROFILE', cluster.ORACLE_STAGING):
            cluster.use_profile('aws-staging')
            self.assertIs(cluster.PROFILE, AWS)
            for bad in ('', 'AWS-STAGING', 'aws', 'ip-172-31-16-154', 'vm-swarm-worker'):
                with self.subTest(bad=bad), self.assertRaisesRegex(RuntimeError, 'Unknown profile'):
                    cluster.use_profile(bad)
            self.assertIs(cluster.PROFILE, AWS)  # a rejected name changes nothing

    def run_main(self, *argv):
        with patch.object(sys, 'argv', ['kolovibe_cluster.py', *argv]), \
                patch.object(cluster, 'PROFILE', cluster.ORACLE_STAGING):
            return cluster.main()

    def test_every_cluster_mode_requires_an_explicit_profile(self):
        for mode in ('worker-preflight', 'plan', 'update-plan', 'update', 'rollback', 'verify-worker', 'deploy'):
            with self.subTest(mode=mode), patch('sys.stderr'), self.assertRaises(SystemExit) as raised:
                self.run_main(mode)
            self.assertEqual(raised.exception.code, 2)
        with patch('sys.stderr'), self.assertRaises(SystemExit):
            self.run_main('worker-preflight', '--profile', 'guess-from-hostname')

    def test_the_hostname_never_selects_a_profile(self):
        with patch.object(cluster.socket, 'gethostname', return_value=WORKER), \
                patch.object(cluster.os, 'geteuid', return_value=0), patch('sys.stderr'), \
                self.assertRaises(SystemExit):
            self.run_main('worker-preflight')
        self.assertIs(cluster.PROFILE, cluster.ORACLE_STAGING)

    def test_verify_edge_needs_no_profile_and_cloud_run_is_oracle_only(self):
        report = {'checks': []}
        with patch.object(cluster, 'verify_edge', return_value=report) as edge, patch('builtins.print'):
            self.run_main('verify-edge')
        edge.assert_called_once()
        with patch.object(cluster, 'PROFILE', AWS), self.assertRaisesRegex(RuntimeError, 'only supports --profile oracle'):
            cluster.cloud_run('operator', TARGET, TARGET_REVISION)

    def test_dry_run_is_still_the_default_for_update(self):
        swarm = AwsSwarm()
        with aws(swarm), patch('sys.stderr'), tempfile.TemporaryDirectory() as directory:
            record = Path(directory) / 'r.json'
            cluster.update('e.json', 'operator', NEW_IMAGE, TARGET_REVISION, ['audit'], None, None, str(record), False)
            self.assertFalse(record.exists())
        self.assertEqual(swarm.posts, [])


class HostGuardTests(unittest.TestCase):
    def check(self, profile, running_on, required, uid=0):
        with patch.object(cluster, 'PROFILE', profile), patch.object(cluster.os, 'geteuid', return_value=uid), \
                patch.object(cluster.socket, 'gethostname', return_value=running_on):
            cluster.root(required)

    def test_aws_hostnames_are_accepted_only_under_the_aws_profile(self):
        self.check(AWS, WORKER, AWS.worker_host)
        self.check(AWS, MANAGER, AWS.manager_host)
        self.check(cluster.ORACLE_STAGING, 'vm-swarm-worker', cluster.ORACLE_STAGING.worker_host)

    def test_other_environments_hostnames_and_non_root_are_refused(self):
        for profile, host in ((AWS, 'vm-swarm-worker'), (AWS, 'vm-swarm-manager'), (AWS, 'ip-172-31-99-1'),
                              (cluster.ORACLE_STAGING, WORKER), (cluster.ORACLE_STAGING, MANAGER)):
            with self.subTest(profile=profile.name, host=host), self.assertRaisesRegex(RuntimeError, 'Run with sudo'):
                self.check(profile, host, profile.worker_host)
        with self.assertRaisesRegex(RuntimeError, 'Run with sudo'):
            self.check(AWS, WORKER, AWS.worker_host, uid=1000)
        with self.assertRaisesRegex(RuntimeError, 'Run with sudo'):  # worker host is not the manager
            self.check(AWS, WORKER, AWS.manager_host)

    def test_manager_modes_demand_the_manager_not_the_worker(self):
        with patch.object(cluster, 'PROFILE', AWS), patch.object(cluster, 'root') as guard, \
                patch.object(cluster, 'policy_baseline'), patch.object(cluster, 'docker', side_effect=[
                    {'ApiVersion': '1.52'}, {'Swarm': {'ControlAvailable': True},
                                             'Plugins': {'Authorization': ['openpolicyagent/opa-docker-authz-v2:0.9']}}]), \
                patch.object(cluster, 'run', return_value='true ["-policy-file","/opa/policies/authz.rego","-quiet"]'):
            cluster.manager_checks()
        guard.assert_called_once_with(MANAGER)


class EvidenceTests(unittest.TestCase):
    def load(self, **overrides):
        evidence = {'kind': 'KVB-CLUSTER-WORKER-V1', 'host': WORKER, 'profile': 'aws-staging',
                    'time': time.time(), 'guard': True, 'gateway_live': True}
        evidence.update(overrides)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'evidence.json'
            path.write_text(json.dumps({k: v for k, v in evidence.items() if v is not None}))
            return cluster.load_evidence(path)

    def test_aws_evidence_is_accepted_only_for_the_aws_profile(self):
        with patch.object(cluster, 'PROFILE', AWS):
            self.load()
            for label, overrides in (('oracle host', {'host': 'vm-swarm-worker'}),
                                     ('oracle profile', {'profile': 'oracle-staging'}),
                                     ('no profile', {'profile': None}), ('other host', {'host': 'ip-172-31-1-1'}),
                                     ('stale', {'time': time.time() - 301}), ('future', {'time': time.time() + 100}),
                                     ('guard', {'guard': False}), ('gateway', {'gateway_live': False})):
                with self.subTest(label), self.assertRaisesRegex(RuntimeError, 'Fresh VM2 preflight'):
                    self.load(**overrides)

    def test_aws_evidence_cannot_drive_the_oracle_profile(self):
        with patch.object(cluster, 'PROFILE', cluster.ORACLE_STAGING), \
                self.assertRaisesRegex(RuntimeError, 'Fresh VM2 preflight'):
            self.load()


class WorkerPreflightTests(unittest.TestCase):
    def preflight(self, profile, db_probe=None):
        calls = []
        def run(args, **kw):
            calls.append(args)
            return json.dumps({'guard': True, 'db': '10.0.2.103'})
        with patch.object(cluster, 'PROFILE', profile), patch.object(cluster, 'root'), \
                patch.object(cluster, 'run', side_effect=run), \
                patch.object(cluster, 'gateway_database_endpoint', return_value=(DB, '5432')), \
                patch.object(cluster, 'probe_database', return_value={'guard': True, 'db': DB}) as probe, \
                patch.object(cluster, 'inside', return_value=[200, {'status': 'ok'}]), \
                patch.object(cluster.Path, 'read_text', return_value='MemAvailable: 4000000 kB'):
            return cluster.worker_preflight(), calls, probe

    def test_aws_preflight_never_needs_the_oracle_route_script_and_records_its_profile(self):
        evidence, calls, probe = self.preflight(AWS)
        probe.assert_called_once_with(DB, '5432')
        self.assertFalse(any('kolovibe_db_route_fix' in ' '.join(c) for c in calls))
        self.assertEqual((evidence['host'], evidence['profile'], evidence['guard'], evidence['gateway_live']),
                         (WORKER, 'aws-staging', True, True))

    def test_oracle_preflight_still_requires_its_route_script(self):
        evidence, calls, probe = self.preflight(cluster.ORACLE_STAGING)
        probe.assert_not_called()
        self.assertTrue(any('kolovibe_db_route_fix' in ' '.join(c) for c in calls))
        self.assertEqual((evidence['host'], evidence['profile']), ('vm-swarm-worker', 'oracle-staging'))

    def test_failed_database_probe_or_gateway_stops_the_preflight(self):
        with patch.object(cluster, 'PROFILE', AWS), patch.object(cluster, 'root'), \
                patch.object(cluster, 'gateway_database_endpoint', return_value=(DB, '5432')), \
                patch.object(cluster, 'probe_database', side_effect=RuntimeError('BLOCKED: Database does not offer TLS')), \
                patch.object(cluster, 'inside') as inside:
            with self.assertRaisesRegex(RuntimeError, 'does not offer TLS'):
                cluster.worker_preflight()
            inside.assert_not_called()
        with patch.object(cluster, 'PROFILE', AWS), patch.object(cluster, 'root'), \
                patch.object(cluster, 'database_guard'), patch.object(cluster, 'inside', return_value=[503, None]):
            with self.assertRaisesRegex(RuntimeError, 'Gateway HTTPS liveness'):
                cluster.worker_preflight()


class DatabaseProbeTests(unittest.TestCase):
    """The probe sends only PostgreSQL's SSLRequest; no credential exists in this process."""

    class Socket:
        def __init__(self, reply):
            self.reply, self.sent = reply, b''
        def __enter__(self):
            return self
        def __exit__(self, *exc):
            return False
        def sendall(self, data):
            self.sent += data
        def recv(self, size):
            return self.reply

    def probe(self, reply=b'S', version='TLSv1.3', host=DB, port='5432', connect_error=None, handshake_error=None):
        sock = self.Socket(reply)
        context = MagicMock()
        wrapped = MagicMock()
        wrapped.__enter__.return_value.version.return_value = version
        context.wrap_socket.return_value = wrapped
        if handshake_error:
            context.wrap_socket.side_effect = handshake_error
        with patch.object(cluster, 'PROFILE', AWS), \
                patch.object(cluster.socket, 'create_connection', side_effect=connect_error, return_value=sock) as connect, \
                patch.object(cluster.ssl, 'SSLContext', return_value=context):
            result = cluster.probe_database(host, port)
        return result, sock, connect, context

    def test_tls_offered_and_handshake_complete(self):
        result, sock, connect, context = self.probe()
        self.assertEqual(result, {'guard': True, 'db': DB})
        self.assertEqual(sock.sent, bytes([0, 0, 0, 8, 4, 210, 22, 47]))  # SSLRequest only
        connect.assert_called_once_with((DB, 5432), timeout=5)
        self.assertEqual(context.minimum_version, cluster.ssl.TLSVersion.TLSv1_2)

    def test_plaintext_unreachable_or_failed_handshake_are_refused(self):
        for label, kwargs, message in (
                ('server refuses TLS', {'reply': b'N'}, 'does not offer TLS'),
                ('no answer', {'reply': b''}, 'does not offer TLS'),
                ('no version negotiated', {'version': None}, 'handshake failed'),
                ('handshake error', {'handshake_error': cluster.ssl.SSLError()}, 'handshake failed'),
                ('refused', {'connect_error': ConnectionRefusedError()}, 'not reachable'),
                ('timeout', {'connect_error': TimeoutError()}, 'not reachable')):
            with self.subTest(label), self.assertRaisesRegex(RuntimeError, message):
                self.probe(**kwargs)

    def test_addresses_outside_the_aws_profile_are_never_contacted(self):
        for host in ('10.0.2.103', '172.32.0.1', 'vm-swarm-worker', '127.0.0.1', '', '172.31.0.1; id'):
            with self.subTest(host=host), patch.object(cluster.socket, 'create_connection') as connect, \
                    patch.object(cluster, 'PROFILE', AWS), self.assertRaisesRegex(RuntimeError, 'outside the aws-staging'):
                cluster.probe_database(host, '5432')
            connect.assert_not_called()
        for port in ('0', '65536', 'x', ''):
            with self.subTest(port=port), patch.object(cluster, 'PROFILE', AWS), \
                    self.assertRaisesRegex(RuntimeError, 'outside the aws-staging'):
                cluster.probe_database(DB, port)

    def test_endpoint_is_read_only_from_the_gateways_own_database_settings(self):
        inspect = json.dumps([{'Config': {'Env': ['KOLOVIBE_DB_HOST=' + DB, 'KOLOVIBE_DB_PORT=6432', 'OTHER=ignored']}}])
        with patch.object(cluster, 'container_id', return_value='cid'), patch.object(cluster, 'run', return_value=inspect):
            self.assertEqual(cluster.gateway_database_endpoint(), (DB, '6432'))


class AwsServicePlanTests(unittest.TestCase):
    def plan(self, swarm, services, **kw):
        with aws(swarm):
            return cluster.update_plan(EVIDENCE, NEW_IMAGE, TARGET_REVISION, services, **kw)

    def test_every_receiver_and_the_gateway_plan_on_the_aws_names(self):
        swarm = AwsSwarm()
        report = self.plan(swarm, list(cluster.UPDATE_ORDER))
        self.assertEqual([e['service'] for e in report['entries']], list(cluster.UPDATE_ORDER))
        self.assertTrue(all(e['action'] == 'update' for e in report['entries']))
        self.assertEqual(swarm.posts, [])
        self.assertEqual(swarm.services['kolovibe-identity']['Spec']['Name'], 'kolovibe-identity')

    def test_create_plan_adopts_the_existing_aws_services_and_creates_only_missing_ones(self):
        swarm = AwsSwarm()
        with aws(swarm):
            self.assertEqual(cluster.plan(EVIDENCE, NEW_IMAGE, TARGET_REVISION)[2], [])
            del swarm.services['kolovibe-points']
            new = cluster.plan(EVIDENCE, NEW_IMAGE, TARGET_REVISION)[2]
        self.assertEqual([s['Name'] for s in new], ['kolovibe-points'])
        env = cluster.env_dict(new[0]['TaskTemplate']['ContainerSpec'])
        self.assertEqual(env['KOLOVIBE_DB_HOST'], DB)
        self.assertEqual(new[0]['TaskTemplate']['Placement']['Constraints'], [PIN])

    def test_oracle_service_names_are_not_the_aws_services(self):
        swarm = AwsSwarm()
        swarm.services['kvtest-audit'] = swarm.services.pop('kolovibe-audit')
        swarm.services['kvtest-audit']['Spec']['Name'] = 'kvtest-audit'
        with self.assertRaisesRegex(RuntimeError, 'kolovibe-audit is not deployed'):
            self.plan(swarm, ['audit'])

    def test_update_apply_changes_only_the_named_aws_service_and_rolls_back(self):
        swarm = AwsSwarm()
        with aws(swarm), tempfile.TemporaryDirectory() as directory, patch('sys.stderr'):
            record = str(Path(directory) / 'r.json')
            cluster.update('e.json', 'operator', NEW_IMAGE, TARGET_REVISION, ['audit'], 'restore-2026-11-14',
                           NEW_IMAGE, record, False)
            self.assertNotIn('Secrets', Path(record).read_text())
            with self.assertRaisesRegex(RuntimeError, 'exactly the planned'):
                cluster.rollback(['audit'], 'identity')
            swarm.posts.clear()
            cluster.rollback(['audit'], 'audit')
        self.assertEqual([p[0] for p in swarm.posts], ['kolovibe-audit'])
        self.assertEqual(cluster.live_image(swarm.services['kolovibe-audit']['Spec']), cluster.BASELINE_IMAGE)
        self.assertEqual(cluster.live_image(swarm.services['kolovibe-gateway']['Spec']), cluster.BASELINE_IMAGE)

    def test_update_guards_still_apply_on_aws(self):
        swarm = AwsSwarm()
        with aws(swarm), tempfile.TemporaryDirectory() as directory, patch('sys.stderr'):
            record = str(Path(directory) / 'r.json')
            with self.assertRaisesRegex(RuntimeError, 'repeat the approved release digest'):
                cluster.update('e.json', 'operator', NEW_IMAGE, TARGET_REVISION, ['audit'], 'restore-2026-11-14',
                               cluster.REPOSITORY + '@sha256:' + 'f' * 64, record, False)
            with self.assertRaisesRegex(RuntimeError, 'restore-point-ref'):
                cluster.update('e.json', 'operator', NEW_IMAGE, TARGET_REVISION, ['audit'], None, NEW_IMAGE, record, False)
            with self.assertRaisesRegex(RuntimeError, 'No readiness healthcheck'):
                cluster.update('e.json', 'operator', NEW_IMAGE, TARGET_REVISION, ['gateway'], 'restore-2026-11-14',
                               NEW_IMAGE, record, False)
        self.assertEqual(swarm.posts, [])

    def test_verify_worker_uses_the_aws_worker_and_service_names(self):
        seen = []
        with patch.object(cluster, 'PROFILE', AWS), patch.object(cluster, 'root') as guard, \
                patch.object(cluster, 'inside', side_effect=lambda s, m, i: seen.append(s) or {'service': s, 'checks': []}), \
                patch.object(cluster, 'run', return_value=''):
            cluster.verify_worker(NEW_IMAGE, ['audit'])
        guard.assert_called_once_with(WORKER)
        self.assertEqual(seen, ['audit'])
        with patch.object(cluster, 'PROFILE', AWS), patch.object(cluster, 'run', return_value='cid\n') as run:
            cluster.container_id('audit')
        self.assertIn('label=com.docker.swarm.service.name=kolovibe-audit', run.call_args[0][0])

    def test_container_probe_runs_under_the_same_profile(self):
        calls = []
        with patch.object(cluster, 'PROFILE', AWS), patch.object(cluster, 'container_id', return_value='cid'), \
                patch.object(cluster, 'run', side_effect=lambda args, **kw: calls.append(kw) or
                             (json.dumps([{'Config': {'Image': NEW_IMAGE}}]) if args[1] == 'inspect' else '{}')):
            cluster.inside('audit', 'tests', NEW_IMAGE)
        self.assertIn("use_profile('aws-staging')", calls[-1]['data'])


class AwsGuardsStillFailClosedTests(unittest.TestCase):
    """One negative test per guard the AWS profile touches."""

    def plan(self, swarm, services=('audit',)):
        with aws(swarm):
            return cluster.update_plan(EVIDENCE, NEW_IMAGE, TARGET_REVISION, list(services))

    def mount_on(self, swarm, service, target, name):
        refs = swarm.services['kolovibe-' + service]['Spec']['TaskTemplate']['ContainerSpec']['Secrets']
        refs.append(mount(target, name))

    def test_secret_ownership_allows_only_the_listed_aws_names_for_their_own_service(self):
        swarm = AwsSwarm()
        self.plan(swarm, ['identity', 'gateway'])  # the observed mounts pass
        cases = (
            ('identity takes the gateway peers secret', 'identity', 'extra', PEERS),
            ('identity takes another service\'s secret', 'identity', 'extra', 'creators_callers'),
            ('content takes the UAT approval', 'content', 'account_approvals', APPROVAL),
            ('creators takes the SMTP user', 'creators', 'smtp_user', SMTP_USER),
            ('gateway takes the SMTP password', 'gateway', 'smtp_password', SMTP_PASSWORD),
            ('gateway takes an identity secret', 'gateway', 'audit_key', 'identity_audit_signing'),
            ('a rotated version of a listed name', 'identity', 'extra', APPROVAL.replace('_v1', '_v2')),
            ('a listed name as a cluster CA target', 'identity', 'internal_ca', SMTP_USER),
            ('the Oracle shared secret on the gateway', 'gateway', 'trusted_peers', 'trusted_peers'))
        for label, service, target, name in cases:
            with self.subTest(label), self.assertRaisesRegex(RuntimeError, 'does not belong to it: kolovibe-' + service):
                swarm = AwsSwarm()
                if label.startswith('a listed name as a cluster CA'):
                    refs = swarm.services['kolovibe-identity']['Spec']['TaskTemplate']['ContainerSpec']['Secrets']
                    refs[:] = [r for r in refs if r['File']['Name'] != 'internal_ca']
                self.mount_on(swarm, service, target, name)
                self.plan(swarm, [service])

    def test_the_aws_names_mean_nothing_to_the_oracle_profile(self):
        swarm = AwsSwarm()
        for service, name in (('identity', SMTP_USER), ('gateway', PEERS)):
            spec = swarm.services['kolovibe-' + service]['Spec']
            with self.subTest(service), patch.object(cluster, 'PROFILE', cluster.ORACLE_STAGING), \
                    self.assertRaisesRegex(RuntimeError, 'does not belong'):
                cluster.require_secrets_belong(service, spec)
            self.assertIn(name, cluster.secret_refs(spec).values())

    def test_existing_service_secret_set_must_match_exactly_in_a_create_plan(self):
        swarm = AwsSwarm()
        swarm.services['kolovibe-identity']['Spec']['TaskTemplate']['ContainerSpec']['Secrets'].pop()
        with aws(swarm), self.assertRaisesRegex(RuntimeError, 'secrets differ; inspect without overwriting: kolovibe-identity'):
            cluster.plan(EVIDENCE, NEW_IMAGE, TARGET_REVISION)

    def test_gateway_must_stay_pinned_with_the_exact_observed_constraint(self):
        for label, constraint in (('oracle pin', 'node.hostname == vm-swarm-worker'),
                                  ('spaced aws pin', 'node.hostname == ' + WORKER),
                                  ('other node', 'node.hostname==ip-172-31-99-9'),
                                  ('label only', 'node.labels.kolovibe.workloads == true')):
            with self.subTest(label), self.assertRaisesRegex(RuntimeError, 'pinned to VM2'):
                self.plan(AwsSwarm(gateway=aws_gateway(constraint=constraint)))

    def test_gateway_database_must_be_a_private_aws_address(self):
        for host in ('vm-swarm-worker', '10.0.2.103', '172.32.0.9', '8.8.8.8', 'db.example.test', ''):
            with self.subTest(host), self.assertRaisesRegex(RuntimeError, 'differs from the working pinned baseline'):
                self.plan(AwsSwarm(gateway=aws_gateway(db_host=host)))

    def test_gateway_networks_must_be_the_reviewed_set_and_stay_internal(self):
        for label, networks in (('no data network', ('services-net',)), ('no services network', ('data-net',))):
            with self.subTest(label), self.assertRaisesRegex(RuntimeError, 'networks differ'):
                self.plan(AwsSwarm(gateway=aws_gateway(networks=networks)))
        swarm = AwsSwarm()
        swarm.static['/v1.52/networks/data-net']['Internal'] = False
        with self.assertRaisesRegex(RuntimeError, 'remain internal'):
            self.plan(swarm)
        swarm = AwsSwarm()
        swarm.static['/v1.52/networks/data-net']['Options'] = {}
        with self.assertRaisesRegex(RuntimeError, 'overlay encryption'):
            self.plan(swarm)
        swarm = AwsSwarm(gateway=aws_gateway(networks=('services-net', 'data-net', 'unreviewed-net')))
        swarm.static['/v1.52/networks/unreviewed-net'] = {'Name': 'other', 'Driver': 'overlay', 'Internal': True,
                                                          'Options': {'encrypted': ''}}
        with self.assertRaisesRegex(RuntimeError, 'networks differ'):
            self.plan(swarm)

    def test_oracle_gateway_is_not_accepted_as_the_aws_gateway(self):
        swarm = AwsSwarm()
        oracle = gateway_fixture()
        oracle['Version'] = {'Index': 7}
        oracle['Spec']['Name'] = 'kolovibe-gateway'
        swarm.services['kolovibe-gateway'] = oracle
        with self.assertRaisesRegex(RuntimeError, 'differs from the working pinned baseline'):
            self.plan(swarm)

    def test_worker_node_must_be_the_aws_worker_ready_and_active(self):
        ready = {'Description': {'Hostname': WORKER}, 'Status': {'State': 'ready'},
                 'Spec': {'Availability': 'active', 'Labels': {}}}
        for label, node in (('oracle name', dict(ready, Description={'Hostname': 'vm-swarm-worker'})),
                            ('drained', dict(ready, Spec={'Availability': 'drain', 'Labels': {}})),
                            ('down', dict(ready, Status={'State': 'down'}))):
            with self.subTest(label), aws(AwsSwarm(node=node)), self.assertRaisesRegex(RuntimeError, 'Ready/Active'):
                cluster.plan(EVIDENCE, NEW_IMAGE, TARGET_REVISION)

    def test_capacity_guard_still_applies(self):
        with aws(AwsSwarm()), self.assertRaisesRegex(RuntimeError, 'VM2 capacity'):
            cluster.plan({'available_memory_bytes': 1, 'time': 1}, NEW_IMAGE, TARGET_REVISION)
        swarm = AwsSwarm()
        del swarm.services['kolovibe-points']
        with aws(swarm), self.assertRaisesRegex(RuntimeError, 'VM2 capacity'):
            cluster.plan({'available_memory_bytes': 1, 'time': 1}, NEW_IMAGE, TARGET_REVISION)

    def test_service_shape_and_credential_guards_still_apply(self):
        for mutate, message in (
                (lambda s: s['TaskTemplate']['ContainerSpec'].update(Image='ghcr.io/x/y:latest'), 'immutable GHCR digest'),
                (lambda s: s.update(Mode={'Replicated': {'Replicas': 2}}), 'single replica'),
                (lambda s: s.update(EndpointSpec={'Ports': [{'PublishedPort': 80}]}), 'publishes ports'),
                (lambda s: s['TaskTemplate']['ContainerSpec']['Env'].append('API_TOKEN=do-not-print'), 'Inline credential')):
            swarm = AwsSwarm()
            mutate(swarm.services['kolovibe-audit']['Spec'])
            with self.subTest(message), self.assertRaisesRegex(RuntimeError, message):
                self.plan(swarm)

    def test_rabbitmq_must_be_pinned_to_the_worker_without_labels(self):
        digest = 'dhi.io/rabbitmq@sha256:' + 'a' * 64
        def broker(constraints):
            return {'Spec': {'Name': 'kolovibe-rabbitmq', 'Mode': {'Replicated': {'Replicas': 1}},
                             'TaskTemplate': {'Placement': {'Constraints': constraints}, 'Networks': [],
                                              'ContainerSpec': {'Image': digest, 'Env': [], 'Secrets': []}}}}
        with patch.object(cluster, 'PROFILE', AWS):
            _, why = cluster.broker_candidate([broker(['node.labels.kolovibe.workloads == true'])], '1.52')
            self.assertEqual(why, 'RabbitMQ is not pinned to the worker')
            _, why = cluster.broker_candidate([broker(['node.hostname == vm-swarm-worker'])], '1.52')
            self.assertEqual(why, 'RabbitMQ is not pinned to the worker')
            _, why = cluster.broker_candidate([broker([PIN])], '1.52')
            self.assertEqual(why, 'RabbitMQ secret set differs from candidate')  # later checks still run
        with patch.object(cluster, 'PROFILE', cluster.ORACLE_STAGING):
            _, why = cluster.broker_candidate([broker([PIN])], '1.52')
            self.assertEqual(why, 'RabbitMQ lacks the worker workload constraint')


if __name__ == '__main__':
    unittest.main()
