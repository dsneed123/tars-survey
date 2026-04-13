from django.urls import path

from . import views

app_name = "tasks"

urlpatterns = [
    path("dashboard/tasks/", views.task_list, name="list"),
    path("dashboard/tasks/new/", views.task_add, name="add"),
    path("dashboard/tasks/<int:pk>/", views.task_detail, name="detail"),
    # Callback from TARS controller/worker (X-API-Key auth via TARS_API_KEY)
    path("api/tasks/<int:pk>/status", views.api_task_status, name="api_status"),
]
