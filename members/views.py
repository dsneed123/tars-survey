from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from analytics.utils import fire_event
from inquiries.models import Inquiry
from projects.forms import ProjectForm
from projects.models import Project
from tasks.models import Task
from tasks.views import _forward_to_controller

from .models import MemberProfile


@login_required
def dashboard(request):
    profile, _ = MemberProfile.objects.get_or_create(user=request.user)
    recent_inquiries = Inquiry.objects.filter(email=request.user.email)[:5]
    projects = Project.objects.filter(owner=request.user)
    recent_tasks = Task.objects.filter(created_by=request.user).select_related("project")[:10]
    active_tasks = Task.objects.filter(created_by=request.user, status__in=["pending", "queued", "assigned", "in_progress", "reviewing"])
    completed_count = Task.objects.filter(created_by=request.user, status="completed").count()

    # Onboarding checklist state
    has_project = projects.exists()
    has_task = Task.objects.filter(created_by=request.user).exists()
    onboarding_checklist = None
    if not profile.onboarding_completed:
        onboarding_checklist = [
            {
                "label": "Add Your First Project",
                "done": has_project or profile.onboarding_step > 1,
            },
            {
                "label": "Submit Your First Task",
                "done": has_task or profile.onboarding_step > 2,
            },
            {
                "label": "Watch TARS Work",
                "done": False,
            },
        ]

    ctx = {
        "profile": profile,
        "recent_inquiries": recent_inquiries,
        "projects": projects,
        "recent_tasks": recent_tasks,
        "active_tasks": active_tasks,
        "completed_count": completed_count,
        "onboarding_checklist": onboarding_checklist,
        "has_project": has_project,
        "has_task": has_task,
    }
    return render(request, "members/dashboard.html", ctx)


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
