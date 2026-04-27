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
    # Reorder pending/queued tasks by updating priority (session auth + CSRF)
    path("api/tasks/reorder", views.api_task_reorder, name="api_reorder"),
    # Callback from TARS controller/worker (X-API-Key auth via TARS_API_KEY)
    path("api/tasks/<int:pk>/status", views.api_task_status, name="api_status"),
    # Inline detail JSON for expandable bubble panel (session auth)
    path("api/tasks/<int:pk>/detail", views.api_task_detail, name="api_detail"),
    # PR diff summary for completed tasks (session auth)
    path("api/tasks/<int:pk>/pr_diff", views.api_task_pr_diff, name="api_pr_diff"),
    # Retry a failed task (session auth + CSRF)
    path("api/tasks/<int:pk>/retry", views.api_task_retry, name="api_retry"),
    # Cancel a pending/queued task (session auth + CSRF)
    path("api/tasks/<int:pk>/cancel", views.api_task_cancel, name="api_cancel"),
    # Hard-delete a pending/queued task (session auth + CSRF)
    path("api/tasks/<int:pk>/delete", views.api_task_delete, name="api_delete"),
    # Pin / unpin a task (session auth + CSRF; max 5 pins per user)
    path("api/tasks/<int:pk>/pin", views.api_task_pin, name="api_pin"),
    # GitHub webhook receiver (HMAC-SHA256 signature validation)
    path("api/webhooks/github/", views.github_webhook, name="github_webhook"),
    # CSV export of task history (date_from, date_to, project filters)
    path("api/tasks/export/", views.export_tasks_csv, name="export_csv"),
]
