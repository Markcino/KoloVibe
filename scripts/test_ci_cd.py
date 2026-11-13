"""Regression checks for the single workflow's event and privilege boundaries."""

import ast
import json
import os
from pathlib import Path
import subprocess
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[1]
QUALITY = {"python", "security", "flutter", "osv", "image-build", "build-and-verify"}
SERVICES = {"gateway", "identity", "creators", "content", "engagement", "points",
            "moderation", "audit"}
MAIN_PUSH = "github.event_name == 'push' && github.ref == 'refs/heads/main'"


def matches(expression, event, ref="refs/heads/main", operation=""):
    """Evaluate only the simple comparisons used by our job event filters."""
    values = {"github.event_name": event, "github.ref": ref, "inputs.operation": operation}
    tree = ast.parse(expression.replace("&&", " and ").replace("||", " or "), mode="eval")

    def visit(node):
        if isinstance(node, ast.Expression):
            return visit(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return node.value
        if isinstance(node, ast.Attribute):
            return values[ast.unparse(node)]
        if isinstance(node, ast.BoolOp):
            operands = [visit(value) for value in node.values]
            if isinstance(node.op, ast.And):
                return all(operands)
            if isinstance(node.op, ast.Or):
                return any(operands)
        if isinstance(node, ast.Compare) and len(node.ops) == 1:
            left, right = visit(node.left), visit(node.comparators[0])
            if isinstance(node.ops[0], ast.Eq):
                return left == right
            if isinstance(node.ops[0], ast.NotEq):
                return left != right
        raise AssertionError("Unsupported workflow condition")

    return visit(tree)


class WorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow = yaml.safe_load((ROOT / ".github/workflows/ci_cd.yml").read_text())
        # PyYAML's YAML 1.1 resolver reads the Actions key "on" as True.
        cls.workflow["on"] = cls.workflow.pop(True)
        cls.jobs = cls.workflow["jobs"]

    def test_one_entry_point_and_preserved_triggers(self):
        self.assertEqual(
            {path.name for path in (ROOT / ".github/workflows").iterdir()},
            {"ci_cd.yml"})
        self.assertEqual(self.workflow["name"], "ci_cd")
        self.assertEqual(set(self.workflow["on"]),
                         {"push", "pull_request", "schedule", "workflow_dispatch"})
        self.assertEqual(self.workflow["on"]["push"]["branches"],
                         ["main"])
        self.assertEqual(self.workflow["on"]["schedule"], [{"cron": "13 5 * * 1"}])
        inputs = self.workflow["on"]["workflow_dispatch"]["inputs"]["operation"]
        self.assertEqual(inputs["default"], "ci")
        self.assertEqual(inputs["options"], ["ci", "dependency-locks", "staging-security", "identity-secrets"])

    def test_full_checks_run_for_main_pr_and_manual_ci_only(self):
        for job in QUALITY - {"osv"}:
            condition = self.jobs[job]["if"]
            for event, ref, operation, expected in [
                ("push", "refs/heads/main", "", True),
                ("pull_request", "refs/pull/7/merge", "", True),
                ("workflow_dispatch", "refs/heads/feature/test", "ci", True),
                ("push", "refs/heads/feature/test", "", False),
                ("schedule", "refs/heads/main", "", False),
                ("workflow_dispatch", "refs/heads/main", "staging-security", False),
                ("workflow_dispatch", "refs/heads/main", "identity-secrets", False),
                ("workflow_dispatch", "refs/heads/security/ci-hardening", "dependency-locks", False),
            ]:
                with self.subTest(job=job, event=event, operation=operation):
                    self.assertEqual(matches(condition, event, ref, operation), expected)

    def test_advisory_schedule_and_ci_coverage_are_preserved(self):
        condition = self.jobs["osv"]["if"]
        for event in ("push", "pull_request", "schedule"):
            self.assertTrue(matches(condition, event, "refs/heads/feature/test"))
        self.assertTrue(matches(condition, "workflow_dispatch", operation="ci"))
        self.assertFalse(matches(condition, "workflow_dispatch", operation="dependency-locks"))
        self.assertFalse(matches(condition, "workflow_dispatch", operation="staging-security"))

    def test_dependency_scan_does_not_depend_on_artifact_quota(self):
        osv = self.jobs["osv"]
        self.assertEqual(osv["name"], "Python and Flutter dependency advisories / osv-scan")
        self.assertEqual(osv["permissions"], {"contents": "read"})
        scanner = next(step for step in osv["steps"] if step.get("name") == "Scan locked Python and Flutter dependencies")
        self.assertIn("google/osv-scanner-action/osv-scanner-action@", scanner["uses"])
        self.assertIn("--lockfile=requirements.txt:requirements-dev.txt", scanner["with"]["scan-args"])
        self.assertIn("--lockfile=apps/mobile/pubspec.lock", scanner["with"]["scan-args"])
        self.assertFalse(any(step.get("uses", "").startswith("actions/upload-artifact@")
                             for step in osv["steps"] + self.jobs["security"]["steps"]))
        image_steps = self.jobs["image-build"]["steps"]
        sbom = next(step for step in image_steps if step.get("name") == "Preserve Python dependency SBOM")
        self.assertIn("cyclonedx-py requirements requirements-dev.txt", sbom["run"])
        self.assertIn("python-sbom.json", next(step for step in image_steps
                                              if step.get("name") == "Preserve the verified image")["run"])

    def test_both_dependency_locks_are_audited_and_failures_block(self):
        # The CI toolchain lock once carried a High advisory that only
        # Dependabot reported, because only the application lock was audited.
        steps = self.jobs["security"]["steps"]
        audit = next(step for step in steps if step.get("name") == "Dependency vulnerability audit")
        commands = [line.strip() for line in audit["run"].splitlines() if "pip-audit" in line]
        for lock in ("requirements-dev.txt", "requirements-ci.txt"):
            self.assertTrue(any(f"pip-audit -r {lock} " in line and "--no-deps --disable-pip" in line
                                for line in commands), lock)
        self.assertEqual(len(commands), 2)
        for forbidden in ("|| true", "--ignore-vuln", "--skip-editable", "continue-on-error"):
            self.assertNotIn(forbidden, audit["run"])
            self.assertNotIn(forbidden, str(audit.get("continue-on-error", "")))

    def test_publish_requires_every_quality_job_without_status_bypass(self):
        publish = self.jobs["publish"]
        self.assertEqual(set(publish["needs"]), QUALITY)
        self.assertEqual(publish["if"], MAIN_PUSH)
        for job in QUALITY | {"publish"}:
            self.assertNotIn("continue-on-error", self.jobs[job])
            for step in self.jobs[job].get("steps", []):
                self.assertNotIn("continue-on-error", step)
        # No status function overrides GitHub's implicit success() requirement.
        self.assertNotIn("(", publish["if"])
        self.assertFalse(self.jobs["build-and-verify"]["strategy"]["fail-fast"])
        self.assertEqual(set(self.jobs["build-and-verify"]["strategy"]["matrix"]["service"]), SERVICES)
        self.assertNotIn("strategy", publish)
        self.assertNotIn("strategy", self.jobs["image-build"])
        self.assertEqual(self.jobs["build-and-verify"]["needs"], ["image-build"])

    def test_pr_schedule_and_manual_runs_cannot_publish(self):
        condition = self.jobs["publish"]["if"]
        self.assertTrue(matches(condition, "push"))
        for event, ref, operation in [
            ("pull_request", "refs/heads/main", ""),
            ("push", "refs/heads/feature/test", ""),
            ("schedule", "refs/heads/main", ""),
            ("workflow_dispatch", "refs/heads/main", "ci"),
            ("workflow_dispatch", "refs/heads/main", "staging-security"),
            ("workflow_dispatch", "refs/heads/security/ci-hardening", "dependency-locks"),
        ]:
            self.assertFalse(matches(condition, event, ref, operation))

    def test_same_run_exact_commit_artifact_handoff(self):
        build = self.jobs["image-build"]["steps"]
        publish = self.jobs["publish"]["steps"]
        upload = next(step for step in build if step["name"] == "Upload the verified image")
        download = next(step for step in publish if step.get("uses", "").startswith("actions/download-artifact@"))
        self.assertEqual(upload["with"]["name"], download["with"]["name"])
        # PR/manual jobs share the built artifact but can never publish it.
        self.assertNotIn("if", upload)
        self.assertEqual(download["with"],
                         {"name": "verified-image-${{ github.sha }}",
                          "path": "verified-image"})
        for step in publish:
            self.assertNotIn("ref", step.get("with", {}))
            if "REVISION" in step.get("env", {}):
                self.assertEqual(step["env"]["REVISION"], "${{ github.sha }}")
        commands = "\n".join(step.get("run", "") for step in publish)
        self.assertIn("scripts/verify_image_artifact.py", commands)
        self.assertIn("docker load", commands)
        self.assertNotIn("docker build", commands)
        self.assertIn('docker pull "$TARGET"', commands)
        matrix_steps = self.jobs["build-and-verify"]["steps"]
        matrix_download = next(step for step in matrix_steps
                               if step.get("uses", "").startswith("actions/download-artifact@"))
        self.assertEqual(matrix_download["with"], download["with"])
        all_commands = "\n".join(step.get("run", "") for job in self.jobs.values()
                                 for step in job.get("steps", []))
        self.assertEqual(all_commands.count("docker build "), 1)
        self.assertEqual(all_commands.count("docker push "), 1)
        self.assertIn('TARGET="ghcr.io/$REPOSITORY/services:', commands)
        smoke = next(step for step in matrix_steps if step.get("name") == "Run service HTTP smoke check")
        self.assertIn('-e "KOLOVIBE_SERVICE_NAME=$SERVICE"', smoke["run"])
        self.assertIn('"kolovibe/services:ci"', smoke["run"])

    def test_permissions_are_job_scoped(self):
        self.assertEqual(self.workflow["permissions"], {"contents": "read"})
        self.assertEqual([key for key, job in self.jobs.items()
                          if job.get("permissions", {}).get("packages") == "write"], ["publish"])
        self.assertEqual([key for key, job in self.jobs.items()
                          if job.get("permissions", {}).get("contents") == "write"], ["generate"])
        for key in QUALITY - {"osv"}:
            self.assertEqual(self.jobs[key].get("permissions", self.workflow["permissions"]),
                             {"contents": "read"})

    def test_lock_generation_is_restricted_to_maintenance_branch(self):
        condition = self.jobs["generate"]["if"]
        branch = "refs/heads/security/ci-hardening"
        self.assertFalse(matches(condition, "push", branch))
        self.assertTrue(matches(condition, "workflow_dispatch", branch, "dependency-locks"))
        self.assertFalse(matches(condition, "push"))
        self.assertFalse(matches(condition, "pull_request", branch))
        self.assertFalse(matches(condition, "workflow_dispatch", operation="dependency-locks"))
        self.assertFalse(matches(condition, "workflow_dispatch", branch, "ci"))

    def test_staging_secrets_require_explicit_main_dispatch(self):
        job = self.jobs["verify"]
        self.assertEqual(job["environment"], {"name": "staging-security-review"})
        self.assertTrue(matches(job["if"], "workflow_dispatch", operation="staging-security"))
        for event in ("push", "pull_request", "schedule"):
            self.assertFalse(matches(job["if"], event, operation="staging-security"))
        self.assertFalse(matches(job["if"], "workflow_dispatch", "refs/heads/feature/test",
                                 "staging-security"))
        self.assertFalse(matches(job["if"], "workflow_dispatch", operation="ci"))
        self.assertEqual(job["concurrency"]["group"], "kolovibe-environment-security-review")
        identity = self.jobs["identity-secrets"]
        self.assertEqual(identity["environment"], {"name": "staging-security-review"})
        self.assertTrue(matches(identity["if"], "workflow_dispatch", operation="identity-secrets"))
        self.assertFalse(matches(identity["if"], "pull_request", operation="identity-secrets"))
        self.assertFalse(matches(identity["if"], "workflow_dispatch", "refs/heads/feature/test",
                                 "identity-secrets"))
        self.assertFalse(matches(identity["if"], "workflow_dispatch", operation="ci"))
        self.assertEqual(identity["permissions"], {"contents": "read"})
        self.assertEqual(identity["needs"], ["validate-dispatch"])
        self.assertFalse(any(step.get("uses", "").startswith("actions/upload-artifact")
                             for step in identity["steps"]))

    def test_invalid_maintenance_branch_reports_failure(self):
        job = self.jobs["validate-dispatch"]
        self.assertEqual(job["if"], "github.event_name == 'workflow_dispatch'")
        script = job["steps"][0]["run"]
        self.assertIn("refs/heads/security/ci-hardening", script)
        self.assertIn("refs/heads/main", script)
        self.assertIn("::error::", script)
        self.assertIn("exit 1", script)
        for operation, ref, expected in [
            ("ci", "refs/heads/feature/test", 0),
            ("dependency-locks", "refs/heads/security/ci-hardening", 0),
            ("dependency-locks", "refs/heads/main", 1),
            ("staging-security", "refs/heads/main", 0),
            ("staging-security", "refs/heads/feature/test", 1),
            ("identity-secrets", "refs/heads/main", 0),
            ("identity-secrets", "refs/heads/feature/test", 1),
            ("unknown", "refs/heads/main", 1),
        ]:
            with self.subTest(operation=operation, ref=ref):
                result = subprocess.run(
                    ["bash", "-c", script], capture_output=True, text=True, check=False,
                    env={**os.environ, "OPERATION": operation, "GITHUB_REF": ref},
                    timeout=5)
                self.assertEqual(result.returncode, expected)
                if expected:
                    self.assertIn("::error::", result.stdout)

    def test_existing_required_check_names_are_preserved(self):
        checks = json.loads((ROOT / ".github/branch-protection/main.json").read_text())
        required = {check["context"] for check in checks["required_status_checks"]["checks"]}
        provided = {self.jobs[job]["name"] for job in ("python", "security", "flutter")}
        provided.add(self.jobs["osv"]["name"])
        provided.update(self.jobs["build-and-verify"]["name"].replace("${{ matrix.service }}", service)
                        for service in SERVICES)
        self.assertEqual(provided, required)


if __name__ == "__main__":
    unittest.main()
