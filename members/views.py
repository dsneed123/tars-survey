import json

from django.contrib import messages
from django.contrib.auth import logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from analytics.utils import fire_event
from notifications.models import NotificationPreference
from projects.models import Project
from tasks.models import Task
from tasks.templates import TASK_TEMPLATES
from tasks.views import _forward_to_controller, _get_queue_positions, _get_wait_times

from .models import MemberProfile

_WIDGET_STATUS_ORDER = {"in_progress": 0, "assigned": 1, "reviewing": 2, "queued": 3, "pending": 4}


@login_required
def dashboard(request):
    profile, _ = MemberProfile.objects.get_or_create(user=request.user)

    projects = Project.objects.filter(owner=request.user)

    # Latest 20 tasks for the chat feed, newest first
    all_tasks = list(
        Task.objects.filter(created_by=request.user)
        .select_related("project", "created_by")
        .order_by("-created_at")[:20]
    )

    # Pinned tasks, newest first (separate query so they always appear even outside the 50-task window)
    pinned_tasks = list(
        Task.objects.filter(created_by=request.user, is_pinned=True)
        .select_related("project", "created_by")
        .order_by("-created_at")
    )

    # Annotate each task with its queue position and estimated wait (pending/queued only)
    queue_positions = _get_queue_positions(request.user.pk)
    wait_times = _get_wait_times(request.user.pk, queue_positions)
    for task in all_tasks:
        task.queue_position = queue_positions.get(task.pk)
        task.wait_time = wait_times.get(task.pk)
    for task in pinned_tasks:
        task.queue_position = queue_positions.get(task.pk)
        task.wait_time = wait_times.get(task.pk)

    # All status counts in a single aggregate query instead of 8 separate COUNTs
    now = timezone.now()
    today = now.date()
    stats = Task.objects.filter(created_by=request.user).aggregate(
        total_tasks=Count("pk"),
        completed_count=Count("pk", filter=Q(status="completed")),
        failed_count=Count("pk", filter=Q(status="failed")),
        active_count=Count(
            "pk",
            filter=Q(status__in=["pending", "queued", "assigned", "in_progress", "reviewing"]),
        ),
        pending_count=Count("pk", filter=Q(status__in=["pending", "queued"])),
        in_progress_count=Count("pk", filter=Q(status="in_progress")),
        completed_today=Count("pk", filter=Q(status="completed", completed_at__date=today)),
        tasks_this_month=Count(
            "pk", filter=Q(created_at__year=now.year, created_at__month=now.month)
        ),
    )

    completed_count = stats["completed_count"]
    failed_count = stats["failed_count"]
    active_count = stats["active_count"]
    pending_count = stats["pending_count"]
    in_progress_count = stats["in_progress_count"]
    completed_today = stats["completed_today"]
    tasks_this_month = stats["tasks_this_month"]
    total_tasks = stats["total_tasks"]

    # Derive widget tasks from already-loaded all_tasks (no extra query).
    # Active tasks are almost always recent, so the latest-50 window covers them.
    queue_widget_tasks = sorted(
        (t for t in all_tasks if t.status in _WIDGET_STATUS_ORDER),
        key=lambda t: (_WIDGET_STATUS_ORDER[t.status], t.created_at),
    )[:3]

    # Build project-grouped queue data with health indicators for the queue panel.
    # Group active tasks by project, preserving priority/created_at ordering.
    _active_sorted = sorted(
        (t for t in all_tasks if t.status in _WIDGET_STATUS_ORDER),
        key=lambda t: (_WIDGET_STATUS_ORDER[t.status], t.created_at),
    )
    _proj_map: dict = {}
    for _t in _active_sorted:
        _pid = _t.project_id
        if _pid not in _proj_map:
            _proj_map[_pid] = {"project": _t.project, "tasks": []}
        _proj_map[_pid]["tasks"].append(_t)

    if _proj_map:
        _proj_ids = list(_proj_map.keys())
        _health_rows = (
            Task.objects.filter(
                project_id__in=_proj_ids,
                created_by=request.user,
                status__in=("completed", "failed"),
            )
            .values("project_id")
            .annotate(
                completed_cnt=Count("pk", filter=Q(status="completed")),
                failed_cnt=Count("pk", filter=Q(status="failed")),
            )
        )
        _health_by_proj = {row["project_id"]: row for row in _health_rows}
        queue_projects = []
        for _pid, _pdata in _proj_map.items():
            _row = _health_by_proj.get(_pid, {})
            _comp = _row.get("completed_cnt", 0)
            _fail = _row.get("failed_cnt", 0)
            _total = _comp + _fail
            if _total == 0:
                _health = "green"
            else:
                _rate = _comp / _total
                if _rate >= 0.8:
                    _health = "green"
                elif _rate >= 0.5:
                    _health = "yellow"
                else:
                    _health = "red"
            queue_projects.append(
                {
                    "project": _pdata["project"],
                    "tasks": _pdata["tasks"],
                    "health": _health,
                    "completed_cnt": _comp,
                    "failed_cnt": _fail,
                }
            )
    else:
        queue_projects = []

    # Success rate
    total_done = completed_count + failed_count
    success_rate = round((completed_count / total_done * 100) if total_done > 0 else 0)
    success_rate_display = f"{success_rate}%" if total_done > 0 else "—"

    # Queue bar percentages
    completed_pct = round((completed_count / total_tasks * 100) if total_tasks > 0 else 0)
    active_pct = round((active_count / total_tasks * 100) if total_tasks > 0 else 0)
    pending_pct = max(0, 100 - completed_pct - active_pct)

    ctx = {
        "profile": profile,
        "projects": projects,
        "all_tasks": all_tasks,
        "recent_tasks": all_tasks,
        "pinned_tasks": pinned_tasks,
        "task_templates": TASK_TEMPLATES,
        "task_templates_json": json.dumps(TASK_TEMPLATES),
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
        "queue_projects": queue_projects,
        "in_progress_count": in_progress_count,
        "completed_today": completed_today,
        "has_more": total_tasks > 20,
        "oldest_task_id": all_tasks[-1].pk if all_tasks else None,
        "show_tour": not profile.tour_completed and total_tasks == 0,
    }
    return render(request, "members/dashboard.html", ctx)


