import asyncio
import hashlib
import hmac
import json
import tempfile
from unittest.mock import patch

from channels.layers import channel_layers
from channels.testing import WebsocketCommunicator
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings

from members.models import MemberProfile
from notifications.models import Notification
from projects.models import Project
from tasks.consumers import DashboardConsumer, QueueConsumer, TaskDetailConsumer
from tasks.models import Task, TaskAttachment

User = get_user_model()

_TEMP_MEDIA = tempfile.mkdtemp()


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
# Task model
# ---------------------------------------------------------------------------

class TaskModelTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.project = make_project(self.user)

    def test_str_representation(self):
        task = make_task(self.project, self.user, title="Fix bug", status="pending")
        s = str(task)
        self.assertIn("Fix bug", s)
        self.assertIn("Pending", s)

    def test_default_status_is_pending(self):
        task = Task.objects.create(
            project=self.project, created_by=self.user, title="T", description="D"
        )
        self.assertEqual(task.status, "pending")

    def test_default_priority_is_50(self):
        task = Task.objects.create(
            project=self.project, created_by=self.user, title="T", description="D"
        )
        self.assertEqual(task.priority, 50)

    def test_is_active_for_active_statuses(self):
        for status in ("queued", "assigned", "in_progress", "reviewing"):
            task = make_task(self.project, self.user, status=status)
            self.assertTrue(task.is_active, f"Expected is_active for {status}")

    def test_is_not_active_for_non_active_statuses(self):
        for status in ("pending", "completed", "failed"):
            task = make_task(self.project, self.user, status=status)
            self.assertFalse(task.is_active, f"Expected not is_active for {status}")

    def test_is_done_for_terminal_statuses(self):
        for status in ("completed", "failed"):
            task = make_task(self.project, self.user, status=status)
            self.assertTrue(task.is_done, f"Expected is_done for {status}")

    def test_is_not_done_for_non_terminal_statuses(self):
        for status in ("pending", "queued", "assigned", "in_progress", "reviewing"):
            task = make_task(self.project, self.user, status=status)
            self.assertFalse(task.is_done, f"Expected not is_done for {status}")

    def test_ordering_newest_first(self):
        make_task(self.project, self.user, title="First")
        make_task(self.project, self.user, title="Second")
        tasks = list(Task.objects.filter(project=self.project))
        self.assertEqual(tasks[0].title, "Second")

    def test_cascade_delete_with_project(self):
        make_task(self.project, self.user)
        self.project.delete()
        self.assertEqual(Task.objects.count(), 0)

    def test_optional_fields_nullable(self):
        task = make_task(self.project, self.user)
        self.assertIsNone(task.worker_id)
        self.assertIsNone(task.branch_name)
        self.assertIsNone(task.pr_url)
        self.assertIsNone(task.error_message)
        self.assertIsNone(task.started_at)
        self.assertIsNone(task.completed_at)


# ---------------------------------------------------------------------------
# TaskAttachment model
# ---------------------------------------------------------------------------

class TaskAttachmentModelTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.project = make_project(self.user)
        self.task = make_task(self.project, self.user)

    def test_str_representation(self):
        att = TaskAttachment(task=self.task, filename="test.py")
        self.assertEqual(str(att), "test.py")

    def test_extension_property(self):
        att = TaskAttachment(filename="script.py")
        self.assertEqual(att.extension, "py")

    def test_extension_lowercase(self):
        att = TaskAttachment(filename="Image.PNG")
        self.assertEqual(att.extension, "png")

    def test_is_image_for_image_types(self):
        for ext in ("jpg", "jpeg", "png", "gif", "webp", "svg"):
            att = TaskAttachment(filename=f"image.{ext}")
            self.assertTrue(att.is_image, f"Expected is_image for .{ext}")

    def test_is_not_image_for_code_files(self):
        for ext in ("py", "js", "txt", "pdf", "go", "rs"):
            att = TaskAttachment(filename=f"file.{ext}")
            self.assertFalse(att.is_image, f"Expected not is_image for .{ext}")


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
        })
        self.assertEqual(Task.objects.count(), 1)
        task = Task.objects.get()
        self.assertEqual(task.title, "Add dark mode")
        self.assertEqual(task.description, "Add dark mode")
        self.assertEqual(task.created_by, self.user)
        self.assertEqual(task.project, self.project)
        self.assertEqual(task.priority, 50)

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

    @patch("tasks.views._forward_to_controller")
    def test_post_without_description_creates_task(self, _mock):
        self.client.force_login(self.user)
        resp = self.client.post(self.url, {
            "project": self.project.pk,
            "title": "Some title",
        })
        self.assertEqual(Task.objects.count(), 1)
        task = Task.objects.get()
        self.assertEqual(task.description, "Some title")

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

    @patch("tasks.views.http_requests.post")
    @override_settings(TARS_CONTROLLER_URL="http://tars.local", TARS_API_KEY="testkey")
    def test_forward_payload_includes_survey_task_id(self, mock_post):
        mock_post.return_value.ok = True
        mock_post.return_value.json.return_value = {"task": {"id": "ctrl-1"}}
        self.client.force_login(self.user)
        self.client.post(self.url, {
            "project": self.project.pk,
            "title": "Payload check",
            "description": "Verifying survey_task_id is forwarded.",
            "priority": 50,
        })
        task = Task.objects.get()
        _, kwargs = mock_post.call_args
        self.assertEqual(kwargs["json"]["survey_task_id"], task.pk)

    def test_get_prefills_project_from_query_param(self):
        self.client.force_login(self.user)
        resp = self.client.get(self.url, {"project": self.project.pk})
        self.assertEqual(resp.status_code, 200)

    @override_settings(MEDIA_ROOT=_TEMP_MEDIA)
    @patch("tasks.views._forward_to_controller")
    def test_file_attachment_uploaded(self, _mock):
        self.client.force_login(self.user)
        f = SimpleUploadedFile("notes.txt", b"task notes", content_type="text/plain")
        self.client.post(self.url, {
            "project": self.project.pk,
            "title": "Task with file",
            "description": "Details",
            "priority": 50,
            "attachments": [f],
        })
        self.assertEqual(TaskAttachment.objects.count(), 1)
        att = TaskAttachment.objects.get()
        self.assertEqual(att.filename, "notes.txt")


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


