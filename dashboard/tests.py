from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta

from inquiries.models import Inquiry, InquiryNote


class DashboardAuthTests(TestCase):
    def setUp(self):
        self.client = Client()

    def test_home_redirects_when_not_logged_in(self):
        response = self.client.get(reverse('dashboard:home'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/admin/login/', response['Location'])

    def test_inquiry_detail_redirects_when_not_logged_in(self):
        inquiry = Inquiry.objects.create(name='Test', email='t@t.com', message='hi')
        response = self.client.get(reverse('dashboard:inquiry_detail', args=[inquiry.pk]))
        self.assertEqual(response.status_code, 302)

    def test_add_note_redirects_when_not_logged_in(self):
        inquiry = Inquiry.objects.create(name='Test', email='t@t.com', message='hi')
        response = self.client.post(reverse('dashboard:add_note', args=[inquiry.pk]), {'note': 'x'})
        self.assertEqual(response.status_code, 302)

    def test_change_status_redirects_when_not_logged_in(self):
        inquiry = Inquiry.objects.create(name='Test', email='t@t.com', message='hi')
        response = self.client.post(
            reverse('dashboard:change_status', args=[inquiry.pk]), {'status': 'contacted'}
        )
        self.assertEqual(response.status_code, 302)


class DashboardHomeTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_superuser('admin', 'admin@example.com', 'password')
        self.client.login(username='admin', password='password')

    def test_home_returns_200(self):
        response = self.client.get(reverse('dashboard:home'))
        self.assertEqual(response.status_code, 200)

    def test_home_uses_correct_template(self):
        response = self.client.get(reverse('dashboard:home'))
        self.assertTemplateUsed(response, 'dashboard/dashboard.html')
        self.assertTemplateUsed(response, 'dashboard/base.html')

    def test_summary_totals_correct(self):
        Inquiry.objects.create(name='A', email='a@a.com', message='m1', status='won')
        Inquiry.objects.create(name='B', email='b@b.com', message='m2', status='lost')
        Inquiry.objects.create(name='C', email='c@c.com', message='m3', status='new')
        response = self.client.get(reverse('dashboard:home'))
        self.assertEqual(response.context['total'], 3)

    def test_new_this_week_count(self):
        Inquiry.objects.create(name='Recent', email='r@r.com', message='new')
        # Create an old inquiry by overriding created_at via update
        old = Inquiry.objects.create(name='Old', email='o@o.com', message='old')
        Inquiry.objects.filter(pk=old.pk).update(
            created_at=timezone.now() - timedelta(days=10)
        )
        response = self.client.get(reverse('dashboard:home'))
        self.assertEqual(response.context['new_this_week'], 1)

    def test_conversion_rate_with_no_won_lost(self):
        Inquiry.objects.create(name='A', email='a@a.com', message='m', status='new')
        response = self.client.get(reverse('dashboard:home'))
        self.assertEqual(response.context['conversion_rate'], 0)

    def test_conversion_rate_calculation(self):
        Inquiry.objects.create(name='W1', email='w1@a.com', message='m', status='won')
        Inquiry.objects.create(name='W2', email='w2@a.com', message='m', status='won')
        Inquiry.objects.create(name='L1', email='l1@a.com', message='m', status='lost')
        response = self.client.get(reverse('dashboard:home'))
        # 2 won / 3 total closed = 67%
        self.assertEqual(response.context['conversion_rate'], 67)

    def test_pipeline_has_six_stages(self):
        response = self.client.get(reverse('dashboard:home'))
        self.assertEqual(len(response.context['pipeline']), 6)

    def test_pipeline_stage_labels(self):
        response = self.client.get(reverse('dashboard:home'))
        labels = [col['label'] for col in response.context['pipeline']]
        self.assertIn('New', labels)
        self.assertIn('Contacted', labels)
        self.assertIn('Won', labels)
        self.assertIn('Lost', labels)

    def test_pipeline_shows_inquiry_in_correct_column(self):
        Inquiry.objects.create(name='Pipeline Test', email='p@p.com', message='m', status='qualified')
        response = self.client.get(reverse('dashboard:home'))
        qualified_col = next(c for c in response.context['pipeline'] if c['status'] == 'qualified')
        self.assertEqual(qualified_col['count'], 1)
        self.assertEqual(qualified_col['inquiries'][0].name, 'Pipeline Test')

    def test_avg_response_display_no_data(self):
        response = self.client.get(reverse('dashboard:home'))
        self.assertEqual(response.context['avg_response_display'], 'N/A')


class InquiryDetailViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_superuser('admin', 'admin@example.com', 'password')
        self.client.login(username='admin', password='password')
        self.inquiry = Inquiry.objects.create(
            name='Jane Doe',
            email='jane@example.com',
            phone='555-1234',
            company='Acme Corp',
            message='Interested in your services.',
            status='new',
        )

    def test_detail_returns_200(self):
        response = self.client.get(reverse('dashboard:inquiry_detail', args=[self.inquiry.pk]))
        self.assertEqual(response.status_code, 200)

    def test_detail_uses_correct_template(self):
        response = self.client.get(reverse('dashboard:inquiry_detail', args=[self.inquiry.pk]))
        self.assertTemplateUsed(response, 'dashboard/inquiry_detail.html')

    def test_detail_shows_inquiry_info(self):
        response = self.client.get(reverse('dashboard:inquiry_detail', args=[self.inquiry.pk]))
        self.assertContains(response, 'Jane Doe')
        self.assertContains(response, 'jane@example.com')
        self.assertContains(response, 'Acme Corp')
        self.assertContains(response, 'Interested in your services.')

    def test_detail_404_for_missing_inquiry(self):
        response = self.client.get(reverse('dashboard:inquiry_detail', args=[99999]))
        self.assertEqual(response.status_code, 404)

    def test_detail_shows_notes(self):
        InquiryNote.objects.create(inquiry=self.inquiry, note='Called and left voicemail.')
        response = self.client.get(reverse('dashboard:inquiry_detail', args=[self.inquiry.pk]))
        self.assertContains(response, 'Called and left voicemail.')

    def test_detail_shows_no_notes_message(self):
        response = self.client.get(reverse('dashboard:inquiry_detail', args=[self.inquiry.pk]))
        self.assertContains(response, 'No notes yet.')

    def test_detail_context_has_statuses(self):
        response = self.client.get(reverse('dashboard:inquiry_detail', args=[self.inquiry.pk]))
        self.assertIn('statuses', response.context)
        self.assertEqual(len(response.context['statuses']), 6)


class AddNoteTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_superuser('admin', 'admin@example.com', 'password')
        self.client.login(username='admin', password='password')
        self.inquiry = Inquiry.objects.create(name='Test', email='t@t.com', message='hi')

    def test_add_note_creates_note(self):
        self.client.post(
            reverse('dashboard:add_note', args=[self.inquiry.pk]),
            {'note': 'Follow-up scheduled.'},
        )
        self.assertEqual(InquiryNote.objects.filter(inquiry=self.inquiry).count(), 1)
        self.assertEqual(InquiryNote.objects.get(inquiry=self.inquiry).note, 'Follow-up scheduled.')

    def test_add_note_redirects_to_detail(self):
        response = self.client.post(
            reverse('dashboard:add_note', args=[self.inquiry.pk]),
            {'note': 'Some note'},
        )
        self.assertRedirects(response, reverse('dashboard:inquiry_detail', args=[self.inquiry.pk]))

    def test_add_empty_note_does_not_create(self):
        self.client.post(reverse('dashboard:add_note', args=[self.inquiry.pk]), {'note': '   '})
        self.assertEqual(InquiryNote.objects.filter(inquiry=self.inquiry).count(), 0)

    def test_add_note_get_redirects(self):
        # GET requests should just redirect (no note created)
        response = self.client.get(reverse('dashboard:add_note', args=[self.inquiry.pk]))
        self.assertRedirects(response, reverse('dashboard:inquiry_detail', args=[self.inquiry.pk]))


class ChangeStatusTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_superuser('admin', 'admin@example.com', 'password')
        self.client.login(username='admin', password='password')
        self.inquiry = Inquiry.objects.create(name='Test', email='t@t.com', message='hi', status='new')

    def test_change_status_updates_status(self):
        self.client.post(
            reverse('dashboard:change_status', args=[self.inquiry.pk]),
            {'status': 'qualified'},
        )
        self.inquiry.refresh_from_db()
        self.assertEqual(self.inquiry.status, 'qualified')

    def test_change_status_redirects_to_detail(self):
        response = self.client.post(
            reverse('dashboard:change_status', args=[self.inquiry.pk]),
            {'status': 'won'},
        )
        self.assertRedirects(response, reverse('dashboard:inquiry_detail', args=[self.inquiry.pk]))

    def test_change_status_to_contacted_sets_contacted_at(self):
        self.assertIsNone(self.inquiry.contacted_at)
        self.client.post(
            reverse('dashboard:change_status', args=[self.inquiry.pk]),
            {'status': 'contacted'},
        )
        self.inquiry.refresh_from_db()
        self.assertIsNotNone(self.inquiry.contacted_at)

    def test_contacted_at_not_overwritten_on_second_contact_change(self):
        first_contact = timezone.now() - timedelta(hours=2)
        self.inquiry.status = 'contacted'
        self.inquiry.contacted_at = first_contact
        self.inquiry.save()
        # Change back to new then contacted again
        self.client.post(
            reverse('dashboard:change_status', args=[self.inquiry.pk]),
            {'status': 'new'},
        )
        self.client.post(
            reverse('dashboard:change_status', args=[self.inquiry.pk]),
            {'status': 'contacted'},
        )
        self.inquiry.refresh_from_db()
        # contacted_at should still be the original first_contact
        self.assertEqual(
            self.inquiry.contacted_at.replace(microsecond=0),
            first_contact.replace(microsecond=0),
        )

    def test_invalid_status_does_not_update(self):
        self.client.post(
            reverse('dashboard:change_status', args=[self.inquiry.pk]),
            {'status': 'invalid_status'},
        )
        self.inquiry.refresh_from_db()
        self.assertEqual(self.inquiry.status, 'new')
