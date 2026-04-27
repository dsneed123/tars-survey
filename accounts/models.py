from django.contrib.auth.models import AbstractUser
from django.db import models


class CustomUser(AbstractUser):
    PLAN_CHOICES = [
        ("free", "Free"),
        ("starter", "Starter"),
        ("pro", "Pro"),
        ("enterprise", "Enterprise"),
    ]

    company_name = models.CharField(max_length=200, blank=True)
    plan = models.CharField(max_length=20, choices=PLAN_CHOICES, default="free")
    created_at = models.DateTimeField(auto_now_add=True)
    is_email_verified = models.BooleanField(default=False)

    def __str__(self):
        return self.email or self.username
