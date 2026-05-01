from django.contrib.auth.views import LogoutView
from django.urls import path

from . import views

app_name = "members"

urlpatterns = [
    path("dashboard/", views.dashboard, name="dashboard"),
    path("dashboard/activity/", views.activity_log, name="activity_log"),
    path("dashboard/settings/", views.settings_view, name="settings"),
    path("dashboard/quick-task/", views.quick_add_task, name="quick_task"),
    path("dashboard/clarify-task/", views.clarify_task, name="clarify_task"),
    path("dashboard/bulk-tasks/", views.bulk_add_tasks, name="bulk_add_tasks"),
    path("dashboard/messages/", views.load_more_messages, name="load_more_messages"),
    path("dashboard/complete-tour/", views.complete_tour, name="complete_tour"),
    path("logout/", LogoutView.as_view(next_page="/"), name="logout"),
]
