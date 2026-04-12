from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import Inquiry


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    DEFAULT_FROM_EMAIL="TARS <noreply@tars.ai>",
    TARS_ADMIN_EMAIL="admin@tars.ai",
)
class InquiryViewTests(TestCase):
    def _post_inquiry(self, **overrides):
        data = {
            "name": "Jane Smith",
            "email": "jane@example.com",
            "company": "Acme Corp",
            "repo": "github.com/acme/repo",
            "team_size": "2-5",
            "use_case": "Automate bug fixes",
        }
        data.update(overrides)
        return self.client.post(reverse("pages:inquiry"), data)

    def test_get_inquiry_page(self):
        response = self.client.get(reverse("pages:inquiry"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "pages/inquiry.html")

    def test_valid_submission_creates_inquiry(self):
        self._post_inquiry()
        self.assertEqual(Inquiry.objects.count(), 1)
        inquiry = Inquiry.objects.first()
        self.assertEqual(inquiry.name, "Jane Smith")
        self.assertEqual(inquiry.email, "jane@example.com")

    def test_valid_submission_redirects_to_success(self):
        response = self._post_inquiry()
        self.assertRedirects(response, reverse("pages:inquiry_success"))

    def test_valid_submission_sends_two_emails(self):
        self._post_inquiry()
        self.assertEqual(len(mail.outbox), 2)

    def test_admin_notification_email(self):
        self._post_inquiry()
        admin_email = next(m for m in mail.outbox if "admin@tars.ai" in m.to)
        self.assertIn("Jane Smith", admin_email.body)
        self.assertIn("jane@example.com", admin_email.body)
        self.assertIn("Acme Corp", admin_email.body)

    def test_auto_reply_email(self):
        self._post_inquiry()
        auto_reply = next(m for m in mail.outbox if "jane@example.com" in m.to)
        self.assertIn("Jane Smith", auto_reply.body)
        self.assertEqual(auto_reply.subject, "We received your TARS early access request")

    def test_missing_name_shows_error(self):
        response = self._post_inquiry(name="")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Name and email are required")
        self.assertEqual(Inquiry.objects.count(), 0)
        self.assertEqual(len(mail.outbox), 0)

    def test_missing_email_shows_error(self):
        response = self._post_inquiry(email="")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Name and email are required")
        self.assertEqual(Inquiry.objects.count(), 0)

    def test_success_page(self):
        response = self.client.get(reverse("pages:inquiry_success"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "pages/inquiry_success.html")