# ---------------------------------------------------------------------------
# GET /api/tasks/  — paginated task history
# ---------------------------------------------------------------------------

class ApiTaskListTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.url = "/api/tasks/"
        self.user = make_user()
        self.project = make_project(self.user)

    def test_requires_authentication(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 401)
        self.assertEqual(resp.json()["error"], "Authentication required")

    def test_returns_200_for_authenticated_user(self):
        self.client.force_login(self.user)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)

    def test_returns_json_content_type(self):
        self.client.force_login(self.user)
        resp = self.client.get(self.url)
        self.assertEqual(resp["Content-Type"], "application/json")

    def test_empty_result_when_no_tasks(self):
        self.client.force_login(self.user)
        resp = self.client.get(self.url)
        data = resp.json()
        self.assertEqual(data["tasks"], [])
        self.assertFalse(data["has_more"])
        self.assertIsNone(data["next_page"])

    def test_returns_correct_task_fields(self):
        task = make_task(self.project, self.user)
        self.client.force_login(self.user)
        resp = self.client.get(self.url)
        data = resp.json()
        self.assertEqual(len(data["tasks"]), 1)
        t = data["tasks"][0]
        self.assertEqual(t["id"], task.pk)
        self.assertEqual(t["title"], task.title)
        self.assertEqual(t["status"], task.status)
        self.assertIn("status_display", t)
        self.assertEqual(t["project"], self.project.name)
        self.assertIn("created_at", t)
        self.assertIn("branch_name", t)
        self.assertIn("pr_url", t)
        self.assertIn("error_message", t)
        self.assertIn("completed_at", t)

    def test_only_returns_own_tasks(self):
        make_task(self.project, self.user)
        other = make_user(email="other@example.com", username="other")
        other_project = make_project(other, github_repo="other/repo")
        make_task(other_project, other)

        self.client.force_login(self.user)
        resp = self.client.get(self.url)
        data = resp.json()
        self.assertEqual(len(data["tasks"]), 1)

    def test_returns_tasks_newest_first(self):
        make_task(self.project, self.user, title="First")
        make_task(self.project, self.user, title="Second")

        self.client.force_login(self.user)
        resp = self.client.get(self.url)
        titles = [t["title"] for t in resp.json()["tasks"]]
        self.assertEqual(titles, ["Second", "First"])

    def test_pagination_per_page_limits_results(self):
        for i in range(5):
            make_task(self.project, self.user, title=f"Task {i}")

        self.client.force_login(self.user)
        resp = self.client.get(self.url, {"per_page": 2})
        data = resp.json()
        self.assertEqual(len(data["tasks"]), 2)
        self.assertTrue(data["has_more"])
        self.assertEqual(data["next_page"], 2)

    def test_pagination_page_2(self):
        for i in range(5):
            make_task(self.project, self.user, title=f"Task {i}")

        self.client.force_login(self.user)
        resp = self.client.get(self.url, {"per_page": 2, "page": 2})
        data = resp.json()
        self.assertEqual(len(data["tasks"]), 2)
        self.assertTrue(data["has_more"])

    def test_last_page_has_more_false(self):
        make_task(self.project, self.user)

        self.client.force_login(self.user)
        resp = self.client.get(self.url)
        data = resp.json()
        self.assertFalse(data["has_more"])
        self.assertIsNone(data["next_page"])

    def test_out_of_range_page_returns_empty_list(self):
        self.client.force_login(self.user)
        resp = self.client.get(self.url, {"page": 999})
        data = resp.json()
        self.assertEqual(data["tasks"], [])
        self.assertFalse(data["has_more"])

    def test_invalid_page_returns_400(self):
        self.client.force_login(self.user)
        resp = self.client.get(self.url, {"page": "abc"})
        self.assertEqual(resp.status_code, 400)
        self.assertIn("error", resp.json())

    def test_invalid_per_page_returns_400(self):
        self.client.force_login(self.user)
        resp = self.client.get(self.url, {"per_page": "xyz"})
        self.assertEqual(resp.status_code, 400)
        self.assertIn("error", resp.json())

    def test_per_page_capped_at_100(self):
        for i in range(10):
            make_task(self.project, self.user, title=f"Task {i}")

        self.client.force_login(self.user)
        resp = self.client.get(self.url, {"per_page": 9999})
        data = resp.json()
        self.assertLessEqual(len(data["tasks"]), 100)
        self.assertFalse(data["has_more"])

    def test_page_clamped_to_1_for_zero_or_negative(self):
        make_task(self.project, self.user)
        self.client.force_login(self.user)
        resp = self.client.get(self.url, {"page": 0})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()["tasks"]), 1)

    def test_delete_method_not_allowed(self):
        self.client.force_login(self.user)
        resp = self.client.delete(self.url)
        self.assertEqual(resp.status_code, 405)


