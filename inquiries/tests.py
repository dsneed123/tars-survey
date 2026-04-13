from unittest.mock import patch

from django.test import Client, TestCase

from inquiries.forms import InquiryForm
from inquiries.models import Inquiry


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _valid_inquiry_data(**overrides):
    data = {
        "contact_name": "Jane Smith",
        "email": "jane@acmecorp.com",
        "company_name": "Acme Corp",
        "company_size": "2_10",
        "phone": "+1 555-000-0000",
        "industry": "SaaS",
        "project_description": "Build an automated code review pipeline.",
        "primary_language": "Python",
        "repo_url": "https://github.com/acme/repo",
        "budget_range": "5k_15k",
        "timeline": "1_3_months",
        "how_heard_about_us": "Twitter",
    }
    data.update(overrides)
    return data


def make_inquiry(**kwargs):
    defaults = {
        "contact_name": "Jane Smith",
        "email": "jane@acmecorp.com",
        "company_name": "Acme Corp",
        "company_size": "2_10",
        "industry": "SaaS",
        "project_description": "Build an automated code review pipeline.",
        "budget_range": "5k_15k",
        "timeline": "1_3_months",
        "how_heard_about_us": "Twitter",
    }
    defaults.update(kwargs)
    return Inquiry.objects.create(**defaults)


# ---------------------------------------------------------------------------
# Inquiry model
# ---------------------------------------------------------------------------

class InquiryModelTests(TestCase):
    def test_str_representation(self):
        inquiry = make_inquiry(company_name="Widgets Inc", contact_name="Bob")
        s = str(inquiry)
        self.assertIn("Widgets Inc", s)
        self.assertIn("Bob", s)

    def test_default_status_is_new(self):
        inquiry = make_inquiry()
        self.assertEqual(inquiry.status, "new")

    def test_created_at_auto_set(self):
        inquiry = make_inquiry()
        self.assertIsNotNone(inquiry.created_at)

    def test_ordering_newest_first(self):
        i1 = make_inquiry(company_name="First Co")
        i2 = make_inquiry(company_name="Second Co")
        inquiries = list(Inquiry.objects.all())
        self.assertEqual(inquiries[0].company_name, "Second Co")
        self.assertEqual(inquiries[1].company_name, "First Co")

    def test_phone_optional(self):
        inquiry = make_inquiry(phone="")
        self.assertEqual(inquiry.phone, "")

    def test_primary_language_optional(self):
        inquiry = make_inquiry(primary_language="")
        self.assertEqual(inquiry.primary_language, "")

    def test_repo_url_optional(self):
        inquiry = make_inquiry(repo_url="")
        self.assertEqual(inquiry.repo_url, "")

    def test_status_choices_include_all_stages(self):
        statuses = [k for k, _ in Inquiry.STATUS_CHOICES]
        for expected in ("new", "contacted", "qualified", "proposal_sent", "closed_won", "closed_lost"):
            self.assertIn(expected, statuses)

    def test_company_size_choices(self):
        sizes = [k for k, _ in Inquiry.COMPANY_SIZE_CHOICES]
        for expected in ("solo", "2_10", "11_50", "51_200", "200_plus"):
            self.assertIn(expected, sizes)

    def test_budget_range_choices(self):
        budgets = [k for k, _ in Inquiry.BUDGET_RANGE_CHOICES]
        for expected in ("under_5k", "5k_15k", "15k_50k", "50k_plus", "not_sure"):
            self.assertIn(expected, budgets)

    def test_timeline_choices(self):
        timelines = [k for k, _ in Inquiry.TIMELINE_CHOICES]
        for expected in ("asap", "1_3_months", "3_6_months", "flexible"):
            self.assertIn(expected, timelines)


# ---------------------------------------------------------------------------
# InquiryForm
# ---------------------------------------------------------------------------

