from django.test import TestCase
from django.urls import reverse

from .models import InquirySubmission


class LandingPageTests(TestCase):
    def test_landing_page_returns_200(self):
        response = self.client.get(reverse("pages:landing"))
        self.assertEqual(response.status_code, 200)

    def test_landing_page_uses_correct_template(self):
        response = self.client.get(reverse("pages:landing"))
        self.assertTemplateUsed(response, "pages/landing.html")
        self.assertTemplateUsed(response, "base.html")

    def test_landing_page_contains_cta(self):
        response = self.client.get(reverse("pages:landing"))
        self.assertContains(response, "Get Started")


class InquiryFormTests(TestCase):
    def test_inquiry_page_returns_200(self):
        response = self.client.get(reverse("pages:inquiry"))
        self.assertEqual(response.status_code, 200)

    def test_inquiry_page_uses_correct_template(self):
        response = self.client.get(reverse("pages:inquiry"))
        self.assertTemplateUsed(response, "pages/inquiry.html")

    def test_inquiry_form_submission_creates_record(self):
        data = {
            "name": "Jane Smith",
            "email": "jane@example.com",
            "company": "Acme Corp",
            "repo": "github.com/acme/app",
            "team_size": "2–5 engineers",
            "use_case": "Automate bug fixes and feature development.",
        }
        response = self.client.post(reverse("pages:inquiry"), data)
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse("pages:inquiry_success"))
        self.assertEqual(InquirySubmission.objects.count(), 1)
        submission = InquirySubmission.objects.first()
        self.assertEqual(submission.name, "Jane Smith")
        self.assertEqual(submission.email, "jane@example.com")
        self.assertEqual(submission.company, "Acme Corp")

    def test_inquiry_form_submission_with_minimal_data(self):
        data = {
            "name": "Solo Dev",
            "email": "solo@example.com",
        }
        response = self.client.post(reverse("pages:inquiry"), data)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(InquirySubmission.objects.count(), 1)

    def test_inquiry_success_page_returns_200(self):
        response = self.client.get(reverse("pages:inquiry_success"))
        self.assertEqual(response.status_code, 200)


class HealthCheckTests(TestCase):
    def test_health_check_returns_200(self):
        response = self.client.get(reverse("pages:health"))
        self.assertEqual(response.status_code, 200)

    def test_health_check_returns_ok_status(self):
        response = self.client.get(reverse("pages:health"))
        data = response.json()
        self.assertEqual(data["status"], "ok")

    def test_health_check_content_type(self):
        response = self.client.get(reverse("pages:health"))
        self.assertEqual(response["Content-Type"], "application/json")
