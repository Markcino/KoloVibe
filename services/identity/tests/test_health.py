from django.test import SimpleTestCase
from django.urls import reverse

class LivenessTests(SimpleTestCase):
    def test_alive(self):
        response = self.client.get(reverse("liveness"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_post_rejected(self):
        response = self.client.post(reverse("liveness"))
        self.assertEqual(response.status_code, 405)