# ---------------------------------------------------------------------------
# POST /api/tasks/  — task creation via API
# ---------------------------------------------------------------------------

class ApiTaskCreateTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.url = "/api/tasks/"
        self.user = make_user()
        self.project = make_project(self.user)

    def _post(self, payload):
        return self.client.post(
            self.url,
            data=json.dumps(payload),
            content_type="application/json",
        )

    def test_requires_authentication(self):
        resp = self._post({"project_id": self.project.pk, "title": "Task"})
        self.assertEqual(resp.status_code, 401)
        self.assertEqual(resp.json()["error"], "Authentication required")

    def test_returns_400_for_invalid_json(self):
        self.client.force_login(self.user)
        resp = self.client.post(self.url, data="not json", content_type="application/json")
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()["error"], "Invalid JSON")

    def test_returns_400_for_missing_project_id(self):
        self.client.force_login(self.user)
        resp = self._post({"title": "Task without project"})
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()["error"], "project_id is required")

    def test_returns_400_for_missing_title(self):
        self.client.force_login(self.user)
        resp = self._post({"project_id": self.project.pk})
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()["error"], "title is required")

    def test_returns_400_for_blank_title(self):
        self.client.force_login(self.user)
        resp = self._post({"project_id": self.project.pk, "title": "   "})
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()["error"], "title is required")

    def test_returns_400_for_html_only_title(self):
        self.client.force_login(self.user)
        # bleach.clean("<b></b>", tags=[], strip=True) → "" (empty after stripping)
        resp = self._post({"project_id": self.project.pk, "title": "<b></b>"})
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()["error"], "title is required")

    def test_returns_404_for_project_not_owned_by_user(self):
        other = make_user(email="other@example.com", username="other")
        other_project = make_project(other, github_repo="other/repo")

        self.client.force_login(self.user)
        resp = self._post({"project_id": other_project.pk, "title": "Sneaky task"})
        self.assertEqual(resp.status_code, 404)
        self.assertEqual(resp.json()["error"], "Project not found")

    def test_returns_404_for_nonexistent_project(self):
        self.client.force_login(self.user)
        resp = self._post({"project_id": 999999, "title": "Task"})
        self.assertEqual(resp.status_code, 404)

    @patch("tasks.views._broadcast_queue_task_added")
    @patch("tasks.views._forward_to_controller")
    def test_creates_task_and_returns_201(self, _mock_fwd, _mock_bcast):
        self.client.force_login(self.user)
        resp = self._post({"project_id": self.project.pk, "title": "New API task"})
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(Task.objects.count(), 1)

    @patch("tasks.views._broadcast_queue_task_added")
    @patch("tasks.views._forward_to_controller")
    def test_response_contains_task_fields(self, _mock_fwd, _mock_bcast):
        self.client.force_login(self.user)
        resp = self._post({
            "project_id": self.project.pk,
            "title": "My Task",
            "description": "Some description",
        })
        data = resp.json()
        self.assertIn("id", data)
        self.assertEqual(data["title"], "My Task")
        self.assertEqual(data["description"], "Some description")
        self.assertEqual(data["status"], "pending")
        self.assertIn("status_display", data)
        self.assertEqual(data["project"], self.project.name)
        self.assertIn("created_at", data)

    @patch("tasks.views._broadcast_queue_task_added")
    @patch("tasks.views._forward_to_controller")
    def test_description_defaults_to_title_when_omitted(self, _mock_fwd, _mock_bcast):
        self.client.force_login(self.user)
        self._post({"project_id": self.project.pk, "title": "Title only"})
        task = Task.objects.get()
        self.assertEqual(task.description, "Title only")

    @patch("tasks.views._broadcast_queue_task_added")
    @patch("tasks.views._forward_to_controller")
    def test_priority_defaults_to_50(self, _mock_fwd, _mock_bcast):
        self.client.force_login(self.user)
        self._post({"project_id": self.project.pk, "title": "Task"})
        task = Task.objects.get()
        self.assertEqual(task.priority, 50)

    @patch("tasks.views._broadcast_queue_task_added")
    @patch("tasks.views._forward_to_controller")
    def test_status_defaults_to_pending(self, _mock_fwd, _mock_bcast):
        self.client.force_login(self.user)
        self._post({"project_id": self.project.pk, "title": "Task"})
        task = Task.objects.get()
        self.assertEqual(task.status, "pending")

    @patch("tasks.views._broadcast_queue_task_added")
    @patch("tasks.views._forward_to_controller")
    def test_sanitizes_html_tags_from_title(self, _mock_fwd, _mock_bcast):
        self.client.force_login(self.user)
        resp = self._post({
            "project_id": self.project.pk,
            "title": "<b>Bold</b> task",
        })
        self.assertEqual(resp.status_code, 201)
        task = Task.objects.get()
        self.assertEqual(task.title, "Bold task")

    @patch("tasks.views._broadcast_queue_task_added")
    @patch("tasks.views._forward_to_controller")
    def test_calls_forward_to_controller(self, mock_fwd, _mock_bcast):
        self.client.force_login(self.user)
        self._post({"project_id": self.project.pk, "title": "Task"})
        mock_fwd.assert_called_once()

    def test_get_returns_task_list(self):
        self.client.force_login(self.user)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertIn("tasks", resp.json())


