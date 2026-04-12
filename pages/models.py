from django.db import models


class Inquiry(models.Model):
    TEAM_SIZE_CHOICES = [
        ("1", "1 — just me"),
        ("2-5", "2–5 engineers"),
        ("6-20", "6–20 engineers"),
        ("20+", "20+ engineers"),
    ]

    STATUS_CHOICES = [
        ("new", "New"),
        ("contacted", "Contacted"),
        ("qualified", "Qualified"),
        ("proposal", "Proposal"),
        ("won", "Won"),
        ("lost", "Lost"),
    ]

    name = models.CharField(max_length=255)
    email = models.EmailField()
    company = models.CharField(max_length=255, blank=True)
    repo = models.CharField(max_length=500, blank=True)
    team_size = models.CharField(max_length=10, choices=TEAM_SIZE_CHOICES, blank=True)
    use_case = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="new")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} <{self.email}>"

    def get_status_display_class(self):
        return {
            "new": "primary",
            "contacted": "info",
            "qualified": "warning",
            "proposal": "secondary",
            "won": "success",
            "lost": "danger",
        }.get(self.status, "secondary")


class InquiryNote(models.Model):
    inquiry = models.ForeignKey(Inquiry, on_delete=models.CASCADE, related_name="notes")
    note = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"Note on {self.inquiry} at {self.created_at:%Y-%m-%d %H:%M}"
