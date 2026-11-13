"""Offline regression tests for explicit release selection, safe image updates and rollback.

No Docker, registry or VM is contacted; Swarm is a small in-memory fake.
"""
import contextlib
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent))
from test_cluster_operations import (  # noqa: E402
    TARGET, TARGET_REVISION, ClusterOperationsTests, all_secrets, cluster, gateway_fixture)

NEW_IMAGE = TARGET
EVIDENCE = {'available_memory_bytes': 3000 * cluster.MIB, 'time': 1}


class FakeSwarm:
    """Read endpoints come from the shared fixture; update POSTs mutate the fake."""

    def __init__(self, fail_on=None, drift=None):
        base = ClusterOperationsTests().manager_responses()
        gateway = gateway_fixture()
        gateway['Version'] = {'Index': 7}
        self.services = {'kvtest-gateway': gateway}
        for service in cluster.SERVICES[1:]:
            spec = cluster.api_spec(gateway, service, all_secrets(), cluster.BASELINE_IMAGE, cluster.BASELINE_REVISION)
            self.services[spec['Name']] = {'ID': 'id-' + service, 'Version': {'Index': 3}, 'Spec': spec}
        self.static = {k: v for k, v in base.items() if not k.startswith('/v1.52/services')}
        self.posts = []
        self.fail_on = fail_on
        self.drift = drift
        self.gets_of_gateway = 0

    def by_id(self, key):
        for name, svc in self.services.items():
            if key in (name, svc['ID']):
                return name, svc
        raise KeyError(key)

    def __call__(self, method, path, body=None, auth=None):
        if method == 'POST':
            service_id = path.split('/services/')[1].split('/update')[0]
            name, svc = self.by_id(service_id)
            self.posts.append((name, path, copy.deepcopy(body), auth))
            previous = svc['Spec']
            if '&rollback=previous' in path:
                svc['Spec'], svc['PreviousSpec'] = svc['PreviousSpec'], previous
                svc['UpdateStatus'] = {'State': 'rollback_completed', 'StartedAt': 'r%d' % len(self.posts)}
            else:
                svc['PreviousSpec'] = previous
                svc['Spec'] = body
                state = 'rollback_completed' if name == self.fail_on else 'completed'
                svc['UpdateStatus'] = {'State': state, 'StartedAt': 'u%d' % len(self.posts)}
            svc['Version'] = {'Index': svc['Version']['Index'] + 1}
            return {}
        if path == '/v1.52/services':
            return [dict(s, ID=s.get('ID', 'gateway-id')) for s in self.services.values()]
        if path.startswith('/v1.52/services/'):
            name, svc = self.by_id(path.rsplit('/', 1)[1])
            if name == self.drift:
                svc['Spec'] = copy.deepcopy(svc['Spec'])
                svc['Spec']['Labels']['drift'] = '1'
                self.drift = None
            return dict(svc, ID=svc.get('ID', 'gateway-id'))
        return self.static[path]


@contextlib.contextmanager
def manager(swarm):
    with patch.object(cluster, 'root'), patch.object(cluster, 'policy_baseline'), \
            patch.object(cluster, 'docker', side_effect=swarm), \
            patch.object(cluster, 'run', return_value='true ["-policy-file","/opa/policies/authz.rego","-quiet"]'), \
            patch.object(cluster, 'allow_once', lambda *args: contextlib.nullcontext()), \
            patch.object(cluster, 'wait_running'), patch.object(cluster, 'load_evidence', return_value=EVIDENCE), \
            patch.object(cluster, 'registry_auth', return_value='auth-not-real'), \
            patch.object(cluster.time, 'sleep'):
        yield


def release_dir(directory, **overrides):
    files = {'published-digest.txt': NEW_IMAGE, 'revision.txt': TARGET_REVISION,
             'published-tag.txt': cluster.REPOSITORY + ':' + TARGET_REVISION + '-' + 'b' * 64,
             'services.json': json.dumps(list(cluster.SERVICES)),
             'image-sbom.json': json.dumps({'components': [{'name': 'django'}, {'name': 'gunicorn'}]})}
    files.update(overrides)
    for name, content in files.items():
        (Path(directory) / name).write_text(content)
    return directory


