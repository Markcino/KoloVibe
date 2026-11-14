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

import yaml
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
        # One parameterized base, pinned by digest, used by exactly one FROM; the default is the Alpine 3.23 image.
        self.assertRegex(self.dockerfile, r"(?m)^ARG PYTHON_BASE=python:3\.12\.16-alpine3\.23@sha256:[0-9a-f]{64}$")
        self.assertEqual(re.findall(r"(?m)^FROM [^\n]+$", self.dockerfile)[0], "FROM ${PYTHON_BASE} AS local")
        self.assertEqual(len(re.findall(r"(?m)^FROM python:", self.dockerfile)), 0)
        # The media image's Alpine 3.24 base is named only in CI, by digest.
        self.assertRegex(self.workflow, r"(?m)^\s+MEDIA_PYTHON_BASE: python:3\.12\.16-alpine3\.24@sha256:[0-9a-f]{64}$")

    def test_image_scan_gate_is_not_weakened(self):
        for name in ("Scan local image vulnerabilities", "Scan media image vulnerabilities"):
            start = self.workflow.index(name)
            step = self.workflow[start:self.workflow.index("- name:", start + 1)]
            self.assertIn("fail-build: true", step, name)
            self.assertIn("severity-cutoff: high", step, name)
            for weakening in ("only-fixed", "ignore", "grype.yaml", "continue-on-error", "severity-cutoff: critical"):
                self.assertNotIn(weakening, step, name)
        self.assertEqual(self.workflow.count("fail-build: true"), 2)

    def stages(self):
        parts = re.split(r"(?m)^FROM [^\n]+ AS ([\w-]+)\n", self.dockerfile)
        return dict(zip(parts[1::2], parts[2::2]))

    def test_release_is_the_default_last_stage_and_local_keeps_sqlite(self):
        stages = self.stages()
        self.assertEqual(list(stages), ["local", "ffmpeg-minimal", "ffmpeg-empty", "ffmpeg-source", "release"])
        # A bare `docker build` must produce the PostgreSQL-only image.
        self.assertEqual(re.findall(r"(?m)^FROM .* AS ([\w-]+)$", self.dockerfile)[-1], "release")
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

    def test_ffmpeg_is_installed_only_for_the_media_build_after_sqlite_removal_and_rechecked(self):
        release = self.stages()["release"]
        self.assertIn("ARG WITH_FFMPEG=0", release)
        # Alpine's full ffmpeg package is never installed; the minimal build is copied in and its runtime library added.
        self.assertNotIn("apk add --no-cache ffmpeg", release)
        self.assertIn("COPY --from=ffmpeg-source /out/ /tmp/ffmpeg-out/", release)
        self.assertIn("FROM ${FFMPEG_SOURCE} AS ffmpeg-source", self.dockerfile)
        self.assertGreater(release.index("COPY --from=ffmpeg-source"), release.index("apk del .python-rundeps sqlite-libs"))
        self.assertRegex(release, r'if \[ "\$WITH_FFMPEG" = "1" \]; then[^#]*apk add --no-cache --allow-untrusted /tmp/ffmpeg-out/apk/ffmpeg-\*\.apk')
        self.assertIn("rm -rf /tmp/ffmpeg-out", release)
        self.assertIn("FFmpeg must not be in the shared image", release)
        tail = release[release.index("COPY --from=ffmpeg-source"):]
        for check in ("ffmpeg -version", "ffprobe -version", "A network protocol is compiled into FFmpeg",
                      "apk list -I | grep -qi sqlite", "import sqlite3"):
            self.assertIn(check, tail)
        self.assertTrue(release.rstrip().endswith("USER 10001:10001"))

    def test_the_minimal_ffmpeg_build_is_pinned_packaged_and_compiles_out_everything_the_pipeline_does_not_use(self):
        stage = self.stages()["ffmpeg-minimal"]
        apkbuild = (ROOT / "infra/docker/ffmpeg/APKBUILD").read_text()
        self.assertRegex(self.dockerfile, r"(?m)^ARG FFMPEG_BUILD_BASE=alpine:3\.24\.\d+@sha256:[0-9a-f]{64}$")
        self.assertIn("COPY --chown=builder:builder infra/docker/ffmpeg/APKBUILD", stage)
        # Packaged as an apk named ffmpeg at the true version, so the scanner and the SBOM can see and judge it.
        self.assertIn("pkgname=ffmpeg\n", apkbuild)
        self.assertIn("pkgver=9.0.2\n", apkbuild)  # 9.0 fixes CVE-2026-70628, -70632 and -96611
        self.assertRegex(apkbuild, r'(?s)sha512sums="\s*[0-9a-f]{128}  ffmpeg-9\.0\.2\.tar\.xz\s*"')
        self.assertIn('source="https://ffmpeg.org/releases/ffmpeg-$pkgver.tar.xz"', apkbuild)
        self.assertIn("abuild -r", stage)
        configure = apkbuild[apkbuild.index("./configure"):apkbuild.index("make -j")]
        for flag in ("--disable-everything", "--disable-autodetect", "--disable-network", "--disable-avdevice",
                     "--disable-shared", "--enable-protocol=file", "--enable-protocol=pipe"):
            self.assertIn(flag, configure)
        self.assertEqual(sorted(re.findall(r"--enable-protocol=(\w+)", configure)), ["file", "pipe"])
        for forbidden in ("rtsp", "rtp", "http", "tcp", "udp", "tls", "libssh", "libzmq", "libpulse", "alsa",
                          "--enable-network", "--enable-avdevice", "--enable-libx265", "--enable-libvpx"):
            self.assertNotIn(forbidden, configure)
        self.assertEqual(sorted(re.findall(r"--enable-encoder=(\w+)", configure)), ["aac", "libx264", "mjpeg"])
        self.assertEqual(re.findall(r"--enable-muxer=(\w+)", configure), ["mp4", "image2"])
        self.assertEqual(re.findall(r"--enable-demuxer=(\w+)", configure), ["mov"])
        # The default build copies an empty directory, so the shared image never builds or contains FFmpeg.
        self.assertIn("ARG FFMPEG_SOURCE=ffmpeg-empty", self.dockerfile)
        self.assertNotIn("ffmpeg", self.stages()["ffmpeg-empty"].lower().replace("ffmpeg-empty", "").replace("/ffmpeg", ""))

    def test_the_only_scan_exception_is_the_approved_one_and_has_not_expired(self):
        import datetime

        config = (ROOT / ".grype.yaml").read_text()
        rules = yaml.safe_load(config)
        self.assertEqual(set(rules), {"ignore"})
        self.assertEqual(rules["ignore"], [{"vulnerability": "CVE-2026-107696",
                                            "package": {"name": "ffmpeg", "version": "9.0.2-r0", "type": "apk"}}])
        # The exception is justified by the build having no network protocols, which CI verifies on every build.
        media_job = self.workflow[self.workflow.index("  media-image-build:"):self.workflow.index("  build-and-verify:")]
        for needle in ("rtsp", "http", "tcp", '= "file pipe "'):
            self.assertIn(needle, media_job)
        expiry = datetime.date.fromisoformat(re.search(r"(?m)^# Expires: (\d{4}-\d{2}-\d{2})$", config).group(1))
        self.assertGreater(expiry, datetime.date.today(), "The CVE-2026-107696 scan exception expired: review or remove it")
        self.assertLessEqual(expiry, datetime.date(2027, 3, 1))
        # The gate steps themselves stay exactly as strict, and name no configuration file.
        for name in ("Scan local image vulnerabilities", "Scan media image vulnerabilities"):
            start = self.workflow.index(name)
            step = self.workflow[start:self.workflow.index("- name:", start + 1)]
            self.assertIn("fail-build: true", step)
            self.assertIn("severity-cutoff: high", step)
            self.assertNotIn("config", step)

    def test_the_build_context_excludes_infra_except_the_ffmpeg_apkbuild(self):
        rules = [line.strip() for line in (ROOT / ".dockerignore").read_text().splitlines()
                 if line.strip() and not line.startswith("#")]
        self.assertIn("infra", rules)
        self.assertEqual([r for r in rules if r.startswith("!")], ["!infra/docker/ffmpeg/APKBUILD"])
        self.assertLess(rules.index("infra"), rules.index("!infra/docker/ffmpeg/APKBUILD"))

    def test_the_media_job_verifies_the_minimal_build_and_runs_the_pipeline_test_in_the_image(self):
        media_job = self.workflow[self.workflow.index("  media-image-build:"):self.workflow.index("  build-and-verify:")]
        self.assertIn("--build-arg FFMPEG_SOURCE=ffmpeg-minimal", media_job)
        verify = media_job[media_job.index("Verify FFmpeg is the minimal build"):media_job.index("End-to-end media pipeline test")]
        for needle in ("ffmpeg version 9", "file pipe", "libx264", "cjson|alsa-lib|glib|libssh"):
            self.assertIn(needle, verify)
        for absent in ("libvpx", "libopus", "rtsp", "http", "tcp"):
            self.assertIn(absent, verify)
        self.assertIn("tests.test_posters", media_job)
        self.assertNotIn("manage.py test", media_job)  # the release image has no SQLite for the test runner
        self.assertIn("not result.skipped", media_job)
        self.assertLess(media_job.index("End-to-end media pipeline test"), media_job.index("Scan media image vulnerabilities"))

    def test_the_shared_image_job_proves_no_ffmpeg_and_the_media_job_proves_it_on_the_sandbox_path(self):
        shared_job = self.workflow[self.workflow.index("  image-build:"):self.workflow.index("  media-image-build:")]
        media_job = self.workflow[self.workflow.index("  media-image-build:"):self.workflow.index("  build-and-verify:")]
        self.assertIn("Verify the shared image carries no FFmpeg", shared_job)
        self.assertNotIn("WITH_FFMPEG", shared_job)
        self.assertNotIn("--build-arg", shared_job)
        self.assertIn("--build-arg WITH_FFMPEG=1", media_job)
        self.assertIn('--build-arg "PYTHON_BASE=$MEDIA_PYTHON_BASE"', media_job)
        self.assertIn("--target release", media_job)
        self.assertIn("Verify FFmpeg for the media worker on the sandbox PATH", media_job)
        self.assertIn("os.defpath", media_job)
        self.assertLess(media_job.index("Verify FFmpeg for the media worker"),
                        media_job.index("Scan media image vulnerabilities"))
        self.assertLess(media_job.index("Verify the media image has no SQLite"),
                        media_job.index("Scan media image vulnerabilities"))
        self.assertIn('"ffmpeg" not in names', media_job)

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