# ---------------------------------------------------------------------------
# POST /api/tasks/<pk>/status
# ---------------------------------------------------------------------------

class ApiTaskStatusTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = make_user()
        self.project = make_project(self.user)
        self.task = make_task(self.project, self.user)
        self.url = f"/api/tasks/{self.task.pk}/status"

    def _post(self, payload, api_key="testkey"):
        return self.client.post(
            self.url,
            data=json.dumps(payload),
            content_type="application/json",
            HTTP_X_API_KEY=api_key,
        )

    @override_settings(TARS_API_KEY="testkey")
    def test_returns_401_without_api_key(self):
        resp = self.client.post(
            self.url,
            data=json.dumps({"status": "in_progress"}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 401)

    @override_settings(TARS_API_KEY="testkey")
    def test_returns_401_with_wrong_api_key(self):
        resp = self.client.post(
            self.url,
            data=json.dumps({"status": "in_progress"}),
            content_type="application/json",
            HTTP_X_API_KEY="wrongkey",
        )
        self.assertEqual(resp.status_code, 401)
        self.assertEqual(resp.json()["error"], "Invalid or missing X-API-Key")

    @override_settings(TARS_API_KEY="testkey")
    def test_returns_400_for_invalid_json(self):
        resp = self.client.post(
            self.url,
            data="not json",
            content_type="application/json",
            HTTP_X_API_KEY="testkey",
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()["error"], "Invalid JSON")

    @override_settings(TARS_API_KEY="testkey")
    def test_returns_400_for_invalid_status(self):
        resp = self._post({"status": "flying"})
        self.assertEqual(resp.status_code, 400)
        self.assertIn("Invalid status", resp.json()["error"])

    @override_settings(TARS_API_KEY="testkey")
    def test_returns_400_for_missing_status(self):
        resp = self._post({})
        self.assertEqual(resp.status_code, 400)

    @override_settings(TARS_API_KEY="testkey")
    def test_returns_404_for_nonexistent_task(self):
        resp = self.client.post(
            "/api/tasks/999999/status",
            data=json.dumps({"status": "in_progress"}),
            content_type="application/json",
            HTTP_X_API_KEY="testkey",
        )
        self.assertEqual(resp.status_code, 404)
        self.assertEqual(resp.json()["error"], "Task not found")

    @patch("tasks.views._broadcast_task_update")
    @override_settings(TARS_API_KEY="testkey")
    def test_updates_status_and_returns_200(self, _mock_bcast):
        resp = self._post({"status": "in_progress"})
        self.assertEqual(resp.status_code, 200)
        self.task.refresh_from_db()
        self.assertEqual(self.task.status, "in_progress")

    @patch("tasks.views._broadcast_task_update")
    @override_settings(TARS_API_KEY="testkey")
    def test_response_contains_task_fields(self, _mock_bcast):
        resp = self._post({"status": "completed"})
        data = resp.json()
        self.assertTrue(data["ok"])
        self.assertEqual(data["task_id"], self.task.pk)
        self.assertEqual(data["status"], "completed")
        self.assertIn("status_display", data)

    @patch("tasks.views._broadcast_task_update")
    @override_settings(TARS_API_KEY="testkey")
    def test_sets_started_at_for_in_progress(self, _mock_bcast):
        self._post({"status": "in_progress"})
        self.task.refresh_from_db()
        self.assertIsNotNone(self.task.started_at)

    @patch("tasks.views._broadcast_task_update")
    @override_settings(TARS_API_KEY="testkey")
    def test_sets_started_at_for_assigned(self, _mock_bcast):
        self._post({"status": "assigned"})
        self.task.refresh_from_db()
        self.assertIsNotNone(self.task.started_at)

    @patch("tasks.views._broadcast_task_update")
    @override_settings(TARS_API_KEY="testkey")
    def test_sets_completed_at_for_completed(self, _mock_bcast):
        self._post({"status": "completed"})
        self.task.refresh_from_db()
        self.assertIsNotNone(self.task.completed_at)

    @patch("tasks.views._broadcast_task_update")
    @override_settings(TARS_API_KEY="testkey")
    def test_sets_completed_at_for_failed(self, _mock_bcast):
        self._post({"status": "failed"})
        self.task.refresh_from_db()
        self.assertIsNotNone(self.task.completed_at)

    @patch("tasks.views._broadcast_task_update")
    @override_settings(TARS_API_KEY="testkey")
    def test_does_not_overwrite_started_at(self, _mock_bcast):
        from django.utils import timezone
        original_time = timezone.now() - timezone.timedelta(hours=1)
        self.task.started_at = original_time
        self.task.save(update_fields=["started_at"])

        self._post({"status": "in_progress"})
        self.task.refresh_from_db()
        self.assertEqual(self.task.started_at, original_time)

    @patch("tasks.views._broadcast_task_update")
    @override_settings(TARS_API_KEY="testkey")
    def test_does_not_overwrite_completed_at(self, _mock_bcast):
        from django.utils import timezone
        original_time = timezone.now() - timezone.timedelta(hours=1)
        self.task.completed_at = original_time
        self.task.save(update_fields=["completed_at"])

        self._post({"status": "completed"})
        self.task.refresh_from_db()
        self.assertEqual(self.task.completed_at, original_time)

    @patch("tasks.views._broadcast_task_update")
    @override_settings(TARS_API_KEY="testkey")
    def test_updates_branch_name(self, _mock_bcast):
        self._post({"status": "in_progress", "branch_name": "feature/my-branch"})
        self.task.refresh_from_db()
        self.assertEqual(self.task.branch_name, "feature/my-branch")

    @patch("tasks.views._broadcast_task_update")
    @override_settings(TARS_API_KEY="testkey")
    def test_updates_pr_url(self, _mock_bcast):
        self._post({"status": "reviewing", "pr_url": "https://github.com/org/repo/pull/42"})
        self.task.refresh_from_db()
        self.assertEqual(self.task.pr_url, "https://github.com/org/repo/pull/42")

    @patch("tasks.views._broadcast_task_update")
    @override_settings(TARS_API_KEY="testkey")
    def test_updates_error_message(self, _mock_bcast):
        self._post({"status": "failed", "error_message": "Build failed at step 3"})
        self.task.refresh_from_db()
        self.assertEqual(self.task.error_message, "Build failed at step 3")

    @patch("tasks.views._broadcast_task_update")
    @override_settings(TARS_API_KEY="testkey")
    def test_updates_worker_id(self, _mock_bcast):
        self._post({"status": "assigned", "worker_id": "worker-mac-mini-1"})
        self.task.refresh_from_db()
        self.assertEqual(self.task.worker_id, "worker-mac-mini-1")

    @patch("tasks.views._broadcast_task_update")
    @override_settings(TARS_API_KEY="testkey")
    def test_csrf_exempt(self, _mock_bcast):
        # Verify the endpoint works without CSRF token even with enforcement on
        client = Client(enforce_csrf_checks=True)
        resp = client.post(
            self.url,
            data=json.dumps({"status": "in_progress"}),
            content_type="application/json",
            HTTP_X_API_KEY="testkey",
        )
        self.assertEqual(resp.status_code, 200)

    @patch("tasks.views._broadcast_task_update")
    @override_settings(TARS_API_KEY="testkey")
    def test_calls_broadcast_on_success(self, mock_bcast):
        self._post({"status": "in_progress"})
        mock_bcast.assert_called_once()


# ---------------------------------------------------------------------------
# WebSocket consumers
# ---------------------------------------------------------------------------

_WS_CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer",
    }
}


