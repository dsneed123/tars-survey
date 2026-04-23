from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Case, IntegerField, Value, When
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from projects.models import Project
from tasks.models import Task
from tasks.views import _forward_to_controller, _get_queue_positions

from .models import MemberProfile


@login_required
def dashboard(request):
    profile, _ = MemberProfile.objects.get_or_create(user=request.user)

    projects = Project.objects.filter(owner=request.user)

    # All tasks for the chat feed, newest last
    all_tasks = list(
        Task.objects.filter(created_by=request.user)
        .select_related("project", "created_by")
        .order_by("-created_at")[:50]
    )

    # Annotate each task with its queue position (pending/queued only)
    queue_positions = _get_queue_positions(request.user.pk)
    for task in all_tasks:
        task.queue_position = queue_positions.get(task.pk)

    completed_count = Task.objects.filter(created_by=request.user, status="completed").count()
    active_count = Task.objects.filter(
        created_by=request.user,
        status__in=["pending", "queued", "assigned", "in_progress", "reviewing"],
    ).count()
    pending_count = Task.objects.filter(
        created_by=request.user,
        status__in=["pending", "queued"],
    ).count()
    failed_count = Task.objects.filter(created_by=request.user, status="failed").count()
    in_progress_count = Task.objects.filter(
        created_by=request.user, status="in_progress"
    ).count()

    _widget_status_order = Case(
        When(status="in_progress", then=Value(0)),
        When(status="assigned", then=Value(1)),
        When(status="reviewing", then=Value(2)),
        When(status="queued", then=Value(3)),
        When(status="pending", then=Value(4)),
        default=Value(5),
        output_field=IntegerField(),
    )
    queue_widget_tasks = list(
        Task.objects.filter(
            created_by=request.user,
            status__in=["pending", "queued", "assigned", "in_progress", "reviewing"],
        )
        .select_related("project")
        .annotate(_widget_order=_widget_status_order)
        .order_by("_widget_order", "created_at")[:3]
    )
    total_tasks = Task.objects.filter(created_by=request.user).count()

    # Success rate
    total_done = completed_count + failed_count
    success_rate = round((completed_count / total_done * 100) if total_done > 0 else 0)
    success_rate_display = f"{success_rate}%" if total_done > 0 else "—"

    # Tasks this month
    now = timezone.now()
    tasks_this_month = Task.objects.filter(
        created_by=request.user,
        created_at__year=now.year,
        created_at__month=now.month,
    ).count()

    # Queue bar percentages
    completed_pct = round((completed_count / total_tasks * 100) if total_tasks > 0 else 0)
    active_pct = round((active_count / total_tasks * 100) if total_tasks > 0 else 0)
    pending_pct = max(0, 100 - completed_pct - active_pct)

    ctx = {
        "profile": profile,
        "projects": projects,
        "all_tasks": all_tasks,
        "recent_tasks": all_tasks,
        "completed_count": completed_count,
        "active_count": active_count,
        "pending_count": pending_count,
        "total_tasks": total_tasks,
        "tasks_this_month": tasks_this_month,
        "success_rate": success_rate,
        "success_rate_display": success_rate_display,
        "completed_pct": completed_pct,
        "active_pct": active_pct,
        "pending_pct": pending_pct,
        "queue_widget_tasks": queue_widget_tasks,
        "in_progress_count": in_progress_count,
    }
    return render(request, "members/dashboard.html", ctx)


@login_required
@require_POST
def quick_add_task(request):
    title = request.POST.get("title", "").strip()
    description = request.POST.get("description", "").strip()
    project_id = request.POST.get("project_id")

    if not title or not project_id:
        messages.error(request, "Please provide a task title and select a project.")
        return redirect("members:dashboard")

    try:
        project = Project.objects.get(pk=project_id, owner=request.user)
        task = Task.objects.create(
            title=title,
            description=description or title,
            project=project,
            created_by=request.user,
            status="pending",
        )
        _forward_to_controller(task)
        messages.success(request, f'Task "{title}" submitted — TARS is on it.')
    except Project.DoesNotExist:
        messages.error(request, "Project not found.")

    return redirect("members:dashboard")

