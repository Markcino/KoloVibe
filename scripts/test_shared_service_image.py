"""Exercise shared-image service selection with real isolated Gunicorn processes."""

from http.client import HTTPConnection
import json
import os
from pathlib import Path
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