@override_settings(CHANNEL_LAYERS=_WS_CHANNEL_LAYERS)
class TaskDetailConsumerTests(TestCase):
    def setUp(self):
        channel_layers.backends.clear()
        self.user = make_user(email="wsuser@example.com", username="wsuser")
        self.project = make_project(self.user)
        self.task = make_task(self.project, self.user)

    def _make_comm(self, task_id, user=None):
        comm = WebsocketCommunicator(
            TaskDetailConsumer.as_asgi(),
            f"/ws/tasks/{task_id}/",
        )
        comm.scope["url_route"] = {"kwargs": {"task_id": str(task_id)}}
        if user is not None:
            comm.scope["user"] = user
        return comm

    def test_unauthenticated_connection_rejected(self):
        task_pk = self.task.pk

        async def _run():
            comm = self._make_comm(task_pk)
            connected, _ = await comm.connect()
            self.assertFalse(connected)

        asyncio.run(_run())

    def test_authenticated_connection_accepted(self):
        user = self.user
        task_pk = self.task.pk

        async def _run():
            comm = self._make_comm(task_pk, user=user)
            connected, _ = await comm.connect()
            self.assertTrue(connected)
            await comm.disconnect()

        asyncio.run(_run())

    def test_ping_responds_with_pong(self):
        user = self.user
        task_pk = self.task.pk

        async def _run():
            comm = self._make_comm(task_pk, user=user)
            connected, _ = await comm.connect()
            self.assertTrue(connected)
            await comm.send_json_to({"type": "ping"})
            response = await comm.receive_json_from()
            self.assertEqual(response, {"type": "pong"})
            await comm.disconnect()

        asyncio.run(_run())

    def test_invalid_json_does_not_crash(self):
        user = self.user
        task_pk = self.task.pk

        async def _run():
            comm = self._make_comm(task_pk, user=user)
            connected, _ = await comm.connect()
            self.assertTrue(connected)
            await comm.send_to(text_data="not valid json {{{")
            # No response expected; check connection still alive with ping
            await comm.send_json_to({"type": "ping"})
            response = await comm.receive_json_from()
            self.assertEqual(response["type"], "pong")
            await comm.disconnect()

        asyncio.run(_run())

    def test_task_update_message_forwarded_to_client(self):
        from channels.layers import get_channel_layer

        user = self.user
        task_pk = self.task.pk

        async def _run():
            comm = self._make_comm(task_pk, user=user)
            connected, _ = await comm.connect()
            self.assertTrue(connected)

            layer = get_channel_layer()
            update_data = {"task_id": task_pk, "status": "in_progress", "title": "Test"}
            await layer.group_send(
                f"task_{task_pk}",
                {"type": "task_update", "data": update_data},
            )

            response = await comm.receive_json_from()
            self.assertEqual(response, update_data)
            await comm.disconnect()

        asyncio.run(_run())

    def test_non_ping_message_ignored(self):
        user = self.user
        task_pk = self.task.pk

        async def _run():
            comm = self._make_comm(task_pk, user=user)
            connected, _ = await comm.connect()
            self.assertTrue(connected)
            await comm.send_json_to({"type": "subscribe", "channel": "all"})
            # No response expected; check we can still ping
            await comm.send_json_to({"type": "ping"})
            response = await comm.receive_json_from()
            self.assertEqual(response["type"], "pong")
            await comm.disconnect()

        asyncio.run(_run())


