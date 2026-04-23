from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from analytics.utils import fire_event
from inquiries.models import Inquiry
from projects.forms import ProjectForm
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

    # Onboarding checklist (None once completed)
    onboarding_checklist = None if profile.onboarding_completed else {
        "has_project": projects.exists(),
        "has_task": total_tasks > 0,
    }

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
        "onboarding_checklist": onboarding_checklist,
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


@login_required
def onboarding(request):
    profile, _ = MemberProfile.objects.get_or_create(user=request.user)

    if profile.onboarding_completed:
        return redirect("members:dashboard")

    step = profile.onboarding_step
    project_form = None
    project = Project.objects.filter(owner=request.user).first()
    last_task = None

    if request.method == "POST":
        action = request.POST.get("action")

        if action == "add_project":
            project_form = ProjectForm(request.POST)
            if project_form.is_valid():
                p = project_form.save(commit=False)
                p.owner = request.user
                p.save()
                fire_event("onboarding_project_added", user=request.user, metadata={"project": p.github_repo})
                profile.onboarding_step = 2
                profile.save()
                return redirect("members:onboarding")
            # fall through to render with errors

        elif action == "submit_task":
            task_title = request.POST.get("task_title", "").strip()
            task_description = request.POST.get("task_description", "").strip()
            project_id = request.POST.get("project_id")
            if task_title and project_id:
                try:
                    proj = Project.objects.get(pk=project_id, owner=request.user)
                    task = Task.objects.create(
                        title=task_title,
                        description=task_description,
                        project=proj,
                        created_by=request.user,
                        status="pending",
                    )
                    _forward_to_controller(task)
                    fire_event("onboarding_task_submitted", user=request.user, metadata={"task_id": task.pk})
                    profile.onboarding_step = 3
                    profile.save()
                    return redirect("members:onboarding")
                except Project.DoesNotExist:
                    pass

        elif action == "complete":
            profile.onboarding_completed = True
            profile.save()
            messages.success(request, "Welcome to TARS! You're all set. Your first task is on its way.")
            return redirect("members:dashboard")

        elif action == "skip":
            profile.onboarding_completed = True
            profile.save()
            return redirect("members:dashboard")

    if step == 1:
        project_form = project_form or ProjectForm()

    if step == 3:
        last_task = Task.objects.filter(created_by=request.user).order_by("-created_at").first()

    ctx = {
        "profile": profile,
        "step": step,
        "project_form": project_form,
        "project": project,
        "last_task": last_task,
        "progress_pct": {1: 33, 2: 66, 3: 100}.get(step, 33),
        "example_tasks": [
            "Add a favicon to the site",
            "Fix the README with better installation instructions",
            "Add dark mode support",
            "Add input validation to all forms",
            "Write unit tests for the authentication module",
        ],
    }
    return render(request, "members/onboarding.html", ctx)


@login_required
def onboarding_skip(request):
    if request.method == "POST":
        profile, _ = MemberProfile.objects.get_or_create(user=request.user)
        profile.onboarding_completed = True
        profile.save()
    return redirect("members:dashboard")
