import os

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from projects.models import Project

from .forms import TaskForm
from .models import Task, TaskAttachment


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

    projects = Project.objects.filter(owner=request.user, is_active=True)

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
    task = get_object_or_404(Task, pk=pk, created_by=request.user)
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
