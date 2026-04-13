from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase

from members.models import MemberProfile
from projects.forms import ProjectForm
from projects.models import Project
from tasks.models import Task

User = get_user_model()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_user(email="owner@example.com", password="TestPass123!", **kwargs):
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


# ---------------------------------------------------------------------------
# Project model
# ---------------------------------------------------------------------------

class ProjectModelTests(TestCase):
    def setUp(self):
        self.user = make_user()

    def test_str_representation(self):
        p = make_project(self.user, name="My App", github_repo="user/myapp")
        self.assertIn("My App", str(p))
        self.assertIn("user/myapp", str(p))

    def test_github_url_property(self):
        p = make_project(self.user, github_repo="acme/widget")
        self.assertEqual(p.github_url, "https://github.com/acme/widget")

    def test_default_is_active(self):
        p = make_project(self.user)
        self.assertTrue(p.is_active)

    def test_default_language_is_other(self):
        p = make_project(self.user)
        self.assertEqual(p.language, "other")

    def test_ordering_newest_first(self):
        p1 = make_project(self.user, name="First", github_repo="u/first")
        p2 = make_project(self.user, name="Second", github_repo="u/second")
        projects = list(Project.objects.filter(owner=self.user))
        self.assertEqual(projects[0].name, "Second")
        self.assertEqual(projects[1].name, "First")

    def test_cascade_delete_with_user(self):
        make_project(self.user)
        self.user.delete()
        self.assertEqual(Project.objects.count(), 0)

    def test_cascade_delete_tasks_with_project(self):
        p = make_project(self.user)
        Task.objects.create(project=p, created_by=self.user, title="T", description="D")
        p.delete()
        self.assertEqual(Task.objects.count(), 0)


# ---------------------------------------------------------------------------
# ProjectForm
# ---------------------------------------------------------------------------

class ProjectFormTests(TestCase):
    def _valid_data(self, **overrides):
        data = {
            "name": "My Project",
            "description": "A test",
            "language": "python",
            "default_branch": "main",
            "github_repo_url": "owner/repo",
        }
        data.update(overrides)
        return data

    @patch("projects.forms._repo_exists_on_github", return_value=True)
    def test_valid_form(self, _mock):
        form = ProjectForm(data=self._valid_data())
        self.assertTrue(form.is_valid())

    @patch("projects.forms._repo_exists_on_github", return_value=False)
    def test_nonexistent_repo_rejected(self, _mock):
        form = ProjectForm(data=self._valid_data())
        self.assertFalse(form.is_valid())
        self.assertIn("github_repo_url", form.errors)

    @patch("projects.forms._repo_exists_on_github", return_value=True)
    def test_full_github_url_parsed_to_slug(self, _mock):
        form = ProjectForm(data=self._valid_data(github_repo_url="https://github.com/owner/repo"))
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data["github_repo_url"], "owner/repo")

    @patch("projects.forms._repo_exists_on_github", return_value=True)
    def test_github_url_with_git_suffix_parsed(self, _mock):
        form = ProjectForm(data=self._valid_data(github_repo_url="https://github.com/owner/repo.git"))
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data["github_repo_url"], "owner/repo")

    def test_invalid_repo_format_rejected(self):
        form = ProjectForm(data=self._valid_data(github_repo_url="not-valid-at-all"))
        self.assertFalse(form.is_valid())

    @patch("projects.forms._repo_exists_on_github", return_value=None)
    def test_network_error_allows_through(self, _mock):
        # None return means network error — form should still be valid
        form = ProjectForm(data=self._valid_data())
        self.assertTrue(form.is_valid())

    @patch("projects.forms._repo_exists_on_github", return_value=True)
    def test_missing_name_rejected(self, _mock):
        form = ProjectForm(data=self._valid_data(name=""))
        self.assertFalse(form.is_valid())
        self.assertIn("name", form.errors)

    @patch("projects.forms._repo_exists_on_github", return_value=True)
    def test_save_sets_github_repo(self, _mock):
        form = ProjectForm(data=self._valid_data())
        self.assertTrue(form.is_valid())
        project = form.save(commit=False)
        self.assertEqual(project.github_repo, "owner/repo")


# ---------------------------------------------------------------------------
# GET /dashboard/projects/
# ---------------------------------------------------------------------------

class ProjectListViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.url = "/dashboard/projects/"
        self.user = make_user()

    def test_requires_login(self):
        resp = self.client.get(self.url)
        self.assertRedirects(resp, f"/login/?next={self.url}", fetch_redirect_response=False)

    def test_returns_200_for_logged_in_user(self):
        self.client.force_login(self.user)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)

    def test_only_shows_own_projects(self):
        make_project(self.user, name="Mine")
        other = make_user(email="other@example.com", username="other")
        make_project(other, name="Theirs", github_repo="other/repo")

        self.client.force_login(self.user)
        resp = self.client.get(self.url)
        projects = list(resp.context["projects"])
        self.assertEqual(len(projects), 1)
        self.assertEqual(projects[0].name, "Mine")


# ---------------------------------------------------------------------------
# GET/POST /dashboard/projects/add/
# ---------------------------------------------------------------------------

class ProjectAddViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.url = "/dashboard/projects/add/"
        self.user = make_user()

    def test_requires_login(self):
        resp = self.client.get(self.url)
        self.assertRedirects(resp, f"/login/?next={self.url}", fetch_redirect_response=False)

    def test_get_returns_200(self):
        self.client.force_login(self.user)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)

    @patch("projects.forms._repo_exists_on_github", return_value=True)
    def test_post_creates_project(self, _mock):
        self.client.force_login(self.user)
        resp = self.client.post(self.url, {
            "name": "New Project",
            "github_repo_url": "owner/new-repo",
            "description": "A test project",
            "language": "python",
            "default_branch": "main",
        })
        self.assertEqual(Project.objects.filter(owner=self.user).count(), 1)
        project = Project.objects.get(owner=self.user)
        self.assertEqual(project.name, "New Project")
        self.assertEqual(project.github_repo, "owner/new-repo")

    @patch("projects.forms._repo_exists_on_github", return_value=True)
    def test_post_redirects_to_detail(self, _mock):
        self.client.force_login(self.user)
        resp = self.client.post(self.url, {
            "name": "New Project",
            "github_repo_url": "owner/new-repo",
            "description": "",
            "language": "python",
            "default_branch": "main",
        })
        project = Project.objects.get(owner=self.user)
        self.assertRedirects(
            resp,
            f"/dashboard/projects/{project.pk}/",
            fetch_redirect_response=False,
        )

    @patch("projects.forms._repo_exists_on_github", return_value=False)
    def test_post_invalid_repo_stays_on_form(self, _mock):
        self.client.force_login(self.user)
        resp = self.client.post(self.url, {
            "name": "Bad Project",
            "github_repo_url": "owner/nonexistent",
            "description": "",
            "language": "python",
            "default_branch": "main",
        })
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(Project.objects.count(), 0)

    def test_post_malformed_repo_url_rejected(self):
        self.client.force_login(self.user)
        resp = self.client.post(self.url, {
            "name": "Bad",
            "github_repo_url": "not-a-valid-repo",
            "description": "",
            "language": "python",
            "default_branch": "main",
        })
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(Project.objects.count(), 0)

    def test_post_sets_owner_to_current_user(self):
        with patch("projects.forms._repo_exists_on_github", return_value=True):
            self.client.force_login(self.user)
            self.client.post(self.url, {
                "name": "Owned Project",
                "github_repo_url": "owner/my-repo",
                "description": "",
                "language": "python",
                "default_branch": "main",
            })
        project = Project.objects.get()
        self.assertEqual(project.owner, self.user)


# ---------------------------------------------------------------------------
# GET /dashboard/projects/<pk>/
# ---------------------------------------------------------------------------

class ProjectDetailViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = make_user()
        self.project = make_project(self.user)
        self.url = f"/dashboard/projects/{self.project.pk}/"

    def test_requires_login(self):
        resp = self.client.get(self.url)
        self.assertRedirects(resp, f"/login/?next={self.url}", fetch_redirect_response=False)

    @patch("projects.views._github_request", return_value=None)
    def test_returns_200_for_owner(self, _mock):
        self.client.force_login(self.user)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)

    @patch("projects.views._github_request", return_value=None)
    def test_returns_404_for_other_user(self, _mock):
        other = make_user(email="other@example.com", username="other")
        self.client.force_login(other)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 404)

    @patch("projects.views._github_request", return_value=None)
    def test_context_contains_project(self, _mock):
        self.client.force_login(self.user)
        resp = self.client.get(self.url)
        self.assertEqual(resp.context["project"], self.project)


# ---------------------------------------------------------------------------
# GET/POST /dashboard/projects/<pk>/settings/
# ---------------------------------------------------------------------------

class ProjectSettingsViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = make_user()
        self.project = make_project(self.user)
        self.url = f"/dashboard/projects/{self.project.pk}/settings/"

    def test_requires_login(self):
        resp = self.client.get(self.url)
        self.assertRedirects(resp, f"/login/?next={self.url}", fetch_redirect_response=False)

    def test_get_returns_200_for_owner(self):
        self.client.force_login(self.user)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)

    def test_get_returns_404_for_other_user(self):
        other = make_user(email="other@example.com", username="other")
        self.client.force_login(other)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 404)

    @patch("projects.forms._repo_exists_on_github", return_value=True)
    def test_post_updates_project(self, _mock):
        self.client.force_login(self.user)
        self.client.post(self.url, {
            "name": "Updated Name",
            "github_repo_url": self.project.github_repo,
            "description": "New desc",
            "language": "javascript",
            "default_branch": "develop",
        })
        self.project.refresh_from_db()
        self.assertEqual(self.project.name, "Updated Name")
        self.assertEqual(self.project.language, "javascript")

    def test_delete_removes_project(self):
        self.client.force_login(self.user)
        resp = self.client.post(self.url, {"delete": "1"})
        self.assertFalse(Project.objects.filter(pk=self.project.pk).exists())
        self.assertRedirects(resp, "/dashboard/projects/", fetch_redirect_response=False)


# ---------------------------------------------------------------------------
# POST /dashboard/projects/<pk>/rollback/
# ---------------------------------------------------------------------------

class ProjectRollbackViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = make_user()
        self.project = make_project(self.user)
        self.url = f"/dashboard/projects/{self.project.pk}/rollback/"

    def test_requires_login(self):
        resp = self.client.post(self.url, {"sha": "abc1234"})
        self.assertRedirects(resp, f"/login/?next={self.url}", fetch_redirect_response=False)

    def test_post_creates_revert_task(self):
        self.client.force_login(self.user)
        resp = self.client.post(self.url, {"sha": "abc1234def5678", "message": "Fix bug"})
        self.assertEqual(Task.objects.filter(project=self.project).count(), 1)
        task = Task.objects.get(project=self.project)
        self.assertIn("abc1234", task.title)

    def test_post_invalid_sha_redirects_with_error(self):
        self.client.force_login(self.user)
        resp = self.client.post(self.url, {"sha": "bad"})
        self.assertEqual(Task.objects.count(), 0)
        self.assertRedirects(
            resp,
            f"/dashboard/projects/{self.project.pk}/",
            fetch_redirect_response=False,
        )

    def test_get_not_allowed(self):
        self.client.force_login(self.user)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 405)
