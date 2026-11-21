import os
import subprocess
import sys
from unittest.mock import patch
from urllib.request import ProxyHandler

from django.conf import settings
from django.test import SimpleTestCase
from django.urls import reverse


class WebJourneys(SimpleTestCase):
    def test_liveness_does_not_depend_on_gateway(self):
        response = self.client.get(reverse("web-liveness"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_staging_refuses_missing_secret_mount(self):
        environment = dict(os.environ,
                           KOLOVIBE_ENV="staging", KOLOVIBE_GATEWAY_URL="http://127.0.0.1")
        environment.pop("KOLOVIBE_WEB_SECRET_KEY_FILE", None)
        result = subprocess.run([sys.executable, "-c", "import web.settings"],
                                cwd=settings.BASE_DIR, env=environment,
                                capture_output=True, text=True, check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Staging web requires its fixed secret mount", result.stderr)

    def test_gateway_request_uses_fixed_host_without_environment_proxy(self):
        from web.views import _NoRedirect, _api

        with patch("web.views.build_opener") as opener, \
             self.settings(GATEWAY_URL="http://127.0.0.1", GATEWAY_HOST="mobile-api.cabetechs.shop"):
            response = opener.return_value.open.return_value.__enter__.return_value
            response.status = 200
            response.read.return_value = b"{}"
            self.assertEqual(_api("/moderation/videos"), (200, {}))
        self.assertIsInstance(opener.call_args.args[0], ProxyHandler)
        self.assertEqual(opener.call_args.args[0].proxies, {})
        self.assertIsInstance(opener.call_args.args[1], _NoRedirect)
        request = opener.return_value.open.call_args.args[0]
        self.assertEqual(request.get_header("Host"), "mobile-api.cabetechs.shop")
        self.assertEqual(request.full_url, "http://127.0.0.1/api/v1/moderation/videos")
