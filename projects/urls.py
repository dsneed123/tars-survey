from django.urls import path

from . import views

app_name = "projects"

urlpatterns = [
    path("dashboard/projects/", views.project_list, name="list"),
    path("dashboard/projects/add/", views.project_add, name="add"),
    path("dashboard/projects/new/", views.project_new, name="new"),
    path("dashboard/projects/<int:pk>/autopopulate/", views.project_autopopulate, name="autopopulate"),
    path("dashboard/projects/<int:pk>/go/", views.project_go_launch, name="go_launch"),
    path("dashboard/projects/<int:pk>/go/<str:session_id>/", views.project_go_session, name="go_session"),
    path("dashboard/projects/<int:pk>/go/<str:session_id>/poll/", views.project_go_poll, name="go_poll"),
    path("dashboard/projects/<int:pk>/share/", views.project_share, name="share"),
    path("dashboard/projects/<int:pk>/pages/", views.project_pages, name="pages"),
    path("dashboard/projects/detect/", views.project_detect, name="detect"),
    path("dashboard/projects/add-chat/", views.project_add_chat, name="add_chat"),
    path("dashboard/projects/<int:pk>/", views.project_detail, name="detail"),
    path("dashboard/projects/<int:pk>/settings/", views.project_settings, name="settings"),
    path("dashboard/projects/<int:pk>/rollback/", views.project_rollback, name="rollback"),
    path("dashboard/projects/<int:pk>/diff/<str:sha>/", views.project_commit_diff, name="commit_diff"),
]
