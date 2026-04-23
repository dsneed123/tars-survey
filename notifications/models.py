from django.conf import settings
from django.db import models


class Notification(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    title = models.CharField(max_length=200)
    message = models.TextField()
    link = models.CharField(max_length=500, blank=True)
    is_read = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user} — {self.title}"


class NotificationPreference(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notification_preferences",
    )
    email_welcome = models.BooleanField(default=True)
    email_task_started = models.BooleanField(default=True)
    email_pr_ready = models.BooleanField(default=True)
    email_task_failed = models.BooleanField(default=True)
    email_weekly_digest = models.BooleanField(default=True)

    def __str__(self):
        return f"Preferences for {self.user}"
