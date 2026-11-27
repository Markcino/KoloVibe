"""Offline tests for the read-only capacity report (D13-004, #274); no Docker or VM required."""
import importlib.util
from pathlib import Path
import unittest

MODULE = Path(__file__).parent / 'ops/kolovibe_cluster.py'
spec = importlib.util.spec_from_file_location('cluster_capacity', MODULE)
cluster = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cluster)

MIB = 1024 * 1024
NODE = {'ID': 'vm2', 'Description': {'Hostname': 'ip-172-31-16-154',
                                     'Resources': {'NanoCPUs': 2_000_000_000, 'MemoryBytes': 3891 * MIB}}}


def task(service, cpu_millis, memory_mib, node='vm2', desired='running', state='running'):
    return {'NodeID': node, 'ServiceID': service, 'DesiredState': desired, 'Status': {'State': state},
            'Spec': {'Resources': {'Reservations': {'NanoCPUs': cpu_millis * 1_000_000,
                                                    'MemoryBytes': memory_mib * MIB}}}}


class CapacitySummaryTests(unittest.TestCase):
    def test_the_26_november_layout_has_no_room_for_a_100m_job(self):
        # 8 APIs and 7 workers at 100m, PostgreSQL and RabbitMQ at 250m: the D13-004 reading.
        names = {f's{i}': f'kolovibe-s{i}' for i in range(15)} | {'pg': 'kolovibe-postgres', 'mq': 'kolovibe-rabbitmq'}
        tasks = [task(f's{i}', 100, 128) for i in range(15)] + [task('pg', 250, 256), task('mq', 250, 256)]
        report = cluster.capacity_summary(NODE, tasks, names)
        self.assertEqual(report['cpu_millis'], {'allocatable': 2000, 'reserved': 2000, 'free': 0})
        self.assertEqual(report['checks'], [{'test': 'a 100m one-shot job can be scheduled', 'status': 'FAIL'}])
        self.assertTrue(cluster.has_failures(report))
        self.assertEqual(report['services']['kolovibe-postgres'], {'tasks': 1, 'cpu_millis': 250, 'memory_mib': 256})

    def test_only_running_tasks_on_the_worker_count(self):
        names = {'a': 'kolovibe-a', 'b': 'kolovibe-b'}
        tasks = [task('a', 100, 64), task('a', 900, 64, node='vm1'), task('b', 900, 64, desired='shutdown'),
                 task('b', 900, 64, state='complete')]
        report = cluster.capacity_summary(NODE, tasks, names)
        self.assertEqual(report['cpu_millis']['reserved'], 100)
        self.assertEqual(report['memory_mib']['free'], 3891 - 64)
        self.assertEqual(report['checks'][0]['status'], 'PASS')
        self.assertFalse(cluster.has_failures(report))

    def test_a_task_without_reservations_or_a_known_service_still_counts_safely(self):
        report = cluster.capacity_summary(NODE, [{'NodeID': 'vm2', 'ServiceID': 'x', 'DesiredState': 'running',
                                                  'Status': {'State': 'running'}, 'Spec': {}}], {})
        self.assertEqual(report['services'], {'unknown': {'tasks': 1, 'cpu_millis': 0, 'memory_mib': 0}})

    def test_the_report_carries_names_and_numbers_only(self):
        report = cluster.capacity_summary(NODE, [task('a', 50, 64)], {'a': 'kolovibe-a'})
        self.assertEqual(set(report), {'kind', 'node', 'cpu_millis', 'memory_mib', 'services', 'checks', 'not_tested'})

    def test_capacity_is_a_mode_and_is_read_only(self):
        source = MODULE.read_text()
        body = source[source.index('def capacity():'):source.index('def verify_worker(')]
        self.assertIn("'capacity'))", source)
        self.assertNotIn("docker('POST'", body)
        self.assertNotIn("docker('DELETE'", body)
        self.assertIn('manager_checks()', body)


if __name__ == '__main__':
    unittest.main()