_LOAD_MORE_BATCH = 20


@login_required
def load_more_messages(request):
    before_id = request.GET.get("before_id")
    if not before_id:
        return JsonResponse({"html": "", "has_more": False, "oldest_id": None})
    try:
        before_id = int(before_id)
    except (ValueError, TypeError):
        return JsonResponse({"html": "", "has_more": False, "oldest_id": None})

    qs = (
        Task.objects.filter(created_by=request.user, pk__lt=before_id)
        .select_related("project", "created_by")
        .order_by("-created_at")
    )
    tasks = list(qs[: _LOAD_MORE_BATCH + 1])
    has_more = len(tasks) > _LOAD_MORE_BATCH
    tasks = tasks[:_LOAD_MORE_BATCH]

    queue_positions = _get_queue_positions(request.user.pk)
    wait_times = _get_wait_times(request.user.pk, queue_positions)
    for task in tasks:
        task.queue_position = queue_positions.get(task.pk)
        task.wait_time = wait_times.get(task.pk)

    html = render_to_string(
        "members/_task_messages.html",
        {"tasks": tasks},
        request=request,
    )
    oldest_id = tasks[-1].pk if tasks else None
    return JsonResponse({"html": html, "has_more": has_more, "oldest_id": oldest_id})


@login_required
@require_POST
def quick_add_task(request):
    is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"
    title = request.POST.get("title", "").strip()
    project_id = request.POST.get("project_id")

    if not title or not project_id:
        if is_ajax:
            return JsonResponse(
                {"ok": False, "error": "Please provide a task title and select a project."},
                status=400,
            )
        messages.error(request, "Please provide a task title and select a project.")
        return redirect("members:dashboard")

    try:
        project = Project.objects.get(pk=project_id, owner=request.user)
        task = Task.objects.create(
            title=title,
            description=title,
            project=project,
            created_by=request.user,
            status="pending",
            priority=50,
        )
        _forward_to_controller(task)
        fire_event(
            "task_submitted",
            user=request.user,
            metadata={"task_id": task.pk, "project": project.github_repo},
        )
        if is_ajax:
            return JsonResponse({"ok": True, "task_id": task.pk, "title": task.title, "status": task.status})
        messages.success(request, f'Task "{title}" submitted — TARS is on it.')
    except Project.DoesNotExist:
        if is_ajax:
            return JsonResponse({"ok": False, "error": "Project not found."}, status=400)
        messages.error(request, "Project not found.")

    return redirect("members:dashboard")


@login_required
@require_POST
def bulk_add_tasks(request):
    tasks_text = request.POST.get("tasks", "").strip()
    project_id = request.POST.get("project_id")

    if not tasks_text or not project_id:
        return JsonResponse(
            {"ok": False, "error": "Please provide tasks and select a project."},
            status=400,
        )

    lines = [line.strip() for line in tasks_text.splitlines() if line.strip()]
    if not lines:
        return JsonResponse(
            {"ok": False, "error": "No tasks found. Enter one task per line."},
            status=400,
        )

    try:
        project = Project.objects.get(pk=project_id, owner=request.user)
    except Project.DoesNotExist:
        return JsonResponse({"ok": False, "error": "Project not found."}, status=400)

    created = []
    for title in lines:
        task = Task.objects.create(
            title=title,
            description=title,
            project=project,
            created_by=request.user,
            status="pending",
            priority=50,
        )
        _forward_to_controller(task)
        fire_event(
            "task_submitted",
            user=request.user,
            metadata={"task_id": task.pk, "project": project.github_repo},
        )
        created.append({"task_id": task.pk, "title": task.title, "status": task.status})

    return JsonResponse({"ok": True, "tasks": created})