class ReleaseSelectionTests(unittest.TestCase):
    def test_no_image_is_ever_defaulted(self):
        with self.assertRaisesRegex(RuntimeError, 'Supply an immutable'):
            cluster.resolve_release()
        with self.assertRaisesRegex(RuntimeError, '40-hex'):
            cluster.resolve_release(NEW_IMAGE)

    def test_only_immutable_project_digests_are_accepted(self):
        for bad in (cluster.REPOSITORY + ':latest', cluster.REPOSITORY + '@sha256:' + 'a' * 63,
                    'ghcr.io/other/services@sha256:' + 'a' * 64, 'dhi.io/x@sha256:' + 'a' * 64):
            with self.assertRaisesRegex(RuntimeError, 'Supply an immutable'):
                cluster.resolve_release(bad, TARGET_REVISION)
        with self.assertRaisesRegex(RuntimeError, '40-hex'):
            cluster.resolve_release(NEW_IMAGE, 'main')
        self.assertEqual(cluster.resolve_release(NEW_IMAGE, TARGET_REVISION), (NEW_IMAGE, TARGET_REVISION))

    def test_stale_baseline_is_not_a_target(self):
        with self.assertRaisesRegex(RuntimeError, 'baseline image is not an approved'):
            cluster.resolve_release(cluster.BASELINE_IMAGE, cluster.BASELINE_REVISION)

    def test_ci_publication_evidence_is_cross_checked(self):
        with tempfile.TemporaryDirectory() as directory:
            release_dir(directory)
            self.assertEqual(cluster.resolve_release(release_dir=directory), (NEW_IMAGE, TARGET_REVISION))
            with self.assertRaisesRegex(RuntimeError, 'disagree'):
                cluster.resolve_release(cluster.REPOSITORY + '@sha256:' + 'd' * 64, release_dir=directory)

    def test_unscanned_or_inconsistent_evidence_is_refused(self):
        cases = {
            'Published tag': {'published-tag.txt': cluster.REPOSITORY + ':' + 'e' * 40 + '-' + 'b' * 64},
            'different service set': {'services.json': json.dumps(['gateway'])},
            'scan gate': {'image-sbom.json': json.dumps({'components': [{'name': 'sqlite-libs'}]})},
            'valid JSON': {'image-sbom.json': 'not json'},
        }
        for message, overrides in cases.items():
            with tempfile.TemporaryDirectory() as directory:
                release_dir(directory, **overrides)
                with self.assertRaisesRegex(RuntimeError, message):
                    cluster.resolve_release(release_dir=directory)
        with tempfile.TemporaryDirectory() as directory, self.assertRaisesRegex(RuntimeError, 'missing or unsafe'):
            cluster.resolve_release(release_dir=directory)


