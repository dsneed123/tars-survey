import json

from django.contrib.admin.views.decorators import staff_member_required
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from tasks.models import Task

from .models import Worker

# ---------------------------------------------------------------------------
# Auth helper
# ---------------------------------------------------------------------------

def _get_worker(request):
    """Authenticate via X-Worker-Key header. Returns Worker or None."""
    api_key = request.META.get("HTTP_X_WORKER_KEY", "").strip()
    if not api_key:
        return None
    try:
        return Worker.objects.get(api_key=api_key)
    except (Worker.DoesNotExist, ValueError):
        return None


def _require_worker(request):
    """Return (worker, None) on success or (None, JsonResponse) on failure."""
    worker = _get_worker(request)
    if worker is None:
        return None, JsonResponse({"error": "Invalid or missing X-Worker-Key"}, status=401)
    return worker, None


# ---------------------------------------------------------------------------
# POST /api/workers/register/
# ---------------------------------------------------------------------------

@csrf_exempt
@require_http_methods(["POST"])
def register(request):
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    hostname = data.get("hostname", "").strip()
    if not hostname:
        return JsonResponse({"error": "hostname is required"}, status=400)

    ip_address = (
        request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[0].strip()
        or request.META.get("REMOTE_ADDR")
    )

    worker = Worker.objects.create(
        hostname=hostname,
        ip_address=ip_address or None,
        capacity=int(data.get("capacity", 1)),
        specs=data.get("specs") or None,
        status="online",
    )

    return JsonResponse(
        {
            "worker_id": worker.pk,
            "api_key": str(worker.api_key),
        },
        status=201,
    )


# ---------------------------------------------------------------------------
# POST /api/workers/heartbeat/
# ---------------------------------------------------------------------------

@csrf_exempt
@require_http_methods(["POST"])
def heartbeat(request):
    worker, err = _require_worker(request)
    if err:
        return err

    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        data = {}

    worker.last_heartbeat = timezone.now()

    current_load = data.get("current_load")
    if current_load is not None:
        worker.current_load = int(current_load)

    status = data.get("status")
    if status and status in dict(Worker.STATUS_CHOICES):
        worker.status = status

    worker.save(update_fields=["last_heartbeat", "current_load", "status"])

    return JsonResponse({"ok": True})


# ---------------------------------------------------------------------------
# GET /api/workers/next-task/
# ---------------------------------------------------------------------------

@csrf_exempt
@require_http_methods(["GET"])
@transaction.atomic
def next_task(request):
    worker, err = _require_worker(request)
    if err:
        return err

    # Projects that already have an active task being worked on
    busy_project_ids = list(
        Task.objects.filter(
            status__in=["assigned", "in_progress", "reviewing"],
        )
        .values_list("project_id", flat=True)
        .distinct()
    )

    task = (
        Task.objects.select_for_update()
        .filter(status="pending")
        .exclude(project_id__in=busy_project_ids)
        .order_by("-priority", "created_at")
        .select_related("project")
        .first()
    )

    if task is None:
        return JsonResponse({"task": None})

    task.status = "assigned"
    task.worker_id = str(worker.pk)
    task.save(update_fields=["status", "worker_id"])

    return JsonResponse(
        {
            "task": {
                "id": task.pk,
                "title": task.title,
                "description": task.description,
                "priority": task.priority,
                "project": {
                    "id": task.project.pk,
                    "name": task.project.name,
                    "github_repo": task.project.github_repo,
                    "default_branch": task.project.default_branch,
                },
            }
        }
    )


# ---------------------------------------------------------------------------
# POST /api/workers/task/<id>/update/
# ---------------------------------------------------------------------------

@csrf_exempt
@require_http_methods(["POST"])
def task_update(request, task_id):
    worker, err = _require_worker(request)
    if err:
        return err

    try:
        task = Task.objects.get(pk=task_id)
    except Task.DoesNotExist:
        return JsonResponse({"error": "Task not found"}, status=404)

    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    update_fields = []

    status = data.get("status")
    if status and status in dict(Task.STATUS_CHOICES):
        task.status = status
        update_fields.append("status")
        if status == "in_progress" and not task.started_at:
            task.started_at = timezone.now()
            update_fields.append("started_at")
        elif status in ("completed", "failed") and not task.completed_at:
            task.completed_at = timezone.now()
            update_fields.append("completed_at")

    if "branch_name" in data:
        task.branch_name = data["branch_name"] or None
        update_fields.append("branch_name")

    if "pr_url" in data:
        task.pr_url = data["pr_url"] or None
        update_fields.append("pr_url")

    if "error_message" in data:
        task.error_message = data["error_message"] or None
        update_fields.append("error_message")

    if update_fields:
        task.save(update_fields=update_fields)

    return JsonResponse({"ok": True, "task_id": task.pk, "status": task.status})


# ---------------------------------------------------------------------------
# GET /admin-dashboard/workers/
# ---------------------------------------------------------------------------

@staff_member_required
def worker_list(request):
    # Mark stale workers offline (no heartbeat in 5 minutes)
    cutoff = timezone.now() - timezone.timedelta(minutes=5)
    Worker.objects.filter(
        last_heartbeat__lt=cutoff,
    ).exclude(status="offline").update(status="offline")

    workers = Worker.objects.all()

    return render(request, "workers/worker_list.html", {"workers": workers})
