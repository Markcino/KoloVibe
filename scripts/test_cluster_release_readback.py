"""Offline tests for the read-only release read-back (D13-005); no Docker or VM required."""
import importlib.util
from pathlib import Path
import unittest

MODULE = Path(__file__).parent / 'ops/kolovibe_cluster.py'
spec = importlib.util.spec_from_file_location('cluster_release', MODULE)
cluster = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cluster)

# Published Git commit identifier, not an authentication credential.
REVISION = '38d038056cf77df4d4193e0aecef472dc7226aea'  # pragma: allowlist secret
EXPECTED = {'services': cluster.REPOSITORY + '@sha256:' + 'a' * 64,
            'media': cluster.RELEASE_REPOSITORIES['media'] + '@sha256:' + 'b' * 64,
            'web': cluster.RELEASE_REPOSITORIES['web'] + '@sha256:' + 'c' * 64}


def service(name, image, revision=REVISION):
    labels = {cluster.REVISION_LABEL: revision} if revision else {}
    return {'Spec': {'Name': name, 'Labels': labels, 'TaskTemplate': {'ContainerSpec': {'Image': image}}}}


def statuses(report):
    return {row['test']: row['status'] for row in report['checks']}


class ReleaseReadbackTests(unittest.TestCase):
    def test_a_consistent_release_passes_and_other_images_are_skipped(self):
        report = cluster.release_summary([
            service('kolovibe-gateway', EXPECTED['services']),
            service('kolovibe-jobs_points-audit', EXPECTED['services']),
            service('kolovibe-jobs_media-worker', EXPECTED['media']),
            service('kolovibe-web_web', EXPECTED['web']),
            service('kolovibe-postgres', 'postgres:17.6@sha256:' + 'd' * 64, revision=None)], EXPECTED, REVISION)
        self.assertFalse(cluster.has_failures(report))
        self.assertEqual(len(report['checks']), 8)
        postgres = next(row for row in report['services'] if row['service'] == 'kolovibe-postgres')
        self.assertEqual(postgres['kind'], 'not-a-release-image')

    def test_a_stale_label_fails_even_on_the_right_digest(self):
        # D13-005: v0.531.1 kept the v0.341.1 labels after a rollout outside the tool.
        report = cluster.release_summary([service('kolovibe-gateway', EXPECTED['services'], revision='9' * 40)],
                                         EXPECTED, REVISION)
        self.assertEqual(statuses(report), {'kolovibe-gateway runs the published services digest': 'PASS',
                                            'kolovibe-gateway is labelled with the release revision': 'FAIL'})

    def test_another_digest_or_a_missing_label_fails(self):
        report = cluster.release_summary([
            service('kolovibe-jobs_identity-audit', cluster.REPOSITORY + '@sha256:' + 'e' * 64),
            service('kolovibe-web_web', EXPECTED['web'], revision=None)], EXPECTED, REVISION)
        self.assertEqual(statuses(report)['kolovibe-jobs_identity-audit runs the published services digest'], 'FAIL')
        self.assertEqual(statuses(report)['kolovibe-web_web is labelled with the release revision'], 'FAIL')

    def test_a_tagged_reference_is_judged_by_its_digest(self):
        report = cluster.release_summary([service('kolovibe-gateway', cluster.REPOSITORY + ':v0.542.1@sha256:' + 'a' * 64)],
                                         EXPECTED, REVISION)
        self.assertFalse(cluster.has_failures(report))

    def test_nothing_to_compare_is_a_failure_not_a_pass(self):
        report = cluster.release_summary([service('kolovibe-postgres', 'postgres:17.6', revision=None)], EXPECTED, REVISION)
        self.assertTrue(cluster.has_failures(report))

    def test_the_mode_is_read_only(self):
        source = MODULE.read_text()
        body = source[source.index('def release_readback('):source.index('PROBE_JOB_NANOCPUS')]
        self.assertIn('manager_checks()', body)
        self.assertNotIn("docker('POST'", body)
        self.assertNotIn("docker('DELETE'", body)
        self.assertIn("'release-readback'", source)


if __name__ == '__main__':
    unittest.main()
