"""The Gateway guard accepts the baseline, the exact target, or an earlier release the profile lists by digest. Nothing else."""

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

V0_187_2 = cluster.REPOSITORY + '@sha256:0b3bba46d1de2c988fe06099944a9a1a9be37df128c407ec51430f95fe576f69'
V0_200_1 = cluster.REPOSITORY + '@sha256:c681a909334f6196c1144dfe6569876b4df0920c1d7acab46a3ad0ad348f9a4b'
V0_205_1 = AWS.reviewed_releases[2]
V0_271_1 = AWS.reviewed_releases[3]
UNLISTED = cluster.REPOSITORY + '@sha256:' + 'b' * 64
OTHER_REPOSITORY = 'ghcr.io/someone-else/services@sha256:' + 'c' * 64
ORDER = ['audit', 'identity', 'creators', 'content', 'engagement', 'points', 'moderation', 'gateway']


def on_image(swarm, image, services=cluster.SERVICES):
    for service in services:
        swarm.services['kolovibe-' + service]['Spec']['TaskTemplate']['ContainerSpec']['Image'] = image
    return swarm


def plan(swarm, services=ORDER):
    with aws(swarm):
        return cluster.update_plan(EVIDENCE, NEW_IMAGE, TARGET_REVISION, services)


class ReviewedReleaseTableTests(unittest.TestCase):
    def test_the_aws_profile_lists_the_deployed_earlier_digests(self):
        self.assertEqual(AWS.reviewed_releases, (V0_187_2, V0_200_1, V0_205_1, V0_271_1))
        self.assertTrue(V0_205_1.startswith(cluster.REPOSITORY + '@sha256:a43d0cfb'))
        self.assertTrue(V0_205_1.endswith('c5ba8d66' + '4ee509c5'))
        self.assertEqual(len(V0_205_1), len(cluster.REPOSITORY) + len('@sha256:') + 64)
        self.assertTrue(V0_271_1.startswith(cluster.REPOSITORY + '@sha256:7c4942e3'))
        self.assertTrue(V0_271_1.endswith('183036e72'))
        self.assertEqual(len(V0_271_1), len(cluster.REPOSITORY) + len('@sha256:') + 64)
        self.assertNotEqual(V0_187_2, cluster.BASELINE_IMAGE)
        cluster.check_flag_table(AWS)

    def test_oracle_lists_no_earlier_release(self):
        self.assertEqual(cluster.ORACLE_STAGING.reviewed_releases, ())

    def test_broken_lists_are_refused_at_review_time(self):
        bad = {
            'a tag instead of a digest': (cluster.REPOSITORY + ':v0.187.2',),
            'a short digest': (cluster.REPOSITORY + '@sha256:' + 'a' * 63,),
            'another repository': (OTHER_REPOSITORY,),
            'the baseline': (cluster.BASELINE_IMAGE,),
            'a duplicate': (V0_187_2, V0_187_2),
            'not a string': (None,),
            'a wildcard': (cluster.REPOSITORY + '@sha256:*',),
        }
        cluster.check_reviewed_releases(AWS._replace(reviewed_releases=(V0_187_2, UNLISTED)))
        for label, releases in bad.items():
            with self.subTest(label), self.assertRaises(ValueError):
                cluster.check_reviewed_releases(AWS._replace(reviewed_releases=releases))


class GatewayGuardTests(unittest.TestCase):
    def test_a_gateway_on_the_baseline_is_still_accepted(self):
        self.assertEqual([e['service'] for e in plan(AwsSwarm())['entries']], ORDER)

    def test_a_gateway_already_on_the_exact_target_is_still_accepted(self):
        swarm = on_image(AwsSwarm(), NEW_IMAGE, ['gateway'])
        self.assertEqual(next(e for e in plan(swarm)['entries'] if e['service'] == 'gateway')['action'], 'unchanged')

    def test_the_whole_fleet_on_the_listed_earlier_release_can_be_planned_forward(self):
        for earlier in (V0_187_2, V0_200_1, V0_205_1, V0_271_1):
            with self.subTest(earlier=earlier):
                report = plan(on_image(AwsSwarm(), earlier))
                self.assertEqual([e['service'] for e in report['entries']], ORDER)
                for entry in report['entries']:
                    with self.subTest(entry['service']):
                        self.assertEqual(entry['current_image'], earlier)
                        self.assertEqual(entry['target_image'], NEW_IMAGE)
                        self.assertEqual(entry['action'], 'update')
                        self.assertIsNone(entry['r1_changes'])      # an image move changes nothing else
                        self.assertFalse(entry['secret_changes'])

    def test_an_unlisted_digest_of_this_repository_still_stops_every_plan(self):
        for services in (['audit'], ORDER):
            with self.subTest(services=services), self.assertRaisesRegex(RuntimeError, 'differs from the working pinned baseline'):
                plan(on_image(AwsSwarm(), UNLISTED, ['gateway']), services)

    def test_another_repository_or_a_tag_still_stops_every_plan(self):
        for image in (OTHER_REPOSITORY, cluster.REPOSITORY + ':v0.187.2', 'busybox:latest'):
            with self.subTest(image=image), self.assertRaises(RuntimeError):
                plan(on_image(AwsSwarm(), image, ['gateway']), ['audit'])

    def test_the_listing_does_not_relax_any_other_gateway_guard(self):
        for label, change in (
                ('the database login', lambda env: [e.replace('kolovibe_gateway_app', 'kolovibe_other_app') for e in env]),
                ('the environment', lambda env: [e.replace('KOLOVIBE_ENV=staging', 'KOLOVIBE_ENV=local') for e in env])):
            swarm = on_image(AwsSwarm(), V0_187_2, ['gateway'])
            spec = swarm.services['kolovibe-gateway']['Spec']['TaskTemplate']['ContainerSpec']
            spec['Env'] = change(spec['Env'])
            with self.subTest(label), self.assertRaisesRegex(RuntimeError, 'differs from the working pinned baseline'):
                plan(swarm, ['audit'])

    def test_an_unknown_gateway_image_is_not_made_acceptable_by_naming_it_as_the_target(self):
        # Moving to a new target never needs the listing: the target itself is always accepted, but the live image must be known.
        swarm = on_image(AwsSwarm(), UNLISTED, ['gateway'])
        with aws(swarm), self.assertRaisesRegex(RuntimeError, 'differs from the working pinned baseline'):
            cluster.update_plan(EVIDENCE, cluster.REPOSITORY + '@sha256:' + 'd' * 64, TARGET_REVISION, ['gateway'])

    def test_applying_from_the_listed_release_moves_only_the_image_and_rolls_back(self):
        swarm = on_image(AwsSwarm(), V0_205_1)
        before = copy.deepcopy(swarm.services['kolovibe-audit']['Spec'])
        with aws(swarm), tempfile.TemporaryDirectory() as directory, patch('sys.stderr'):
            cluster.update('e.json', 'operator', NEW_IMAGE, TARGET_REVISION, ['audit'], 'WAIVED-R1-STAGING-20261114',
                           NEW_IMAGE, str(Path(directory) / 'r.json'), True)
        live = swarm.services['kolovibe-audit']['Spec']
        self.assertEqual(cluster.live_image(live), NEW_IMAGE)
        self.assertEqual([p[0] for p in swarm.posts], ['kolovibe-audit'])
        with aws(swarm), patch('sys.stderr'):
            cluster.rollback(['audit'], 'audit')
        self.assertEqual(swarm.services['kolovibe-audit']['Spec'], before)


if __name__ == '__main__':
    unittest.main()
