"""
Integration tests — full user flows across multiple apps.

These tests exercise real end-to-end paths through the application rather
than individual units, catching regressions that unit tests miss.
"""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase

from members.models import MemberProfile
from projects.models import Project
from tasks.models import Task

User = get_user_model()


# ---------------------------------------------------------------------------
# Full user flow: register → dashboard → add project → submit task → view task
# ---------------------------------------------------------------------------

class UserRegistrationFlowTests(TestCase):
    """Register a new account through the web form."""

    def setUp(self):
        self.client = Client()

    @patch("accounts.views.send_welcome_email")
    def test_register_creates_user_and_profile(self, _mock_email):
        resp = self.client.post("/register/", {
            "email": "newuser@example.com",
            "company_name": "Flow Corp",
            "password1": "SecurePass123!",
            "password2": "SecurePass123!",
        })
        self.assertEqual(User.objects.filter(email="newuser@example.com").count(), 1)
        user = User.objects.get(email="newuser@example.com")
        self.assertTrue(MemberProfile.objects.filter(user=user).exists())

    @patch("accounts.views.send_welcome_email")
    def test_register_logs_in_and_redirects_to_dashboard(self, _mock_email):
        resp = self.client.post("/register/", {
            "email": "flowuser@example.com",
            "company_name": "Flow Corp",
            "password1": "SecurePass123!",
            "password2": "SecurePass123!",
        })
        self.assertRedirects(resp, "/dashboard/", fetch_redirect_response=False)
        resp2 = self.client.get("/dashboard/")
        self.assertTrue(resp2.wsgi_request.user.is_authenticated)

    @patch("accounts.views.send_welcome_email")
    def test_register_sets_default_free_plan(self, _mock_email):
        self.client.post("/register/", {
            "email": "freeplan@example.com",
            "company_name": "Free Co",
            "password1": "SecurePass123!",
            "password2": "SecurePass123!",
        })
        user = User.objects.get(email="freeplan@example.com")
        self.assertEqual(user.plan, "free")


class LoginFlowTests(TestCase):
    """Login with existing credentials."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="existing@example.com",
            email="existing@example.com",
            password="TestPass123!",
        )
        MemberProfile.objects.get_or_create(user=self.user)

    def test_login_with_correct_credentials_redirects_to_dashboard(self):
        resp = self.client.post("/login/", {
            "email": "existing@example.com",
            "password": "TestPass123!",
        })
        self.assertRedirects(resp, "/dashboard/", fetch_redirect_response=False)

    def test_login_with_wrong_password_stays_on_login(self):
        resp = self.client.post("/login/", {
            "email": "existing@example.com",
            "password": "WrongPass999!",
        })
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.wsgi_request.user.is_authenticated)

    def test_logout_clears_session_and_redirects(self):
        self.client.force_login(self.user)
        resp = self.client.get("/logout/")
        self.assertRedirects(resp, "/", fetch_redirect_response=False)
        resp2 = self.client.get("/dashboard/")
        self.assertFalse(resp2.wsgi_request.user.is_authenticated)


class AddProjectFlowTests(TestCase):
    """Authenticated user adds a project via the web form."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="projuser@example.com",
            email="projuser@example.com",
            password="TestPass123!",
        )
        MemberProfile.objects.get_or_create(user=self.user)
        self.client.force_login(self.user)

    @patch("projects.forms._repo_exists_on_github", return_value=True)
    def test_add_project_creates_record_and_redirects(self, _mock_gh):
        resp = self.client.post("/dashboard/projects/add/", {
            "name": "Integration Project",
            "github_repo_url": "integrationuser/integration-project",
            "description": "A test project for integration flows",
            "language": "python",
            "default_branch": "main",
        })
        self.assertEqual(Project.objects.filter(owner=self.user).count(), 1)
        project = Project.objects.get(owner=self.user)
        self.assertEqual(project.name, "Integration Project")
        self.assertEqual(project.github_repo, "integrationuser/integration-project")
        self.assertRedirects(
            resp,
            f"/dashboard/projects/{project.pk}/",
            fetch_redirect_response=False,
        )

    @patch("projects.forms._repo_exists_on_github", return_value=True)
    def test_project_owner_is_logged_in_user(self, _mock_gh):
        self.client.post("/dashboard/projects/add/", {
            "name": "Owned Project",
            "github_repo_url": "myuser/owned",
            "description": "",
            "language": "go",
            "default_branch": "main",
        })
        project = Project.objects.get(owner=self.user)
        self.assertEqual(project.owner, self.user)

    @patch("projects.forms._repo_exists_on_github", return_value=True)
    def test_project_visible_on_dashboard(self, _mock_gh):
        self.client.post("/dashboard/projects/add/", {
            "name": "Dashboard Project",
            "github_repo_url": "user/dashboard-repo",
            "description": "",
            "language": "python",
            "default_branch": "main",
        })
        resp = self.client.get("/dashboard/")
        project_names = [p.name for p in resp.context["projects"]]
        self.assertIn("Dashboard Project", project_names)


