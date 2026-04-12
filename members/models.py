from django.contrib.auth.models import User
from django.db import models


class MemberProfile(models.Model):
    PLAN_CHOICES = [
        ("free", "Free"),
        ("starter", "Starter"),
        ("pro", "Pro"),
        ("enterprise", "Enterprise"),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    plan_tier = models.CharField(max_length=20, choices=PLAN_CHOICES, default="free")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} ({self.get_plan_tier_display()})"
