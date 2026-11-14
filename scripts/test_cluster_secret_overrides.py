"""Offline tests for reviewed `--secret-override` in the cluster tool's update-plan/update.

No Docker, AWS, registry or VM is contacted; Swarm is the in-memory fake from the image-update
tests. Fixtures and assertions carry secret *names* only. Every case runs under both profiles,
because no guard may differ between them.
"""
import contextlib
import copy
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent))
from test_cluster_aws_profile import APPROVAL, SMTP_PASSWORD, SMTP_USER, AwsSwarm, aws  # noqa: E402
from test_cluster_image_update import EVIDENCE, FakeSwarm, NEW_IMAGE, manager  # noqa: E402
from test_cluster_operations import TARGET_REVISION, cluster  # noqa: E402

OUTBOUND = 'outbound_key'
NEW_OUTBOUND = 'gateway_outbound_2'
NEW_CALLERS = 'identity_callers_2'
EXTRA_SECRETS = (NEW_OUTBOUND, NEW_CALLERS, 'content_callers_2', 'audit_callers_2')
GATEWAY_MOUNT = {'File': {'Name': OUTBOUND, 'UID': '10001', 'GID': '10001', 'Mode': 256}}


def add_secrets(swarm, *names):
    swarm.static['/v1.52/secrets'] = swarm.static['/v1.52/secrets'] + [
        {'ID': 'id-' + name, 'Spec': {'Name': name}} for name in names]


def mount_outbound(swarm, gateway_name, oracle):
    """The live gateway mounts the single shared outbound secret at `outbound_key`."""
    refs = swarm.services[gateway_name]['Spec']['TaskTemplate']['ContainerSpec']['Secrets']
    refs.append(dict(GATEWAY_MOUNT, SecretName='gateway_outbound', SecretID='id-gateway_outbound'))
    if oracle:
        refs.append({'SecretName': 'trusted_peers', 'SecretID': 'id-trusted_peers',
                     'File': {'Name': 'trusted_peers', 'UID': '10001', 'GID': '10001', 'Mode': 256}})


