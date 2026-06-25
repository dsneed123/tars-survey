import secrets

from django.contrib.auth.models import AbstractUser
from django.db import models


def _generate_invite_key():
    return secrets.token_urlsafe(16)


class InviteKey(models.Model):
    key = models.CharField(max_length=64, unique=True, default=_generate_invite_key)
    label = models.CharField(max_length=100, blank=True, help_text="Optional note, e.g. 'for John'")
    created_at = models.DateTimeField(auto_now_add=True)
    used_at = models.DateTimeField(null=True, blank=True)
    used_by = models.ForeignKey(
        "CustomUser", null=True, blank=True, on_delete=models.SET_NULL, related_name="invite_used"
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        status = "used" if self.used_at else ("active" if self.is_active else "revoked")
        return f"{self.key[:12]}… [{status}]"

    @property
    def is_used(self):
        return self.used_at is not None


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
    github_id = models.BigIntegerField(null=True, blank=True, unique=True)
    github_username = models.CharField(max_length=100, blank=True)
    github_avatar_url = models.URLField(blank=True)

    def __str__(self):
        return self.email or self.username
