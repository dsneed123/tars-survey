from django.urls import path

from . import views

app_name = "tasks"

urlpatterns = [
    path("dashboard/queue/", views.task_queue, name="queue"),
    path("dashboard/tasks/", views.task_list, name="list"),
    path("dashboard/tasks/new/", views.task_add, name="add"),
    path("dashboard/tasks/<int:pk>/", views.task_detail, name="detail"),
    # GET: paginated task history; POST: create task via AJAX (session auth + CSRF)
    path("api/tasks/", views.api_tasks, name="api_list"),
    # GET: tasks updated since ?since=<iso_timestamp> (WS reconnect re-fetch)
    path("api/tasks/updates/", views.api_task_updates, name="api_updates"),
    # Callback from TARS controller/worker (X-API-Key auth via TARS_API_KEY)
    path("api/tasks/<int:pk>/status", views.api_task_status, name="api_status"),
    # Retry a failed task (session auth + CSRF)
    path("api/tasks/<int:pk>/retry", views.api_task_retry, name="api_retry"),
]
