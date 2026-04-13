from django.urls import path

from . import views

app_name = "analytics"

urlpatterns = [
    path("admin-dashboard/", views.analytics_dashboard, name="dashboard"),
]
