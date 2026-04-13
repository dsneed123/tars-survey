from datetime import datetime, timedelta

from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Count
from django.db.models.functions import TruncDate
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.cache import cache_page

from accounts.models import CustomUser
from projects.models import Project
from tasks.models import Task
from workers.models import Worker

from .models import Event, PageView


@staff_member_required
@cache_page(60)
def analytics_dashboard(request):
    now = timezone.now()

    # ── Date range filter ────────────────────────────────────────────────────
    date_from_str = request.GET.get("date_from", "")
    date_to_str = request.GET.get("date_to", "")

    try:
        date_from = (
            timezone.make_aware(datetime.strptime(date_from_str, "%Y-%m-%d"))
            if date_from_str
            else now - timedelta(days=30)
        )
    except ValueError:
        date_from = now - timedelta(days=30)

    try:
        date_to = (
            timezone.make_aware(
                datetime.strptime(date_to_str, "%Y-%m-%d") + timedelta(days=1)
            )
            if date_to_str
            else now
        )
    except ValueError:
        date_to = now

    # ── KPI cards ────────────────────────────────────────────────────────────
    total_users = CustomUser.objects.count()
    active_projects = Project.objects.filter(is_active=True).count()

    week_ago = now - timedelta(days=7)
    tasks_this_week = Task.objects.filter(created_at__gte=week_ago).count()

    total_tasks = Task.objects.count()
    completed_tasks = Task.objects.filter(status="completed").count()
    completion_rate = (
        round(completed_tasks / total_tasks * 100) if total_tasks else None
    )

    # ── Page views chart (last 30 days, fixed window) ────────────────────────
    chart_start = (now - timedelta(days=29)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    daily_views_qs = (
        PageView.objects.filter(created_at__gte=chart_start)
        .annotate(day=TruncDate("created_at"))
        .values("day")
        .annotate(count=Count("id"))
        .order_by("day")
    )
    daily_map = {row["day"]: row["count"] for row in daily_views_qs}

    chart_days_raw = []
    for i in range(30):
        day = (chart_start + timedelta(days=i)).date()
        chart_days_raw.append(
            {
                "date": day,
                "label": day.strftime("%-d %b"),
                "count": daily_map.get(day, 0),
            }
        )
    max_views = max((d["count"] for d in chart_days_raw), default=1) or 1

    chart_days = []
    for d in chart_days_raw:
        chart_days.append(
            {
                **d,
                "pct": round(d["count"] / max_views * 100),
            }
        )

    # ── Conversion funnel ────────────────────────────────────────────────────
    visitors = (
        PageView.objects.filter(created_at__gte=date_from, created_at__lt=date_to)
        .exclude(ip_address=None)
        .values("ip_address")
        .distinct()
        .count()
    )

    signups = CustomUser.objects.filter(
        created_at__gte=date_from, created_at__lt=date_to
    ).count()

    projects_added_users = (
        Project.objects.filter(created_at__gte=date_from, created_at__lt=date_to)
        .values("owner")
        .distinct()
        .count()
    )

    first_taskers = (
        CustomUser.objects.filter(
            tasks__created_at__gte=date_from, tasks__created_at__lt=date_to
        )
        .distinct()
        .count()
    )

    funnel_steps = [
        {"label": "Visitors", "count": visitors, "icon": "bi-eye"},
        {"label": "Signups", "count": signups, "icon": "bi-person-plus"},
        {"label": "Project Added", "count": projects_added_users, "icon": "bi-folder-plus"},
        {"label": "First Task", "count": first_taskers, "icon": "bi-send"},
    ]
    funnel_max = max((s["count"] for s in funnel_steps), default=1) or 1
    funnel = [
        {**s, "pct": round(s["count"] / funnel_max * 100)}
        for s in funnel_steps
    ]

    # ── Top pages ────────────────────────────────────────────────────────────
    top_pages_raw = list(
        PageView.objects.filter(created_at__gte=date_from, created_at__lt=date_to)
        .values("path")
        .annotate(count=Count("id"))
        .order_by("-count")[:10]
    )
    top_page_max = top_pages_raw[0]["count"] if top_pages_raw else 1
    top_pages = [
        {**p, "pct": round(p["count"] / top_page_max * 100)}
        for p in top_pages_raw
    ]

    # ── Worker fleet status ──────────────────────────────────────────────────
    stale_cutoff = now - timedelta(minutes=5)
    Worker.objects.filter(last_heartbeat__lt=stale_cutoff).exclude(
        status="offline"
    ).update(status="offline")

    worker_online = Worker.objects.filter(status="online").count()
    worker_busy = Worker.objects.filter(status="busy").count()
    worker_offline = Worker.objects.filter(status="offline").count()
    worker_total = worker_online + worker_busy + worker_offline

    # ── Recent signups ───────────────────────────────────────────────────────
    recent_signups = list(
        CustomUser.objects.order_by("-created_at")
        .values("id", "username", "email", "company_name", "plan", "created_at")[:15]
    )

    return render(
        request,
        "analytics/dashboard.html",
        {
            # KPIs
            "total_users": total_users,
            "active_projects": active_projects,
            "tasks_this_week": tasks_this_week,
            "completion_rate": completion_rate,
            # Chart
            "chart_days": chart_days,
            "max_views": max_views,
            # Funnel
            "funnel": funnel,
            "funnel_max": funnel_max,
            # Top pages
            "top_pages": top_pages,
            # Workers
            "worker_online": worker_online,
            "worker_busy": worker_busy,
            "worker_offline": worker_offline,
            "worker_total": worker_total,
            # Recent signups
            "recent_signups": recent_signups,
            # Date filter
            "date_from": date_from_str or (now - timedelta(days=30)).strftime("%Y-%m-%d"),
            "date_to": date_to_str or now.strftime("%Y-%m-%d"),
        },
    )
