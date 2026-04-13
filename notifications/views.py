from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from .models import Notification, NotificationPreference


@login_required
def notification_preferences(request):
    prefs, _ = NotificationPreference.objects.get_or_create(user=request.user)
    if request.method == "POST":
        prefs.email_welcome = "email_welcome" in request.POST
        prefs.email_task_started = "email_task_started" in request.POST
        prefs.email_pr_ready = "email_pr_ready" in request.POST
        prefs.email_task_failed = "email_task_failed" in request.POST
        prefs.email_weekly_digest = "email_weekly_digest" in request.POST
        prefs.save()
        messages.success(request, "Notification preferences saved.")
        return redirect("notifications:preferences")
    return render(request, "notifications/preferences.html", {"prefs": prefs})


@login_required
@require_POST
def mark_read(request, pk):
    Notification.objects.filter(pk=pk, user=request.user).update(is_read=True)
    return JsonResponse({"ok": True})


@login_required
@require_POST
def mark_all_read(request):
    Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
    return JsonResponse({"ok": True})
