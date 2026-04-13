from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from inquiries.models import Inquiry
from projects.models import Project
from tasks.models import Task

from .models import MemberProfile


@login_required
def dashboard(request):
    profile, _ = MemberProfile.objects.get_or_create(user=request.user)
    recent_inquiries = Inquiry.objects.filter(email=request.user.email)[:5]
    projects = Project.objects.filter(owner=request.user)
    recent_tasks = Task.objects.filter(created_by=request.user).select_related("project")[:10]
    active_tasks = recent_tasks.filter(status__in=["pending", "queued", "assigned", "in_progress", "reviewing"])
    completed_count = Task.objects.filter(created_by=request.user, status="completed").count()
    ctx = {
        "profile": profile,
        "recent_inquiries": recent_inquiries,
        "projects": projects,
        "recent_tasks": recent_tasks,
        "active_tasks": active_tasks,
        "completed_count": completed_count,
    }
    return render(request, "members/dashboard.html", ctx)
