import hashlib
import hmac
import json
import logging
import os
import re

import bleach
import requests as http_requests
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.core.paginator import EmptyPage, Paginator
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from analytics.utils import fire_event
from notifications.utils import create_notification
from projects.models import Project

from .forms import TaskForm
from .models import Task, TaskAttachment

logger = logging.getLogger(__name__)


_TARS_STATUS_CHOICES = {s for s, _ in Task.STATUS_CHOICES}

# Sentinel used to distinguish "key not in cache" from "cached value is None".
_CACHE_MISS = object()

# Valid status transitions for the task state machine.
# Non-terminal states accept any valid status; only terminal states (completed, failed)
# are locked — the controller cannot walk a task back from a terminal state.
_VALID_TRANSITIONS = {
    "pending": {"queued", "assigned", "in_progress", "reviewing", "failed", "completed"},
    "queued": {"pending", "assigned", "in_progress", "reviewing", "failed", "completed"},
    "assigned": {"queued", "in_progress", "reviewing", "failed", "completed"},
    "in_progress": {"assigned", "reviewing", "completed", "failed"},
    "reviewing": {"in_progress", "completed", "failed"},
    "completed": set(),
    "failed": set(),
}

_IDEMPOTENCY_TTL = 86_400  # 24 hours


def _get_queue_positions(user_id):
    """Return {task_pk: position} (1-indexed, oldest first) for pending/queued tasks."""
    pks = list(
        Task.objects.filter(
            created_by_id=user_id,
            status__in=("pending", "queued"),
        )
        .order_by("created_at")
        .values_list("pk", flat=True)
    )
    return {pk: i + 1 for i, pk in enumerate(pks)}


def _get_avg_completion_seconds(user_id, sample=20):
    """Return average task duration (started_at→completed_at) in seconds, or None if < 3 samples."""
    cache_key = f"tars_avg_sec_{user_id}"
    result = cache.get(cache_key, _CACHE_MISS)
    if result is not _CACHE_MISS:
        return result

    tasks = list(
        Task.objects.filter(
            created_by_id=user_id,
            status="completed",
            started_at__isnull=False,
            completed_at__isnull=False,
        )
        .order_by("-completed_at")
        .values("started_at", "completed_at")[:sample]
    )
    durations = [
        (t["completed_at"] - t["started_at"]).total_seconds()
        for t in tasks
        if t["completed_at"] > t["started_at"]
    ]
    result = None if len(durations) < 3 else sum(durations) / len(durations)
    cache.set(cache_key, result, timeout=300)
    return result


def _format_wait(seconds):
    if seconds < 90:
        return "~1m wait"
    minutes = round(seconds / 60)
    if minutes < 60:
        return f"~{minutes}m wait"
    return f"~{round(minutes / 60)}h wait"


def _get_wait_times(user_id, queue_positions=None):
    """Return {task_pk: str} estimated wait labels for pending/queued tasks."""
    if queue_positions is None:
        queue_positions = _get_queue_positions(user_id)
    avg_seconds = _get_avg_completion_seconds(user_id)
    return {
        pk: ("Estimating..." if avg_seconds is None else _format_wait(avg_seconds * pos))
        for pk, pos in queue_positions.items()
    }


