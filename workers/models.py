import uuid

from django.db import models


class Worker(models.Model):
    STATUS_CHOICES = [
        ("online", "Online"),
        ("busy", "Busy"),
        ("offline", "Offline"),
        ("maintenance", "Maintenance"),
    ]

    hostname = models.CharField(max_length=255)
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    capacity = models.IntegerField(default=1)
    current_load = models.IntegerField(default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="offline", db_index=True)
    last_heartbeat = models.DateTimeField(blank=True, null=True, db_index=True)
    registered_at = models.DateTimeField(auto_now_add=True)
    api_key = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    specs = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ["-registered_at"]

    def __str__(self):
        return f"{self.hostname} [{self.get_status_display()}]"


class TaskAssignment(models.Model):
    RESULT_CHOICES = [
        ("success", "Success"),
        ("failed", "Failed"),
        ("timeout", "Timeout"),
    ]

    task = models.ForeignKey(
        "tasks.Task",
        on_delete=models.CASCADE,
        related_name="assignments",
    )
    worker = models.ForeignKey(
        Worker,
        on_delete=models.CASCADE,
        related_name="assignments",
    )
    assigned_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(blank=True, null=True)
    result = models.CharField(max_length=20, choices=RESULT_CHOICES, blank=True, null=True)

    class Meta:
        ordering = ["-assigned_at"]

    def __str__(self):
        return f"Task {self.task_id} → {self.worker.hostname} [{self.result or 'pending'}]"
