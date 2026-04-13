from django.urls import path

from . import views

app_name = "workers"

urlpatterns = [
    # API endpoints (authenticated via X-Worker-Key header)
    path("api/workers/register/", views.register, name="register"),
    path("api/workers/heartbeat/", views.heartbeat, name="heartbeat"),
    path("api/workers/next-task/", views.next_task, name="next-task"),
    path("api/workers/task/<int:task_id>/update/", views.task_update, name="task-update"),
    # Admin dashboard
    path("admin-dashboard/workers/", views.worker_list, name="list"),
]
