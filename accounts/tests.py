from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase

from accounts.forms import LoginForm, RegisterForm
from members.models import MemberProfile

User = get_user_model()


def make_user(email="test@example.com", password="TestPass123!", **kwargs):
    username = kwargs.pop("username", email)
    user = User.objects.create_user(username=username, email=email, password=password, **kwargs)
    MemberProfile.objects.get_or_create(user=user)
    return user


# ---------------------------------------------------------------------------
# CustomUser model
# ---------------------------------------------------------------------------

class CustomUserModelTests(TestCase):
    def test_str_returns_email(self):
        user = make_user(email="me@example.com", username="me@example.com")
        self.assertEqual(str(user), "me@example.com")

    def test_default_plan_is_free(self):
        user = make_user(email="plan@example.com", username="plan@example.com")
        self.assertEqual(user.plan, "free")

    def test_company_name_blank_by_default(self):
        user = User.objects.create_user(
            username="bare", email="bare@example.com", password="TestPass123!"
        )
        self.assertEqual(user.company_name, "")

    def test_str_falls_back_to_username_when_no_email(self):
        user = User.objects.create_user(username="noemail", password="TestPass123!")
        user.email = ""
        user.save()
        self.assertEqual(str(user), "noemail")

    def test_plan_choices_include_all_tiers(self):
        plan_keys = [k for k, _ in User.PLAN_CHOICES]
        self.assertIn("free", plan_keys)
        self.assertIn("starter", plan_keys)
        self.assertIn("pro", plan_keys)
        self.assertIn("enterprise", plan_keys)

    def test_created_at_auto_set(self):
        user = make_user(email="ts@example.com", username="ts@example.com")
        self.assertIsNotNone(user.created_at)


# ---------------------------------------------------------------------------
# LoginForm
# ---------------------------------------------------------------------------

class LoginFormTests(TestCase):
    def test_valid_form(self):
        form = LoginForm(data={"email": "user@example.com", "password": "TestPass123!"})
        self.assertTrue(form.is_valid())

    def test_missing_email_invalid(self):
        form = LoginForm(data={"email": "", "password": "TestPass123!"})
        self.assertFalse(form.is_valid())
        self.assertIn("email", form.errors)

    def test_missing_password_invalid(self):
        form = LoginForm(data={"email": "user@example.com", "password": ""})
        self.assertFalse(form.is_valid())
        self.assertIn("password", form.errors)

    def test_invalid_email_format_rejected(self):
        form = LoginForm(data={"email": "not-an-email", "password": "TestPass123!"})
        self.assertFalse(form.is_valid())


# ---------------------------------------------------------------------------
# RegisterForm
# ---------------------------------------------------------------------------

class RegisterFormTests(TestCase):
    def _valid_data(self, **overrides):
        data = {
            "email": "new@example.com",
            "company_name": "Acme Corp",
            "password1": "SecurePass123!",
            "password2": "SecurePass123!",
        }
        data.update(overrides)
        return data

    def test_valid_form(self):
        form = RegisterForm(data=self._valid_data())
        self.assertTrue(form.is_valid())

    def test_passwords_must_match(self):
        form = RegisterForm(data=self._valid_data(password2="DifferentPass999!"))
        self.assertFalse(form.is_valid())
        self.assertIn("password2", form.errors)

    def test_duplicate_email_rejected(self):
        User.objects.create_user(
            username="existing@example.com",
            email="existing@example.com",
            password="TestPass123!",
        )
        form = RegisterForm(data=self._valid_data(email="existing@example.com"))
        self.assertFalse(form.is_valid())
        self.assertIn("email", form.errors)

    def test_weak_password_rejected(self):
        form = RegisterForm(data=self._valid_data(password1="password", password2="password"))
        self.assertFalse(form.is_valid())

    def test_save_creates_user_with_correct_fields(self):
        form = RegisterForm(data=self._valid_data())
        self.assertTrue(form.is_valid())
        user = form.save()
        self.assertEqual(user.email, "new@example.com")
        self.assertTrue(user.check_password("SecurePass123!"))

    def test_email_lowercased_on_save(self):
        form = RegisterForm(data=self._valid_data(email="UPPER@EXAMPLE.COM",
                                                   password2="SecurePass123!"))
        self.assertTrue(form.is_valid())
        user = form.save()
        self.assertEqual(user.email, "upper@example.com")


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
