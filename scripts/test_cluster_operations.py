"""Offline regression tests for live deployment boundaries; no Docker/VM required."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

MODULE = Path(__file__).parent / 'ops/kolovibe_cluster.py'
spec = importlib.util.spec_from_file_location('cluster', MODULE)
cluster = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cluster)

TARGET = cluster.REPOSITORY + '@sha256:' + 'a' * 64
TARGET_REVISION = 'c' * 40


def gateway_fixture():
    return {'ID': 'gateway-id', 'Spec': {
        'Name': 'kvtest-gateway', 'Mode': {'Replicated': {'Replicas': 1}},
        'Labels': {}, 'EndpointSpec': {'Mode': 'vip'},
        'TaskTemplate': {
            'ContainerSpec': {
                'Image': cluster.IMAGE, 'User': '10001:10001', 'ReadOnly': True,
                'Hosts': ['10.0.2.103 vm-swarm-worker'],
                'Env': ['KOLOVIBE_ENV=staging', 'KOLOVIBE_SERVICE_NAME=gateway',
                        'KOLOVIBE_ALLOWED_HOSTS=gateway', 'KOLOVIBE_DB_HOST=vm-swarm-worker',
                        # Public database/role identifiers in an offline fixture.
                        'KOLOVIBE_DB_NAME=kolovibe_staging', 'KOLOVIBE_DB_USER=kv_gateway_run',  # pragma: allowlist secret
                        'KOLOVIBE_DB_PORT=5432', 'KOLOVIBE_STAGING_ACCOUNTS=0',
                        'KOLOVIBE_STAGING_PRIVILEGED=0',
                        'KOLOVIBE_TRUSTED_PEERS_FILE=/run/secrets/trusted_peers',
                        # Container mount path, without any key material.
                        'KOLOVIBE_OUTBOUND_KEY_FILE=/run/secrets/outbound_key'],  # pragma: allowlist secret
                'Secrets': [], 'Healthcheck': {'Test': ['NONE']}},
            'Networks': [{'Target': 'services-net', 'Aliases': ['gateway']},
                         {'Target': 'data-net'}, {'Target': 'host-net'}],
            'Placement': {'Constraints': ['node.labels.kolovibe.workloads == true',
                                           'node.hostname == vm-swarm-worker']}}}}


def all_secrets():
    names = {'internal_ca', 'db_ca', 'gateway_outbound', 'trusted_peers',
             'kolovibe_rmq_ca', 'kolovibe_rmq_cert', 'kolovibe_rmq_key', 'kolovibe_rmq_definitions'}
    for service in cluster.SERVICES:
        names.update(service + suffix for suffix in cluster.COMMON.values())
    for mapping in cluster.EXTRA.values():
        names.update(mapping.values())
    return {name: 'id-' + name for name in names}


class ClusterOperationsTests(unittest.TestCase):
    def manager_responses(self):
        gateway = gateway_fixture()
        secrets = [{'ID': sid, 'Spec': {'Name': name}} for name, sid in all_secrets().items()]
        networks = {}
        for network_id, name in [('services-net', 'kolovibe_services'), ('data-net', 'kolovibe_data'),
                                 ('host-net', 'kolovibe_db_host_access')]:
            networks['/v1.52/networks/' + network_id] = {'Name': name, 'Driver': 'overlay',
                'Internal': name != 'kolovibe_db_host_access', 'Options': {'encrypted': ''}}
        responses = {'/version': {'ApiVersion': '1.52'}, '/v1.52/info': {
            'Swarm': {'ControlAvailable': True}, 'Plugins': {'Authorization': ['openpolicyagent/opa-docker-authz-v2:0.9']}},
            '/v1.52/services/kvtest-gateway': gateway, '/v1.52/services': [gateway],
            '/v1.52/secrets': secrets, '/v1.52/nodes': [{'Description': {'Hostname': 'vm-swarm-worker'},
                'Status': {'State': 'ready'}, 'Spec': {'Availability': 'active', 'Labels': {'kolovibe.workloads': 'true'}}}],
            **networks}
        return responses

    def test_plan_checks_capacity_before_mutating(self):
        responses = self.manager_responses()
        def read_only(method, path, *args):
            self.assertEqual(method, 'GET')
            return responses[path]
        with patch.object(cluster, 'root'), patch.object(cluster, 'policy_baseline'), \
                patch.object(cluster, 'docker', side_effect=read_only), \
                patch.object(cluster, 'run', return_value='true ["-policy-file","/opa/policies/authz.rego","-quiet"]'):
            with self.assertRaisesRegex(RuntimeError, 'VM2 capacity'):
                cluster.plan({'available_memory_bytes': 100*cluster.MIB}, TARGET, TARGET_REVISION)
            api, gateway, new, broker, pending = cluster.plan({'available_memory_bytes': 3000*cluster.MIB}, TARGET, TARGET_REVISION)
        self.assertEqual(api, '1.52')
        self.assertEqual(len(new), 7)
        self.assertNotIn('kvtest-gateway', [item['Name'] for item in new])
        self.assertIsNone(broker)
        self.assertIn('no broker image was guessed', pending)

    def test_existing_different_service_is_not_overwritten(self):
        responses = self.manager_responses()
        responses['/v1.52/services'].append({'Spec': {'Name': 'kvtest-content', 'TaskTemplate': {}}})
        with patch.object(cluster, 'root'), patch.object(cluster, 'policy_baseline'), \
                patch.object(cluster, 'docker', side_effect=lambda method, path: responses[path]), \
                patch.object(cluster, 'run', return_value='true ["-policy-file","/opa/policies/authz.rego","-quiet"]'):
            with self.assertRaisesRegex(RuntimeError, 'Existing service differs'):
                cluster.plan({'available_memory_bytes': 3000*cluster.MIB}, TARGET, TARGET_REVISION)

    def test_each_new_service_has_own_credentials_and_keeps_database_route(self):
        gateway = gateway_fixture()
        original = copy.deepcopy(gateway)
        for service in cluster.SERVICES[1:]:
            selected = cluster.api_spec(gateway, service, all_secrets(), TARGET, TARGET_REVISION)
            container = selected['TaskTemplate']['ContainerSpec']
            env = cluster.env_dict(container)
            self.assertEqual(env['KOLOVIBE_DB_USER'], 'kv_' + service + '_run')
            self.assertEqual(env['KOLOVIBE_DB_HOST'], 'vm-swarm-worker')
            self.assertEqual(container['Hosts'], original['Spec']['TaskTemplate']['ContainerSpec']['Hosts'])
            self.assertEqual(container['Image'], TARGET)
            self.assertEqual(env['KOLOVIBE_STAGING_ACCOUNTS'], '0')
            self.assertEqual(env['KOLOVIBE_STAGING_PRIVILEGED'], '0')
            refs = {item['File']['Name']: item for item in container['Secrets']}
            self.assertEqual(refs['db_password']['SecretName'], service + '_db')
            self.assertTrue(all(item['File']['Mode'] == 0o400 for item in refs.values()))
            self.assertNotIn('Ports', selected['EndpointSpec'])
            self.assertEqual([n['Aliases'] for n in selected['TaskTemplate']['Networks']], [[service]]*3)
            self.assertNotEqual(container['Healthcheck']['Test'], ['NONE'])
        self.assertEqual(gateway, original)

    def plan_with(self, responses):
        with patch.object(cluster, 'root'), patch.object(cluster, 'policy_baseline'), \
                patch.object(cluster, 'docker', side_effect=lambda method, path: responses[path]), \
                patch.object(cluster, 'run', return_value='true ["-policy-file","/opa/policies/authz.rego","-quiet"]'):
            return cluster.plan({'available_memory_bytes': 3000*cluster.MIB}, TARGET, TARGET_REVISION)

    def test_secret_count_is_not_a_contract_but_missing_gateway_secrets_are(self):
        responses = self.manager_responses()
        responses['/v1.52/secrets'].append({'ID': 'id-new', 'Spec': {'Name': 'content_callers_2'}})
        self.assertEqual(len(self.plan_with(responses)[2]), 7)  # a new versioned secret is fine
        responses = self.manager_responses()
        responses['/v1.52/services/kvtest-gateway']['Spec']['TaskTemplate']['ContainerSpec']['Secrets'] = [
            # Offline fixture: a secret name and id placeholder, no key material.
            {'SecretName': 'gateway_outbound_2', 'SecretID': 'x', 'File': {'Name': 'outbound_key'}}]  # pragma: allowlist secret
        with self.assertRaisesRegex(RuntimeError, 'gateway_outbound_2'):
            self.plan_with(responses)

    def deployed(self, service, names):
        gateway = gateway_fixture()
        known = {**all_secrets(), **{name: 'id-' + name for name in names.values()}}
        live = cluster.api_spec(gateway, service, known, TARGET, TARGET_REVISION, names=names)
        return {'Spec': live}

    def test_rotated_secret_names_on_an_existing_service_are_not_drift(self):
        names = cluster.convention_secrets('content')
        names['caller_keys'] = 'content_callers_2'
        responses = self.manager_responses()
        responses['/v1.52/secrets'].append({'ID': 'id-content_callers_2', 'Spec': {'Name': 'content_callers_2'}})
        responses['/v1.52/services'].append(self.deployed('content', names))
        self.assertEqual(len(self.plan_with(responses)[2]), 6)  # content is adopted, not recreated

    def test_existing_service_with_another_services_secret_is_refused(self):
        names = cluster.convention_secrets('content')
        names['caller_keys'] = 'creators_callers'
        responses = self.manager_responses()
        responses['/v1.52/services'].append(self.deployed('content', names))
        with self.assertRaisesRegex(RuntimeError, 'does not belong'):
            self.plan_with(responses)
        names = cluster.convention_secrets('content')
        names['internal_ca'] = 'db_ca'
        responses['/v1.52/services'][-1] = self.deployed('content', names)
        with self.assertRaisesRegex(RuntimeError, 'does not belong'):
            self.plan_with(responses)
        spec = self.deployed('content', cluster.convention_secrets('content'))
        spec['Spec']['TaskTemplate']['ContainerSpec']['Secrets'].pop()
        responses['/v1.52/services'][-1] = spec
        with self.assertRaisesRegex(RuntimeError, 'secrets differ'):
            self.plan_with(responses)

    def test_missing_secret_stops_before_any_deployment(self):
        with self.assertRaisesRegex(RuntimeError, 'Missing existing Swarm secret'):
            cluster.api_spec(gateway_fixture(), 'identity', {}, TARGET, TARGET_REVISION)

    def test_inline_credentials_are_never_serialized(self):
        for key in ('DATABASE_PASSWORD', 'AUTH_TOKEN', 'DJANGO_SECRET_KEY'):
            gateway = gateway_fixture()['Spec']
            gateway['TaskTemplate']['ContainerSpec']['Env'].append(key + '=do-not-print')
            with self.assertRaisesRegex(RuntimeError, 'Inline credential'):
                cluster.safe_spec(gateway)
        gateway = gateway_fixture()['Spec']
        gateway['TaskTemplate']['ContainerSpec']['PullOptions'] = {'RegistryAuth': 'do-not-print'}
        with self.assertRaisesRegex(RuntimeError, 'Unexpected inspect credential'):
            cluster.safe_spec(gateway)

    def test_inspection_defaults_do_not_hide_substantive_spec_changes(self):
        original = gateway_fixture()['Spec']
        defaulted = copy.deepcopy(original)
        defaulted['TaskTemplate']['ForceUpdate'] = 0
        defaulted['TaskTemplate']['ContainerSpec']['Healthcheck']['Interval'] = 0
        self.assertEqual(cluster.canonical(defaulted), cluster.canonical(original))
        defaulted['TaskTemplate']['ContainerSpec']['Image'] = 'other-image'
        self.assertNotEqual(cluster.canonical(defaulted), cluster.canonical(original))

    def test_stale_future_and_wrong_host_worker_evidence_rejected(self):
        valid = {'kind': 'KVB-CLUSTER-WORKER-V1', 'host': 'vm-swarm-worker',
                 'time': time.time(), 'guard': True, 'gateway_live': True}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'evidence.json'
            path.write_text(json.dumps(valid))
            cluster.load_evidence(path)
            for overrides in ({'time': time.time()-301}, {'time': time.time()+100},
                              {'host': 'other'}, {'guard': False}, {'gateway_live': False}):
                path.write_text(json.dumps(dict(valid, **overrides)))
                with self.assertRaisesRegex(RuntimeError, 'Fresh VM2 preflight'):
                    cluster.load_evidence(path)

    def test_response_contracts_fail_closed_and_do_not_echo_error_strings(self):
        rows = []
        cluster.record(rows, 'health', lambda: (200, {'not': 'health'}), (200,),
                       lambda body: body == {'status': 'ok'})
        self.assertTrue(cluster.has_failures({'checks': rows}))
        def bad_call():
            raise ValueError('sensitive-error-do-not-print')
        cluster.record(rows, 'transport', bad_call, (200,))
        self.assertNotIn('sensitive-error', json.dumps(rows))

    def test_public_503_is_never_a_successful_negative_test(self):
        with patch.object(cluster, 'https_check', return_value=(503, None)):
            report = cluster.verify_edge()
        self.assertEqual(len(report['checks']), 19)
        self.assertTrue(all(row['status'] == 'FAIL' for row in report['checks']))

    def test_redirects_are_not_followed(self):
        self.assertIsNone(cluster.NoRedirect().redirect_request(None, None, 302, '', {}, 'https://other.test'))

    def test_policy_restored_after_failed_mutation(self):
        class Reply:
            status = 403
            def read(self):
                return b''
        class Connection:
            def __init__(self, *args, **kwargs):
                pass
            def request(self, *args):
                pass
            def getresponse(self):
                return Reply()
            def close(self):
                pass
        with tempfile.TemporaryDirectory() as directory:
            policy = Path(directory) / 'authz.rego'
            original = cluster.BASE.encode()
            policy.write_bytes(original)
            with patch.object(cluster, 'POLICY', policy), patch.object(cluster, 'run', return_value=''), \
                    patch.object(cluster, 'DockerConnection', Connection), patch.object(cluster, 'policy_baseline', return_value=original):
                with self.assertRaisesRegex(RuntimeError, 'simulated'):
                    with cluster.allow_once('1.52', '/v1.52/services/create', {'Name': 'kvtest-content'}):
                        active = policy.read_text()
                        self.assertIn('input.Body == {"Name":"kvtest-content"}', active)
                        self.assertIn('input.PathPlain == "/v1.52/services/create"', active)
                        raise RuntimeError('simulated')
            self.assertEqual(policy.read_bytes(), original)
            self.assertEqual(list(Path(directory).iterdir()), [policy])


if __name__ == '__main__':
    unittest.main()
