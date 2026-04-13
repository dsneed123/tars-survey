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
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="offline")
    last_heartbeat = models.DateTimeField(blank=True, null=True)
    registered_at = models.DateTimeField(auto_now_add=True)
    api_key = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    specs = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ["-registered_at"]

    def __str__(self):
        return f"{self.hostname} [{self.get_status_display()}]"
