from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase

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


def make_project(owner, **kwargs):
    defaults = {
        "name": "Test Project",
        "github_repo": "owner/repo",
        "default_branch": "main",
    }
    defaults.update(kwargs)
    return Project.objects.create(owner=owner, **defaults)


def make_task(project, owner, **kwargs):
    defaults = {
        "title": "Fix the bug",
        "description": "Detailed description.",
        "status": "pending",
        "priority": 50,
    }
    defaults.update(kwargs)
    return Task.objects.create(project=project, created_by=owner, **defaults)


# ---------------------------------------------------------------------------
# GET /dashboard/
# ---------------------------------------------------------------------------

class DashboardViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.url = "/dashboard/"
        self.user = make_user()

    def test_requires_login(self):
        resp = self.client.get(self.url)
        self.assertRedirects(resp, f"/login/?next={self.url}", fetch_redirect_response=False)

    def test_returns_200_for_logged_in_user(self):
        self.client.force_login(self.user)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)

    def test_context_contains_profile(self):
        self.client.force_login(self.user)
        resp = self.client.get(self.url)
        self.assertIn("profile", resp.context)
        self.assertEqual(resp.context["profile"].user, self.user)

    def test_context_contains_projects(self):
        self.client.force_login(self.user)
        resp = self.client.get(self.url)
        self.assertIn("projects", resp.context)

    def test_context_contains_recent_tasks(self):
        self.client.force_login(self.user)
        resp = self.client.get(self.url)
        self.assertIn("recent_tasks", resp.context)

    def test_context_contains_stats(self):
        self.client.force_login(self.user)
        resp = self.client.get(self.url)
        for key in ("completed_count", "tasks_this_month", "success_rate", "success_rate_display"):
            self.assertIn(key, resp.context)

    def test_success_rate_zero_when_no_tasks(self):
        self.client.force_login(self.user)
        resp = self.client.get(self.url)
        self.assertEqual(resp.context["success_rate"], 0)
        self.assertEqual(resp.context["success_rate_display"], "—")

    def test_success_rate_calculated_with_tasks(self):
        project = make_project(self.user)
        make_task(project, self.user, status="completed")
        make_task(project, self.user, status="failed")

        self.client.force_login(self.user)
        resp = self.client.get(self.url)
        self.assertEqual(resp.context["success_rate"], 50)
        self.assertIn("%", resp.context["success_rate_display"])

    def test_only_shows_own_projects(self):
        make_project(self.user, name="Mine")
        other = make_user(email="other@example.com", username="other")
        make_project(other, name="Theirs", github_repo="other/repo")

        self.client.force_login(self.user)
        resp = self.client.get(self.url)
        project_names = [p.name for p in resp.context["projects"]]
        self.assertIn("Mine", project_names)
        self.assertNotIn("Theirs", project_names)

    def test_creates_profile_if_missing(self):
        user = User.objects.create_user(
            username="noprofile@example.com",
            email="noprofile@example.com",
            password="TestPass123!",
        )
        # Ensure no profile exists
        MemberProfile.objects.filter(user=user).delete()

        self.client.force_login(user)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(MemberProfile.objects.filter(user=user).exists())


# ---------------------------------------------------------------------------
# POST /dashboard/quick-task/
# ---------------------------------------------------------------------------

class QuickAddTaskViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.url = "/dashboard/quick-task/"
        self.user = make_user()
        self.project = make_project(self.user)

    def test_requires_login(self):
        resp = self.client.post(self.url, {"title": "Task", "project_id": self.project.pk})
        self.assertRedirects(resp, f"/login/?next={self.url}", fetch_redirect_response=False)

    def test_get_not_allowed(self):
        self.client.force_login(self.user)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 405)

    @patch("members.views._forward_to_controller")
    def test_creates_task_and_redirects(self, _mock):
        self.client.force_login(self.user)
        resp = self.client.post(self.url, {
            "title": "Quick task",
            "description": "Details here.",
            "project_id": self.project.pk,
        })
        self.assertEqual(Task.objects.count(), 1)
        task = Task.objects.get()
        self.assertEqual(task.title, "Quick task")
        self.assertEqual(task.project, self.project)
        self.assertEqual(task.created_by, self.user)
        self.assertRedirects(resp, "/dashboard/", fetch_redirect_response=False)

    @patch("members.views._forward_to_controller")
    def test_missing_title_redirects_with_error(self, _mock):
        self.client.force_login(self.user)
        resp = self.client.post(self.url, {
            "title": "",
            "project_id": self.project.pk,
        })
        self.assertEqual(Task.objects.count(), 0)
        self.assertRedirects(resp, "/dashboard/", fetch_redirect_response=False)

    @patch("members.views._forward_to_controller")
    def test_missing_project_redirects_with_error(self, _mock):
        self.client.force_login(self.user)
        resp = self.client.post(self.url, {
            "title": "Task",
            "project_id": "",
        })
        self.assertEqual(Task.objects.count(), 0)
        self.assertRedirects(resp, "/dashboard/", fetch_redirect_response=False)

    @patch("members.views._forward_to_controller")
    def test_other_users_project_not_accepted(self, _mock):
        other = make_user(email="other@example.com", username="other")
        other_project = make_project(other, github_repo="other/repo")

        self.client.force_login(self.user)
        self.client.post(self.url, {
            "title": "Sneaky",
            "description": "Trying other project.",
            "project_id": other_project.pk,
        })
        self.assertEqual(Task.objects.count(), 0)

    @patch("members.views._forward_to_controller")
    def test_description_defaults_to_title_when_empty(self, _mock):
        self.client.force_login(self.user)
        self.client.post(self.url, {
            "title": "Auto desc",
            "description": "",
            "project_id": self.project.pk,
        })
        task = Task.objects.get()
        self.assertEqual(task.description, "Auto desc")


# ---------------------------------------------------------------------------
# MemberProfile model
# ---------------------------------------------------------------------------

class MemberProfileModelTests(TestCase):
    def test_str_representation(self):
        user = make_user(email="profile@example.com", username="profileuser")
        profile = MemberProfile.objects.get(user=user)
        self.assertIn("profile@example.com", str(profile))

    def test_default_plan_tier(self):
        user = make_user(email="plan@example.com", username="planuser")
        profile = MemberProfile.objects.get(user=user)
        self.assertEqual(profile.plan_tier, "free")
