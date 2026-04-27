from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from django_ratelimit.decorators import ratelimit

from analytics.utils import fire_event
from members.models import MemberProfile
from notifications.utils import send_verification_email, send_welcome_email

from .forms import LoginForm, RegisterForm
from .models import CustomUser
from .tokens import email_verification_token


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