@override_settings(CHANNEL_LAYERS=_WS_CHANNEL_LAYERS)
class DashboardConsumerTests(TestCase):
    def setUp(self):
        channel_layers.backends.clear()
        self.user = make_user(email="dashuser@example.com", username="dashuser")

    def _make_comm(self, user=None):
        comm = WebsocketCommunicator(DashboardConsumer.as_asgi(), "/ws/dashboard/")
        if user is not None:
            comm.scope["user"] = user
        return comm

    def test_unauthenticated_connection_rejected(self):
        async def _run():
            comm = self._make_comm()
            connected, _ = await comm.connect()
            self.assertFalse(connected)

        asyncio.run(_run())

    def test_authenticated_connection_accepted(self):
        user = self.user

        async def _run():
            comm = self._make_comm(user=user)
            connected, _ = await comm.connect()
            self.assertTrue(connected)
            await comm.disconnect()

        asyncio.run(_run())

    def test_ping_responds_with_pong(self):
        user = self.user

        async def _run():
            comm = self._make_comm(user=user)
            connected, _ = await comm.connect()
            self.assertTrue(connected)
            await comm.send_json_to({"type": "ping"})
            response = await comm.receive_json_from()
            self.assertEqual(response, {"type": "pong"})
            await comm.disconnect()

        asyncio.run(_run())

    def test_task_update_message_forwarded_to_client(self):
        from channels.layers import get_channel_layer

        user = self.user
        user_pk = self.user.pk

        async def _run():
            comm = self._make_comm(user=user)
            connected, _ = await comm.connect()
            self.assertTrue(connected)

            layer = get_channel_layer()
            update_data = {"task_id": 1, "status": "completed", "title": "Done"}
            await layer.group_send(
                f"dashboard_{user_pk}",
                {"type": "task_update", "data": update_data},
            )

            response = await comm.receive_json_from()
            self.assertEqual(response, update_data)
            await comm.disconnect()

        asyncio.run(_run())


