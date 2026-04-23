from django.test import Client, TestCase


class HealthViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.url = "/health/"

    def test_returns_200(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)

    def test_returns_json_content_type(self):
        resp = self.client.get(self.url)
        self.assertIn("application/json", resp["Content-Type"])

    def test_status_is_ok(self):
        resp = self.client.get(self.url)
        data = resp.json()
        self.assertEqual(data, {"status": "ok"})

    def test_no_authentication_required(self):
        # Health check must be accessible without login
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)

    def test_returns_consistent_response_on_repeated_calls(self):
        for _ in range(3):
            resp = self.client.get(self.url)
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(resp.json()["status"], "ok")
