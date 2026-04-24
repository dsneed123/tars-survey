import os

from django.conf import settings
from django.db import models


class Task(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("queued", "Queued"),
        ("assigned", "Assigned"),
        ("in_progress", "In Progress"),
        ("reviewing", "Reviewing"),
        ("completed", "Completed"),
        ("failed", "Failed"),
    ]

    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.CASCADE,
        related_name="tasks",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="tasks",
    )
    title = models.CharField(max_length=300)
    description = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending", db_index=True)
    priority = models.IntegerField(default=50)
    worker_id = models.CharField(max_length=200, blank=True, null=True)
    branch_name = models.CharField(max_length=200, blank=True, null=True)
    pr_url = models.URLField(blank=True, null=True)
    error_message = models.TextField(blank=True, null=True)
    is_pinned = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True, db_index=True)
    started_at = models.DateTimeField(blank=True, null=True)
    completed_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.title} [{self.get_status_display()}]"

    @property
    def is_active(self):
        return self.status in ("queued", "assigned", "in_progress", "reviewing")

    @property
    def is_done(self):
        return self.status in ("completed", "failed")

    @property
    def duration_display(self):
        if not self.completed_at or not self.created_at:
            return None
        total_seconds = int((self.completed_at - self.created_at).total_seconds())
        if total_seconds <= 0:
            return None
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        if hours:
            return f"{hours}h {minutes}m"
        if minutes:
            return f"{minutes}m {seconds}s"
        return f"{seconds}s"


class TaskAttachment(models.Model):
    task = models.ForeignKey(
        Task,
        on_delete=models.CASCADE,
        related_name="attachments",
    )
    file = models.FileField(upload_to="attachments/%Y/%m/")
    filename = models.CharField(max_length=255)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["uploaded_at"]

    def __str__(self):
        return self.filename

    @property
    def extension(self):
        _, ext = os.path.splitext(self.filename)
        return ext.lower().lstrip(".")

    @property
    def is_image(self):
        return self.extension in ("jpg", "jpeg", "png", "gif", "webp", "svg")