class SubmitTaskFlowTests(TestCase):
    """Authenticated user submits a task for an existing project."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="taskuser@example.com",
            email="taskuser@example.com",
            password="TestPass123!",
        )
        MemberProfile.objects.get_or_create(user=self.user)
        self.project = Project.objects.create(
            owner=self.user,
            name="Task Project",
            github_repo="taskuser/task-project",
        )
        self.client.force_login(self.user)

    @patch("tasks.views._forward_to_controller")
    def test_submit_task_creates_record(self, _mock_controller):
        self.client.post("/dashboard/tasks/new/", {
            "project": self.project.pk,
            "title": "Add dark mode",
            "description": "Implement a dark mode toggle in the settings page.",
            "priority": 60,
        })
        self.assertEqual(Task.objects.filter(created_by=self.user).count(), 1)
        task = Task.objects.get(created_by=self.user)
        self.assertEqual(task.title, "Add dark mode")
        self.assertEqual(task.project, self.project)
        self.assertEqual(task.status, "pending")

    @patch("tasks.views._forward_to_controller")
    def test_submit_task_redirects_to_task_detail(self, _mock_controller):
        resp = self.client.post("/dashboard/tasks/new/", {
            "project": self.project.pk,
            "title": "Fix the login bug",
            "description": "Users cannot log in when using Safari.",
            "priority": 80,
        })
        task = Task.objects.get(created_by=self.user)
        self.assertRedirects(
            resp,
            f"/dashboard/tasks/{task.pk}/",
            fetch_redirect_response=False,
        )

    @patch("tasks.views._forward_to_controller")
    def test_task_visible_on_task_list(self, _mock_controller):
        self.client.post("/dashboard/tasks/new/", {
            "project": self.project.pk,
            "title": "Visible task",
            "description": "This should appear in the list.",
            "priority": 50,
        })
        resp = self.client.get("/dashboard/tasks/")
        task_titles = [t.title for t in resp.context["tasks"]]
        self.assertIn("Visible task", task_titles)

    @patch("tasks.views._forward_to_controller")
    def test_task_visible_on_dashboard(self, _mock_controller):
        self.client.post("/dashboard/tasks/new/", {
            "project": self.project.pk,
            "title": "Dashboard visible task",
            "description": "Should appear on dashboard.",
            "priority": 50,
        })
        resp = self.client.get("/dashboard/")
        task_titles = [t.title for t in resp.context["recent_tasks"]]
        self.assertIn("Dashboard visible task", task_titles)


class CheckTaskStatusFlowTests(TestCase):
    """User views task detail page and sees status progression."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="statususer@example.com",
            email="statususer@example.com",
            password="TestPass123!",
        )
        MemberProfile.objects.get_or_create(user=self.user)
        self.project = Project.objects.create(
            owner=self.user,
            name="Status Project",
            github_repo="statususer/status-project",
        )
        self.task = Task.objects.create(
            project=self.project,
            created_by=self.user,
            title="Status check task",
            description="Check the task status flow.",
            status="pending",
            priority=50,
        )
        self.client.force_login(self.user)

    def test_task_detail_returns_200(self):
        resp = self.client.get(f"/dashboard/tasks/{self.task.pk}/")
        self.assertEqual(resp.status_code, 200)

    def test_task_detail_shows_correct_task(self):
        resp = self.client.get(f"/dashboard/tasks/{self.task.pk}/")
        self.assertEqual(resp.context["task"].title, "Status check task")

    def test_task_detail_shows_timeline(self):
        resp = self.client.get(f"/dashboard/tasks/{self.task.pk}/")
        timeline = resp.context["timeline"]
        self.assertIsInstance(timeline, list)
        self.assertGreater(len(timeline), 0)
        statuses = [step["status"] for step in timeline]
        self.assertIn("pending", statuses)

    def test_pending_task_shows_pending_as_current_in_timeline(self):
        resp = self.client.get(f"/dashboard/tasks/{self.task.pk}/")
        timeline = resp.context["timeline"]
        pending_step = next((s for s in timeline if s["status"] == "pending"), None)
        self.assertIsNotNone(pending_step)
        self.assertEqual(pending_step["state"], "current")

    def test_completed_task_shows_done_state(self):
        self.task.status = "completed"
        self.task.save()
        resp = self.client.get(f"/dashboard/tasks/{self.task.pk}/")
        timeline = resp.context["timeline"]
        completed_step = next((s for s in timeline if s["status"] == "completed"), None)
        self.assertIsNotNone(completed_step)
        self.assertIn(completed_step["state"], ("done", "current"))

    def test_other_user_cannot_view_task(self):
        other = User.objects.create_user(
            username="intruder@example.com",
            email="intruder@example.com",
            password="TestPass123!",
        )
        MemberProfile.objects.get_or_create(user=other)
        self.client.force_login(other)
        resp = self.client.get(f"/dashboard/tasks/{self.task.pk}/")
        self.assertEqual(resp.status_code, 404)