class OverrideCases:
    """Shared cases; the subclasses supply one profile's fixture."""

    prefix = ''

    def make(self):
        raise NotImplementedError

    def context(self, swarm):
        raise NotImplementedError

    def setUp(self):
        self.swarm = self.make()
        add_secrets(self.swarm, *EXTRA_SECRETS)

    def live(self, service):
        return self.swarm.services[self.prefix + service]['Spec']

    def plan(self, services, overrides, **kw):
        with self.context(self.swarm):
            return cluster.update_plan(EVIDENCE, NEW_IMAGE, TARGET_REVISION, services, secret_overrides=overrides, **kw)

    def apply(self, services, overrides, *, confirm=NEW_IMAGE, restore='restore-2026-11-14'):
        stderr = io.StringIO()
        with tempfile.TemporaryDirectory() as directory, self.context(self.swarm), contextlib.redirect_stderr(stderr):
            record = Path(directory) / 'rollback.json'
            cluster.update('e.json', 'operator', NEW_IMAGE, TARGET_REVISION, services, restore, confirm,
                           str(record), True, overrides)
            return (record.read_text() if record.exists() else None), stderr.getvalue()

    def assert_refused(self, message, services, overrides):
        before = copy.deepcopy(self.swarm.services)
        with self.assertRaisesRegex(RuntimeError, message):
            self.apply(services, overrides)
        self.assertEqual(self.swarm.posts, [])
        self.assertEqual(self.swarm.services, before)

    # --- what a reviewed override does -------------------------------------------------------

    def test_gateway_image_and_outbound_secret_move_in_one_guarded_update(self):
        live = copy.deepcopy(self.live('gateway'))
        plan = self.plan(['gateway'], ['gateway:outbound_key=gateway_outbound_2'])
        entry = plan['entries'][0]
        self.assertEqual(entry['action'], 'update')
        self.assertEqual(entry['secret_changes'],
                         [{'target': OUTBOUND, 'from': 'gateway_outbound', 'to': NEW_OUTBOUND}])
        self.assertEqual(self.swarm.posts, [])  # planning is read-only
        self.assertEqual(self.live('gateway'), live)

        self.apply(['gateway'], ['gateway:outbound_key=gateway_outbound_2'])
        self.assertEqual(len(self.swarm.posts), 1)  # one update carries image and secret together
        new = self.live('gateway')
        self.assertEqual(cluster.live_image(new), NEW_IMAGE)
        refs = cluster.secret_refs(new)
        self.assertEqual(refs[OUTBOUND], NEW_OUTBOUND)
        self.assertEqual({t: n for t, n in refs.items() if t != OUTBOUND},
                         {t: n for t, n in cluster.secret_refs(live).items() if t != OUTBOUND})

    def test_the_diff_is_only_pin_revision_guards_and_the_named_secret_ref(self):
        live = copy.deepcopy(self.live('identity'))
        self.apply(['identity'], ['identity:caller_keys=identity_callers_2'])
        new = copy.deepcopy(self.live('identity'))
        # Undo exactly the allowed changes, by hand, and require the specs to be identical.
        new['TaskTemplate']['ContainerSpec']['Image'] = cluster.live_image(live)
        new['Labels'] = live['Labels']
        for key in cluster.ROLLING_KEYS:
            new.pop(key, None)
            live.pop(key, None)
        before = {r['File']['Name']: r for r in live['TaskTemplate']['ContainerSpec']['Secrets']}
        for ref in new['TaskTemplate']['ContainerSpec']['Secrets']:
            if ref['File']['Name'] == 'caller_keys':
                self.assertEqual(ref['SecretName'], NEW_CALLERS)
                self.assertEqual(ref['SecretID'], 'id-' + NEW_CALLERS)
            ref['SecretName'] = before[ref['File']['Name']]['SecretName']
            ref['SecretID'] = before[ref['File']['Name']]['SecretID']
        self.assertEqual(new, live)

    def test_mount_target_mode_and_uid_are_kept(self):
        before = next(r['File'] for r in self.live('gateway')['TaskTemplate']['ContainerSpec']['Secrets']
                      if r['File']['Name'] == OUTBOUND)
        self.apply(['gateway'], ['gateway:outbound_key=gateway_outbound_2'])
        after = next(r['File'] for r in self.live('gateway')['TaskTemplate']['ContainerSpec']['Secrets']
                     if r['SecretName'] == NEW_OUTBOUND)
        self.assertEqual(after, before)
        self.assertEqual((after['Name'], after['UID'], after['GID'], after['Mode']), (OUTBOUND, '10001', '10001', 256))

    def test_receiver_secret_can_move_with_the_image_and_alone(self):
        self.apply(['identity', 'audit'], ['identity:caller_keys=identity_callers_2'])
        self.assertEqual(cluster.secret_refs(self.live('identity'))['caller_keys'], NEW_CALLERS)
        self.assertEqual(cluster.secret_refs(self.live('audit'))['caller_keys'], 'audit_callers')  # not named
        # The image is already current: only the secret differs, and that is still an update.
        self.swarm.posts.clear()
        add_secrets(self.swarm, 'identity_callers_3')
        plan = self.plan(['identity'], ['identity:caller_keys=identity_callers_3'])
        self.assertEqual(plan['entries'][0]['action'], 'update')
        self.apply(['identity'], ['identity:caller_keys=identity_callers_3'])
        self.assertEqual(len(self.swarm.posts), 1)
        self.assertEqual(cluster.secret_refs(self.live('identity'))['caller_keys'], 'identity_callers_3')

    def test_a_secret_is_never_swapped_unless_named(self):
        self.apply(['gateway', 'identity'], [])
        self.assertEqual(cluster.secret_refs(self.live('gateway'))[OUTBOUND], 'gateway_outbound')
        self.assertEqual(cluster.secret_refs(self.live('identity'))['caller_keys'], 'identity_callers')
        self.assertEqual(self.plan(['identity'], None)['entries'][0]['secret_changes'], [])

    def test_a_rerun_with_the_override_already_in_place_is_unchanged(self):
        self.apply(['identity'], ['identity:caller_keys=identity_callers_2'])
        self.swarm.posts.clear()
        entry = self.plan(['identity'], ['identity:caller_keys=identity_callers_2'])['entries'][0]
        self.assertEqual((entry['action'], entry['secret_changes']), ('unchanged', []))

    # --- dry run, confirmation and what is recorded --------------------------------------------

    def test_dry_run_is_still_the_default_and_the_digest_must_still_be_repeated(self):
        record, shown = self.apply(['gateway'], ['gateway:outbound_key=gateway_outbound_2'], confirm=None)
        self.assertIsNone(record)
        self.assertEqual(self.swarm.posts, [])
        self.assertIn('DRY RUN', shown)
        self.assertIn(NEW_OUTBOUND, shown)  # the reviewer sees the names
        with self.assertRaisesRegex(RuntimeError, 'repeat the approved release digest'):
            self.apply(['gateway'], ['gateway:outbound_key=gateway_outbound_2'],
                       confirm=cluster.REPOSITORY + '@sha256:' + 'f' * 64)
        with self.assertRaisesRegex(RuntimeError, 'restore-point-ref'):
            self.apply(['gateway'], ['gateway:outbound_key=gateway_outbound_2'], restore=None)
        self.assertEqual(self.swarm.posts, [])
        self.assertEqual(cluster.secret_refs(self.live('gateway'))[OUTBOUND], 'gateway_outbound')

    def test_plan_and_rollback_record_show_names_only(self):
        record, shown = self.apply(['gateway'], ['gateway:outbound_key=gateway_outbound_2'])
        document = json.loads(record)
        self.assertEqual(document['entries'][0]['secret_changes'],
                         [{'target': OUTBOUND, 'from': 'gateway_outbound', 'to': NEW_OUTBOUND}])
        for text in (record, shown):
            self.assertIn('gateway_outbound', text)
            for forbidden in ('SecretID', 'id-gateway_outbound', 'Secrets', 'update_spec'):
                self.assertNotIn(forbidden, text)
        self.assertNotIn('auth-not-real', record)

    # --- guards: each one refuses before anything is changed -----------------------------------

    def test_a_secret_that_does_not_exist_in_swarm_is_refused(self):
        self.assert_refused('does not exist in Swarm: gateway_outbound_9', ['gateway'],
                            ['gateway:outbound_key=gateway_outbound_9'])

    def test_foreign_secrets_are_refused_by_the_ownership_check(self):
        cases = (('identity', 'caller_keys', 'content_callers_2'),     # another service's versioned secret
                 ('content', 'caller_keys', 'trusted_peers'),           # a name mounted only by the gateway
                 ('audit', 'caller_keys', APPROVAL),                    # another service's allow-listed name
                 ('gateway', OUTBOUND, 'identity_callers_2'))
        add_secrets(self.swarm, APPROVAL)
        for service, target, name in cases:
            with self.subTest(service=service, name=name):
                self.assert_refused('does not belong to it: ' + self.prefix + service, [service],
                                    [service + ':' + target + '=' + name])

    def test_the_cluster_ca_mounts_cannot_be_replaced(self):
        add_secrets(self.swarm, 'identity_ca_2')
        self.assert_refused('does not belong to it', ['identity'], ['identity:internal_ca=identity_ca_2'])
        self.assert_refused('does not belong to it', ['identity'], ['identity:db_ca=identity_ca_2'])

    def test_a_secret_already_mounted_at_another_target_is_refused(self):
        self.assert_refused('already mounted at another target', ['identity'], ['identity:django_key=identity_db'])

    def test_the_target_must_already_be_mounted_by_that_service(self):
        for service, target in (('identity', OUTBOUND), ('gateway', 'caller_keys'), ('identity', 'no_such_target')):
            with self.subTest(service=service, target=target):
                self.assert_refused('mounts no secret at target ' + target, [service],
                                    [service + ':' + target + '=' + NEW_OUTBOUND])

    def test_malformed_unlisted_or_repeated_overrides_are_refused(self):
        cases = (('must look like', ['gateway=gateway_outbound_2']),
                 ('must look like', ['gateway:outbound_key=']),
                 ('must look like', ['gateway:outbound_key=../gateway_outbound_2']),
                 ('must look like', ['Gateway:outbound_key=gateway_outbound_2']),
                 ('not in --services', ['identity:caller_keys=identity_callers_2']),
                 ('same mount target twice', ['gateway:outbound_key=gateway_outbound_2',
                                              'gateway:outbound_key=gateway_outbound_9']))
        for message, overrides in cases:
            with self.subTest(overrides=overrides):
                self.assert_refused(message, ['gateway'], overrides)

    def test_an_unnamed_extra_change_is_refused_before_it_is_planned(self):
        def file_mode(new):
            for ref in new['TaskTemplate']['ContainerSpec']['Secrets']:
                ref['File']['Mode'] = 420

        def file_uid(new):
            new['TaskTemplate']['ContainerSpec']['Secrets'][0]['File']['UID'] = '0'

        def other_secret(new):
            for ref in new['TaskTemplate']['ContainerSpec']['Secrets']:
                if ref['File']['Name'] == 'db_password':
                    ref['SecretName'] = 'identity_probe'

        def environment(new):
            new['TaskTemplate']['ContainerSpec']['Env'].append('EXTRA=1')

        def mounted_twice(new):
            new['TaskTemplate']['ContainerSpec']['Secrets'].append(
                dict(new['TaskTemplate']['ContainerSpec']['Secrets'][0]))

        for name, change in (('mode', file_mode), ('uid', file_uid), ('other secret', other_secret),
                             ('env', environment), ('extra mount', mounted_twice)):
            with self.subTest(change=name), tamper_once(change):
                with self.assertRaisesRegex(RuntimeError, 'more than the release pin and the named secret references'):
                    self.plan(['identity'], ['identity:caller_keys=identity_callers_2'])
        self.assertEqual(self.swarm.posts, [])

    def test_without_overrides_the_original_release_pin_guard_is_unchanged(self):
        with tamper_once(lambda new: new.update(Name='other')):
            with self.assertRaisesRegex(RuntimeError, 'more than the release pin$'):
                self.plan(['audit'], None)

    def test_drift_after_planning_stops_the_secret_swap_before_mutation(self):
        self.swarm.drift = self.prefix + 'identity'
        with self.assertRaisesRegex(RuntimeError, 'changed since it was planned'):
            self.apply(['identity'], ['identity:caller_keys=identity_callers_2'])
        self.assertEqual(self.swarm.posts, [])

    def test_a_swap_swarm_did_not_actually_apply_is_reported(self):
        # Swarm silently keeps the old secret; the tool re-reads the service and must notice.
        original = self.swarm

        def ignores_secrets(method, path, body=None, auth=None):
            if method == 'POST' and body:
                body = copy.deepcopy(body)
                for ref in body['TaskTemplate']['ContainerSpec']['Secrets']:
                    if ref['File']['Name'] == 'caller_keys':
                        ref['SecretName'] = 'identity_callers'
            return original(method, path, body, auth)
        with self.context(ignores_secrets), tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(RuntimeError, 'different secret references than planned'), \
                    contextlib.redirect_stderr(io.StringIO()):
                cluster.update('e.json', 'operator', NEW_IMAGE, TARGET_REVISION, ['identity'], 'restore-2026-11-14',
                               NEW_IMAGE, str(Path(directory) / 'r.json'), False,
                               ['identity:caller_keys=identity_callers_2'])

    # --- rollback ------------------------------------------------------------------------------

    def rolled_back(self):
        self.apply(['gateway', 'identity'], ['gateway:outbound_key=gateway_outbound_2',
                                              'identity:caller_keys=identity_callers_2'])
        self.swarm.posts.clear()

    def test_rollback_restores_the_previous_image_and_secrets(self):
        before = {s: copy.deepcopy(self.live(s)) for s in ('gateway', 'identity')}
        self.rolled_back()
        self.assertEqual(cluster.secret_refs(self.live('gateway'))[OUTBOUND], NEW_OUTBOUND)
        stderr = io.StringIO()
        with self.context(self.swarm), contextlib.redirect_stderr(stderr):
            cluster.rollback(['gateway', 'identity'], 'gateway,identity')
        self.assertEqual([p[0] for p in self.swarm.posts], [self.prefix + 'gateway', self.prefix + 'identity'])
        self.assertTrue(all('&rollback=previous' in p[1] and p[3] is None for p in self.swarm.posts))
        for service in ('gateway', 'identity'):
            self.assertEqual(self.live(service), before[service])  # image, labels, guards and secrets
        self.assertEqual(cluster.secret_refs(self.live('gateway'))[OUTBOUND], 'gateway_outbound')
        self.assertEqual(cluster.secret_refs(self.live('identity'))['caller_keys'], 'identity_callers')
        self.assertIn('secret ' + OUTBOUND + ': ' + NEW_OUTBOUND + ' -> gateway_outbound', stderr.getvalue())

    def test_rollback_dry_run_names_the_secret_it_would_restore_and_changes_nothing(self):
        self.rolled_back()
        stderr = io.StringIO()
        with self.context(self.swarm), contextlib.redirect_stderr(stderr):
            cluster.rollback(['identity'], None)
        self.assertEqual(self.swarm.posts, [])
        self.assertIn('secret caller_keys: ' + NEW_CALLERS + ' -> identity_callers', stderr.getvalue())
        self.assertNotIn('id-', stderr.getvalue())

    def test_rollback_is_refused_if_the_previous_secret_was_deleted_from_swarm(self):
        self.rolled_back()
        self.swarm.static['/v1.52/secrets'] = [s for s in self.swarm.static['/v1.52/secrets']
                                               if s['Spec']['Name'] != 'identity_callers']
        with self.context(self.swarm), self.assertRaisesRegex(RuntimeError, 'no longer exist: identity_callers'):
            cluster.rollback(['identity'], 'identity')
        self.assertEqual(self.swarm.posts, [])


