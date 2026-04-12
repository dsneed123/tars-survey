from django.conf import settings
from django.core import mail
from django.test import TestCase
from django.urls import reverse

from .models import Inquiry


class InquiryModelTests(TestCase):
    def test_str(self):
        inquiry = Inquiry(name='Alice', email='alice@example.com', subject='Hello', message='Hi')
        self.assertEqual(str(inquiry), 'Hello from Alice')


class InquiryFormViewTests(TestCase):
    def test_get_renders_form(self):
        response = self.client.get(reverse('inquiries:inquiry_form'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'inquiries/inquiry_form.html')

    def test_post_valid_creates_inquiry_and_redirects(self):
        data = {
            'name': 'Bob',
            'email': 'bob@example.com',
            'subject': 'Test subject',
            'message': 'Test message body.',
        }
        response = self.client.post(reverse('inquiries:inquiry_form'), data)
        self.assertRedirects(response, reverse('inquiries:inquiry_success'))
        self.assertEqual(Inquiry.objects.count(), 1)
        inquiry = Inquiry.objects.first()
        self.assertEqual(inquiry.name, 'Bob')
        self.assertEqual(inquiry.email, 'bob@example.com')

    def test_post_invalid_rerenders_form(self):
        response = self.client.post(reverse('inquiries:inquiry_form'), {})
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'inquiries/inquiry_form.html')
        self.assertEqual(Inquiry.objects.count(), 0)


class InquiryEmailTests(TestCase):
    def setUp(self):
        self.data = {
            'name': 'Carol',
            'email': 'carol@example.com',
            'subject': 'Email test',
            'message': 'Please check your email.',
        }

    def test_auto_reply_sent_to_inquirer(self):
        self.client.post(reverse('inquiries:inquiry_form'), self.data)
        auto_replies = [m for m in mail.outbox if 'carol@example.com' in m.to]
        self.assertEqual(len(auto_replies), 1)
        self.assertIn('received your inquiry', auto_replies[0].subject.lower())

    def test_admin_notification_sent_when_admin_email_set(self):
        with self.settings(ADMIN_EMAIL='admin@example.com'):
            self.client.post(reverse('inquiries:inquiry_form'), self.data)
        admin_mails = [m for m in mail.outbox if 'admin@example.com' in m.to]
        self.assertEqual(len(admin_mails), 1)
        self.assertIn('Email test', admin_mails[0].subject)

    def test_no_admin_notification_when_admin_email_empty(self):
        with self.settings(ADMIN_EMAIL=''):
            self.client.post(reverse('inquiries:inquiry_form'), self.data)
        admin_mails = [m for m in mail.outbox if 'admin@example.com' in m.to]
        self.assertEqual(len(admin_mails), 0)


class InquirySuccessViewTests(TestCase):
    def test_success_page_renders(self):
        response = self.client.get(reverse('inquiries:inquiry_success'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'inquiries/inquiry_success.html')
