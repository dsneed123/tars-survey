import json
import logging
import os

import requests as http_requests
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from analytics.utils import fire_event
from projects.models import Project

from .forms import TaskForm
from .models import Task, TaskAttachment

logger = logging.getLogger(__name__)


_TARS_STATUS_CHOICES = {s for s, _ in Task.STATUS_CHOICES}


def _broadcast_task_update(task):
    """Push a task status update to the WS groups listening for this task."""
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
        "error_message": task.error_message,
    }
    send = async_to_sync(channel_layer.group_send)
    send(f"task_{task.pk}", {"type": "task_update", "data": data})
    send(f"dashboard_{task.created_by_id}", {"type": "task_update", "data": data})


@login_required
def task_queue(request):
    from django.db.models import Case, IntegerField, Value, When

    status_order = Case(
        When(status="in_progress", then=Value(0)),
        When(status="assigned", then=Value(1)),
        When(status="reviewing", then=Value(2)),
        When(status="queued", then=Value(3)),
        When(status="pending", then=Value(4)),
        default=Value(5),
        output_field=IntegerField(),
    )
    tasks = (
        Task.objects.filter(created_by=request.user)
        .exclude(status__in=("completed", "failed"))
        .select_related("project")
        .annotate(status_order=status_order)
        .order_by("status_order", "created_at")
    )
    return render(request, "tasks/task_queue.html", {"tasks": list(tasks)})


@login_required
def task_list(request):
    tasks = Task.objects.filter(created_by=request.user).select_related("project")

    # Filtering
    project_filter = request.GET.get("project")
    status_filter = request.GET.get("status")

    if project_filter:
        tasks = tasks.filter(project_id=project_filter)
    if status_filter:
        tasks = tasks.filter(status=status_filter)

    from django.db.models import Q
    projects = Project.objects.filter(
        Q(owner=request.user) | Q(team__owner=request.user) | Q(team__memberships__user=request.user),
        is_active=True,
    ).distinct()

    return render(
        request,
        "tasks/task_list.html",
        {
            "tasks": tasks,
            "projects": projects,
            "project_filter": project_filter,
            "status_filter": status_filter,
            "status_choices": Task.STATUS_CHOICES,
        },
    )


@login_required
def task_add(request):
    if request.method == "POST":
        form = TaskForm(request.user, request.POST)
        if form.is_valid():
            task = form.save(commit=False)
            task.created_by = request.user
            task.save()

            # Handle multiple file uploads
            files = request.FILES.getlist("attachments")
            for f in files:
                TaskAttachment.objects.create(
                    task=task,
                    file=f,
                    filename=f.name,
                )

            # Forward task to TARS controller on the Mac Mini
            _forward_to_controller(task)

            fire_event(
                "task_submitted",
                user=request.user,
                metadata={"task_id": task.pk, "project": task.project.github_repo},
            )
            messages.success(request, f'Task "{task.title}" submitted successfully.')
            return redirect("tasks:detail", pk=task.pk)
    else:
        initial = {}
        # Pre-fill from query params (e.g. from dashboard "Request TARS Code" button)
        project_id = request.GET.get("project")
        if project_id:
            initial["project"] = project_id
        service = request.GET.get("service")
        if service == "tars-code":
            initial.setdefault("title", "")
        form = TaskForm(request.user, initial=initial)

    return render(request, "tasks/task_add.html", {"form": form, "service": request.GET.get("service", "")})


@login_required
def task_detail(request, pk):
    task = get_object_or_404(
        Task.objects.select_related("project", "created_by").prefetch_related("attachments"),
        pk=pk,
        created_by=request.user,
    )
    attachments = task.attachments.all()

    # Build status timeline steps
    timeline = _build_timeline(task)

    return render(
        request,
        "tasks/task_detail.html",
        {
            "task": task,
            "attachments": attachments,
            "timeline": timeline,
        },
    )


