from django.test import TestCase
from django.urls import reverse


class LandingPageTest(TestCase):
    def test_landing_page_status(self):
        response = self.client.get(reverse('pages:landing'))
        self.assertEqual(response.status_code, 200)

    def test_landing_page_uses_correct_template(self):
        response = self.client.get(reverse('pages:landing'))
        self.assertTemplateUsed(response, 'pages/landing.html')
