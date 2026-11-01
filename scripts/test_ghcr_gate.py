"""Publication must never substitute a different commit or incomplete checks."""

import copy
import unittest

from scripts.ghcr_gate import WORKFLOWS, select_runs

SHA = "a" * 40


class FakeAPI:
    def __init__(self):
        self.runs = {}
        self.jobs = {}
        for number, (name, (filename, jobs)) in enumerate(WORKFLOWS.items(), 1):
            run = {"id": number, "run_number": 1, "run_attempt": 1,
                   "head_sha": SHA, "head_branch": "main", "event": "push",
                   "status": "completed", "conclusion": "success", "name": name}
            self.runs[filename] = [run]
            self.jobs[number] = [{"name": job, "status": "completed",
                                  "conclusion": "success"} for job in jobs]

    def items(self, path, key):
        if key == "workflow_runs":
            return self.runs[path.split("/")[3]]
        return self.jobs[int(path.split("/")[3])]

    def event(self):
        return copy.deepcopy(self.runs["api-quality.yml"][0])


class GateTests(unittest.TestCase):
    def test_requires_all_successful_exact_commit_runs(self):
        api = FakeAPI()
        selected, _ = select_runs(api, SHA, api.event())
        self.assertEqual(selected["Container quality"], 2)

    def test_missing_failed_cancelled_pending_and_skipped_runs_block(self):
        for value in ("failure", "cancelled", "skipped", None):
            api = FakeAPI()
            api.runs["container-quality.yml"][0]["conclusion"] = value
            with self.subTest(value=value):
                self.assertIsNone(select_runs(api, SHA, api.event())[0])
        api = FakeAPI()
        api.runs["container-quality.yml"] = []
        self.assertIsNone(select_runs(api, SHA, api.event())[0])
        api = FakeAPI()
        api.runs["container-quality.yml"][0]["status"] = "in_progress"
        self.assertIsNone(select_runs(api, SHA, api.event())[0])

    def test_other_commit_branch_or_pr_does_not_qualify(self):
        for field, value in (("head_sha", "b" * 40), ("head_branch", "feature/test"),
                             ("event", "pull_request")):
            api = FakeAPI()
            api.runs["container-quality.yml"][0][field] = value
            self.assertIsNone(select_runs(api, SHA, api.event())[0])
            event = api.event()
            event[field] = value
            self.assertIsNone(select_runs(api, SHA, event)[0])

    def test_missing_or_unsuccessful_jobs_block(self):
        for value in ("failure", "skipped", "cancelled", None):
            api = FakeAPI()
            api.jobs[2][0]["conclusion"] = value
            self.assertIsNone(select_runs(api, SHA, api.event())[0])
        api = FakeAPI()
        api.jobs[2].pop()
        self.assertIsNone(select_runs(api, SHA, api.event())[0])

    def test_stale_success_cannot_override_newer_failed_run(self):
        api = FakeAPI()
        newer = dict(api.runs["container-quality.yml"][0], id=20,
                     run_number=2, conclusion="failure")
        api.runs["container-quality.yml"].append(newer)
        self.assertIsNone(select_runs(api, SHA, api.event())[0])

    def test_stale_trigger_attempt_is_rejected(self):
        api = FakeAPI()
        event = api.event()
        api.runs["api-quality.yml"][0]["run_attempt"] = 2
        self.assertIsNone(select_runs(api, SHA, event)[0])

    def test_malformed_commit_and_unexpected_workflow_are_errors(self):
        api = FakeAPI()
        with self.assertRaises(ValueError):
            select_runs(api, "main", api.event())
        event = api.event()
        event["name"] = "Untrusted workflow"
        with self.assertRaises(ValueError):
            select_runs(api, SHA, event)


if __name__ == "__main__":
    unittest.main()
