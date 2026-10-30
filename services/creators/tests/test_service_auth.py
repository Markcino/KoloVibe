from django.test import SimpleTestCase, RequestFactory
from service.service_auth import ServiceAuthMiddleware

class InternalAuthenticationTests(SimpleTestCase):
    def setUp(self):
        self.middleware = ServiceAuthMiddleware(lambda request: None)
        self.factory = RequestFactory()
    def test_unsigned_internal_request_rejected(self):
        response = self.middleware(self.factory.get("/internal/probe"))
        self.assertEqual(response.status_code, 403)
    def test_spoofed_service_identity_rejected(self):
        req = self.factory.get("/internal/probe", HTTP_X_KOLOVIBE_CALLER="identity")
        self.assertEqual(self.middleware(req).status_code, 403)
    def test_public_health_path_not_blocked(self):
        self.assertIsNone(self.middleware(self.factory.get("/health/live")))
