import logging

from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags

from .models import Notification, NotificationPreference

logger = logging.getLogger(__name__)


def create_notification(user, title, message, link=""):
    """Create an in-app notification for a user."""
    return Notification.objects.create(
        user=user,
        title=title,
        message=message,
        link=link,
    )


def _get_prefs(user):
    """Get or create notification preferences for user."""
    prefs, _ = NotificationPreference.objects.get_or_create(user=user)
    return prefs


def send_html_email(subject, template_name, context, recipient_email):
    """Send an HTML email using a template. Falls back gracefully on error."""
    try:
        html_message = render_to_string(template_name, context)
        plain_message = strip_tags(html_message)
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[recipient_email],
            html_message=html_message,
            fail_silently=False,
        )
    except Exception as e:
        logger.warning("Failed to send email '%s' to %s: %s", subject, recipient_email, e)


def send_welcome_email(user):
    """Send the immediate welcome email on signup."""
    prefs = _get_prefs(user)
    if not prefs.email_welcome:
        return
    context = {
        "user": user,
        "site_url": settings.SITE_URL,
    }
    send_html_email(
        subject="Welcome to TARS — Your autonomous coding agent",
        template_name="emails/welcome.html",
        context=context,
        recipient_email=user.email,
    )
    create_notification(
        user=user,
        title="Welcome to TARS",
        message="Your account is ready. Connect a project and submit your first task.",
        link="/dashboard/projects/add/",
    )


def send_getting_started_email(user):
    """Send the 24h follow-up 'Getting Started' email."""
    prefs = _get_prefs(user)
    if not prefs.email_welcome:
        return
    context = {
        "user": user,
        "site_url": settings.SITE_URL,
    }
    send_html_email(
        subject="Getting started with TARS — tips for your first task",
        template_name="emails/getting_started.html",
        context=context,
        recipient_email=user.email,
    )


def send_task_started_email(task):
    """Notify user when a task transitions to in_progress."""
    user = task.created_by
    prefs = _get_prefs(user)
    if not prefs.email_task_started:
        return
    context = {
        "user": user,
        "task": task,
        "site_url": settings.SITE_URL,
        "task_url": f"{settings.SITE_URL}/dashboard/tasks/{task.pk}/",
    }
    send_html_email(
        subject=f"TARS is working on: {task.title}",
        template_name="emails/task_started.html",
        context=context,
        recipient_email=user.email,
    )
    create_notification(
        user=user,
        title=f"Task started: {task.title}",
        message=f"TARS is now working on your task in project {task.project.name}.",
        link=f"/dashboard/tasks/{task.pk}/",
    )


def send_task_pr_ready_email(task):
    """Notify user when a PR is ready for review."""
    user = task.created_by
    prefs = _get_prefs(user)
    if not prefs.email_pr_ready:
        return
    context = {
        "user": user,
        "task": task,
        "site_url": settings.SITE_URL,
        "task_url": f"{settings.SITE_URL}/dashboard/tasks/{task.pk}/",
    }
    send_html_email(
        subject=f"PR ready for review: {task.title}",
        template_name="emails/task_pr_ready.html",
        context=context,
        recipient_email=user.email,
    )
    create_notification(
        user=user,
        title=f"PR ready: {task.title}",
        message="TARS has opened a pull request. Review and merge when ready.",
        link=task.pr_url or f"/dashboard/tasks/{task.pk}/",
    )


def send_task_failed_email(task):
    """Notify user when a task fails."""
    user = task.created_by
    prefs = _get_prefs(user)
    if not prefs.email_task_failed:
        return
    context = {
        "user": user,
        "task": task,
        "site_url": settings.SITE_URL,
        "task_url": f"{settings.SITE_URL}/dashboard/tasks/{task.pk}/",
    }
    send_html_email(
        subject=f"Task failed: {task.title}",
        template_name="emails/task_failed.html",
        context=context,
        recipient_email=user.email,
    )
    create_notification(
        user=user,
        title=f"Task failed: {task.title}",
        message="A task encountered an error. View details to retry or update the task.",
        link=f"/dashboard/tasks/{task.pk}/",
    )
