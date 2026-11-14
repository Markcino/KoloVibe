"""Exercise shared-image service selection with real isolated Gunicorn processes."""

from http.client import HTTPConnection
import json
import os
from pathlib import Path
import re
import secrets
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services"))
from staging_runtime import SERVICES
from staging_runtime.launch import main, service_directory


class ImageSecurityContractTests(unittest.TestCase):
    """Guard the CI image-scan repair against regressions and weakened gates."""

    def setUp(self):
        self.dockerfile = (ROOT / "infra/docker/Dockerfile.service").read_text()
        self.workflow = (ROOT / ".github/workflows/ci_cd.yml").read_text()

    def test_os_packages_are_upgraded_before_python_dependencies(self):
        self.assertIn("RUN apk upgrade --no-cache", self.dockerfile)
        self.assertLess(self.dockerfile.index("apk upgrade --no-cache"),
                        self.dockerfile.index("pip install"))

    def test_base_image_stays_digest_pinned(self):
        self.assertRegex(self.dockerfile, r"(?m)^FROM python:[^@\s]+@sha256:[0-9a-f]{64}( AS \w+)?$")
        self.assertEqual(len(re.findall(r"(?m)^FROM python:", self.dockerfile)), 1)

    def test_image_scan_gate_is_not_weakened(self):
        start = self.workflow.index("Scan local image vulnerabilities")
        step = self.workflow[start:self.workflow.index("- name:", start + 1)]
        self.assertIn("fail-build: true", step)
        self.assertIn("severity-cutoff: high", step)
        for weakening in ("only-fixed", "ignore", "grype.yaml", "continue-on-error"):
            self.assertNotIn(weakening, step)

    def stages(self):
        parts = re.split(r"(?m)^FROM [^\n]+ AS (\w+)\n", self.dockerfile)
        return dict(zip(parts[1::2], parts[2::2]))

    def test_release_is_the_default_last_stage_and_local_keeps_sqlite(self):
        stages = self.stages()
        self.assertEqual(list(stages), ["local", "release"])
        # A bare `docker build` must produce the PostgreSQL-only image.
        self.assertEqual(re.findall(r"(?m)^FROM .* AS (\w+)$", self.dockerfile)[-1], "release")
        self.assertIn("FROM local AS release", self.dockerfile)
        # The local target is the unchanged SQLite-capable image: nothing is removed from it.
        for removal in ("apk del", "rm -rf", "_sqlite3"):
            self.assertNotIn(removal, stages["local"])

    def test_release_stage_removes_sqlite_and_fails_closed(self):
        release = self.stages()["release"]
        self.assertIn("apk del .python-rundeps sqlite-libs", release)
        # Other Python runtime libraries are re-pinned first so removal cannot cascade.
        self.assertLess(release.index(".kolovibe-python-rundeps"), release.index("apk del"))
        for check in ("apk info -e sqlite-libs", "apk list -I", "import sqlite3",
                      "import django, psycopg", "pip check"):
            self.assertIn(check, release)
        # `! command` is ignored by `set -e`; checks must use explicit conditionals.
        self.assertNotRegex(release, r"(?m)^\s*!\s")
        self.assertTrue(release.rstrip().endswith("USER 10001:10001"))
        self.assertIn("USER root", release)

    def test_release_stage_installs_ffmpeg_after_sqlite_removal_and_rechecks(self):
        release = self.stages()["release"]
        self.assertIn("apk add --no-cache ffmpeg", release)
        self.assertGreater(release.index("apk add --no-cache ffmpeg"), release.index("apk del .python-rundeps sqlite-libs"))
        tail = release[release.index("apk add --no-cache ffmpeg"):]
        for check in ("ffmpeg -version", "ffprobe -version", "apk list -I | grep -qi sqlite", "import sqlite3"):
            self.assertIn(check, tail)
        self.assertTrue(release.rstrip().endswith("USER 10001:10001"))
        self.assertIn("Verify FFmpeg for the media worker on the sandbox PATH", self.workflow)
        self.assertLess(self.workflow.index("Verify FFmpeg for the media worker"),
                        self.workflow.index("Scan local image vulnerabilities"))

    def test_ci_builds_scans_and_publishes_only_the_release_target(self):
        build = self.workflow[self.workflow.index("- name: Build shared service image"):
                              self.workflow.index("- name: Inspect image configuration")]
        self.assertIn("--target release", build)
        self.assertIn("--file infra/docker/Dockerfile.service", build)
        self.assertNotIn("--target local", self.workflow)
        verify = self.workflow[self.workflow.index("- name: Verify the release image has no SQLite"):
                               self.workflow.index("- name: Scan local image vulnerabilities")]
        self.assertIn("import sqlite3", verify)
        self.assertIn("list -I", verify)
        self.assertLess(self.workflow.index("Verify the release image has no SQLite"),
                        self.workflow.index("Scan local image vulnerabilities"))
        self.assertIn("lists no SQLite component", self.workflow)


