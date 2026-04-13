from django.contrib.auth import get_user_model
from django.test import Client, TestCase

from members.models import MemberProfile

User = get_user_model()


def make_user(email="test@example.com", password="TestPass123!", **kwargs):
    username = kwargs.pop("username", email)
    return User.objects.create_user(username=username, email=email, password=password, **kwargs)


# ---------------------------------------------------------------------------
# GET /login/
# ---------------------------------------------------------------------------

class LoginViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.url = "/login/"
        self.user = make_user()

    def test_get_returns_200(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)

    def test_authenticated_user_redirected(self):
        self.client.force_login(self.user)
        resp = self.client.get(self.url)
        self.assertRedirects(resp, "/dashboard/", fetch_redirect_response=False)

    def test_login_success_redirects_to_dashboard(self):
        resp = self.client.post(self.url, {"email": "test@example.com", "password": "TestPass123!"})
        self.assertRedirects(resp, "/dashboard/", fetch_redirect_response=False)

    def test_login_success_authenticates_user(self):
        self.client.post(self.url, {"email": "test@example.com", "password": "TestPass123!"})
        resp = self.client.get("/dashboard/")
        self.assertEqual(resp.wsgi_request.user, self.user)

    def test_login_invalid_password_stays_on_page(self):
        resp = self.client.post(self.url, {"email": "test@example.com", "password": "wrongpass"})
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.wsgi_request.user.is_authenticated)

    def test_login_unknown_email_stays_on_page(self):
        resp = self.client.post(self.url, {"email": "nobody@example.com", "password": "TestPass123!"})
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.wsgi_request.user.is_authenticated)

    def test_login_missing_email_shows_form_error(self):
        resp = self.client.post(self.url, {"email": "", "password": "TestPass123!"})
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.wsgi_request.user.is_authenticated)

    def test_next_param_respected(self):
        resp = self.client.post(
            self.url + "?next=/dashboard/projects/",
            {"email": "test@example.com", "password": "TestPass123!"},
        )
        self.assertRedirects(resp, "/dashboard/projects/", fetch_redirect_response=False)


# ---------------------------------------------------------------------------
# GET /register/
# ---------------------------------------------------------------------------

class RegisterViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.url = "/register/"

    def test_get_returns_200(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)

    def test_authenticated_user_redirected(self):
        user = make_user()
        self.client.force_login(user)
        resp = self.client.get(self.url)
        self.assertRedirects(resp, "/dashboard/", fetch_redirect_response=False)

    def test_register_success_creates_user(self):
        resp = self.client.post(self.url, {
            "email": "new@example.com",
            "company_name": "Acme Corp",
            "password1": "SecurePass123!",
            "password2": "SecurePass123!",
        })
        self.assertEqual(User.objects.filter(email="new@example.com").count(), 1)

    def test_register_success_creates_member_profile(self):
        self.client.post(self.url, {
            "email": "new@example.com",
            "company_name": "Acme Corp",
            "password1": "SecurePass123!",
            "password2": "SecurePass123!",
        })
        user = User.objects.get(email="new@example.com")
        self.assertTrue(MemberProfile.objects.filter(user=user).exists())

    def test_register_success_logs_in_user(self):
        self.client.post(self.url, {
            "email": "new@example.com",
            "company_name": "Acme Corp",
            "password1": "SecurePass123!",
            "password2": "SecurePass123!",
        })
        resp = self.client.get("/dashboard/")
        self.assertTrue(resp.wsgi_request.user.is_authenticated)

    def test_register_passwords_mismatch(self):
        resp = self.client.post(self.url, {
            "email": "new@example.com",
            "company_name": "Acme Corp",
            "password1": "SecurePass123!",
            "password2": "DifferentPass456!",
        })
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(User.objects.filter(email="new@example.com").count(), 0)

    def test_register_duplicate_email_rejected(self):
        make_user(email="existing@example.com")
        resp = self.client.post(self.url, {
            "email": "existing@example.com",
            "company_name": "Corp",
            "password1": "SecurePass123!",
            "password2": "SecurePass123!",
        })
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(User.objects.filter(email="existing@example.com").count(), 1)

    def test_register_weak_password_rejected(self):
        resp = self.client.post(self.url, {
            "email": "new@example.com",
            "company_name": "Corp",
            "password1": "password",
            "password2": "password",
        })
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(User.objects.filter(email="new@example.com").count(), 0)


# ---------------------------------------------------------------------------
# POST /logout/
# ---------------------------------------------------------------------------

class LogoutViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.url = "/logout/"
        self.user = make_user()

    def test_logout_redirects_to_landing(self):
        self.client.force_login(self.user)
        resp = self.client.get(self.url)
        self.assertRedirects(resp, "/", fetch_redirect_response=False)

    def test_logout_ends_session(self):
        self.client.force_login(self.user)
        self.client.get(self.url)
        resp = self.client.get("/dashboard/")
        self.assertFalse(resp.wsgi_request.user.is_authenticated)