def _broadcast_task_update(task):
    """Push a task status update to the WS groups listening for this task."""
    channel_layer = get_channel_layer()
    if channel_layer is None:
        return

    queue_positions = _get_queue_positions(task.created_by_id)
    wait_times = _get_wait_times(task.created_by_id, queue_positions)
    project_name = task.project.name if task.project_id else ""

    data = {
        "task_id": task.pk,
        "title": task.title,
        "status": task.status,
        "status_display": task.get_status_display(),
        "branch_name": task.branch_name,
        "pr_url": task.pr_url,
        "error_message": task.error_message,
        "queue_position": queue_positions.get(task.pk),
        "estimated_wait": wait_times.get(task.pk),
    }
    send = async_to_sync(channel_layer.group_send)
    send(f"task_{task.pk}", {"type": "task_update", "data": data})
    send(f"dashboard_{task.created_by_id}", {"type": "task_update", "data": data})
    send(
        f"queue_{task.created_by_id}",
        {
            "type": "queue_update",
            "data": {**data, "project_name": project_name, "kind": "status_update"},
        },
    )

    # Broadcast updated queue stats to the dashboard welcome message.
    active_count = Task.objects.filter(
        created_by_id=task.created_by_id,
        status__in=("pending", "queued", "assigned", "in_progress", "reviewing"),
    ).count()
    completed_today = Task.objects.filter(
        created_by_id=task.created_by_id,
        status="completed",
        completed_at__date=timezone.now().date(),
    ).count()
    send(
        f"dashboard_{task.created_by_id}",
        {
            "type": "queue_stats",
            "data": {"type": "queue_stats", "active_count": active_count, "completed_today": completed_today},
        },
    )

    # When the queue shifts, broadcast updated positions to other pending/queued tasks.
    other_pks = [pk for pk in queue_positions if pk != task.pk]
    if other_pks:
        status_display_map = dict(Task.STATUS_CHOICES)
        other_statuses = dict(
            Task.objects.filter(pk__in=other_pks).values_list("pk", "status")
        )
        for pk in other_pks:
            st = other_statuses.get(pk, "pending")
            pos_data = {
                "task_id": pk,
                "status": st,
                "status_display": status_display_map.get(st, st),
                "queue_position": queue_positions[pk],
                "estimated_wait": wait_times.get(pk),
            }
            send(f"dashboard_{task.created_by_id}", {"type": "task_update", "data": pos_data})
            send(
                f"queue_{task.created_by_id}",
                {
                    "type": "queue_update",
                    "data": {**pos_data, "project_name": "", "kind": "status_update"},
                },
            )


def _broadcast_queue_task_added(task):
    """Notify queue WS clients that a new task has entered the queue."""
    channel_layer = get_channel_layer()
    if channel_layer is None:
        return

    queue_positions = _get_queue_positions(task.created_by_id)
    wait_times = _get_wait_times(task.created_by_id, queue_positions)
    project_name = task.project.name if task.project_id else ""

    data = {
        "kind": "task_added",
        "task_id": task.pk,
        "title": task.title,
        "status": task.status,
        "status_display": task.get_status_display(),
        "queue_position": queue_positions.get(task.pk),
        "estimated_wait": wait_times.get(task.pk),
        "project_name": project_name,
    }
    async_to_sync(channel_layer.group_send)(
        f"queue_{task.created_by_id}",
        {"type": "queue_update", "data": data},
    )


@login_required
def task_queue(request):
    from django.db.models import Case, IntegerField, Value, When

    _ACTIVE_STATUSES = {"in_progress", "assigned", "reviewing"}
    _PENDING_STATUSES = {"pending", "queued"}
    _FILTER_GROUP_MAP = {
        "in_progress": "active", "assigned": "active", "reviewing": "active",
        "pending": "pending", "queued": "pending",
        "completed": "completed",
        "failed": "failed",
    }

    status_order = Case(
        When(status="in_progress", then=Value(0)),
        When(status="assigned", then=Value(1)),
        When(status="reviewing", then=Value(2)),
        When(status="queued", then=Value(3)),
        When(status="pending", then=Value(4)),
        When(status="completed", then=Value(5)),
        When(status="failed", then=Value(6)),
        default=Value(7),
        output_field=IntegerField(),
    )
    tasks = list(
        Task.objects.filter(created_by=request.user)
        .select_related("project")
        .annotate(status_order=status_order)
        .order_by("status_order", "created_at")
    )

    today = timezone.now().date()
    completed_today = Task.objects.filter(
        created_by=request.user,
        status="completed",
        completed_at__date=today,
    ).count()

    queue_positions = _get_queue_positions(request.user.pk)
    wait_times = _get_wait_times(request.user.pk, queue_positions)
    for task in tasks:
        task.wait_time = wait_times.get(task.pk)
        task.filter_group = _FILTER_GROUP_MAP.get(task.status, "pending")

    in_progress_count = sum(1 for t in tasks if t.status == "in_progress")
    active_count = sum(1 for t in tasks if t.status in _ACTIVE_STATUSES)
    pending_count = sum(1 for t in tasks if t.status in _PENDING_STATUSES)
    completed_count = sum(1 for t in tasks if t.status == "completed")
    failed_count = sum(1 for t in tasks if t.status == "failed")
    total_count = active_count + pending_count + completed_today

    return render(request, "tasks/task_queue.html", {
        "tasks": tasks,
        "completed_today": completed_today,
        "in_progress_count": in_progress_count,
        "pending_count": pending_count,
        "total_count": total_count,
        "active_count": active_count,
        "completed_count": completed_count,
        "failed_count": failed_count,
    })


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
            task.description = task.title
            task.priority = 50
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
            _broadcast_queue_task_added(task)

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


