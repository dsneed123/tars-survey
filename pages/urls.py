from django.urls import path
from . import views

app_name = "pages"

urlpatterns = [
    path("", views.landing, name="landing"),
    path("inquiry/", views.inquiry, name="inquiry"),
    path("inquiry/success/", views.inquiry_success, name="inquiry_success"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("dashboard/<int:inquiry_id>/", views.inquiry_detail, name="inquiry_detail"),
    path("dashboard/<int:inquiry_id>/add-note/", views.add_note, name="add_note"),
    path("dashboard/<int:inquiry_id>/update-status/", views.update_status, name="update_status"),
]