@override_settings(CHANNEL_LAYERS=_WS_CHANNEL_LAYERS)
class QueueConsumerTests(TestCase):
    def setUp(self):
        channel_layers.backends.clear()
        self.user = make_user(email="queueuser@example.com", username="queueuser")

    def _make_comm(self, user=None):
        comm = WebsocketCommunicator(QueueConsumer.as_asgi(), "/ws/queue/")
        if user is not None:
            comm.scope["user"] = user
        return comm

    def test_unauthenticated_connection_rejected(self):
        async def _run():
            comm = self._make_comm()
            connected, _ = await comm.connect()
            self.assertFalse(connected)

        asyncio.run(_run())

    def test_authenticated_connection_accepted(self):
        user = self.user

        async def _run():
            comm = self._make_comm(user=user)
            connected, _ = await comm.connect()
            self.assertTrue(connected)
            await comm.disconnect()

        asyncio.run(_run())

    def test_ping_responds_with_pong(self):
        user = self.user

        async def _run():
            comm = self._make_comm(user=user)
            connected, _ = await comm.connect()
            self.assertTrue(connected)
            await comm.send_json_to({"type": "ping"})
            response = await comm.receive_json_from()
            self.assertEqual(response, {"type": "pong"})
            await comm.disconnect()

        asyncio.run(_run())

    def test_queue_update_message_forwarded_to_client(self):
        from channels.layers import get_channel_layer

        user = self.user
        user_pk = self.user.pk

        async def _run():
            comm = self._make_comm(user=user)
            connected, _ = await comm.connect()
            self.assertTrue(connected)

            layer = get_channel_layer()
            update_data = {
                "kind": "task_added",
                "task_id": 42,
                "status": "pending",
                "queue_position": 1,
            }
            await layer.group_send(
                f"queue_{user_pk}",
                {"type": "queue_update", "data": update_data},
            )

            response = await comm.receive_json_from()
            self.assertEqual(response, update_data)
            await comm.disconnect()

        asyncio.run(_run())


# ---------------------------------------------------------------------------
# POST /api/webhooks/github/
# ---------------------------------------------------------------------------

_WEBHOOK_SECRET = "test-webhook-secret"
_WEBHOOK_URL = "/api/webhooks/github/"


def _sign(body: bytes, secret: str = _WEBHOOK_SECRET) -> str:
    """Compute the GitHub-style HMAC-SHA256 signature header value."""
    digest = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def _pr_payload(action="opened", merged=False, pr_url="https://github.com/owner/repo/pull/1", pr_body=""):
    return json.dumps({
        "action": action,
        "pull_request": {
            "html_url": pr_url,
            "body": pr_body,
            "merged": merged,
        },
    }).encode()