_ACTIVITY_CONFIGS = {
    "task_submitted":  ("bi-send",              "accent", "Task submitted"),
    "task_completed":  ("bi-check-circle-fill", "green",  "Task completed"),
    "task_failed":     ("bi-x-circle",          "red",    "Task failed"),
    "project_added":   ("bi-folder-plus",       "amber",  "Project added"),
    "pr_merged":       ("bi-git",               "purple", "PR merged"),
    "signup_completed":("bi-person-check",      "accent", "Account created"),
}


def _build_activity_entry(event, task_map, project_map):
    name = event.name
    meta = event.metadata or {}
    task_id = meta.get("task_id")
    project_id = meta.get("project_id")

    icon, color, label = _ACTIVITY_CONFIGS.get(
        name,
        ("bi-activity", "muted", name.replace("_", " ").title()),
    )

    task = task_map.get(task_id) if task_id else None
    project = project_map.get(project_id) if project_id else None
    link = None
    link_label = "View"

    if name in ("task_submitted", "task_completed", "task_failed"):
        description = task.title if task else (meta.get("title") or meta.get("project", ""))
        if task_id:
            link = reverse("tasks:detail", args=[task_id])
            link_label = "View task"
    elif name == "project_added":
        description = project.github_repo if project else meta.get("repo", "")
        if project_id:
            link = reverse("projects:detail", args=[project_id])
            link_label = "View project"
    elif name == "pr_merged":
        description = meta.get("title", "")
        pr_url = meta.get("pr_url")
        if pr_url:
            link = pr_url
            link_label = "View PR"
        elif task_id:
            link = reverse("tasks:detail", args=[task_id])
            link_label = "View task"
    elif name == "signup_completed":
        description = "You joined TARS"
    else:
        description = ""

    return {
        "name": name,
        "icon": icon,
        "color": color,
        "label": label,
        "description": description,
        "link": link,
        "link_label": link_label,
        "created_at": event.created_at,
    }


@login_required
def activity_log(request):
    from analytics.models import Event

    qs = Event.objects.filter(user=request.user).order_by("-created_at")
    paginator = Paginator(qs, 30)
    try:
        page_obj = paginator.page(request.GET.get("page", 1))
    except (EmptyPage, PageNotAnInteger):
        page_obj = paginator.page(1)

    events = list(page_obj)

    task_ids = {e.metadata.get("task_id") for e in events if e.metadata.get("task_id")}
    project_ids = {e.metadata.get("project_id") for e in events if e.metadata.get("project_id")}

    task_map = (
        {t.pk: t for t in Task.objects.filter(pk__in=task_ids).only("pk", "title")}
        if task_ids else {}
    )
    project_map = (
        {p.pk: p for p in Project.objects.filter(pk__in=project_ids).only("pk", "name", "github_repo")}
        if project_ids else {}
    )

    entries = [_build_activity_entry(e, task_map, project_map) for e in events]

    return render(request, "members/activity_log.html", {
        "entries": entries,
        "page_obj": page_obj,
    })


@login_required
def settings_view(request):
    user = request.user
    prefs, _ = NotificationPreference.objects.get_or_create(user=user)
    projects = Project.objects.filter(owner=user).order_by("name")

    if request.method == "POST":
        action = request.POST.get("action", "")

        if action == "profile":
            first_name = request.POST.get("first_name", "").strip()
            last_name = request.POST.get("last_name", "").strip()
            email = request.POST.get("email", "").strip().lower()
            company_name = request.POST.get("company_name", "").strip()

            if email and email != user.email:
                from accounts.models import CustomUser
                if CustomUser.objects.filter(email__iexact=email).exclude(pk=user.pk).exists():
                    messages.error(request, "That email address is already in use.")
                    return redirect("members:settings")
                user.email = email

            user.first_name = first_name
            user.last_name = last_name
            user.company_name = company_name
            user.save()
            messages.success(request, "Profile updated.")
            return redirect("members:settings")

        elif action == "notifications":
            prefs.email_welcome = "email_welcome" in request.POST
            prefs.email_task_started = "email_task_started" in request.POST
            prefs.email_pr_ready = "email_pr_ready" in request.POST
            prefs.email_task_failed = "email_task_failed" in request.POST
            prefs.email_weekly_digest = "email_weekly_digest" in request.POST
            prefs.save()
            messages.success(request, "Notification preferences saved.")
            return redirect("members:settings")

        elif action == "remove_project":
            project_id = request.POST.get("project_id")
            Project.objects.filter(pk=project_id, owner=user).delete()
            messages.success(request, "Project removed from TARS.")
            return redirect("members:settings")

        elif action == "delete_account":
            if request.POST.get("confirm_text") == "DELETE":
                auth_logout(request)
                user.delete()
                return redirect("pages:landing")
            messages.error(request, "Please type DELETE exactly to confirm.")
            return redirect("members:settings")

    return render(request, "members/settings.html", {
        "prefs": prefs,
        "projects": projects,
    })


@login_required
@require_POST
def complete_tour(request):
    profile, _ = MemberProfile.objects.get_or_create(user=request.user)
    profile.tour_completed = True
    profile.save(update_fields=["tour_completed"])
    return JsonResponse({"ok": True})

