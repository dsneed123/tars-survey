from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from inquiries.models import Inquiry

from .forms import LoginForm, RegisterForm
from .models import MemberProfile


@login_required
def dashboard(request):
    profile, _ = MemberProfile.objects.get_or_create(user=request.user)
    recent_inquiries = Inquiry.objects.filter(email=request.user.email)[:5]
    ctx = {
        "profile": profile,
        "recent_inquiries": recent_inquiries,
    }
    return render(request, "members/dashboard.html", ctx)


def member_login(request):
    if request.user.is_authenticated:
        return redirect("members:dashboard")
    if request.method == "POST":
        form = LoginForm(request.POST)
        if form.is_valid():
            user = authenticate(
                request,
                username=form.cleaned_data["username"],
                password=form.cleaned_data["password"],
            )
            if user:
                login(request, user)
                next_url = request.GET.get("next") or "members:dashboard"
                return redirect(next_url)
            form.add_error(None, "Invalid username or password.")
    else:
        form = LoginForm()
    return render(request, "members/login.html", {"form": form})


def member_register(request):
    if request.user.is_authenticated:
        return redirect("members:dashboard")
    if request.method == "POST":
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            MemberProfile.objects.create(user=user)
            login(request, user)
            return redirect("members:dashboard")
    else:
        form = RegisterForm()
    return render(request, "members/register.html", {"form": form})


def member_logout(request):
    logout(request)
    return redirect("pages:landing")
