from django.db import models


class InquirySubmission(models.Model):
    name = models.CharField(max_length=200)
    email = models.EmailField()
    company = models.CharField(max_length=200, blank=True)
    repo = models.CharField(max_length=300, blank=True)
    team_size = models.CharField(max_length=50, blank=True)
    use_case = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.email})"
