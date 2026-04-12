import json

from django.test import TestCase, override_settings
from django.urls import reverse

from .models import Inquiry

VALID_PAYLOAD = {
    "name": "Alice Tester",
    "email": "alice@example.com",
    "company": "Acme Corp",
    "github_repo": "https://github.com/acme/repo",
    "team_size": "1-5",
    "use_case": "Automate our CI/CD pipeline",
}


class SubmitInquiryTests(TestCase):
    url = "/api/inquiries/"

    def post(self, data):
        return self.client.post(
            self.url,
            data=json.dumps(data),
            content_type="application/json",
        )

    # --- success path ---

    def test_valid_submission_returns_201(self):
        response = self.post(VALID_PAYLOAD)
        self.assertEqual(response.status_code, 201)
        body = response.json()
        self.assertTrue(body["success"])
        self.assertIn("id", body)
        self.assertEqual(Inquiry.objects.count(), 1)

    def test_valid_submission_persists_fields(self):
        self.post(VALID_PAYLOAD)
        inquiry = Inquiry.objects.get()
        self.assertEqual(inquiry.name, "Alice Tester")
        self.assertEqual(inquiry.email, "alice@example.com")
        self.assertEqual(inquiry.company, "Acme Corp")
        self.assertEqual(inquiry.github_repo, "https://github.com/acme/repo")
        self.assertEqual(inquiry.team_size, "1-5")
        self.assertEqual(inquiry.use_case, "Automate our CI/CD pipeline")
        self.assertEqual(inquiry.status, Inquiry.STATUS_PENDING)

    def test_github_repo_optional(self):
        payload = {k: v for k, v in VALID_PAYLOAD.items() if k != "github_repo"}
        response = self.post(payload)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Inquiry.objects.get().github_repo, "")

    # --- validation errors ---

    def test_missing_required_field_returns_400(self):
        for field in ["name", "email", "company", "team_size", "use_case"]:
            payload = {k: v for k, v in VALID_PAYLOAD.items() if k != field}
            with self.subTest(missing=field):
                response = self.post(payload)
                self.assertEqual(response.status_code, 400)
                body = response.json()
                self.assertIn("error", body)
                self.assertIn(field, body.get("fields", []))

    def test_blank_required_field_returns_400(self):
        payload = {**VALID_PAYLOAD, "name": "   "}
        response = self.post(payload)
        self.assertEqual(response.status_code, 400)

    def test_invalid_email_returns_400(self):
        for bad_email in ["notanemail", "missing@dot", "@nodomain.com"]:
            with self.subTest(email=bad_email):
                response = self.post({**VALID_PAYLOAD, "email": bad_email})
                self.assertEqual(response.status_code, 400)

    def test_invalid_json_returns_400(self):
        response = self.client.post(
            self.url,
            data="not-json",
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_non_object_json_returns_400(self):
        response = self.client.post(
            self.url,
            data=json.dumps(["a", "list"]),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    # --- method enforcement ---

    def test_get_method_returns_405(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 405)

    # --- CORS headers ---

    def test_cors_headers_present_on_post(self):
        response = self.post(VALID_PAYLOAD)
        self.assertEqual(response["Access-Control-Allow-Origin"], "*")
        self.assertIn("Content-Type", response["Access-Control-Allow-Headers"])
        self.assertIn("POST", response["Access-Control-Allow-Methods"])

    def test_options_preflight_returns_cors_headers(self):
        response = self.client.options(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Access-Control-Allow-Origin"], "*")

    def test_cors_headers_present_on_error_response(self):
        payload = {**VALID_PAYLOAD, "name": ""}
        response = self.post(payload)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response["Access-Control-Allow-Origin"], "*")


@override_settings(TARS_API_KEY="test-secret-key")
class InquiryStatsTests(TestCase):
    url = "/api/inquiries/stats/"
    api_key = "test-secret-key"

    def _get(self, key=None):
        headers = {"HTTP_X_API_KEY": key} if key else {}
        return self.client.get(self.url, **headers)

    def test_valid_key_returns_200(self):
        response = self._get(self.api_key)
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertIn("stats", body)

    def test_stats_include_all_statuses(self):
        Inquiry.objects.create(**{**VALID_PAYLOAD, "status": Inquiry.STATUS_PENDING})
        Inquiry.objects.create(**{**VALID_PAYLOAD, "status": Inquiry.STATUS_APPROVED})
        response = self._get(self.api_key)
        stats = response.json()["stats"]
        for status, _ in Inquiry.STATUS_CHOICES:
            self.assertIn(status, stats)

    def test_stats_counts_are_accurate(self):
        Inquiry.objects.create(**{**VALID_PAYLOAD, "status": Inquiry.STATUS_PENDING})
        Inquiry.objects.create(**{**VALID_PAYLOAD, "status": Inquiry.STATUS_PENDING})
        Inquiry.objects.create(**{**VALID_PAYLOAD, "status": Inquiry.STATUS_APPROVED})
        response = self._get(self.api_key)
        stats = response.json()["stats"]
        self.assertEqual(stats["pending"], 2)
        self.assertEqual(stats["approved"], 1)
        self.assertEqual(stats["reviewed"], 0)
        self.assertEqual(stats["rejected"], 0)
        self.assertEqual(stats["total"], 3)

    def test_missing_api_key_returns_401(self):
        response = self._get()
        self.assertEqual(response.status_code, 401)

    def test_wrong_api_key_returns_401(self):
        response = self._get("wrong-key")
        self.assertEqual(response.status_code, 401)

    def test_post_method_returns_405(self):
        response = self.client.post(self.url, HTTP_X_API_KEY=self.api_key)
        self.assertEqual(response.status_code, 405)

    @override_settings(TARS_API_KEY="")
    def test_empty_api_key_setting_returns_401(self):
        response = self._get("")
        self.assertEqual(response.status_code, 401)
