from django.contrib.auth import authenticate, login, logout
from django.shortcuts import redirect, render

from members.models import MemberProfile

from .forms import LoginForm, RegisterForm
from .models import CustomUser


def accounts_login(request):
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
            return redirect("members:dashboard")
    else:
        form = RegisterForm()
    return render(request, "accounts/register.html", {"form": form})


def accounts_logout(request):
    logout(request)
    return redirect("pages:landing")
