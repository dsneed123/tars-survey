from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.utils import timezone

from analytics.models import Event, PageView
from analytics.utils import fire_event
from members.models import MemberProfile
from projects.models import Project
from tasks.models import Task

User = get_user_model()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_user(email="user@example.com", password="TestPass123!", **kwargs):
    username = kwargs.pop("username", email)
    user = User.objects.create_user(username=username, email=email, password=password, **kwargs)
    MemberProfile.objects.get_or_create(user=user)
    return user


def make_staff(email="staff@example.com", **kwargs):
    kwargs.setdefault("username", email)
    return make_user(email=email, is_staff=True, **kwargs)


def make_project(owner, **kwargs):
    defaults = {"name": "Test Project", "github_repo": "owner/repo"}
    defaults.update(kwargs)
    return Project.objects.create(owner=owner, **defaults)


def make_task(project, owner, **kwargs):
    defaults = {"title": "Do something", "description": "desc", "status": "pending", "priority": 50}
    defaults.update(kwargs)
    return Task.objects.create(project=project, created_by=owner, **defaults)


# ---------------------------------------------------------------------------
# GET /admin-dashboard/
# ---------------------------------------------------------------------------

class AnalyticsDashboardAccessTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.url = "/admin-dashboard/"

    def test_requires_login(self):
        resp = self.client.get(self.url)
        # Non-authenticated request should redirect to login
        self.assertNotEqual(resp.status_code, 200)

    def test_non_staff_user_denied(self):
        user = make_user()
        self.client.force_login(user)
        resp = self.client.get(self.url)
        self.assertNotEqual(resp.status_code, 200)

    def test_staff_user_gets_200(self):
        staff = make_staff()
        self.client.force_login(staff)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)


class AnalyticsDashboardContextTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.url = "/admin-dashboard/"
        self.staff = make_staff()
        self.client.force_login(self.staff)

    def test_total_users_in_context(self):
        resp = self.client.get(self.url)
        self.assertIn("total_users", resp.context)
        # At minimum the staff user exists
        self.assertGreaterEqual(resp.context["total_users"], 1)

    def test_active_projects_in_context(self):
        owner = make_user(email="proj@example.com", username="projowner")
        make_project(owner, is_active=True)
        resp = self.client.get(self.url)
        self.assertIn("active_projects", resp.context)
        self.assertGreaterEqual(resp.context["active_projects"], 1)

    def test_tasks_this_week_in_context(self):
        owner = make_user(email="tasks@example.com", username="taskowner")
        project = make_project(owner)
        make_task(project, owner)
        resp = self.client.get(self.url)
        self.assertIn("tasks_this_week", resp.context)
        self.assertGreaterEqual(resp.context["tasks_this_week"], 1)

    def test_completion_rate_none_when_no_tasks(self):
        resp = self.client.get(self.url)
        self.assertIn("completion_rate", resp.context)
        # No tasks → completion_rate is None
        if Task.objects.count() == 0:
            self.assertIsNone(resp.context["completion_rate"])

    def test_completion_rate_calculated_correctly(self):
        owner = make_user(email="rate@example.com", username="rateowner")
        project = make_project(owner)
        make_task(project, owner, status="completed")
        make_task(project, owner, status="completed")
        make_task(project, owner, status="pending")
        make_task(project, owner, status="pending")

        resp = self.client.get(self.url)
        self.assertEqual(resp.context["completion_rate"], 50)

    def test_chart_days_in_context(self):
        resp = self.client.get(self.url)
        self.assertIn("chart_days", resp.context)
        self.assertEqual(len(resp.context["chart_days"]), 30)

    def test_funnel_in_context(self):
        resp = self.client.get(self.url)
        self.assertIn("funnel", resp.context)
        funnel = resp.context["funnel"]
        labels = [s["label"] for s in funnel]
        self.assertIn("Visitors", labels)
        self.assertIn("Signups", labels)
        self.assertIn("Project Added", labels)
        self.assertIn("First Task", labels)

    def test_top_pages_in_context(self):
        PageView.objects.create(path="/", created_at=timezone.now())
        PageView.objects.create(path="/", created_at=timezone.now())
        PageView.objects.create(path="/pricing/", created_at=timezone.now())

        resp = self.client.get(self.url)
        self.assertIn("top_pages", resp.context)
        top_paths = [p["path"] for p in resp.context["top_pages"]]
        self.assertIn("/", top_paths)

    def test_worker_stats_in_context(self):
        resp = self.client.get(self.url)
        for key in ("worker_online", "worker_busy", "worker_offline", "worker_total"):
            self.assertIn(key, resp.context)

    def test_recent_signups_in_context(self):
        resp = self.client.get(self.url)
        self.assertIn("recent_signups", resp.context)
        self.assertIsInstance(resp.context["recent_signups"], list)

    def test_date_filter_accepted(self):
        resp = self.client.get(self.url, {"date_from": "2024-01-01", "date_to": "2024-12-31"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context["date_from"], "2024-01-01")
        self.assertEqual(resp.context["date_to"], "2024-12-31")

    def test_invalid_date_filter_falls_back_gracefully(self):
        # Invalid dates should not crash the view
        resp = self.client.get(self.url, {"date_from": "not-a-date", "date_to": "also-bad"})
        self.assertEqual(resp.status_code, 200)


# ---------------------------------------------------------------------------
# PageView and Event models (via middleware / utils)
# ---------------------------------------------------------------------------

class PageViewModelTests(TestCase):
    def test_create_anonymous_page_view(self):
        pv = PageView.objects.create(path="/pricing/")
        self.assertEqual(pv.path, "/pricing/")
        self.assertIsNone(pv.user)

    def test_create_user_page_view(self):
        user = make_user(email="pv@example.com", username="pvuser")
        pv = PageView.objects.create(path="/dashboard/", user=user)
        self.assertEqual(pv.user, user)

    def test_str_representation(self):
        pv = PageView.objects.create(path="/test/")
        self.assertIn("/test/", str(pv))


class EventModelTests(TestCase):
    def test_create_event(self):
        user = make_user(email="ev@example.com", username="evuser")
        event = Event.objects.create(name="signup_completed", user=user, metadata={"plan": "free"})
        self.assertEqual(event.name, "signup_completed")
        self.assertEqual(event.metadata["plan"], "free")

    def test_create_anonymous_event(self):
        event = Event.objects.create(name="page_visit")
        self.assertIsNone(event.user)

    def test_str_representation(self):
        event = Event.objects.create(name="test_event")
        self.assertIn("test_event", str(event))


# ---------------------------------------------------------------------------
# fire_event utility
# ---------------------------------------------------------------------------

class FireEventUtilTests(TestCase):
    def test_creates_event_record(self):
        fire_event("test_event")
        self.assertEqual(Event.objects.filter(name="test_event").count(), 1)

    def test_creates_event_with_user(self):
        user = make_user(email="ev@example.com", username="evfn")
        fire_event("user_event", user=user)
        event = Event.objects.get(name="user_event")
        self.assertEqual(event.user, user)

    def test_creates_event_with_metadata(self):
        fire_event("meta_event", metadata={"plan": "pro", "source": "signup"})
        event = Event.objects.get(name="meta_event")
        self.assertEqual(event.metadata["plan"], "pro")
        self.assertEqual(event.metadata["source"], "signup")

    def test_metadata_defaults_to_empty_dict_when_none(self):
        fire_event("no_meta_event")
        event = Event.objects.get(name="no_meta_event")
        self.assertEqual(event.metadata, {})

    def test_does_not_raise_on_exception(self):
        # Passing None name should not propagate an exception
        try:
            fire_event(None)
        except Exception:
            self.fail("fire_event raised an exception unexpectedly")


# ---------------------------------------------------------------------------
# Health check endpoint
# ---------------------------------------------------------------------------

class HealthCheckTests(TestCase):
    def setUp(self):
        self.client = Client()

    def test_health_returns_200(self):
        resp = self.client.get("/health/")
        self.assertEqual(resp.status_code, 200)

    def test_health_returns_json_status_ok(self):
        resp = self.client.get("/health/")
        self.assertEqual(resp["Content-Type"], "application/json")
        data = resp.json()
        self.assertEqual(data["status"], "ok")

    def test_health_accessible_without_login(self):
        # Health check must be publicly accessible for Railway uptime monitoring
        resp = self.client.get("/health/")
        self.assertEqual(resp.status_code, 200)
