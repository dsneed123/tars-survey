from django.db import models


class Inquiry(models.Model):
    COMPANY_SIZE_CHOICES = [
        ("solo", "Just me"),
        ("2_10", "2–10 people"),
        ("11_50", "11–50 people"),
        ("51_200", "51–200 people"),
        ("200_plus", "200+ people"),
    ]

    BUDGET_RANGE_CHOICES = [
        ("under_5k", "Under $5,000"),
        ("5k_15k", "$5,000 – $15,000"),
        ("15k_50k", "$15,000 – $50,000"),
        ("50k_plus", "$50,000+"),
        ("not_sure", "Not sure yet"),
    ]

    TIMELINE_CHOICES = [
        ("asap", "As soon as possible"),
        ("1_3_months", "1–3 months"),
        ("3_6_months", "3–6 months"),
        ("flexible", "Flexible / exploring"),
    ]

    STATUS_CHOICES = [
        ("new", "New"),
        ("contacted", "Contacted"),
        ("qualified", "Qualified"),
        ("proposal_sent", "Proposal Sent"),
        ("closed_won", "Closed Won"),
        ("closed_lost", "Closed Lost"),
    ]

    company_name = models.CharField(max_length=200)
    contact_name = models.CharField(max_length=200)
    email = models.EmailField()
    phone = models.CharField(max_length=50, blank=True)
    company_size = models.CharField(max_length=20, choices=COMPANY_SIZE_CHOICES)
    industry = models.CharField(max_length=200)
    project_description = models.TextField()
    budget_range = models.CharField(max_length=20, choices=BUDGET_RANGE_CHOICES)
    timeline = models.CharField(max_length=20, choices=TIMELINE_CHOICES)
    how_heard_about_us = models.CharField(max_length=300)
    primary_language = models.CharField(max_length=200, blank=True)
    repo_url = models.URLField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="new")

    class Meta:
        ordering = ["-created_at"]
        verbose_name_plural = "Inquiries"

    def __str__(self):
        return f"{self.company_name} — {self.contact_name} ({self.created_at.date()})"
