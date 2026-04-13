from django.conf import settings
from django.db import models


class Project(models.Model):
    LANGUAGE_CHOICES = [
        ("python", "Python"),
        ("javascript", "JavaScript"),
        ("typescript", "TypeScript"),
        ("go", "Go"),
        ("rust", "Rust"),
        ("java", "Java"),
        ("swift", "Swift"),
        ("other", "Other"),
    ]

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="projects",
    )
    team = models.ForeignKey(
        "teams.Team",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="projects",
        help_text="Optional. Link this project to a team so members can collaborate on it.",
    )
    name = models.CharField(max_length=200)
    github_repo = models.CharField(
        max_length=200,
        help_text='GitHub repository slug, e.g. "username/repo-name"',
    )
    description = models.TextField(blank=True)
    language = models.CharField(max_length=20, choices=LANGUAGE_CHOICES, default="other")
    default_branch = models.CharField(max_length=100, default="main")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} ({self.github_repo})"

    @property
    def github_url(self):
        return f"https://github.com/{self.github_repo}"