class SharedImageTests(unittest.TestCase):
    def test_selection_rejects_missing_unknown_or_path_traversal(self):
        for name in (None, "", "unknown", "../identity", "/identity", "staging_runtime"):
            with self.subTest(name=name), self.assertRaises(RuntimeError):
                service_directory(ROOT / "services", name)
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaises(RuntimeError):
                service_directory(root, "gateway")
        for name in SERVICES:
            self.assertEqual(service_directory(ROOT / "services", name),
                             ROOT / "services" / name)

    def test_pid_one_is_replaced_with_one_selected_wsgi_process(self):
        for name in SERVICES:
            with self.subTest(service=name), patch.dict(os.environ, {"KOLOVIBE_SERVICE_NAME": name}), \
                    patch.object(sys, "argv", ["launch"]), patch("os.chdir") as chdir, \
                    patch.object(sys, "path", sys.path.copy()), patch("os.execv") as execute:
                main()
                chdir.assert_called_once_with(ROOT / "services" / name)
                executable, command = execute.call_args.args
                self.assertEqual(executable, sys.executable)
                self.assertEqual(command[command.index("--chdir") + 1],
                                 str(ROOT / "services" / name))
                self.assertEqual(command[-1], "staging_runtime.wsgi:application")
                self.assertEqual(command[command.index("--pythonpath") + 1],
                                 f"{ROOT / 'services'},{ROOT / 'services' / name}")
                self.assertEqual(command.count("gunicorn"), 1)

    def test_all_eight_service_settings_are_selected_without_cross_imports(self):
        for name in SERVICES:
            environment = {
                **{key: value for key, value in os.environ.items()
                   if not key.startswith(("KOLOVIBE_", "DJANGO_", "PYTHONPATH"))},
                "PYTHONPATH": str(ROOT / "services"), "KOLOVIBE_ENV": "local",
                "KOLOVIBE_SERVICE_NAME": name, "DJANGO_SECRET_KEY": secrets.token_urlsafe(48),
            }
            result = subprocess.run(
                [sys.executable, "-c",
                 "import os, sys; from staging_runtime.launch import main; "
                 "sys.argv=['launch','--check-settings']; main(); "
                 "from service import settings; "
                 "assert settings.KOLOVIBE_SERVICE_NAME == os.environ['KOLOVIBE_SERVICE_NAME']; "
                 "assert str(settings.BASE_DIR) == os.getcwd()"],
                cwd=ROOT, env=environment, capture_output=True, text=True, timeout=20)
            self.assertEqual(result.returncode, 0, f"{name}: {result.stderr}")
            for unsafe in ("production", "staging"):
                result = subprocess.run(
                    [sys.executable, "-m", "staging_runtime.launch", "--check-settings"],
                    cwd=ROOT, env=dict(environment, KOLOVIBE_ENV=unsafe),
                    capture_output=True, text=True, timeout=20)
                self.assertNotEqual(result.returncode, 0, f"{name} accepted incomplete {unsafe}")

    def test_shared_launcher_serves_real_http_without_database_or_other_services(self):
        with tempfile.TemporaryDirectory(prefix="kolovibe-shared-runtime-") as temporary:
            for name in sorted(SERVICES):
                with socket.socket() as reservation:
                    reservation.bind(("127.0.0.1", 0))
                    port = reservation.getsockname()[1]
                environment = {
                    **{key: value for key, value in os.environ.items()
                       if not key.startswith(("KOLOVIBE_", "DJANGO_", "PYTHONPATH", "GUNICORN_"))},
                    "PYTHONPATH": str(ROOT / "services"),
                    "KOLOVIBE_ENV": "local", "KOLOVIBE_SERVICE_NAME": name,
                    "DJANGO_SECRET_KEY": secrets.token_urlsafe(48),
                    "GUNICORN_CMD_ARGS": f"--bind 127.0.0.1:{port} --workers 1",
                }
                with (Path(temporary) / f"{name}.log").open("w") as log:
                    process = subprocess.Popen(
                        [sys.executable, "-m", "staging_runtime.launch"],
                        cwd=ROOT, env=environment, stdout=log, stderr=log)
                    try:
                        deadline = time.monotonic() + 20
                        while True:
                            if process.poll() is not None:
                                self.fail(f"Selected {name} WSGI process exited before startup")
                            connection = HTTPConnection("127.0.0.1", port, timeout=2)
                            try:
                                connection.request("GET", "/health/live")
                                response = connection.getresponse()
                                self.assertEqual(response.status, 200)
                                self.assertEqual(json.loads(response.read()), {"status": "ok"})
                                break
                            except (ConnectionError, OSError):
                                if time.monotonic() >= deadline:
                                    self.fail(f"Selected {name} WSGI startup timed out")
                                time.sleep(0.1)
                            finally:
                                connection.close()
                    finally:
                        process.terminate()
                        try:
                            process.wait(timeout=10)
                        except subprocess.TimeoutExpired:
                            process.kill()
                            process.wait(timeout=5)


if __name__ == "__main__":
    unittest.main()
