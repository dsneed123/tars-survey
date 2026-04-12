from django.db import models


class Inquiry(models.Model):
    TEAM_SIZE_CHOICES = [
        ("1", "1 — just me"),
        ("2-5", "2–5 engineers"),
        ("6-20", "6–20 engineers"),
        ("20+", "20+ engineers"),
    ]

    name = models.CharField(max_length=255)
    email = models.EmailField()
    company = models.CharField(max_length=255, blank=True)
    repo = models.CharField(max_length=500, blank=True)
    team_size = models.CharField(max_length=10, choices=TEAM_SIZE_CHOICES, blank=True)
    use_case = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name_plural = "inquiries"

    def __str__(self):
        return f"{self.name} <{self.email}>"
