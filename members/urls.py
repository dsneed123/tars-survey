from django.contrib.auth.views import LogoutView
from django.urls import path

from . import views

app_name = "members"

urlpatterns = [
    path("dashboard/", views.dashboard, name="dashboard"),
    path("dashboard/onboarding/", views.onboarding, name="onboarding"),
    path("dashboard/onboarding/skip/", views.onboarding_skip, name="onboarding_skip"),
    path("logout/", LogoutView.as_view(next_page="/"), name="logout"),
]