@contextlib.contextmanager
def tamper_once(change):
    """Make the first `pinned()` call (the one that builds the update spec) also apply `change`.
    Later calls, which build the drift-check comparison, stay honest, as a real bug would."""
    original, calls = cluster.pinned, []

    def wrapper(spec, image, revision):
        new = original(spec, image, revision)
        if not calls:
            change(new)
        calls.append(1)
        return new
    with patch.object(cluster, 'pinned', wrapper):
        yield


class OracleOverrides(OverrideCases, unittest.TestCase):
    prefix = 'kvtest-'

    def make(self):
        swarm = FakeSwarm()
        mount_outbound(swarm, 'kvtest-gateway', oracle=True)
        return swarm

    def context(self, swarm):
        return manager(swarm)


class AwsOverrides(OverrideCases, unittest.TestCase):
    prefix = 'kolovibe-'

    def make(self):
        swarm = AwsSwarm()
        mount_outbound(swarm, 'kolovibe-gateway', oracle=False)
        return swarm

    def context(self, swarm):
        return aws(swarm)

    def test_the_aws_allow_list_names_still_count_as_the_services_own(self):
        add_secrets(self.swarm, APPROVAL)
        entry = self.plan(['identity'], ['identity:account_approvals=' + APPROVAL])['entries'][0]
        self.assertEqual(entry['secret_changes'], [])  # already mounted there: no change
        add_secrets(self.swarm, SMTP_PASSWORD)
        self.assert_refused('does not belong to it', ['gateway'], ['gateway:outbound_key=' + SMTP_PASSWORD])

    def test_an_allow_listed_name_on_the_wrong_service_is_refused(self):
        add_secrets(self.swarm, SMTP_USER)
        self.assert_refused('does not belong to it: kolovibe-audit', ['audit'], ['audit:caller_keys=' + SMTP_USER])


