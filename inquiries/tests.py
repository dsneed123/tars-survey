from django.test import TestCase, Client
from django.urls import reverse
from .models import Inquiry


class InquiryFormViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.url = reverse('inquiries:form')

    def test_get_renders_form(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'inquiries/inquiry_form.html')

    def test_post_valid_saves_inquiry_and_redirects(self):
        data = {
            'name': 'Alice',
            'email': 'alice@example.com',
            'message': 'Hello from Alice',
        }
        response = self.client.post(self.url, data)
        self.assertRedirects(response, reverse('inquiries:success'))
        self.assertEqual(Inquiry.objects.count(), 1)
        inquiry = Inquiry.objects.get()
        self.assertEqual(inquiry.name, 'Alice')
        self.assertEqual(inquiry.email, 'alice@example.com')
        self.assertEqual(inquiry.message, 'Hello from Alice')

    def test_post_missing_required_field_does_not_save(self):
        data = {
            'name': '',
            'email': 'alice@example.com',
            'message': 'Hello',
        }
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Inquiry.objects.count(), 0)

    def test_post_invalid_email_does_not_save(self):
        data = {
            'name': 'Bob',
            'email': 'not-an-email',
            'message': 'Test message',
        }
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Inquiry.objects.count(), 0)


class InquirySuccessViewTests(TestCase):
    def setUp(self):
        self.client = Client()

    def test_success_page_returns_200(self):
        response = self.client.get(reverse('inquiries:success'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'inquiries/inquiry_success.html')


class HealthCheckTests(TestCase):
    def setUp(self):
        self.client = Client()

    def test_health_check_returns_200(self):
        response = self.client.get('/health/')
        self.assertEqual(response.status_code, 200)

    def test_health_check_returns_ok_status(self):
        import json
        response = self.client.get('/health/')
        data = json.loads(response.content)
        self.assertEqual(data['status'], 'ok')