@login_required
@require_GET
def api_task_detail(request, pk):
    """Return task detail as JSON for the inline expandable panel."""
    task = get_object_or_404(
        Task.objects.select_related("project", "created_by").prefetch_related("attachments"),
        pk=pk,
        created_by=request.user,
    )
    attachments = [
        {
            "filename": a.filename,
            "url": request.build_absolute_uri(a.file.url) if a.file else None,
        }
        for a in task.attachments.all()
    ]
    timeline = _build_timeline(task)
    return JsonResponse({
        "id": task.pk,
        "title": task.title,
        "description": task.description,
        "status": task.status,
        "status_display": task.get_status_display(),
        "pr_url": task.pr_url,
        "branch_name": task.branch_name,
        "worker_id": task.worker_id,
        "error_message": task.error_message,
        "created_at": task.created_at.isoformat(),
        "started_at": task.started_at.isoformat() if task.started_at else None,
        "completed_at": task.completed_at.isoformat() if task.completed_at else None,
        "attachments": attachments,
        "timeline": [
            {"status": s["status"], "label": s["label"], "state": s["state"]}
            for s in timeline
        ],
    })


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
    # failed is special — all regular steps show as pending, Failed appended at end
    failed = task.status == "failed"
    current_index = order.get(task.status, -1)

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
# GET /api/tasks/?page=X&per_page=20
#
# Paginated task history for the authenticated user, newest first.
# Intended for infinite-scroll in the chat feed.
# ---------------------------------------------------------------------------


@require_GET
def api_task_list(request):
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Authentication required"}, status=401)

    try:
        page = max(int(request.GET.get("page", 1)), 1)
        per_page = min(max(int(request.GET.get("per_page", 20)), 1), 100)
    except (ValueError, TypeError):
        return JsonResponse({"error": "Invalid page or per_page parameter"}, status=400)

    qs = (
        Task.objects.filter(created_by=request.user)
        .select_related("project")
        .order_by("-created_at")
    )

    paginator = Paginator(qs, per_page)
    try:
        page_obj = paginator.page(page)
    except EmptyPage:
        return JsonResponse({"tasks": [], "has_more": False, "next_page": None})

    tasks = [
        {
            "id": t.pk,
            "title": t.title,
            "status": t.status,
            "status_display": t.get_status_display(),
            "project": t.project.name if t.project_id else None,
            "branch_name": t.branch_name,
            "pr_url": t.pr_url,
            "error_message": t.error_message,
            "created_at": t.created_at.isoformat(),
            "completed_at": t.completed_at.isoformat() if t.completed_at else None,
        }
        for t in page_obj
    ]

    has_more = page_obj.has_next()
    return JsonResponse({
        "tasks": tasks,
        "has_more": has_more,
        "next_page": page_obj.next_page_number() if has_more else None,
    })


# ---------------------------------------------------------------------------
# POST /api/tasks/
#
# Create a task via AJAX from the chat input.  Accepts JSON body:
#   {project_id, title, description}
# Returns the new task as JSON (201).  Protected by Django's standard CSRF
# middleware — callers must include the X-CSRFToken header.
# ---------------------------------------------------------------------------