class OracleOnlyOverrides(unittest.TestCase):
    def test_the_aws_allow_list_names_do_not_apply_to_oracle(self):
        swarm = FakeSwarm()
        add_secrets(swarm, APPROVAL)
        with manager(swarm), self.assertRaisesRegex(RuntimeError, 'does not belong to it: kvtest-identity'):
            cluster.update_plan(EVIDENCE, NEW_IMAGE, TARGET_REVISION, ['identity'],
                                secret_overrides=['identity:account_approvals=' + APPROVAL])


class CommandLineTests(unittest.TestCase):
    def run_main(self, *argv):
        with patch.object(sys, 'argv', ['kolovibe_cluster.py', *argv]), \
                patch.object(cluster, 'PROFILE', cluster.ORACLE_STAGING):
            return cluster.main()

    def test_the_flag_is_repeatable_and_reaches_update_for_the_named_profile(self):
        with patch.object(cluster, 'resolve_release', return_value=(NEW_IMAGE, TARGET_REVISION)), \
                patch.object(cluster, 'update') as update:
            self.run_main('update-plan', '--profile', 'aws-staging', '--worker-evidence', 'w.json',
                          '--services', 'gateway,identity',
                          '--secret-override', 'gateway:outbound_key=gateway_outbound_2',
                          '--secret-override', 'identity:caller_keys=identity_callers_2')
        self.assertEqual(update.call_args.args[-1], ['gateway:outbound_key=gateway_outbound_2',
                                                     'identity:caller_keys=identity_callers_2'])
        self.assertIsNone(update.call_args.args[6])  # update-plan never confirms

    def test_overrides_are_never_defaulted(self):
        with patch.object(cluster, 'resolve_release', return_value=(NEW_IMAGE, TARGET_REVISION)), \
                patch.object(cluster, 'update') as update:
            self.run_main('update-plan', '--profile', 'oracle-staging', '--worker-evidence', 'w.json',
                          '--services', 'gateway')
        self.assertIsNone(update.call_args.args[-1])

    def test_the_flag_is_refused_outside_update_plan_and_update(self):
        for mode in ('rollback', 'plan', 'deploy', 'verify-worker', 'worker-preflight'):
            with self.subTest(mode=mode), patch('sys.stderr'), self.assertRaises(SystemExit) as raised:
                self.run_main(mode, '--profile', 'aws-staging', '--worker-evidence', 'w.json',
                              '--secret-override', 'gateway:outbound_key=gateway_outbound_2')
            self.assertEqual(raised.exception.code, 2)


if __name__ == '__main__':
    unittest.main()
