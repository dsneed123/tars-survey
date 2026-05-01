import logging
import re
import secrets

import requests
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from django_ratelimit.decorators import ratelimit

from analytics.utils import fire_event
from members.models import MemberProfile
from notifications.utils import send_verification_email, send_welcome_email

from .forms import LoginForm, RegisterForm
from .models import CustomUser
from .tokens import email_verification_token

logger = logging.getLogger(__name__)

_GITHUB_AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
_GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
_GITHUB_API_URL = "https://api.github.com"


@ratelimit(key="ip", rate="5/m", method=["POST"], block=False)
def accounts_login(request):
    if getattr(request, "limited", False):
        form = LoginForm()
        form.add_error(None, "Too many login attempts. Please wait a minute before trying again.")
        response = render(request, "accounts/login.html", {"form": form})
        response.status_code = 429
        response["Retry-After"] = "60"
        return response
    if request.user.is_authenticated:
        return redirect("members:dashboard")
    if request.method == "POST":
        form = LoginForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data["email"].lower()
            password = form.cleaned_data["password"]
            try:
                user_obj = CustomUser.objects.get(email__iexact=email)
                user = authenticate(request, username=user_obj.username, password=password)
            except CustomUser.DoesNotExist:
                user = None
            if user:
                login(request, user)
                next_url = request.GET.get("next") or "members:dashboard"
                return redirect(next_url)
            form.add_error(None, "Invalid email or password.")
    else:
        form = LoginForm()
    return render(request, "accounts/login.html", {"form": form})


def accounts_register(request):
    if request.user.is_authenticated:
        return redirect("members:dashboard")
    if request.method == "POST":
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            MemberProfile.objects.create(user=user)
            login(request, user)
            fire_event("signup_completed", user=user, metadata={"plan": user.plan})
            send_welcome_email(user)
            send_verification_email(user)
            return redirect("members:dashboard")
    else:
        form = RegisterForm()
    return render(request, "accounts/register.html", {"form": form})


def accounts_logout(request):
    logout(request)
    return redirect("pages:landing")


def verify_email(request, uidb64, token):
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = CustomUser.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, CustomUser.DoesNotExist):
        user = None

    if user and email_verification_token.check_token(user, token):
        user.is_email_verified = True
        user.save(update_fields=["is_email_verified"])
        messages.success(request, "Email verified successfully!")
        if request.user.is_authenticated:
            return redirect("members:dashboard")
        return redirect("accounts:login")
    return render(request, "accounts/verify_email_invalid.html", status=400)


@login_required
def resend_verification_email(request):
    if request.user.is_email_verified:
        messages.info(request, "Your email is already verified.")
    else:
        send_verification_email(request.user)
        messages.success(request, "Verification email sent. Please check your inbox.")
    return redirect("members:dashboard")


def github_login(request):
    if request.user.is_authenticated:
        return redirect("members:dashboard")
    if not settings.GITHUB_CLIENT_ID:
        messages.error(request, "GitHub login is not configured.")
        return redirect("accounts:login")
    state = secrets.token_urlsafe(32)
    request.session["github_oauth_state"] = state
    callback_uri = request.build_absolute_uri(reverse("accounts:github_callback"))
    params = (
        f"client_id={settings.GITHUB_CLIENT_ID}"
        f"&redirect_uri={callback_uri}"
        f"&scope=user:email"
        f"&state={state}"
    )
    return redirect(f"{_GITHUB_AUTHORIZE_URL}?{params}")


def github_callback(request):
    if request.user.is_authenticated:
        return redirect("members:dashboard")

    state = request.GET.get("state")
    session_state = request.session.pop("github_oauth_state", None)
    if not state or state != session_state:
        messages.error(request, "GitHub authentication failed. Please try again.")
        return redirect("accounts:login")

    code = request.GET.get("code")
    if not code:
        messages.error(request, "GitHub authentication was denied.")
        return redirect("accounts:login")

    callback_uri = request.build_absolute_uri(reverse("accounts:github_callback"))
    try:
        token_resp = requests.post(
            _GITHUB_TOKEN_URL,
            data={
                "client_id": settings.GITHUB_CLIENT_ID,
                "client_secret": settings.GITHUB_CLIENT_SECRET,
                "code": code,
                "redirect_uri": callback_uri,
            },
            headers={"Accept": "application/json"},
            timeout=10,
        )
        token_data = token_resp.json()
    except Exception:
        logger.exception("Failed to exchange GitHub OAuth code for token")
        messages.error(request, "GitHub authentication failed. Please try again.")
        return redirect("accounts:login")

    access_token = token_data.get("access_token")
    if not access_token:
        messages.error(request, "GitHub authentication failed. Please try again.")
        return redirect("accounts:login")

    auth_headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/vnd.github+json",
    }

    try:
        gh_user = requests.get(f"{_GITHUB_API_URL}/user", headers=auth_headers, timeout=10).json()
    except Exception:
        logger.exception("Failed to fetch GitHub user profile")
        messages.error(request, "GitHub authentication failed. Please try again.")
        return redirect("accounts:login")

    gh_id = gh_user.get("id")
    gh_username = gh_user.get("login", "")
    gh_avatar = gh_user.get("avatar_url", "")
    gh_email = gh_user.get("email") or ""

    if not gh_email:
        try:
            emails = requests.get(f"{_GITHUB_API_URL}/user/emails", headers=auth_headers, timeout=10).json()
            primary = next((e for e in emails if e.get("primary") and e.get("verified")), None)
            if primary:
                gh_email = primary["email"]
        except Exception:
            pass

    if not gh_id:
        messages.error(request, "GitHub authentication failed. Please try again.")
        return redirect("accounts:login")

    try:
        user = CustomUser.objects.get(github_id=gh_id)
        user.github_username = gh_username
        user.github_avatar_url = gh_avatar
        user.save(update_fields=["github_username", "github_avatar_url"])
    except CustomUser.DoesNotExist:
        user = CustomUser.objects.filter(email__iexact=gh_email).first() if gh_email else None
        if user:
            user.github_id = gh_id
            user.github_username = gh_username
            user.github_avatar_url = gh_avatar
            if not user.is_email_verified and gh_email:
                user.is_email_verified = True
            user.save(update_fields=["github_id", "github_username", "github_avatar_url", "is_email_verified"])
        else:
            username = _unique_github_username(gh_username)
            user = CustomUser.objects.create_user(
                username=username,
                email=gh_email,
                password=None,
                github_id=gh_id,
                github_username=gh_username,
                github_avatar_url=gh_avatar,
                is_email_verified=bool(gh_email),
            )
            MemberProfile.objects.get_or_create(user=user)
            fire_event("signup_completed", user=user, metadata={"plan": user.plan, "method": "github"})
            send_welcome_email(user)

    user.backend = "django.contrib.auth.backends.ModelBackend"
    login(request, user)
    next_url = request.GET.get("next") or "members:dashboard"
    return redirect(next_url)


def _unique_github_username(base):
    sanitized = re.sub(r"[^\w.@+\-]", "_", base)[:140]
    if sanitized and not CustomUser.objects.filter(username=sanitized).exists():
        return sanitized
    for _ in range(10):
        candidate = f"{sanitized}_{secrets.token_hex(3)}"[:150]
        if not CustomUser.objects.filter(username=candidate).exists():
            return candidate
    return f"gh_{secrets.token_hex(8)}"