@require_POST
def api_task_create(request):
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Authentication required"}, status=401)

    try:
        data = json.loads(request.body or b"{}")
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    project_id = data.get("project_id")
    title = (data.get("title") or "").strip()
    description = (data.get("description") or "").strip()

    if not project_id:
        return JsonResponse({"error": "project_id is required"}, status=400)
    if not title:
        return JsonResponse({"error": "title is required"}, status=400)

    from django.db.models import Q

    project = (
        Project.objects.filter(
            Q(owner=request.user)
            | Q(team__owner=request.user)
            | Q(team__memberships__user=request.user),
            pk=project_id,
            is_active=True,
        )
        .distinct()
        .first()
    )
    if project is None:
        return JsonResponse({"error": "Project not found"}, status=404)

    title = bleach.clean(title, tags=[], strip=True)
    if not title:
        return JsonResponse({"error": "title is required"}, status=400)

    task = Task.objects.create(
        project=project,
        created_by=request.user,
        title=title,
        description=description or title,
        priority=50,
    )

    _forward_to_controller(task)
    _broadcast_queue_task_added(task)

    fire_event(
        "task_submitted",
        user=request.user,
        metadata={"task_id": task.pk, "project": task.project.github_repo},
    )

    logger.info("Task %s created via API by user %s", task.pk, request.user.id)
    return JsonResponse(
        {
            "id": task.pk,
            "title": task.title,
            "description": task.description,
            "status": task.status,
            "status_display": task.get_status_display(),
            "project": task.project.name,
            "created_at": task.created_at.isoformat(),
        },
        status=201,
    )


def api_tasks(request):
    """Dispatcher for GET /api/tasks/ (list) and POST /api/tasks/ (create)."""
    if request.method == "POST":
        return api_task_create(request)
    return api_task_list(request)


# ---------------------------------------------------------------------------
# GET /api/tasks/updates/?since=<iso_timestamp>
#
# Returns tasks updated since the given timestamp (used by WS clients to
# re-fetch missed status changes after a reconnect).  The `since` param must
# be an ISO-8601 datetime string; if omitted or invalid, returns all active
# tasks for the user.
# ---------------------------------------------------------------------------


