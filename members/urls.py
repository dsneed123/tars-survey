from django.contrib.auth.views import LogoutView
from django.urls import path

from . import views

app_name = "members"

urlpatterns = [
    path("dashboard/", views.dashboard, name="dashboard"),
    path("dashboard/quick-task/", views.quick_add_task, name="quick_task"),
    path("dashboard/messages/", views.load_more_messages, name="load_more_messages"),
    path("logout/", LogoutView.as_view(next_page="/"), name="logout"),
]
