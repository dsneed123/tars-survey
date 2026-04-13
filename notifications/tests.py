from django.contrib.auth import get_user_model
from django.test import Client, TestCase

from members.models import MemberProfile
from notifications.models import Notification, NotificationPreference

User = get_user_model()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_user(email="user@example.com", password="TestPass123!", **kwargs):
    username = kwargs.pop("username", email)
    user = User.objects.create_user(username=username, email=email, password=password, **kwargs)
    MemberProfile.objects.get_or_create(user=user)
    return user


def make_notification(user, **kwargs):
    defaults = {
        "title": "Task completed",
        "message": "Your task finished successfully.",
        "is_read": False,
    }
    defaults.update(kwargs)
    return Notification.objects.create(user=user, **defaults)


# ---------------------------------------------------------------------------
# Notification model
# ---------------------------------------------------------------------------

class NotificationModelTests(TestCase):
    def test_str_representation(self):
        user = make_user(email="notif@example.com", username="notifuser")
        n = make_notification(user, title="Hello")
        self.assertIn("Hello", str(n))

    def test_default_is_read_false(self):
        user = make_user(email="read@example.com", username="readuser")
        n = make_notification(user)
        self.assertFalse(n.is_read)

    def test_ordering_newest_first(self):
        user = make_user(email="order@example.com", username="orderuser")
        n1 = make_notification(user, title="First")
        n2 = make_notification(user, title="Second")
        notifications = list(Notification.objects.filter(user=user))
        self.assertEqual(notifications[0].title, "Second")
        self.assertEqual(notifications[1].title, "First")

    def test_optional_link_field(self):
        user = make_user(email="link@example.com", username="linkuser")
        n = make_notification(user, link="/dashboard/tasks/1/")
        self.assertEqual(n.link, "/dashboard/tasks/1/")

    def test_blank_link_allowed(self):
        user = make_user(email="nolink@example.com", username="nolinkuser")
        n = make_notification(user, link="")
        self.assertEqual(n.link, "")


# ---------------------------------------------------------------------------
# NotificationPreference model
# ---------------------------------------------------------------------------

class NotificationPreferenceModelTests(TestCase):
    def test_str_representation(self):
        user = make_user(email="prefs@example.com", username="prefsuser")
        prefs = NotificationPreference.objects.create(user=user)
        self.assertIn("prefs@example.com", str(prefs))

    def test_all_email_prefs_default_true(self):
        user = make_user(email="defaults@example.com", username="defaultsuser")
        prefs = NotificationPreference.objects.create(user=user)
        self.assertTrue(prefs.email_welcome)
        self.assertTrue(prefs.email_task_started)
        self.assertTrue(prefs.email_pr_ready)
        self.assertTrue(prefs.email_task_failed)
        self.assertTrue(prefs.email_weekly_digest)

    def test_can_disable_preferences(self):
        user = make_user(email="disable@example.com", username="disableuser")
        prefs = NotificationPreference.objects.create(
            user=user,
            email_welcome=False,
            email_task_failed=False,
        )
        self.assertFalse(prefs.email_welcome)
        self.assertFalse(prefs.email_task_failed)


# ---------------------------------------------------------------------------
# GET/POST /dashboard/settings/notifications/
# ---------------------------------------------------------------------------

class NotificationPreferencesViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.url = "/dashboard/settings/notifications/"
        self.user = make_user()

    def test_requires_login(self):
        resp = self.client.get(self.url)
        self.assertRedirects(resp, f"/login/?next={self.url}", fetch_redirect_response=False)

    def test_get_returns_200(self):
        self.client.force_login(self.user)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)

    def test_get_creates_prefs_if_missing(self):
        self.client.force_login(self.user)
        self.client.get(self.url)
        self.assertTrue(NotificationPreference.objects.filter(user=self.user).exists())

    def test_context_contains_prefs(self):
        self.client.force_login(self.user)
        resp = self.client.get(self.url)
        self.assertIn("prefs", resp.context)

    def test_post_updates_preferences_all_on(self):
        self.client.force_login(self.user)
        resp = self.client.post(self.url, {
            "email_welcome": "on",
            "email_task_started": "on",
            "email_pr_ready": "on",
            "email_task_failed": "on",
            "email_weekly_digest": "on",
        })
        self.assertRedirects(resp, self.url, fetch_redirect_response=False)
        prefs = NotificationPreference.objects.get(user=self.user)
        self.assertTrue(prefs.email_welcome)
        self.assertTrue(prefs.email_task_started)

    def test_post_updates_preferences_all_off(self):
        NotificationPreference.objects.create(user=self.user)
        self.client.force_login(self.user)
        resp = self.client.post(self.url, {})  # no checkboxes = all False
        self.assertRedirects(resp, self.url, fetch_redirect_response=False)
        prefs = NotificationPreference.objects.get(user=self.user)
        self.assertFalse(prefs.email_welcome)
        self.assertFalse(prefs.email_task_started)
        self.assertFalse(prefs.email_pr_ready)
        self.assertFalse(prefs.email_task_failed)
        self.assertFalse(prefs.email_weekly_digest)

    def test_post_partial_preferences(self):
        NotificationPreference.objects.create(user=self.user)
        self.client.force_login(self.user)
        self.client.post(self.url, {"email_welcome": "on", "email_task_failed": "on"})
        prefs = NotificationPreference.objects.get(user=self.user)
        self.assertTrue(prefs.email_welcome)
        self.assertFalse(prefs.email_task_started)
        self.assertTrue(prefs.email_task_failed)


# ---------------------------------------------------------------------------
# POST /dashboard/notifications/<pk>/read/
# ---------------------------------------------------------------------------

class MarkReadViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = make_user()
        self.notification = make_notification(self.user)
        self.url = f"/dashboard/notifications/{self.notification.pk}/read/"

    def test_requires_login(self):
        resp = self.client.post(self.url)
        self.assertRedirects(resp, f"/login/?next={self.url}", fetch_redirect_response=False)

    def test_get_not_allowed(self):
        self.client.force_login(self.user)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 405)

    def test_marks_own_notification_read(self):
        self.client.force_login(self.user)
        resp = self.client.post(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {"ok": True})
        self.notification.refresh_from_db()
        self.assertTrue(self.notification.is_read)

    def test_cannot_mark_other_users_notification(self):
        other = make_user(email="other@example.com", username="other")
        self.client.force_login(other)
        resp = self.client.post(self.url)
        self.assertEqual(resp.status_code, 200)
        # The update is a no-op (filter by user) so notification stays unread
        self.notification.refresh_from_db()
        self.assertFalse(self.notification.is_read)


# ---------------------------------------------------------------------------
# POST /dashboard/notifications/mark-all-read/
# ---------------------------------------------------------------------------

class MarkAllReadViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.url = "/dashboard/notifications/mark-all-read/"
        self.user = make_user()

    def test_requires_login(self):
        resp = self.client.post(self.url)
        self.assertRedirects(resp, f"/login/?next={self.url}", fetch_redirect_response=False)

    def test_get_not_allowed(self):
        self.client.force_login(self.user)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 405)

    def test_marks_all_unread_notifications_read(self):
        n1 = make_notification(self.user, title="One")
        n2 = make_notification(self.user, title="Two")

        self.client.force_login(self.user)
        resp = self.client.post(self.url)
        self.assertEqual(resp.json(), {"ok": True})

        n1.refresh_from_db()
        n2.refresh_from_db()
        self.assertTrue(n1.is_read)
        self.assertTrue(n2.is_read)

    def test_does_not_affect_other_users(self):
        other = make_user(email="other@example.com", username="other")
        other_notif = make_notification(other, title="Other's")

        self.client.force_login(self.user)
        self.client.post(self.url)

        other_notif.refresh_from_db()
        self.assertFalse(other_notif.is_read)

    def test_already_read_stays_read(self):
        n = make_notification(self.user, is_read=True)
        self.client.force_login(self.user)
        self.client.post(self.url)
        n.refresh_from_db()
        self.assertTrue(n.is_read)