class FullEndToEndFlowTests(TestCase):
    """
    Full end-to-end: register → dashboard → add project →
    submit task → check task detail.
    """

    def setUp(self):
        self.client = Client()

    @patch("accounts.views.send_welcome_email")
    @patch("projects.forms._repo_exists_on_github", return_value=True)
    @patch("tasks.views._forward_to_controller")
    def test_full_user_journey(self, _mock_controller, _mock_gh, _mock_email):
        # Step 1: Register
        resp = self.client.post("/register/", {
            "email": "journey@example.com",
            "company_name": "Journey Corp",
            "password1": "SecurePass123!",
            "password2": "SecurePass123!",
        })
        self.assertRedirects(resp, "/dashboard/", fetch_redirect_response=False)

        user = User.objects.get(email="journey@example.com")
        self.assertTrue(MemberProfile.objects.filter(user=user).exists())

        # Step 2: Dashboard accessible
        resp = self.client.get("/dashboard/")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.wsgi_request.user.is_authenticated)

        # Step 3: Add project
        resp = self.client.post("/dashboard/projects/add/", {
            "name": "Journey Project",
            "github_repo_url": "journey/journey-project",
            "description": "End-to-end test project",
            "language": "python",
            "default_branch": "main",
        })
        project = Project.objects.get(owner=user)
        self.assertEqual(project.name, "Journey Project")

        # Step 4: Submit task
        resp = self.client.post("/dashboard/tasks/new/", {
            "project": project.pk,
            "title": "Journey task",
            "description": "Implement the feature described in the issue.",
            "priority": 70,
        })
        task = Task.objects.get(created_by=user)
        self.assertEqual(task.title, "Journey task")
        self.assertEqual(task.status, "pending")
        self.assertRedirects(
            resp,
            f"/dashboard/tasks/{task.pk}/",
            fetch_redirect_response=False,
        )

        # Step 5: View task detail and confirm timeline
        resp = self.client.get(f"/dashboard/tasks/{task.pk}/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context["task"].title, "Journey task")
        timeline = resp.context["timeline"]
        pending_step = next((s for s in timeline if s["status"] == "pending"), None)
        self.assertIsNotNone(pending_step)
        self.assertEqual(pending_step["state"], "current")

        # Step 6: Task appears in list filtered by project
        resp = self.client.get("/dashboard/tasks/", {"project": project.pk})
        task_titles = [t.title for t in resp.context["tasks"]]
        self.assertIn("Journey task", task_titles)

        # Step 7: Project shows in project list
        resp = self.client.get("/dashboard/projects/")
        project_names = [p.name for p in resp.context["projects"]]
        self.assertIn("Journey Project", project_names)


class UnauthenticatedAccessTests(TestCase):
    """Verify all protected views redirect unauthenticated users to login."""

    def setUp(self):
        self.client = Client()

    def _assert_redirects_to_login(self, url):
        resp = self.client.get(url)
        self.assertRedirects(
            resp,
            f"/login/?next={url}",
            fetch_redirect_response=False,
            msg_prefix=f"Expected {url} to redirect to login",
        )

    def test_dashboard_requires_login(self):
        self._assert_redirects_to_login("/dashboard/")

    def test_projects_list_requires_login(self):
        self._assert_redirects_to_login("/dashboard/projects/")

    def test_project_add_requires_login(self):
        self._assert_redirects_to_login("/dashboard/projects/add/")

    def test_tasks_list_requires_login(self):
        self._assert_redirects_to_login("/dashboard/tasks/")

    def test_task_add_requires_login(self):
        self._assert_redirects_to_login("/dashboard/tasks/new/")

    def test_billing_requires_login(self):
        self._assert_redirects_to_login("/dashboard/billing/")

    def test_notification_settings_requires_login(self):
        self._assert_redirects_to_login("/dashboard/settings/notifications/")


class GitHubOAuthFlowTests(TestCase):
    """GitHub OAuth login and registration flow."""

    def setUp(self):
        self.client = Client()

    def test_github_login_redirects_to_github_authorize(self):
        with self.settings(GITHUB_CLIENT_ID="test_client_id"):
            resp = self.client.get("/accounts/github/login/")
        self.assertEqual(resp.status_code, 302)
        self.assertIn("github.com/login/oauth/authorize", resp["Location"])
        self.assertIn("test_client_id", resp["Location"])
        self.assertIn("user", resp["Location"])

    def test_github_login_without_client_id_redirects_to_login(self):
        with self.settings(GITHUB_CLIENT_ID=""):
            resp = self.client.get("/accounts/github/login/")
        self.assertRedirects(resp, "/login/", fetch_redirect_response=False)

    def test_github_login_stores_state_in_session(self):
        with self.settings(GITHUB_CLIENT_ID="test_client_id"):
            self.client.get("/accounts/github/login/")
        self.assertIn("github_oauth_state", self.client.session)

    def test_github_callback_with_missing_state_redirects_to_login(self):
        resp = self.client.get("/accounts/github/callback/?code=abc")
        self.assertRedirects(resp, "/login/", fetch_redirect_response=False)

    def test_github_callback_with_wrong_state_redirects_to_login(self):
        session = self.client.session
        session["github_oauth_state"] = "correct_state"
        session.save()
        resp = self.client.get("/accounts/github/callback/?code=abc&state=wrong_state")
        self.assertRedirects(resp, "/login/", fetch_redirect_response=False)

    def test_github_callback_without_code_redirects_to_login(self):
        session = self.client.session
        session["github_oauth_state"] = "mystate"
        session.save()
        resp = self.client.get("/accounts/github/callback/?state=mystate")
        self.assertRedirects(resp, "/login/", fetch_redirect_response=False)

    @patch("accounts.views.send_welcome_email")
    @patch("accounts.views.requests.get")
    @patch("accounts.views.requests.post")
    def test_github_callback_creates_new_user(self, mock_post, mock_get, _mock_email):
        mock_post.return_value.json.return_value = {"access_token": "gh_token_123"}
        mock_get.return_value.json.return_value = {
            "id": 99999,
            "login": "ghuser",
            "avatar_url": "https://avatars.githubusercontent.com/u/99999",
            "email": "ghuser@example.com",
        }

        session = self.client.session
        session["github_oauth_state"] = "validstate"
        session.save()

        with self.settings(GITHUB_CLIENT_ID="cid", GITHUB_CLIENT_SECRET="csecret"):
            resp = self.client.get("/accounts/github/callback/?code=abc&state=validstate")

        self.assertRedirects(resp, "/dashboard/", fetch_redirect_response=False)
        user = User.objects.get(github_id=99999)
        self.assertEqual(user.github_username, "ghuser")
        self.assertEqual(user.github_avatar_url, "https://avatars.githubusercontent.com/u/99999")
        self.assertEqual(user.email, "ghuser@example.com")
        self.assertTrue(user.is_email_verified)
        self.assertTrue(MemberProfile.objects.filter(user=user).exists())

    @patch("accounts.views.send_welcome_email")
    @patch("accounts.views.requests.get")
    @patch("accounts.views.requests.post")
    def test_github_callback_links_existing_email_account(self, mock_post, mock_get, _mock_email):
        existing = User.objects.create_user(
            username="emailuser",
            email="shared@example.com",
            password="pass",
        )
        MemberProfile.objects.get_or_create(user=existing)

        mock_post.return_value.json.return_value = {"access_token": "gh_token_456"}
        mock_get.return_value.json.return_value = {
            "id": 88888,
            "login": "ghlinker",
            "avatar_url": "https://avatars.githubusercontent.com/u/88888",
            "email": "shared@example.com",
        }

        session = self.client.session
        session["github_oauth_state"] = "linkstate"
        session.save()

        with self.settings(GITHUB_CLIENT_ID="cid", GITHUB_CLIENT_SECRET="csecret"):
            resp = self.client.get("/accounts/github/callback/?code=abc&state=linkstate")

        self.assertRedirects(resp, "/dashboard/", fetch_redirect_response=False)
        existing.refresh_from_db()
        self.assertEqual(existing.github_id, 88888)
        self.assertEqual(existing.github_username, "ghlinker")
        self.assertTrue(existing.is_email_verified)
        self.assertEqual(User.objects.filter(email="shared@example.com").count(), 1)

    @patch("accounts.views.requests.get")
    @patch("accounts.views.requests.post")
    def test_github_callback_logs_in_existing_github_user(self, mock_post, mock_get):
        existing = User.objects.create_user(
            username="ghreturner",
            email="returner@example.com",
            password=None,
            github_id=77777,
            github_username="oldname",
            github_avatar_url="https://old.url/",
        )
        MemberProfile.objects.get_or_create(user=existing)

        mock_post.return_value.json.return_value = {"access_token": "gh_token_789"}
        mock_get.return_value.json.return_value = {
            "id": 77777,
            "login": "newname",
            "avatar_url": "https://new.url/",
            "email": "returner@example.com",
        }

        session = self.client.session
        session["github_oauth_state"] = "returnstate"
        session.save()

        with self.settings(GITHUB_CLIENT_ID="cid", GITHUB_CLIENT_SECRET="csecret"):
            resp = self.client.get("/accounts/github/callback/?code=abc&state=returnstate")

        self.assertRedirects(resp, "/dashboard/", fetch_redirect_response=False)
        self.assertEqual(User.objects.filter(github_id=77777).count(), 1)
        existing.refresh_from_db()
        self.assertEqual(existing.github_username, "newname")
        self.assertEqual(existing.github_avatar_url, "https://new.url/")

    @patch("accounts.views.requests.post")
    def test_github_callback_handles_token_exchange_failure(self, mock_post):
        mock_post.return_value.json.return_value = {"error": "bad_verification_code"}

        session = self.client.session
        session["github_oauth_state"] = "errstate"
        session.save()

        with self.settings(GITHUB_CLIENT_ID="cid", GITHUB_CLIENT_SECRET="csecret"):
            resp = self.client.get("/accounts/github/callback/?code=bad&state=errstate")

        self.assertRedirects(resp, "/login/", fetch_redirect_response=False)
        self.assertFalse(resp.wsgi_request.user.is_authenticated)

    def test_authenticated_user_github_login_redirects_to_dashboard(self):
        user = User.objects.create_user(username="loggedin", email="li@example.com", password="pass")
        MemberProfile.objects.get_or_create(user=user)
        self.client.force_login(user)
        with self.settings(GITHUB_CLIENT_ID="cid"):
            resp = self.client.get("/accounts/github/login/")
        self.assertRedirects(resp, "/dashboard/", fetch_redirect_response=False)
