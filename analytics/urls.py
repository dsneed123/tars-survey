from django.urls import path

from . import views

app_name = "analytics"

urlpatterns = [
    path("admin-dashboard/", views.analytics_dashboard, name="dashboard"),
    path("admin-dashboard/invite-keys/generate/", views.invite_key_generate, name="invite_key_generate"),
    path("admin-dashboard/invite-keys/<int:key_id>/revoke/", views.invite_key_revoke, name="invite_key_revoke"),
]
