from django.urls import path

from . import views

app_name = "projects"

urlpatterns = [
    path("dashboard/projects/", views.project_list, name="list"),
    path("dashboard/projects/add/", views.project_add, name="add"),
    path("dashboard/projects/<int:pk>/", views.project_detail, name="detail"),
    path("dashboard/projects/<int:pk>/settings/", views.project_settings, name="settings"),
    path("dashboard/projects/<int:pk>/rollback/", views.project_rollback, name="rollback"),
    path("dashboard/projects/<int:pk>/diff/<str:sha>/", views.project_commit_diff, name="commit_diff"),
]