class UpdatePlanTests(unittest.TestCase):
    def plan(self, swarm, services, **kw):
        with manager(swarm):
            return cluster.update_plan(EVIDENCE, NEW_IMAGE, TARGET_REVISION, services, **kw)

    def test_create_plan_adopts_existing_services_at_their_own_pin(self):
        swarm = FakeSwarm()
        del swarm.services['kvtest-points']
        with manager(swarm):
            _api, _gateway, new, _broker, _pending = cluster.plan(EVIDENCE, NEW_IMAGE, TARGET_REVISION)
        self.assertEqual([s['Name'] for s in new], ['kvtest-points'])
        self.assertEqual(new[0]['TaskTemplate']['ContainerSpec']['Image'], NEW_IMAGE)

    def test_services_must_be_named_and_known(self):
        for services in ([], ['nope'], ['audit', 'audit']):
            with self.assertRaisesRegex(RuntimeError, 'explicitly|unique subset'):
                cluster.ordered(services)

    def test_gateway_is_last_to_update_and_first_to_roll_back(self):
        names = ['gateway', 'moderation', 'audit', 'identity']
        self.assertEqual(cluster.ordered(names), ['audit', 'identity', 'moderation', 'gateway'])
        self.assertEqual(cluster.ordered(names, reverse=True), ['gateway', 'moderation', 'identity', 'audit'])

    def test_only_the_release_pin_and_rolling_guards_change(self):
        swarm = FakeSwarm()
        report = self.plan(swarm, ['identity'], restore_ref='restore-2026-11-13')
        entry = report['entries'][0]
        live = swarm.services['kvtest-identity']['Spec']
        new = entry['update_spec']
        self.assertEqual(new['TaskTemplate']['ContainerSpec']['Image'], NEW_IMAGE)
        self.assertEqual(new['Labels']['kolovibe.source-revision'], TARGET_REVISION)
        self.assertEqual(new['UpdateConfig']['Order'], 'stop-first')
        self.assertEqual(new['UpdateConfig']['FailureAction'], 'rollback')
        self.assertEqual(cluster.release_neutral(new), cluster.release_neutral(live))
        self.assertEqual(live['TaskTemplate']['ContainerSpec']['Image'], cluster.BASELINE_IMAGE)  # plan is read-only
        self.assertEqual(swarm.posts, [])
        self.assertEqual(entry['current_image'], cluster.BASELINE_IMAGE)
        self.assertIn('Forward-only', entry['rollback']['schema'])
        self.assertTrue(entry['health_gated'])

    def test_public_plan_never_contains_full_specs(self):
        report = self.plan(FakeSwarm(), ['audit'])
        self.assertNotIn('update_spec', json.dumps(cluster.public_plan(report)))
        self.assertNotIn('Secrets', json.dumps(cluster.public_plan(report)))

    def test_already_current_service_is_unchanged_and_undeployed_one_is_refused(self):
        swarm = FakeSwarm()
        spec = swarm.services['kvtest-audit']['Spec']
        spec['TaskTemplate']['ContainerSpec']['Image'] = NEW_IMAGE
        self.assertEqual(self.plan(swarm, ['audit'])['entries'][0]['action'], 'unchanged')
        del swarm.services['kvtest-points']
        with self.assertRaisesRegex(RuntimeError, 'never creates services'):
            self.plan(swarm, ['points'])

    def test_unpinned_multi_replica_or_published_services_are_refused(self):
        for mutate, message in (
                (lambda s: s['TaskTemplate']['ContainerSpec'].update(Image='ghcr.io/x/y:latest'), 'immutable GHCR digest'),
                (lambda s: s.update(Mode={'Replicated': {'Replicas': 2}}), 'single replica'),
                (lambda s: s.update(EndpointSpec={'Ports': [{'PublishedPort': 80}]}), 'publishes ports')):
            swarm = FakeSwarm()
            mutate(swarm.services['kvtest-audit']['Spec'])
            with self.assertRaisesRegex(RuntimeError, message):
                self.plan(swarm, ['audit'])

    def test_inline_credentials_stop_the_plan(self):
        swarm = FakeSwarm()
        swarm.services['kvtest-audit']['Spec']['TaskTemplate']['ContainerSpec']['Env'].append('API_TOKEN=do-not-print')
        with self.assertRaisesRegex(RuntimeError, 'Inline credential'):
            self.plan(swarm, ['audit'])


class UpdateApplyTests(unittest.TestCase):
    def run_update(self, swarm, services, *, confirm=NEW_IMAGE, restore='restore-2026-11-13', ungated=False):
        with tempfile.TemporaryDirectory() as directory, manager(swarm):
            record = str(Path(directory) / 'rollback.json')
            cluster.update('evidence.json', 'operator', NEW_IMAGE, TARGET_REVISION, services, restore, confirm,
                           record, ungated)
            return Path(record).read_text() if Path(record).exists() else None

    def test_without_the_exact_digest_it_is_a_dry_run(self):
        swarm = FakeSwarm()
        self.assertIsNone(self.run_update(swarm, ['audit'], confirm=None))
        self.assertEqual(swarm.posts, [])
        with self.assertRaisesRegex(RuntimeError, 'repeat the approved release digest'):
            self.run_update(swarm, ['audit'], confirm=cluster.REPOSITORY + '@sha256:' + 'f' * 64)
        self.assertEqual(swarm.posts, [])

    def test_restore_point_and_health_gate_are_required_before_any_change(self):
        swarm = FakeSwarm()
        with self.assertRaisesRegex(RuntimeError, 'restore-point-ref'):
            self.run_update(swarm, ['audit'], restore=None)
        with self.assertRaisesRegex(RuntimeError, 'No readiness healthcheck'):
            self.run_update(swarm, ['gateway'])
        self.assertEqual(swarm.posts, [])

    def test_ordered_rollout_records_rollback_state_first_and_leaves_gateway_alone(self):
        swarm = FakeSwarm()
        record = self.run_update(swarm, ['moderation', 'audit'])
        self.assertEqual([p[0] for p in swarm.posts], ['kvtest-audit', 'kvtest-moderation'])
        self.assertTrue(all('rollback' not in p[1] and p[3] == 'auth-not-real' for p in swarm.posts))
        for name in ('kvtest-audit', 'kvtest-moderation'):
            self.assertEqual(cluster.live_image(swarm.services[name]['Spec']), NEW_IMAGE)
        self.assertEqual(cluster.live_image(swarm.services['kvtest-gateway']['Spec']), cluster.BASELINE_IMAGE)
        document = json.loads(record)
        self.assertEqual({e['service'] for e in document['entries']}, {'audit', 'moderation'})
        self.assertEqual(document['entries'][0]['current_image'], cluster.BASELINE_IMAGE)
        self.assertEqual(document['restore_point_ref'], 'restore-2026-11-13')
        self.assertNotIn('Secrets', record)
        self.assertNotIn('auth-not-real', record)

    def test_ungated_gateway_needs_explicit_acceptance(self):
        swarm = FakeSwarm()
        self.run_update(swarm, ['gateway'], ungated=True)
        self.assertEqual([p[0] for p in swarm.posts], ['kvtest-gateway'])

    def test_a_service_rolled_back_by_swarm_stops_the_rollout(self):
        swarm = FakeSwarm(fail_on='kvtest-identity')
        with self.assertRaisesRegex(RuntimeError, 'rollback_completed.*Not yet updated: creators'):
            self.run_update(swarm, ['audit', 'identity', 'creators'])
        self.assertEqual([p[0] for p in swarm.posts], ['kvtest-audit', 'kvtest-identity'])

    def test_drift_since_planning_stops_before_mutation(self):
        swarm = FakeSwarm(drift='kvtest-audit')
        # The drift fires on the second read of the service, i.e. after the plan was made.
        with self.assertRaisesRegex(RuntimeError, 'changed since it was planned'):
            self.run_update(swarm, ['audit'])
        self.assertEqual(swarm.posts, [])

    def test_existing_rollback_record_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'rollback.json'
            path.write_text('keep')
            with self.assertRaises(FileExistsError):
                cluster.write_private(str(path), {})
            self.assertEqual(path.read_text(), 'keep')
            fresh = Path(directory) / 'new.json'
            cluster.write_private(str(fresh), {})
            self.assertEqual(fresh.stat().st_mode & 0o777, 0o600)


