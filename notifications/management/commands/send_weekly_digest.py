"""
Management command: send_weekly_digest

Sends a weekly summary email to all active users who have the weekly digest
preference enabled. Includes tasks completed, PRs merged, and project status.

Run via cron every Monday at 9am UTC:
    0 9 * * 1 cd /app && python manage.py send_weekly_digest
"""

import logging

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from notifications.utils import _get_prefs, send_html_email

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Send weekly digest emails to active users."

    def handle(self, *args, **options):
        from django.contrib.auth import get_user_model

        from projects.models import Project
        from tasks.models import Task

        User = get_user_model()

        now = timezone.now()
        week_ago = now - timezone.timedelta(days=7)

        active_users = User.objects.filter(is_active=True).exclude(email="")

        sent = 0
        for user in active_users:
            prefs = _get_prefs(user)
            if not prefs.email_weekly_digest:
                continue

            completed_tasks = Task.objects.filter(
                created_by=user,
                status="completed",
                completed_at__gte=week_ago,
            ).select_related("project")

            failed_tasks = Task.objects.filter(
                created_by=user,
                status="failed",
                completed_at__gte=week_ago,
            ).select_related("project")

            pr_tasks = Task.objects.filter(
                created_by=user,
                status__in=["completed", "reviewing"],
                started_at__gte=week_ago,
            ).exclude(pr_url="").exclude(pr_url__isnull=True).select_related("project")

            active_projects = Project.objects.filter(
                owner=user,
                is_active=True,
            )

            total_completed = completed_tasks.count()
            total_failed = failed_tasks.count()
            total_prs = pr_tasks.count()

            # Skip digest if user had no activity at all
            if total_completed == 0 and total_failed == 0 and total_prs == 0 and not active_projects.exists():
                continue

            context = {
                "user": user,
                "site_url": settings.SITE_URL,
                "week_start": week_ago,
                "week_end": now,
                "completed_tasks": completed_tasks[:10],
                "failed_tasks": failed_tasks[:5],
                "pr_tasks": pr_tasks[:10],
                "active_projects": active_projects[:10],
                "total_completed": total_completed,
                "total_failed": total_failed,
                "total_prs": total_prs,
            }

            try:
                send_html_email(
                    subject=f"Your TARS weekly digest — {total_completed} task(s) completed",
                    template_name="emails/weekly_digest.html",
                    context=context,
                    recipient_email=user.email,
                )
                sent += 1
                self.stdout.write(f"  Sent weekly digest to {user.email}")
            except Exception as e:
                logger.warning("Failed to send weekly digest to %s: %s", user.email, e)

        self.stdout.write(self.style.SUCCESS(f"Done. Sent {sent} weekly digest(s)."))