def _build_timeline(task):
    """Return ordered list of timeline steps with state for display."""
    steps = [
        ("pending", "Submitted", "bi-send"),
        ("queued", "Queued", "bi-hourglass-split"),
        ("assigned", "Assigned to Worker", "bi-cpu"),
        ("in_progress", "In Progress", "bi-code-slash"),
        ("reviewing", "Under Review", "bi-eye"),
        ("completed", "Completed", "bi-check-circle-fill"),
    ]

    # Map status to an ordered index
    order = {s: i for i, (s, _, _) in enumerate(steps)}
    # failed is special — shown as completed but red
    failed = task.status == "failed"
    current_index = order.get(task.status, 0)

    result = []
    for i, (status, label, icon) in enumerate(steps):
        if failed and i == current_index:
            state = "failed"
        elif i < current_index or (not failed and i == current_index):
            state = "done" if i < current_index else "current"
        else:
            state = "pending"
        result.append({"status": status, "label": label, "icon": icon, "state": state})

    if failed:
        result.append({"status": "failed", "label": "Failed", "icon": "bi-x-circle-fill", "state": "failed"})

    return result


def _forward_to_controller(task):
    """Send a newly created task to the TARS controller API on the Mac Mini."""
    url = getattr(settings, "TARS_CONTROLLER_URL", "")
    api_key = getattr(settings, "TARS_API_KEY", "")
    if not url or not api_key:
        logger.info("TARS_CONTROLLER_URL or TARS_API_KEY not set, skipping forward.")
        return

    payload = {
        "project": task.project.github_repo,
        "task_type": "tars-code",
        "title": task.title,
        "description": task.description,
        "priority": task.priority,
        "user_id": str(task.created_by_id),
        "survey_task_id": task.pk,
    }
    try:
        resp = http_requests.post(
            f"{url.rstrip('/')}/api/tasks",
            json=payload,
            headers={"X-API-Key": api_key},
            timeout=10,
        )
        if resp.ok:
            logger.info("Task %s forwarded to controller: %s", task.pk, resp.json().get("task", {}).get("id"))
        else:
            logger.warning("Controller rejected task %s: %s", task.pk, resp.text)
    except Exception as e:
        logger.warning("Failed to forward task %s to controller: %s", task.pk, e)


# ---------------------------------------------------------------------------
# POST /api/tasks/<pk>/status
#
# Authenticated callback from the TARS controller / worker.
# Updates a Task's status and broadcasts to connected WebSocket clients so
# the detail page progress bar and badge update live.
# ---------------------------------------------------------------------------


@csrf_exempt
@require_POST
def api_task_status(request, pk):
    api_key = request.META.get("HTTP_X_API_KEY", "").strip()
    expected = getattr(settings, "TARS_API_KEY", "")
    if not expected or api_key != expected:
        return JsonResponse({"error": "Invalid or missing X-API-Key"}, status=401)

    try:
        data = json.loads(request.body or b"{}")
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    status = (data.get("status") or "").strip()
    if status not in _TARS_STATUS_CHOICES:
        return JsonResponse(
            {"error": f"Invalid status. Must be one of: {sorted(_TARS_STATUS_CHOICES)}"},
            status=400,
        )

    try:
        task = Task.objects.get(pk=pk)
    except Task.DoesNotExist:
        return JsonResponse({"error": "Task not found"}, status=404)

    update_fields = ["status"]
    task.status = status

    for field in ("branch_name", "pr_url", "error_message", "worker_id"):
        if field in data and data[field] is not None:
            setattr(task, field, data[field])
            update_fields.append(field)

    now = timezone.now()
    if status in ("assigned", "in_progress") and task.started_at is None:
        task.started_at = now
        update_fields.append("started_at")
    if status in ("completed", "failed") and task.completed_at is None:
        task.completed_at = now
        update_fields.append("completed_at")

    task.save(update_fields=update_fields)
    _broadcast_task_update(task)

    logger.info("Task %s status -> %s", task.pk, status)
    return JsonResponse(
        {
            "ok": True,
            "task_id": task.pk,
            "status": task.status,
            "status_display": task.get_status_display(),
        }
    )
