from django.urls import path

from . import views

app_name = "notifications"

urlpatterns = [
    path("dashboard/settings/notifications/", views.notification_preferences, name="preferences"),
    path("dashboard/notifications/<int:pk>/read/", views.mark_read, name="mark_read"),
    path("dashboard/notifications/mark-all-read/", views.mark_all_read, name="mark_all_read"),
]
