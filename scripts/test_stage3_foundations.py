"""Static regression gates for foundation and demo removal."""
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SERVICES=("gateway","identity","creators","content","engagement","points","moderation","audit")
class FoundationTests(unittest.TestCase):
    def test_authenticated_services(self):
        for svc in SERVICES:
            text=(ROOT/"services"/svc/"service"/"settings.py").read_text()
            self.assertIn("service.service_auth.ServiceAuthMiddleware", text)
            self.assertIn("verify-full", text)
            self.assertIn("search_path="+svc, text)
    def test_dhi_private_broker(self):
        stack=(ROOT/"infra/rabbitmq/stack.yml").read_text()
        config=(ROOT/"infra/rabbitmq/rabbitmq.conf").read_text()
        self.assertIn("RABBITMQ_DHI_IMAGE", stack)
        self.assertNotIn("ports:",stack)
        self.assertIn("listeners.tcp = none",config)
    def test_no_demo_files(self):
        self.assertFalse((ROOT/"apps/mobile/lib/main_demo.dart").exists())
        self.assertFalse((ROOT/"apps/mobile/lib/demo/demo_repository.dart").exists())
if __name__=="__main__":
    unittest.main()