@login_required
@require_GET
def api_task_updates(request):
    from django.utils.dateparse import parse_datetime

    since_str = request.GET.get("since", "").strip()
    since = parse_datetime(since_str) if since_str else None

    qs = Task.objects.filter(created_by=request.user).select_related("project")
    if since:
        qs = qs.filter(updated_at__gt=since)
    else:
        qs = qs.exclude(status__in=("completed", "failed"))

    queue_positions = _get_queue_positions(request.user.pk)
    wait_times = _get_wait_times(request.user.pk, queue_positions)
    tasks = [
        {
            "task_id": task.pk,
            "title": task.title,
            "status": task.status,
            "status_display": task.get_status_display(),
            "branch_name": task.branch_name,
            "pr_url": task.pr_url,
            "error_message": task.error_message,
            "queue_position": queue_positions.get(task.pk),
            "estimated_wait": wait_times.get(task.pk),
            "project_name": task.project.name if task.project_id else "",
        }
        for task in qs
    ]
    return JsonResponse({"tasks": tasks})


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

    new_status = (data.get("status") or "").strip()
    if new_status not in _TARS_STATUS_CHOICES:
        return JsonResponse(
            {"error": f"Invalid status. Must be one of: {sorted(_TARS_STATUS_CHOICES)}"},
            status=400,
        )

    idempotency_key = (
        request.META.get("HTTP_IDEMPOTENCY_KEY", "") or data.get("idempotency_key", "")
    ).strip()

    logger.info(
        "Task %s status update request: status=%r idempotency_key=%r ip=%s",
        pk,
        new_status,
        idempotency_key or None,
        request.META.get("REMOTE_ADDR"),
    )

    idempotency_cache_key = None
    if idempotency_key:
        idempotency_cache_key = f"task_status_idempotency:{pk}:{idempotency_key}"
        cached = cache.get(idempotency_cache_key, _CACHE_MISS)
        if cached is not _CACHE_MISS:
            logger.info("Task %s idempotency hit for key %r", pk, idempotency_key)
            return JsonResponse(cached)

    try:
        task = Task.objects.select_related("project").get(pk=pk)
    except Task.DoesNotExist:
        return JsonResponse({"error": "Task not found"}, status=404)

    current_status = task.status
    if new_status != current_status:
        allowed = _VALID_TRANSITIONS.get(current_status, set())
        if new_status not in allowed:
            logger.warning(
                "Task %s invalid transition %r -> %r",
                pk,
                current_status,
                new_status,
            )
            return JsonResponse(
                {
                    "error": (
                        f"Invalid status transition: {current_status!r} -> {new_status!r}. "
                        f"Allowed: {sorted(allowed) or 'none (terminal state)'}"
                    )
                },
                status=409,
            )

    update_fields = ["status"]
    task.status = new_status

    for field in ("branch_name", "pr_url", "error_message", "worker_id"):
        if field in data and data[field] is not None:
            setattr(task, field, data[field])
            update_fields.append(field)

    now = timezone.now()
    if new_status in ("assigned", "in_progress") and task.started_at is None:
        task.started_at = now
        update_fields.append("started_at")
    if new_status in ("completed", "failed") and task.completed_at is None:
        task.completed_at = now
        update_fields.append("completed_at")

    task.save(update_fields=update_fields)
    _broadcast_task_update(task)

    logger.info("Task %s status %r -> %r", task.pk, current_status, new_status)

    response_data = {
        "ok": True,
        "task_id": task.pk,
        "status": task.status,
        "status_display": task.get_status_display(),
        "branch_name": task.branch_name,
        "pr_url": task.pr_url,
        "worker_id": task.worker_id,
        "started_at": task.started_at.isoformat() if task.started_at else None,
        "completed_at": task.completed_at.isoformat() if task.completed_at else None,
        "updated_at": task.updated_at.isoformat() if task.updated_at else None,
    }

    if idempotency_cache_key:
        cache.set(idempotency_cache_key, response_data, _IDEMPOTENCY_TTL)

    return JsonResponse(response_data)


# ---------------------------------------------------------------------------
# POST /api/tasks/<pk>/retry
#
# Retry a failed task by creating a new task with the same title/description/
# project.  Protected by Django's standard session auth + CSRF.
# ---------------------------------------------------------------------------


@login_required
@require_POST
def api_task_retry(request, pk):
    task = get_object_or_404(Task.objects.select_related("project"), pk=pk, created_by=request.user)

    if task.status != "failed":
        return JsonResponse({"error": "Only failed tasks can be retried"}, status=400)

    new_task = Task.objects.create(
        project=task.project,
        created_by=request.user,
        title=task.title,
        description=task.description or task.title,
        priority=task.priority,
    )

    _forward_to_controller(new_task)
    _broadcast_queue_task_added(new_task)

    logger.info("Task %s retried as task %s by user %s", task.pk, new_task.pk, request.user.id)
    return JsonResponse(
        {
            "id": new_task.pk,
            "title": new_task.title,
            "status": new_task.status,
            "status_display": new_task.get_status_display(),
        },
        status=201,
    )


# ---------------------------------------------------------------------------
# POST /api/tasks/<pk>/cancel
#
# Cancel a pending or queued task by marking it failed with a user message.
# Protected by Django's standard session auth + CSRF.
# ---------------------------------------------------------------------------


@login_required
@require_POST
def api_task_cancel(request, pk):
    task = get_object_or_404(Task.objects.select_related("project"), pk=pk, created_by=request.user)

    if task.status not in ("pending", "queued"):
        return JsonResponse({"error": "Only pending or queued tasks can be cancelled"}, status=400)

    task.status = "failed"
    task.error_message = "Cancelled by user"
    task.completed_at = timezone.now()
    task.save(update_fields=["status", "error_message", "completed_at"])
    _broadcast_task_update(task)

    logger.info("Task %s cancelled by user %s", task.pk, request.user.id)
    return JsonResponse({"ok": True, "task_id": task.pk})


