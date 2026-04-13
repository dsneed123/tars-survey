from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase

from members.models import MemberProfile
from projects.models import Project
from tasks.models import Task, TaskAttachment

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
        "description": "Detailed description of the bug to fix.",
        "status": "pending",
        "priority": 50,
    }
    defaults.update(kwargs)
    return Task.objects.create(project=project, created_by=owner, **defaults)


# ---------------------------------------------------------------------------
# GET /dashboard/tasks/
# ---------------------------------------------------------------------------

class TaskListViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.url = "/dashboard/tasks/"
        self.user = make_user()

    def test_requires_login(self):
        resp = self.client.get(self.url)
        self.assertRedirects(resp, f"/login/?next={self.url}", fetch_redirect_response=False)

    def test_returns_200_for_logged_in_user(self):
        self.client.force_login(self.user)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)

    def test_only_shows_own_tasks(self):
        project = make_project(self.user)
        make_task(project, self.user, title="Mine")

        other = make_user(email="other@example.com", username="other")
        other_project = make_project(other, github_repo="other/repo")
        make_task(other_project, other, title="Theirs")

        self.client.force_login(self.user)
        resp = self.client.get(self.url)
        tasks = list(resp.context["tasks"])
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0].title, "Mine")

    def test_filter_by_project(self):
        project1 = make_project(self.user, name="P1")
        project2 = make_project(self.user, name="P2", github_repo="owner/repo2")
        make_task(project1, self.user, title="Task A")
        make_task(project2, self.user, title="Task B")

        self.client.force_login(self.user)
        resp = self.client.get(self.url, {"project": project1.pk})
        tasks = list(resp.context["tasks"])
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0].title, "Task A")

    def test_filter_by_status(self):
        project = make_project(self.user)
        make_task(project, self.user, title="Pending", status="pending")
        make_task(project, self.user, title="Completed", status="completed")

        self.client.force_login(self.user)
        resp = self.client.get(self.url, {"status": "pending"})
        tasks = list(resp.context["tasks"])
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0].title, "Pending")

    def test_context_includes_projects_and_status_choices(self):
        self.client.force_login(self.user)
        resp = self.client.get(self.url)
        self.assertIn("projects", resp.context)
        self.assertIn("status_choices", resp.context)


# ---------------------------------------------------------------------------
# GET/POST /dashboard/tasks/new/
# ---------------------------------------------------------------------------

class TaskAddViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.url = "/dashboard/tasks/new/"
        self.user = make_user()
        self.project = make_project(self.user)

    def test_requires_login(self):
        resp = self.client.get(self.url)
        self.assertRedirects(resp, f"/login/?next={self.url}", fetch_redirect_response=False)

    def test_get_returns_200(self):
        self.client.force_login(self.user)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)

    @patch("tasks.views._forward_to_controller")
    def test_post_creates_task(self, _mock):
        self.client.force_login(self.user)
        resp = self.client.post(self.url, {
            "project": self.project.pk,
            "title": "Add dark mode",
            "description": "Implement a dark mode toggle in the settings page.",
            "priority": 60,
        })
        self.assertEqual(Task.objects.count(), 1)
        task = Task.objects.get()
        self.assertEqual(task.title, "Add dark mode")
        self.assertEqual(task.created_by, self.user)
        self.assertEqual(task.project, self.project)
        self.assertEqual(task.priority, 60)

    @patch("tasks.views._forward_to_controller")
    def test_post_redirects_to_task_detail(self, _mock):
        self.client.force_login(self.user)
        resp = self.client.post(self.url, {
            "project": self.project.pk,
            "title": "New task",
            "description": "Some description text here.",
            "priority": 50,
        })
        task = Task.objects.get()
        self.assertRedirects(
            resp,
            f"/dashboard/tasks/{task.pk}/",
            fetch_redirect_response=False,
        )

    @patch("tasks.views._forward_to_controller")
    def test_post_default_status_is_pending(self, _mock):
        self.client.force_login(self.user)
        self.client.post(self.url, {
            "project": self.project.pk,
            "title": "Status check",
            "description": "Checking default status.",
            "priority": 50,
        })
        task = Task.objects.get()
        self.assertEqual(task.status, "pending")

    def test_post_missing_title_stays_on_form(self):
        self.client.force_login(self.user)
        resp = self.client.post(self.url, {
            "project": self.project.pk,
            "title": "",
            "description": "Missing title test.",
            "priority": 50,
        })
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(Task.objects.count(), 0)

    def test_post_missing_description_stays_on_form(self):
        self.client.force_login(self.user)
        resp = self.client.post(self.url, {
            "project": self.project.pk,
            "title": "Some title",
            "description": "",
            "priority": 50,
        })
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(Task.objects.count(), 0)

    def test_post_project_not_belonging_to_user_rejected(self):
        other = make_user(email="other@example.com", username="other")
        other_project = make_project(other, github_repo="other/repo")

        self.client.force_login(self.user)
        resp = self.client.post(self.url, {
            "project": other_project.pk,
            "title": "Sneaky task",
            "description": "Trying to submit to another user's project.",
            "priority": 50,
        })
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(Task.objects.count(), 0)

    @patch("tasks.views._forward_to_controller")
    def test_post_calls_forward_to_controller(self, mock_forward):
        self.client.force_login(self.user)
        self.client.post(self.url, {
            "project": self.project.pk,
            "title": "Controller test",
            "description": "Should be forwarded.",
            "priority": 50,
        })
        mock_forward.assert_called_once()

    def test_get_prefills_project_from_query_param(self):
        self.client.force_login(self.user)
        resp = self.client.get(self.url, {"project": self.project.pk})
        self.assertEqual(resp.status_code, 200)


# ---------------------------------------------------------------------------
# GET /dashboard/tasks/<pk>/
# ---------------------------------------------------------------------------

class TaskDetailViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = make_user()
        self.project = make_project(self.user)
        self.task = make_task(self.project, self.user)
        self.url = f"/dashboard/tasks/{self.task.pk}/"

    def test_requires_login(self):
        resp = self.client.get(self.url)
        self.assertRedirects(resp, f"/login/?next={self.url}", fetch_redirect_response=False)

    def test_returns_200_for_owner(self):
        self.client.force_login(self.user)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)

    def test_returns_404_for_other_user(self):
        other = make_user(email="other@example.com", username="other")
        self.client.force_login(other)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 404)

    def test_context_contains_task(self):
        self.client.force_login(self.user)
        resp = self.client.get(self.url)
        self.assertEqual(resp.context["task"], self.task)

    def test_context_contains_timeline(self):
        self.client.force_login(self.user)
        resp = self.client.get(self.url)
        self.assertIn("timeline", resp.context)
        self.assertIsInstance(resp.context["timeline"], list)
        self.assertTrue(len(resp.context["timeline"]) > 0)

    def test_context_contains_attachments(self):
        self.client.force_login(self.user)
        resp = self.client.get(self.url)
        self.assertIn("attachments", resp.context)

    def test_timeline_shows_pending_status_as_current(self):
        self.client.force_login(self.user)
        resp = self.client.get(self.url)
        timeline = resp.context["timeline"]
        pending_step = next((s for s in timeline if s["status"] == "pending"), None)
        self.assertIsNotNone(pending_step)
        self.assertEqual(pending_step["state"], "current")

    def test_timeline_for_completed_task(self):
        self.task.status = "completed"
        self.task.save()
        self.client.force_login(self.user)
        resp = self.client.get(self.url)
        timeline = resp.context["timeline"]
        completed_step = next((s for s in timeline if s["status"] == "completed"), None)
        self.assertIsNotNone(completed_step)
        self.assertIn(completed_step["state"], ("done", "current"))

    def test_timeline_for_failed_task(self):
        self.task.status = "failed"
        self.task.save()
        self.client.force_login(self.user)
        resp = self.client.get(self.url)
        timeline = resp.context["timeline"]
        failed_step = next((s for s in timeline if s["state"] == "failed"), None)
        self.assertIsNotNone(failed_step)
