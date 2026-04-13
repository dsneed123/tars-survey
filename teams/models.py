import secrets

from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils.text import slugify


def _generate_invite_token():
    return secrets.token_urlsafe(32)


class Team(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=120, unique=True, blank=True)
    description = models.TextField(blank=True)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="owned_teams",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.name) or "team"
            slug = base
            i = 2
            while Team.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base}-{i}"
                i += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("teams:detail", kwargs={"slug": self.slug})

    @property
    def member_count(self):
        return self.memberships.count() + 1  # +1 for the owner

    def is_member(self, user):
        if not user.is_authenticated:
            return False
        return self.owner_id == user.id or self.memberships.filter(user=user).exists()

    def is_admin(self, user):
        if not user.is_authenticated:
            return False
        if self.owner_id == user.id:
            return True
        return self.memberships.filter(user=user, role="admin").exists()


class TeamMembership(models.Model):
    ROLE_CHOICES = [
        ("admin", "Admin"),
        ("member", "Member"),
    ]
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="memberships")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="team_memberships",
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default="member")
    joined_at = models.DateTimeField(auto_now_add=True)
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="team_invites_granted",
    )

    class Meta:
        unique_together = [("team", "user")]
        ordering = ["joined_at"]

    def __str__(self):
        return f"{self.user} in {self.team} ({self.role})"


class TeamInvite(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("accepted", "Accepted"),
        ("revoked", "Revoked"),
    ]
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="invites")
    email = models.EmailField(blank=True)
    token = models.CharField(max_length=64, unique=True, default=_generate_invite_token)
    role = models.CharField(max_length=20, choices=TeamMembership.ROLE_CHOICES, default="member")
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="sent_team_invites",
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    created_at = models.DateTimeField(auto_now_add=True)
    accepted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Invite to {self.team} ({self.status})"

    @property
    def is_pending(self):
        return self.status == "pending"

    def accept_url(self):
        return reverse("teams:invite_accept", kwargs={"token": self.token})
