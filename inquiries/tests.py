import json

from django.test import TestCase, Client, override_settings
from django.urls import reverse

from .models import Inquiry


class InquiryModelTests(TestCase):
    def test_str(self):
        inquiry = Inquiry(name='Alice', email='alice@example.com', message='Hello')
        self.assertEqual(str(inquiry), 'Alice <alice@example.com>')

    def test_default_status_is_new(self):
        inquiry = Inquiry.objects.create(name='Bob', email='bob@example.com', message='Hi')
        self.assertEqual(inquiry.status, Inquiry.NEW)


class SubmitInquiryViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.url = reverse('inquiries:submit_inquiry')

    def _post(self, data):
        return self.client.post(
            self.url,
            data=json.dumps(data),
            content_type='application/json',
        )

    def test_valid_submission_returns_201(self):
        response = self._post({'name': 'Alice', 'email': 'alice@example.com', 'message': 'Hello'})
        self.assertEqual(response.status_code, 201)
        body = response.json()
        self.assertIn('id', body)
        self.assertEqual(body['status'], 'new')
        self.assertEqual(body['message'], 'Inquiry submitted successfully.')

    def test_valid_submission_creates_inquiry(self):
        self._post({'name': 'Alice', 'email': 'alice@example.com', 'message': 'Hello'})
        self.assertEqual(Inquiry.objects.count(), 1)
        inquiry = Inquiry.objects.first()
        self.assertEqual(inquiry.name, 'Alice')
        self.assertEqual(inquiry.email, 'alice@example.com')
        self.assertEqual(inquiry.message, 'Hello')

    def test_missing_name_returns_400(self):
        response = self._post({'email': 'alice@example.com', 'message': 'Hello'})
        self.assertEqual(response.status_code, 400)
        self.assertIn('name', response.json()['errors'])

    def test_missing_email_returns_400(self):
        response = self._post({'name': 'Alice', 'message': 'Hello'})
        self.assertEqual(response.status_code, 400)
        self.assertIn('email', response.json()['errors'])

    def test_invalid_email_returns_400(self):
        response = self._post({'name': 'Alice', 'email': 'not-an-email', 'message': 'Hello'})
        self.assertEqual(response.status_code, 400)
        self.assertIn('email', response.json()['errors'])

    def test_missing_message_returns_400(self):
        response = self._post({'name': 'Alice', 'email': 'alice@example.com'})
        self.assertEqual(response.status_code, 400)
        self.assertIn('message', response.json()['errors'])

    def test_invalid_json_returns_400(self):
        response = self.client.post(self.url, data='not json', content_type='application/json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('error', response.json())

    def test_cors_headers_on_post(self):
        response = self._post({'name': 'Alice', 'email': 'alice@example.com', 'message': 'Hello'})
        self.assertEqual(response['Access-Control-Allow-Origin'], '*')

    def test_options_preflight_returns_200(self):
        response = self.client.options(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Access-Control-Allow-Origin'], '*')
        self.assertIn('POST', response['Access-Control-Allow-Methods'])


@override_settings(TARS_API_KEY='test-secret-key')
class InquiryStatsViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.url = reverse('inquiries:inquiry_stats')

    def test_missing_api_key_returns_401(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 401)

    def test_wrong_api_key_returns_401(self):
        response = self.client.get(self.url, HTTP_X_API_KEY='wrong-key')
        self.assertEqual(response.status_code, 401)

    def test_valid_api_key_returns_200(self):
        response = self.client.get(self.url, HTTP_X_API_KEY='test-secret-key')
        self.assertEqual(response.status_code, 200)

    def test_stats_include_all_statuses(self):
        Inquiry.objects.create(name='A', email='a@example.com', message='m', status=Inquiry.NEW)
        Inquiry.objects.create(name='B', email='b@example.com', message='m', status=Inquiry.NEW)
        Inquiry.objects.create(name='C', email='c@example.com', message='m', status=Inquiry.CONTACTED)
        response = self.client.get(self.url, HTTP_X_API_KEY='test-secret-key')
        stats = response.json()['stats']
        self.assertEqual(stats['new'], 2)
        self.assertEqual(stats['contacted'], 1)
        self.assertEqual(stats['converted'], 0)
        self.assertEqual(stats['closed'], 0)

    def test_empty_stats_returns_zeros(self):
        response = self.client.get(self.url, HTTP_X_API_KEY='test-secret-key')
        stats = response.json()['stats']
        for status in ('new', 'contacted', 'converted', 'closed'):
            self.assertEqual(stats[status], 0)
