import json

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.contrib.admin.views.decorators import staff_member_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django_ratelimit.decorators import ratelimit

from analytics.utils import fire_event
from notifications.utils import send_task_failed_email, send_task_pr_ready_email, send_task_started_email
from tasks.models import Task

from .models import TaskAssignment, Worker

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
    except (Worker.DoesNotExist, ValueError, ValidationError):
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

@ratelimit(key="ip", rate="30/m", block=True)
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

@ratelimit(key="ip", rate="30/m", block=True)
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

# Age bonus: +1 priority per minute waiting, capped at this value
_AGE_BONUS_MAX = 50
# Cache-warm bonus: reward for assigning a task on a project the worker recently touched
_CACHE_WARM_BONUS = 10
# How far back to look for "recently worked" project history (seconds)
_CACHE_WARM_WINDOW_SECS = 3600


@ratelimit(key="ip", rate="30/m", block=True)
@csrf_exempt
@require_http_methods(["GET"])
@transaction.atomic
def next_task(request):
    worker, err = _require_worker(request)
    if err:
        return err

    # Don't assign when worker is at max load
    if worker.current_load >= worker.capacity:
        return JsonResponse({"task": None})

    now = timezone.now()

    # Projects that already have an active task being worked on
    busy_project_ids = list(
        Task.objects.filter(
            status__in=["assigned", "in_progress", "reviewing"],
        )
        .values_list("project_id", flat=True)
        .distinct()
    )

    # Fetch all eligible pending tasks (lock for update to prevent races)
    pending_tasks = list(
        Task.objects.select_for_update()
        .filter(status="pending")
        .exclude(project_id__in=busy_project_ids)
        .select_related("project")
    )

    if not pending_tasks:
        return JsonResponse({"task": None})

    # Projects this worker recently worked on → cache-warm bonus
    warm_project_ids = set(
        TaskAssignment.objects.filter(
            worker=worker,
            assigned_at__gte=now - timezone.timedelta(seconds=_CACHE_WARM_WINDOW_SECS),
        ).values_list("task__project_id", flat=True)
    )

    # Score every candidate task
    def _score(t):
        age_minutes = (now - t.created_at).total_seconds() / 60
        age_bonus = min(int(age_minutes), _AGE_BONUS_MAX)
        cache_bonus = _CACHE_WARM_BONUS if t.project_id in warm_project_ids else 0
        return t.priority + age_bonus + cache_bonus

    # Pick highest score; break ties by created_at ascending (oldest first = round-robin fairness)
    best_task = max(pending_tasks, key=lambda t: (_score(t), -t.created_at.timestamp()))

    best_task.status = "assigned"
    best_task.worker_id = str(worker.pk)
    best_task.save(update_fields=["status", "worker_id"])

    TaskAssignment.objects.create(task=best_task, worker=worker)

    return JsonResponse(
        {
            "task": {
                "id": best_task.pk,
                "title": best_task.title,
                "description": best_task.description,
                "priority": best_task.priority,
                "project": {
                    "id": best_task.project.pk,
                    "name": best_task.project.name,
                    "github_repo": best_task.project.github_repo,
                    "default_branch": best_task.project.default_branch,
                },
            }
        }
    )


# ---------------------------------------------------------------------------
# WebSocket broadcast helper
# ---------------------------------------------------------------------------

def _broadcast_task_update(task):
    """Push a task status update to connected WebSocket clients."""
    channel_layer = get_channel_layer()
    if channel_layer is None:
        return

    data = {
        "task_id": task.pk,
        "title": task.title,
        "status": task.status,
        "status_display": task.get_status_display(),
        "branch_name": task.branch_name,
        "pr_url": task.pr_url,
    }
    send = async_to_sync(channel_layer.group_send)

    # Task detail page subscribers
    send(f"task_{task.pk}", {"type": "task_update", "data": data})

    # Dashboard subscribers for the task owner
    send(f"dashboard_{task.created_by_id}", {"type": "task_update", "data": data})


# ---------------------------------------------------------------------------
# POST /api/workers/task/<id>/update/
# ---------------------------------------------------------------------------

@ratelimit(key="ip", rate="30/m", block=True)
@csrf_exempt
@require_http_methods(["POST"])
def task_update(request, task_id):
    worker, err = _require_worker(request)
    if err:
        return err

    try:
        task = Task.objects.select_related("project", "created_by").get(pk=task_id)
    except Task.DoesNotExist:
        return JsonResponse({"error": "Task not found"}, status=404)

    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    update_fields = []

    prev_status = task.status
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

    # Broadcast the status change to connected WebSocket clients
    if update_fields:
        _broadcast_task_update(task)

    # Send notification emails on meaningful status transitions
    if status and status != prev_status:
        if status == "in_progress":
            send_task_started_email(task)
        elif status == "reviewing" and task.pr_url:
            send_task_pr_ready_email(task)
        elif status == "failed":
            send_task_failed_email(task)

    # Update the TaskAssignment record when the task reaches a terminal state
    if status in ("completed", "failed"):
        result = "success" if status == "completed" else "failed"
        TaskAssignment.objects.filter(
            task=task, worker=worker, result__isnull=True
        ).update(result=result, completed_at=timezone.now())
        fire_event(
            "task_complete",
            user=task.created_by,
            metadata={
                "task_id": task.pk,
                "result": result,
                "worker_id": worker.pk,
            },
        )

    return JsonResponse({"ok": True, "task_id": task.pk, "status": task.status})


# ---------------------------------------------------------------------------
# GET /admin-dashboard/workers/
# ---------------------------------------------------------------------------

@staff_member_required
def worker_list(request):
    now = timezone.now()

    # Mark stale workers offline (no heartbeat in 5 minutes)
    cutoff = now - timezone.timedelta(minutes=5)
    Worker.objects.filter(
        last_heartbeat__lt=cutoff,
    ).exclude(status="offline").update(status="offline")

    workers = Worker.objects.all()

    # Load balancing stats
    pending_count = Task.objects.filter(status="pending").count()
    active_count = Task.objects.filter(status__in=["assigned", "in_progress", "reviewing"]).count()

    stuck_cutoff = now - timezone.timedelta(minutes=30)
    stuck_count = TaskAssignment.objects.filter(
        assigned_at__lt=stuck_cutoff,
        result__isnull=True,
        task__status__in=["assigned", "in_progress"],
        worker__last_heartbeat__lt=cutoff,
    ).count()

    total_assignments = TaskAssignment.objects.count()
    success_count = TaskAssignment.objects.filter(result="success").count()
    success_rate = round(success_count / total_assignments * 100) if total_assignments else None

    recent_assignments = (
        TaskAssignment.objects.select_related("task", "worker")
        .order_by("-assigned_at")[:10]
    )

    return render(request, "workers/worker_list.html", {
        "workers": workers,
        "pending_count": pending_count,
        "active_count": active_count,
        "stuck_count": stuck_count,
        "success_rate": success_rate,
        "total_assignments": total_assignments,
        "recent_assignments": recent_assignments,
    })
