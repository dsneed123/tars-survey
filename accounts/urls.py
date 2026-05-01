from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("login/", views.accounts_login, name="login"),
    path("register/", views.accounts_register, name="register"),
    path("logout/", views.accounts_logout, name="logout"),
    path("verify-email/<uidb64>/<token>/", views.verify_email, name="verify_email"),
    path("verify-email/resend/", views.resend_verification_email, name="resend_verification_email"),
    path("accounts/github/login/", views.github_login, name="github_login"),
    path("accounts/github/callback/", views.github_callback, name="github_callback"),
    # Password reset flow (Django built-in views)
    path(
        "password-reset/",
        auth_views.PasswordResetView.as_view(
            template_name="registration/password_reset_form.html",
            email_template_name="registration/password_reset_email.html",
            html_email_template_name="emails/password_reset_email.html",
            subject_template_name="registration/password_reset_subject.txt",
        ),
        name="password_reset",
    ),
    path(
        "password-reset/done/",
        auth_views.PasswordResetDoneView.as_view(template_name="registration/password_reset_done.html"),
        name="password_reset_done",
    ),
    path(
        "reset/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(template_name="registration/password_reset_confirm.html"),
        name="password_reset_confirm",
    ),
    path(
        "reset/done/",
        auth_views.PasswordResetCompleteView.as_view(template_name="registration/password_reset_complete.html"),
        name="password_reset_complete",
    ),
]