# ---------------------------------------------------------------------------
# POST /api/webhooks/github/
#
# Receives GitHub pull_request webhook events.  Validates the HMAC-SHA256
# signature using GITHUB_WEBHOOK_SECRET.  On a merged PR, updates the
# associated task to "completed" and posts an in-app notification.
# ---------------------------------------------------------------------------

_GITHUB_PR_TASK_RE = re.compile(r"tars[_-]task[_-]id:\s*(\d+)", re.IGNORECASE)


def _verify_github_signature(payload_body, secret, sig_header):
    """Return True if sig_header matches the HMAC-SHA256 of payload_body."""
    if not sig_header:
        return False
    computed = hmac.new(secret.encode(), payload_body, hashlib.sha256).hexdigest()
    expected = f"sha256={computed}"
    return hmac.compare_digest(expected, sig_header)


def _find_task_for_pr(pr_url, pr_body):
    """Look up a Task associated with a GitHub PR.

    Primary strategy: match stored pr_url.
    Fallback: parse 'tars-task-id: <N>' from the PR body.
    """
    if pr_url:
        task = (
            Task.objects.filter(pr_url=pr_url)
            .select_related("project", "created_by")
            .first()
        )
        if task:
            return task

    if pr_body:
        m = _GITHUB_PR_TASK_RE.search(pr_body)
        if m:
            try:
                return (
                    Task.objects.select_related("project", "created_by")
                    .get(pk=int(m.group(1)))
                )
            except Task.DoesNotExist:
                pass

    return None


def _handle_pr_opened(task, pr_url):
    """Update task when a PR is opened: set pr_url and move to 'reviewing'."""
    update_fields = []

    if pr_url and not task.pr_url:
        task.pr_url = pr_url
        update_fields.append("pr_url")

    if task.status not in ("completed", "failed", "reviewing"):
        task.status = "reviewing"
        update_fields.append("status")

    if update_fields:
        task.save(update_fields=update_fields)
        _broadcast_task_update(task)

    logger.info("GitHub webhook: PR opened for task %s", task.pk)


def _handle_pr_merged(task, pr_url):
    """Update task when a PR is merged: set completed and post notification."""
    update_fields = ["status"]
    task.status = "completed"

    if pr_url and not task.pr_url:
        task.pr_url = pr_url
        update_fields.append("pr_url")

    if task.completed_at is None:
        task.completed_at = timezone.now()
        update_fields.append("completed_at")

    task.save(update_fields=update_fields)
    _broadcast_task_update(task)

    create_notification(
        task.created_by,
        "PR merged!",
        "PR merged! Your changes are live.",
        link=task.pr_url or pr_url,
    )

    logger.info("GitHub webhook: PR merged for task %s → completed", task.pk)


@csrf_exempt
@require_POST
def github_webhook(request):
    secret = getattr(settings, "GITHUB_WEBHOOK_SECRET", "")
    if secret:
        sig_header = request.META.get("HTTP_X_HUB_SIGNATURE_256", "")
        if not _verify_github_signature(request.body, secret, sig_header):
            return HttpResponse(status=400)

    event_type = request.META.get("HTTP_X_GITHUB_EVENT", "")
    if event_type != "pull_request":
        return HttpResponse(status=200)

    try:
        payload = json.loads(request.body or b"{}")
    except (json.JSONDecodeError, ValueError):
        return HttpResponse(status=400)

    action = payload.get("action", "")
    if action not in ("opened", "closed", "reopened"):
        return HttpResponse(status=200)

    pr = payload.get("pull_request", {})
    pr_url = pr.get("html_url", "")
    pr_body = pr.get("body") or ""
    merged = pr.get("merged", False)

    task = _find_task_for_pr(pr_url, pr_body)
    if task is None:
        logger.debug("GitHub webhook: no task found for PR %s", pr_url)
        return HttpResponse(status=200)

    if action == "opened":
        _handle_pr_opened(task, pr_url)
    elif action == "closed" and merged:
        _handle_pr_merged(task, pr_url)
    else:
        logger.debug("GitHub webhook: unhandled action %r (merged=%s) for task %s", action, merged, task.pk)

    return HttpResponse(status=200)
