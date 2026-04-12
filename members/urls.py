from django.urls import path

from . import views

app_name = "members"

urlpatterns = [
    path("dashboard/", views.dashboard, name="dashboard"),
    path("login/", views.member_login, name="login"),
    path("register/", views.member_register, name="register"),
    path("logout/", views.member_logout, name="logout"),
]