@override_settings(GITHUB_WEBHOOK_SECRET=_WEBHOOK_SECRET)
class GitHubWebhookTests(TestCase):
    def setUp(self):
        self.client = Client(enforce_csrf_checks=True)
        self.user = make_user(email="ghuser@example.com", username="ghuser")
        self.project = make_project(self.user, github_repo="owner/repo")
        self.task = make_task(
            self.project,
            self.user,
            status="reviewing",
            pr_url="https://github.com/owner/repo/pull/1",
        )

    def _post(self, body: bytes, event="pull_request", sig=None):
        if sig is None:
            sig = _sign(body)
        return self.client.post(
            _WEBHOOK_URL,
            data=body,
            content_type="application/json",
            HTTP_X_GITHUB_EVENT=event,
            HTTP_X_HUB_SIGNATURE_256=sig,
        )

    # -- signature validation ------------------------------------------------

    def test_missing_signature_returns_400(self):
        body = _pr_payload()
        resp = self.client.post(
            _WEBHOOK_URL,
            data=body,
            content_type="application/json",
            HTTP_X_GITHUB_EVENT="pull_request",
        )
        self.assertEqual(resp.status_code, 400)

    def test_invalid_signature_returns_400(self):
        body = _pr_payload()
        resp = self._post(body, sig="sha256=deadbeef")
        self.assertEqual(resp.status_code, 400)

    def test_valid_signature_returns_200(self):
        body = _pr_payload()
        resp = self._post(body)
        self.assertEqual(resp.status_code, 200)

    def test_csrf_exempt(self):
        body = _pr_payload()
        sig = _sign(body)
        resp = self.client.post(
            _WEBHOOK_URL,
            data=body,
            content_type="application/json",
            HTTP_X_GITHUB_EVENT="pull_request",
            HTTP_X_HUB_SIGNATURE_256=sig,
        )
        self.assertEqual(resp.status_code, 200)

    # -- event filtering -----------------------------------------------------

    def test_non_pull_request_event_ignored(self):
        body = json.dumps({"action": "push"}).encode()
        resp = self._post(body, event="push")
        self.assertEqual(resp.status_code, 200)
        self.task.refresh_from_db()
        self.assertEqual(self.task.status, "reviewing")

    def test_unrecognised_pr_action_ignored(self):
        body = _pr_payload(action="labeled")
        resp = self._post(body)
        self.assertEqual(resp.status_code, 200)
        self.task.refresh_from_db()
        self.assertEqual(self.task.status, "reviewing")

    def test_invalid_json_returns_400(self):
        body = b"not valid json {"
        resp = self._post(body)
        self.assertEqual(resp.status_code, 400)

    # -- PR opened -----------------------------------------------------------

    @patch("tasks.views._broadcast_task_update")
    def test_pr_opened_sets_reviewing_status(self, mock_bcast):
        self.task.status = "in_progress"
        self.task.pr_url = ""
        self.task.save()

        # Task has no pr_url yet; use PR body fallback to find it
        pr_body = f"tars-task-id: {self.task.pk}"
        body = _pr_payload(action="opened", pr_body=pr_body)
        resp = self._post(body)
        self.assertEqual(resp.status_code, 200)
        self.task.refresh_from_db()
        self.assertEqual(self.task.status, "reviewing")

    @patch("tasks.views._broadcast_task_update")
    def test_pr_opened_sets_pr_url(self, mock_bcast):
        self.task.pr_url = ""
        self.task.save()

        pr_body = f"tars-task-id: {self.task.pk}"
        body = _pr_payload(action="opened", pr_url="https://github.com/owner/repo/pull/1", pr_body=pr_body)
        self._post(body)
        self.task.refresh_from_db()
        self.assertEqual(self.task.pr_url, "https://github.com/owner/repo/pull/1")

    @patch("tasks.views._broadcast_task_update")
    def test_pr_opened_broadcasts_update(self, mock_bcast):
        self.task.status = "in_progress"
        self.task.pr_url = ""
        self.task.save()

        pr_body = f"tars-task-id: {self.task.pk}"
        body = _pr_payload(action="opened", pr_body=pr_body)
        self._post(body)
        mock_bcast.assert_called_once()

    @patch("tasks.views._broadcast_task_update")
    def test_pr_opened_does_not_overwrite_existing_pr_url(self, mock_bcast):
        existing = "https://github.com/owner/repo/pull/99"
        self.task.pr_url = existing
        self.task.status = "reviewing"
        self.task.save()

        # New PR opened for same task (found via body); should not replace existing pr_url
        pr_body = f"tars-task-id: {self.task.pk}"
        body = _pr_payload(action="opened", pr_url="https://github.com/owner/repo/pull/1", pr_body=pr_body)
        self._post(body)
        self.task.refresh_from_db()
        self.assertEqual(self.task.pr_url, existing)

    # -- PR merged -----------------------------------------------------------

    @patch("tasks.views._broadcast_task_update")
    def test_pr_merged_sets_completed_status(self, mock_bcast):
        body = _pr_payload(action="closed", merged=True)
        resp = self._post(body)
        self.assertEqual(resp.status_code, 200)
        self.task.refresh_from_db()
        self.assertEqual(self.task.status, "completed")

    @patch("tasks.views._broadcast_task_update")
    def test_pr_merged_sets_completed_at(self, mock_bcast):
        self.assertIsNone(self.task.completed_at)
        body = _pr_payload(action="closed", merged=True)
        self._post(body)
        self.task.refresh_from_db()
        self.assertIsNotNone(self.task.completed_at)

    @patch("tasks.views._broadcast_task_update")
    def test_pr_merged_creates_notification(self, mock_bcast):
        body = _pr_payload(action="closed", merged=True)
        self._post(body)
        notif = Notification.objects.filter(user=self.user).first()
        self.assertIsNotNone(notif)
        self.assertIn("merged", notif.title.lower())
        self.assertEqual(notif.message, "PR merged! Your changes are live.")

    @patch("tasks.views._broadcast_task_update")
    def test_pr_merged_broadcasts_update(self, mock_bcast):
        body = _pr_payload(action="closed", merged=True)
        self._post(body)
        mock_bcast.assert_called_once()

    # -- PR closed without merge ---------------------------------------------

    @patch("tasks.views._broadcast_task_update")
    def test_pr_closed_without_merge_leaves_status_unchanged(self, mock_bcast):
        body = _pr_payload(action="closed", merged=False)
        resp = self._post(body)
        self.assertEqual(resp.status_code, 200)
        self.task.refresh_from_db()
        self.assertEqual(self.task.status, "reviewing")
        mock_bcast.assert_not_called()

    # -- unknown PR ----------------------------------------------------------

    def test_unknown_pr_url_returns_200_and_no_changes(self):
        body = _pr_payload(pr_url="https://github.com/other/repo/pull/999", action="closed", merged=True)
        resp = self._post(body)
        self.assertEqual(resp.status_code, 200)
        self.task.refresh_from_db()
        self.assertEqual(self.task.status, "reviewing")

    # -- fallback task lookup via PR body ------------------------------------

    @patch("tasks.views._broadcast_task_update")
    def test_finds_task_by_id_in_pr_body(self, mock_bcast):
        self.task.pr_url = ""
        self.task.save()

        pr_body = f"Fixes the issue.\n\ntars-task-id: {self.task.pk}"
        body = _pr_payload(
            action="closed",
            merged=True,
            pr_url="https://github.com/owner/repo/pull/42",
            pr_body=pr_body,
        )
        resp = self._post(body)
        self.assertEqual(resp.status_code, 200)
        self.task.refresh_from_db()
        self.assertEqual(self.task.status, "completed")

    # -- no secret configured ------------------------------------------------

    @override_settings(GITHUB_WEBHOOK_SECRET="")
    @patch("tasks.views._broadcast_task_update")
    def test_no_secret_skips_signature_check(self, mock_bcast):
        body = _pr_payload(action="closed", merged=True)
        resp = self.client.post(
            _WEBHOOK_URL,
            data=body,
            content_type="application/json",
            HTTP_X_GITHUB_EVENT="pull_request",
        )
        self.assertEqual(resp.status_code, 200)
        self.task.refresh_from_db()
        self.assertEqual(self.task.status, "completed")
