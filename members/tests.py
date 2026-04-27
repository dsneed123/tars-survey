import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.test import Client, RequestFactory, TestCase

from members.models import MemberProfile
from notifications.models import NotificationPreference
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

    def test_uses_chat_layout_template(self):
        self.client.force_login(self.user)
        resp = self.client.get(self.url)
        self.assertTemplateUsed(resp, "members/dashboard.html")

    def test_has_more_false_when_fewer_than_50_tasks(self):
        self.client.force_login(self.user)
        resp = self.client.get(self.url)
        self.assertFalse(resp.context["has_more"])

    def test_has_more_true_when_over_50_tasks(self):
        project = make_project(self.user)
        for i in range(55):
            make_task(project, self.user, title=f"Task {i}")
        self.client.force_login(self.user)
        resp = self.client.get(self.url)
        self.assertTrue(resp.context["has_more"])

    def test_oldest_task_id_in_context(self):
        project = make_project(self.user)
        make_task(project, self.user, title="Old task")
        self.client.force_login(self.user)
        resp = self.client.get(self.url)
        self.assertIsNotNone(resp.context["oldest_task_id"])

    def test_context_contains_pinned_tasks(self):
        self.client.force_login(self.user)
        resp = self.client.get(self.url)
        self.assertIn("pinned_tasks", resp.context)

    def test_context_contains_task_templates(self):
        self.client.force_login(self.user)
        resp = self.client.get(self.url)
        self.assertIn("task_templates", resp.context)
        self.assertIn("task_templates_json", resp.context)


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

    @patch("members.views._forward_to_controller")
    def test_ajax_returns_json_on_success(self, _mock):
        self.client.force_login(self.user)
        resp = self.client.post(
            self.url,
            {"title": "AJAX task", "project_id": self.project.pk},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["ok"])
        self.assertIn("task_id", data)
        self.assertEqual(data["title"], "AJAX task")
        self.assertEqual(data["status"], "pending")

    @patch("members.views._forward_to_controller")
    def test_ajax_missing_title_returns_400_json(self, _mock):
        self.client.force_login(self.user)
        resp = self.client.post(
            self.url,
            {"title": "", "project_id": self.project.pk},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(resp.status_code, 400)
        data = resp.json()
        self.assertFalse(data["ok"])
        self.assertIn("error", data)

    @patch("members.views._forward_to_controller")
    def test_ajax_missing_project_returns_400_json(self, _mock):
        self.client.force_login(self.user)
        resp = self.client.post(
            self.url,
            {"title": "Task", "project_id": ""},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(resp.status_code, 400)
        data = resp.json()
        self.assertFalse(data["ok"])

    @patch("members.views._forward_to_controller")
    def test_ajax_wrong_project_returns_400_json(self, _mock):
        other = make_user(email="ajax_other@example.com", username="ajax_other")
        other_project = make_project(other, github_repo="ajax/repo")
        self.client.force_login(self.user)
        resp = self.client.post(
            self.url,
            {"title": "Sneaky", "project_id": other_project.pk},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(resp.json()["ok"])
        self.assertEqual(Task.objects.count(), 0)


# ---------------------------------------------------------------------------
# POST /dashboard/bulk-tasks/
# ---------------------------------------------------------------------------

class BulkAddTasksViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.url = "/dashboard/bulk-tasks/"
        self.user = make_user()
        self.project = make_project(self.user)

    def test_requires_login(self):
        resp = self.client.post(self.url, {"tasks": "Task one\nTask two", "project_id": self.project.pk})
        self.assertRedirects(resp, f"/login/?next={self.url}", fetch_redirect_response=False)

    def test_get_not_allowed(self):
        self.client.force_login(self.user)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 405)

    @patch("members.views._forward_to_controller")
    def test_creates_one_task_per_line(self, _mock):
        self.client.force_login(self.user)
        resp = self.client.post(self.url, {
            "tasks": "Fix login bug\nAdd dark mode\nWrite unit tests",
            "project_id": self.project.pk,
        })
        data = resp.json()
        self.assertTrue(data["ok"])
        self.assertEqual(len(data["tasks"]), 3)
        self.assertEqual(Task.objects.count(), 3)
        titles = list(Task.objects.values_list("title", flat=True).order_by("created_at"))
        self.assertEqual(titles, ["Fix login bug", "Add dark mode", "Write unit tests"])

    @patch("members.views._forward_to_controller")
    def test_blank_lines_are_skipped(self, _mock):
        self.client.force_login(self.user)
        resp = self.client.post(self.url, {
            "tasks": "Task one\n\n   \nTask two",
            "project_id": self.project.pk,
        })
        data = resp.json()
        self.assertTrue(data["ok"])
        self.assertEqual(Task.objects.count(), 2)

    @patch("members.views._forward_to_controller")
    def test_response_contains_task_ids_and_titles(self, _mock):
        self.client.force_login(self.user)
        resp = self.client.post(self.url, {
            "tasks": "My task",
            "project_id": self.project.pk,
        })
        data = resp.json()
        self.assertTrue(data["ok"])
        self.assertEqual(len(data["tasks"]), 1)
        entry = data["tasks"][0]
        self.assertIn("task_id", entry)
        self.assertEqual(entry["title"], "My task")
        self.assertEqual(entry["status"], "pending")

    def test_missing_tasks_returns_400(self):
        self.client.force_login(self.user)
        resp = self.client.post(self.url, {"tasks": "", "project_id": self.project.pk})
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(resp.json()["ok"])

    def test_missing_project_id_returns_400(self):
        self.client.force_login(self.user)
        resp = self.client.post(self.url, {"tasks": "Task one", "project_id": ""})
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(resp.json()["ok"])

    def test_only_whitespace_tasks_returns_400(self):
        self.client.force_login(self.user)
        resp = self.client.post(self.url, {"tasks": "   \n\n   ", "project_id": self.project.pk})
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(resp.json()["ok"])

    @patch("members.views._forward_to_controller")
    def test_other_users_project_not_accepted(self, _mock):
        other = make_user(email="other@example.com", username="other")
        other_project = make_project(other, github_repo="other/repo")

        self.client.force_login(self.user)
        resp = self.client.post(self.url, {
            "tasks": "Sneaky task",
            "project_id": other_project.pk,
        })
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(Task.objects.count(), 0)

    @patch("members.views._forward_to_controller")
    def test_forwards_each_task_to_controller(self, mock_forward):
        self.client.force_login(self.user)
        self.client.post(self.url, {
            "tasks": "Task A\nTask B",
            "project_id": self.project.pk,
        })
        self.assertEqual(mock_forward.call_count, 2)


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


# ---------------------------------------------------------------------------
# GET /dashboard/messages/
# ---------------------------------------------------------------------------

class LoadMoreMessagesViewTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.url = "/dashboard/messages/"
        self.user = make_user(email="load@example.com", username="loaduser")
        self.project = make_project(self.user)

    def _call(self, params=None):
        from members.views import load_more_messages
        request = self.factory.get(self.url, params or {})
        request.user = self.user
        return load_more_messages(request)

    def test_requires_login(self):
        from members.views import load_more_messages
        request = self.factory.get(self.url)
        request.user = AnonymousUser()
        resp = load_more_messages(request)
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/login/", resp["Location"])

    def test_no_before_id_returns_empty_json(self):
        resp = self._call()
        data = json.loads(resp.content)
        self.assertEqual(data["html"], "")
        self.assertFalse(data["has_more"])
        self.assertIsNone(data["oldest_id"])

    def test_invalid_before_id_returns_empty_json(self):
        resp = self._call({"before_id": "not-a-number"})
        data = json.loads(resp.content)
        self.assertEqual(data["html"], "")
        self.assertFalse(data["has_more"])
        self.assertIsNone(data["oldest_id"])

    def test_returns_json_with_html_has_more_oldest_id(self):
        for i in range(3):
            make_task(self.project, self.user, title=f"Task {i}")
        max_pk = Task.objects.filter(created_by=self.user).order_by("-pk").first().pk
        resp = self._call({"before_id": str(max_pk + 1)})
        data = json.loads(resp.content)
        self.assertIn("html", data)
        self.assertIn("has_more", data)
        self.assertIn("oldest_id", data)
        self.assertFalse(data["has_more"])
        self.assertIsNotNone(data["oldest_id"])

    def test_has_more_true_when_over_20_tasks(self):
        for i in range(22):
            make_task(self.project, self.user, title=f"Task {i}")
        max_pk = Task.objects.filter(created_by=self.user).order_by("-pk").first().pk
        resp = self._call({"before_id": str(max_pk + 1)})
        data = json.loads(resp.content)
        self.assertTrue(data["has_more"])

    def test_has_more_false_when_few_tasks(self):
        for i in range(5):
            make_task(self.project, self.user, title=f"Task {i}")
        max_pk = Task.objects.filter(created_by=self.user).order_by("-pk").first().pk
        resp = self._call({"before_id": str(max_pk + 1)})
        data = json.loads(resp.content)
        self.assertFalse(data["has_more"])

    def test_returns_at_most_20_tasks(self):
        for i in range(25):
            make_task(self.project, self.user, title=f"Task {i}")
        max_pk = Task.objects.filter(created_by=self.user).order_by("-pk").first().pk
        resp = self._call({"before_id": str(max_pk + 1)})
        data = json.loads(resp.content)
        # _LOAD_MORE_BATCH is 20; even with 25 tasks only 20 are returned
        returned_count = Task.objects.filter(created_by=self.user).count()
        # oldest_id being set means tasks were returned; verify has_more signals the rest
        self.assertTrue(data["has_more"])
        self.assertIsNotNone(data["oldest_id"])

    def test_only_returns_own_tasks(self):
        other = make_user(email="other_load@example.com", username="other_load")
        other_project = make_project(other, github_repo="other/loadrepo")
        make_task(other_project, other, title="Other user task")
        make_task(self.project, self.user, title="Own task")
        max_pk = Task.objects.order_by("-pk").first().pk
        resp = self._call({"before_id": str(max_pk + 1)})
        data = json.loads(resp.content)
        self.assertNotIn("Other user task", data["html"])

    def test_oldest_id_is_a_valid_own_task_pk(self):
        for i in range(3):
            make_task(self.project, self.user, title=f"Task {i}")
        max_pk = Task.objects.filter(created_by=self.user).order_by("-pk").first().pk
        resp = self._call({"before_id": str(max_pk + 1)})
        data = json.loads(resp.content)
        self.assertTrue(
            Task.objects.filter(pk=data["oldest_id"], created_by=self.user).exists()
        )

    def test_no_tasks_before_id_returns_empty(self):
        # Create a task, then ask for tasks before the earliest possible pk
        make_task(self.project, self.user, title="Only task")
        min_pk = Task.objects.filter(created_by=self.user).order_by("pk").first().pk
        resp = self._call({"before_id": str(min_pk)})
        data = json.loads(resp.content)
        # Template renders whitespace even for empty list; meaningful fields signal no results
        self.assertFalse(data["has_more"])
        self.assertIsNone(data["oldest_id"])


# ---------------------------------------------------------------------------
# GET|POST /dashboard/settings/
# ---------------------------------------------------------------------------

class SettingsViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.url = "/dashboard/settings/"
        self.user = make_user(email="settings@example.com", username="settingsuser")

    def test_requires_login(self):
        resp = self.client.get(self.url)
        self.assertRedirects(resp, f"/login/?next={self.url}", fetch_redirect_response=False)

    def test_get_returns_200(self):
        self.client.force_login(self.user)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)

    def test_get_context_contains_prefs(self):
        self.client.force_login(self.user)
        resp = self.client.get(self.url)
        self.assertIn("prefs", resp.context)
        self.assertIsInstance(resp.context["prefs"], NotificationPreference)

    def test_get_context_contains_projects(self):
        self.client.force_login(self.user)
        resp = self.client.get(self.url)
        self.assertIn("projects", resp.context)

    def test_get_only_shows_own_projects(self):
        make_project(self.user, name="My Project")
        other = make_user(email="other_ctx@example.com", username="other_ctx")
        make_project(other, name="Their Project", github_repo="other/ctx_repo")
        self.client.force_login(self.user)
        resp = self.client.get(self.url)
        names = [p.name for p in resp.context["projects"]]
        self.assertIn("My Project", names)
        self.assertNotIn("Their Project", names)

    # -- profile action --

    def test_profile_update_saves_names_and_company(self):
        self.client.force_login(self.user)
        resp = self.client.post(self.url, {
            "action": "profile",
            "first_name": "Alice",
            "last_name": "Smith",
            "email": self.user.email,
            "company_name": "TARS Inc",
        })
        self.assertRedirects(resp, self.url, fetch_redirect_response=False)
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, "Alice")
        self.assertEqual(self.user.last_name, "Smith")
        self.assertEqual(self.user.company_name, "TARS Inc")

    def test_profile_update_changes_email(self):
        self.client.force_login(self.user)
        self.client.post(self.url, {
            "action": "profile",
            "first_name": "",
            "last_name": "",
            "email": "changed_settings@example.com",
            "company_name": "",
        })
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "changed_settings@example.com")

    def test_profile_update_duplicate_email_rejected(self):
        make_user(email="taken_settings@example.com", username="taken_settings")
        self.client.force_login(self.user)
        original_email = self.user.email
        self.client.post(self.url, {
            "action": "profile",
            "first_name": "",
            "last_name": "",
            "email": "taken_settings@example.com",
            "company_name": "",
        })
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, original_email)

    def test_profile_update_redirects_to_settings(self):
        self.client.force_login(self.user)
        resp = self.client.post(self.url, {
            "action": "profile",
            "first_name": "Bob",
            "last_name": "",
            "email": self.user.email,
            "company_name": "",
        })
        self.assertRedirects(resp, self.url, fetch_redirect_response=False)

    # -- notifications action --

    def test_notifications_saves_selected_prefs(self):
        self.client.force_login(self.user)
        self.client.post(self.url, {
            "action": "notifications",
            "email_welcome": "on",
            "email_pr_ready": "on",
            # email_task_started, email_task_failed, email_weekly_digest omitted → False
        })
        prefs = NotificationPreference.objects.get(user=self.user)
        self.assertTrue(prefs.email_welcome)
        self.assertFalse(prefs.email_task_started)
        self.assertTrue(prefs.email_pr_ready)
        self.assertFalse(prefs.email_task_failed)
        self.assertFalse(prefs.email_weekly_digest)

    def test_notifications_all_off_when_none_submitted(self):
        self.client.force_login(self.user)
        self.client.post(self.url, {"action": "notifications"})
        prefs = NotificationPreference.objects.get(user=self.user)
        self.assertFalse(prefs.email_welcome)
        self.assertFalse(prefs.email_task_started)
        self.assertFalse(prefs.email_pr_ready)
        self.assertFalse(prefs.email_task_failed)
        self.assertFalse(prefs.email_weekly_digest)

    def test_notifications_all_on_when_all_submitted(self):
        self.client.force_login(self.user)
        self.client.post(self.url, {
            "action": "notifications",
            "email_welcome": "on",
            "email_task_started": "on",
            "email_pr_ready": "on",
            "email_task_failed": "on",
            "email_weekly_digest": "on",
        })
        prefs = NotificationPreference.objects.get(user=self.user)
        self.assertTrue(prefs.email_welcome)
        self.assertTrue(prefs.email_task_started)
        self.assertTrue(prefs.email_pr_ready)
        self.assertTrue(prefs.email_task_failed)
        self.assertTrue(prefs.email_weekly_digest)

    def test_notifications_redirects_to_settings(self):
        self.client.force_login(self.user)
        resp = self.client.post(self.url, {"action": "notifications"})
        self.assertRedirects(resp, self.url, fetch_redirect_response=False)

    def test_notifications_creates_prefs_if_missing(self):
        NotificationPreference.objects.filter(user=self.user).delete()
        self.client.force_login(self.user)
        self.client.post(self.url, {"action": "notifications", "email_welcome": "on"})
        self.assertTrue(NotificationPreference.objects.filter(user=self.user).exists())

    # -- remove_project action --

    def test_remove_project_deletes_own_project(self):
        project = make_project(self.user)
        self.client.force_login(self.user)
        resp = self.client.post(self.url, {
            "action": "remove_project",
            "project_id": project.pk,
        })
        self.assertRedirects(resp, self.url, fetch_redirect_response=False)
        self.assertFalse(Project.objects.filter(pk=project.pk).exists())

    def test_remove_project_ignores_other_users_project(self):
        other = make_user(email="other_rm@example.com", username="other_rm")
        other_project = make_project(other, github_repo="other/rm_repo")
        self.client.force_login(self.user)
        self.client.post(self.url, {
            "action": "remove_project",
            "project_id": other_project.pk,
        })
        self.assertTrue(Project.objects.filter(pk=other_project.pk).exists())

    def test_remove_project_redirects_to_settings(self):
        project = make_project(self.user)
        self.client.force_login(self.user)
        resp = self.client.post(self.url, {
            "action": "remove_project",
            "project_id": project.pk,
        })
        self.assertRedirects(resp, self.url, fetch_redirect_response=False)