class InquiryFormTests(TestCase):
    def test_valid_form(self):
        form = InquiryForm(data=_valid_inquiry_data())
        self.assertTrue(form.is_valid(), form.errors)

    def test_missing_required_contact_name(self):
        form = InquiryForm(data=_valid_inquiry_data(contact_name=""))
        self.assertFalse(form.is_valid())
        self.assertIn("contact_name", form.errors)

    def test_missing_required_email(self):
        form = InquiryForm(data=_valid_inquiry_data(email=""))
        self.assertFalse(form.is_valid())
        self.assertIn("email", form.errors)

    def test_invalid_email_format(self):
        form = InquiryForm(data=_valid_inquiry_data(email="not-an-email"))
        self.assertFalse(form.is_valid())
        self.assertIn("email", form.errors)

    def test_missing_required_company_name(self):
        form = InquiryForm(data=_valid_inquiry_data(company_name=""))
        self.assertFalse(form.is_valid())
        self.assertIn("company_name", form.errors)

    def test_missing_required_project_description(self):
        form = InquiryForm(data=_valid_inquiry_data(project_description=""))
        self.assertFalse(form.is_valid())
        self.assertIn("project_description", form.errors)

    def test_optional_phone_can_be_blank(self):
        form = InquiryForm(data=_valid_inquiry_data(phone=""))
        self.assertTrue(form.is_valid(), form.errors)

    def test_optional_primary_language_can_be_blank(self):
        form = InquiryForm(data=_valid_inquiry_data(primary_language=""))
        self.assertTrue(form.is_valid(), form.errors)

    def test_optional_repo_url_can_be_blank(self):
        form = InquiryForm(data=_valid_inquiry_data(repo_url=""))
        self.assertTrue(form.is_valid(), form.errors)

    def test_invalid_repo_url_rejected(self):
        form = InquiryForm(data=_valid_inquiry_data(repo_url="not-a-url"))
        self.assertFalse(form.is_valid())
        self.assertIn("repo_url", form.errors)

    def test_save_creates_inquiry_record(self):
        form = InquiryForm(data=_valid_inquiry_data())
        self.assertTrue(form.is_valid())
        inquiry = form.save()
        self.assertEqual(Inquiry.objects.count(), 1)
        self.assertEqual(inquiry.company_name, "Acme Corp")
        self.assertEqual(inquiry.email, "jane@acmecorp.com")

    def test_save_default_status_is_new(self):
        form = InquiryForm(data=_valid_inquiry_data())
        form.is_valid()
        inquiry = form.save()
        self.assertEqual(inquiry.status, "new")

    def test_invalid_company_size_rejected(self):
        form = InquiryForm(data=_valid_inquiry_data(company_size="invalid_size"))
        self.assertFalse(form.is_valid())
        self.assertIn("company_size", form.errors)

    def test_invalid_budget_range_rejected(self):
        form = InquiryForm(data=_valid_inquiry_data(budget_range="one_million"))
        self.assertFalse(form.is_valid())
        self.assertIn("budget_range", form.errors)

    def test_invalid_timeline_rejected(self):
        form = InquiryForm(data=_valid_inquiry_data(timeline="yesterday"))
        self.assertFalse(form.is_valid())
        self.assertIn("timeline", form.errors)


# ---------------------------------------------------------------------------
# GET /get-started/
# ---------------------------------------------------------------------------

class GetStartedViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.url = "/get-started/"

    def test_get_returns_200(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)

    def test_get_renders_form_in_context(self):
        resp = self.client.get(self.url)
        self.assertIn("form", resp.context)
        self.assertIsInstance(resp.context["form"], InquiryForm)

    def test_get_context_contains_recaptcha_site_key(self):
        resp = self.client.get(self.url)
        self.assertIn("recaptcha_site_key", resp.context)

    @patch("inquiries.views._send_inquiry_emails")
    def test_valid_post_creates_inquiry(self, _mock_email):
        resp = self.client.post(self.url, data=_valid_inquiry_data())
        self.assertEqual(Inquiry.objects.count(), 1)

    @patch("inquiries.views._send_inquiry_emails")
    def test_valid_post_redirects_to_thank_you(self, _mock_email):
        resp = self.client.post(self.url, data=_valid_inquiry_data())
        self.assertRedirects(resp, "/get-started/thank-you/", fetch_redirect_response=False)

    @patch("inquiries.views._send_inquiry_emails")
    def test_valid_post_sends_emails(self, mock_email):
        self.client.post(self.url, data=_valid_inquiry_data())
        self.assertTrue(mock_email.called)

    def test_invalid_post_stays_on_form(self):
        # Missing required fields
        resp = self.client.post(self.url, data={"contact_name": "", "email": ""})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(Inquiry.objects.count(), 0)

    def test_invalid_post_form_has_errors(self):
        resp = self.client.post(self.url, data={"contact_name": "", "email": "bad"})
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.context["form"].errors)

    @patch("inquiries.views._verify_recaptcha", return_value=False)
    @patch("inquiries.views._send_inquiry_emails")
    def test_failed_recaptcha_stays_on_form(self, _mock_email, _mock_captcha):
        resp = self.client.post(self.url, data=_valid_inquiry_data())
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(Inquiry.objects.count(), 0)

    @patch("inquiries.views._verify_recaptcha", return_value=True)
    @patch("inquiries.views._send_inquiry_emails")
    def test_valid_recaptcha_allows_submission(self, _mock_email, _mock_captcha):
        resp = self.client.post(self.url, data=_valid_inquiry_data())
        self.assertRedirects(resp, "/get-started/thank-you/", fetch_redirect_response=False)
        self.assertEqual(Inquiry.objects.count(), 1)


# ---------------------------------------------------------------------------
# GET /get-started/thank-you/
# ---------------------------------------------------------------------------

class ThankYouViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.url = "/get-started/thank-you/"

    def test_get_returns_200(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)

    def test_accessible_without_login(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)


# ---------------------------------------------------------------------------
# _verify_recaptcha utility
# ---------------------------------------------------------------------------

class VerifyRecaptchaTests(TestCase):
    def test_returns_true_when_no_secret_configured(self):
        from inquiries.views import _verify_recaptcha
        from django.test import override_settings
        with override_settings(RECAPTCHA_SECRET_KEY=""):
            result = _verify_recaptcha("some-token")
        self.assertTrue(result)

    def test_returns_true_on_network_error(self):
        """Fail-open: if reCAPTCHA service is unreachable, allow submission."""
        from inquiries.views import _verify_recaptcha
        from django.test import override_settings
        import urllib.request

        def raise_error(*args, **kwargs):
            raise Exception("network error")

        with override_settings(RECAPTCHA_SECRET_KEY="test-secret"):
            with patch.object(urllib.request, "urlopen", side_effect=raise_error):
                result = _verify_recaptcha("some-token")
        self.assertTrue(result)
