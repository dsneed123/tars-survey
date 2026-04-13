"""
Management command: send_getting_started_emails

Sends the 24-hour follow-up "Getting Started with TARS" email to users who
signed up between 24 and 48 hours ago and have not yet received it.

Run this via cron every hour:
    python manage.py send_getting_started_emails

Example cron entry (every hour):
    0 * * * * cd /app && python manage.py send_getting_started_emails
"""

import logging

from django.core.management.base import BaseCommand
from django.utils import timezone

from notifications.utils import send_getting_started_email

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Send 24h follow-up 'Getting Started' emails to recently signed-up users."

    def handle(self, *args, **options):
        from django.contrib.auth import get_user_model

        User = get_user_model()

        now = timezone.now()
        window_start = now - timezone.timedelta(hours=48)
        window_end = now - timezone.timedelta(hours=24)

        candidates = User.objects.filter(
            created_at__gte=window_start,
            created_at__lt=window_end,
            is_active=True,
        ).exclude(email="")

        sent = 0
        for user in candidates:
            try:
                send_getting_started_email(user)
                sent += 1
                self.stdout.write(f"  Sent getting-started email to {user.email}")
            except Exception as e:
                logger.warning("Failed to send getting-started email to %s: %s", user.email, e)

        self.stdout.write(self.style.SUCCESS(f"Done. Sent {sent} getting-started email(s)."))