class RollbackTests(unittest.TestCase):
    def updated(self):
        swarm = FakeSwarm()
        with manager(swarm), tempfile.TemporaryDirectory() as directory:
            cluster.update('e', 'operator', NEW_IMAGE, TARGET_REVISION, ['audit', 'identity'], 'restore-2026-11-13',
                           NEW_IMAGE, str(Path(directory) / 'r.json'), False)
        swarm.posts.clear()
        return swarm

    def test_dry_run_changes_nothing(self):
        swarm = self.updated()
        with manager(swarm):
            cluster.rollback(['audit', 'identity'], None)
        self.assertEqual(swarm.posts, [])

    def test_confirmation_must_match_the_planned_order(self):
        swarm = self.updated()
        with manager(swarm), self.assertRaisesRegex(RuntimeError, 'exactly the planned services, in order'):
            cluster.rollback(['audit', 'identity'], 'audit,identity')
        self.assertEqual(swarm.posts, [])

    def test_server_side_rollback_restores_previous_pin_without_registry_credentials(self):
        swarm = self.updated()
        with manager(swarm):
            cluster.rollback(['audit', 'identity'], 'identity,audit')
        self.assertEqual([p[0] for p in swarm.posts], ['kvtest-identity', 'kvtest-audit'])
        self.assertTrue(all('&rollback=previous' in p[1] and p[3] is None for p in swarm.posts))
        for name in ('kvtest-identity', 'kvtest-audit'):
            self.assertEqual(cluster.live_image(swarm.services[name]['Spec']), cluster.BASELINE_IMAGE)

    def test_service_without_a_previous_spec_cannot_be_rolled_back(self):
        swarm = FakeSwarm()
        with manager(swarm), self.assertRaisesRegex(RuntimeError, 'no previous spec'):
            cluster.rollback(['audit'], 'audit')
        self.assertEqual(swarm.posts, [])


class VerifyWorkerImageTests(unittest.TestCase):
    def container(self, image):
        return json.dumps([{'Config': {'Image': image}}])

    def test_container_must_run_exactly_the_expected_digest(self):
        with patch.object(cluster, 'container_id', return_value='cid'), \
                patch.object(cluster, 'run', return_value=self.container(cluster.BASELINE_IMAGE)):
            with self.assertRaisesRegex(RuntimeError, 'Container digest differs'):
                cluster.inside('audit', 'tests', NEW_IMAGE)

    def test_preflight_accepts_any_immutable_digest_but_not_a_tag(self):
        with patch.object(cluster, 'container_id', return_value='cid'), \
                patch.object(cluster, 'run', return_value=self.container(cluster.REPOSITORY + ':latest')):
            with self.assertRaisesRegex(RuntimeError, 'Container digest differs'):
                cluster.inside('gateway', 'live', None)


if __name__ == '__main__':
    unittest.main()
