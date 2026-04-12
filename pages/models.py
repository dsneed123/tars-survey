from django.db import models


class Inquiry(models.Model):
    STATUS_PENDING = "pending"
    STATUS_REVIEWED = "reviewed"
    STATUS_APPROVED = "approved"
    STATUS_REJECTED = "rejected"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_REVIEWED, "Reviewed"),
        (STATUS_APPROVED, "Approved"),
        (STATUS_REJECTED, "Rejected"),
    ]

    name = models.CharField(max_length=200)
    email = models.EmailField()
    company = models.CharField(max_length=200)
    github_repo = models.CharField(max_length=500, blank=True, default="")
    team_size = models.CharField(max_length=50)
    use_case = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} ({self.email})"