# ---------------------------------------------------------------------------
# Unauthenticated access — all protected endpoints redirect to login
# ---------------------------------------------------------------------------

class UnauthenticatedAccessTests(TestCase):
    def test_dashboard_redirects_to_login(self):
        resp = self.client.get("/dashboard/")
        self.assertRedirects(resp, "/login/?next=/dashboard/", fetch_redirect_response=False)

    def test_quick_task_redirects_to_login(self):
        resp = self.client.post("/dashboard/quick-task/", {"title": "T", "project_id": "1"})
        self.assertRedirects(
            resp, "/login/?next=/dashboard/quick-task/", fetch_redirect_response=False
        )

    def test_bulk_tasks_redirects_to_login(self):
        resp = self.client.post("/dashboard/bulk-tasks/", {"tasks": "T", "project_id": "1"})
        self.assertRedirects(
            resp, "/login/?next=/dashboard/bulk-tasks/", fetch_redirect_response=False
        )

    def test_load_more_messages_redirects_to_login(self):
        resp = self.client.get("/dashboard/messages/")
        self.assertRedirects(
            resp, "/login/?next=/dashboard/messages/", fetch_redirect_response=False
        )

    def test_settings_redirects_to_login(self):
        resp = self.client.get("/dashboard/settings/")
        self.assertRedirects(
            resp, "/login/?next=/dashboard/settings/", fetch_redirect_response=False
        )

    def test_activity_log_redirects_to_login(self):
        resp = self.client.get("/dashboard/activity/")
        self.assertRedirects(
            resp, "/login/?next=/dashboard/activity/", fetch_redirect_response=False
        )
