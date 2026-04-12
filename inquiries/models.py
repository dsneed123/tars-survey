from django.db import models


class Inquiry(models.Model):
    COMPANY_SIZE_SOLO = 'solo'
    COMPANY_SIZE_2_10 = '2-10'
    COMPANY_SIZE_11_50 = '11-50'
    COMPANY_SIZE_51_200 = '51-200'
    COMPANY_SIZE_200_PLUS = '200+'

    COMPANY_SIZE_CHOICES = [
        (COMPANY_SIZE_SOLO, 'Solo'),
        (COMPANY_SIZE_2_10, '2–10'),
        (COMPANY_SIZE_11_50, '11–50'),
        (COMPANY_SIZE_51_200, '51–200'),
        (COMPANY_SIZE_200_PLUS, '200+'),
    ]

    BUDGET_UNDER_5K = 'under_5k'
    BUDGET_5K_15K = '5k_15k'
    BUDGET_15K_50K = '15k_50k'
    BUDGET_50K_PLUS = '50k_plus'
    BUDGET_NOT_SURE = 'not_sure'

    BUDGET_CHOICES = [
        (BUDGET_UNDER_5K, 'Under $5k'),
        (BUDGET_5K_15K, '$5k – $15k'),
        (BUDGET_15K_50K, '$15k – $50k'),
        (BUDGET_50K_PLUS, '$50k+'),
        (BUDGET_NOT_SURE, 'Not sure yet'),
    ]

    TIMELINE_ASAP = 'asap'
    TIMELINE_1_3_MONTHS = '1_3_months'
    TIMELINE_3_6_MONTHS = '3_6_months'
    TIMELINE_FLEXIBLE = 'flexible'

    TIMELINE_CHOICES = [
        (TIMELINE_ASAP, 'ASAP'),
        (TIMELINE_1_3_MONTHS, '1–3 months'),
        (TIMELINE_3_6_MONTHS, '3–6 months'),
        (TIMELINE_FLEXIBLE, 'Flexible'),
    ]

    STATUS_NEW = 'new'
    STATUS_CONTACTED = 'contacted'
    STATUS_QUALIFIED = 'qualified'
    STATUS_PROPOSAL_SENT = 'proposal_sent'
    STATUS_CLOSED_WON = 'closed_won'
    STATUS_CLOSED_LOST = 'closed_lost'

    STATUS_CHOICES = [
        (STATUS_NEW, 'New'),
        (STATUS_CONTACTED, 'Contacted'),
        (STATUS_QUALIFIED, 'Qualified'),
        (STATUS_PROPOSAL_SENT, 'Proposal Sent'),
        (STATUS_CLOSED_WON, 'Closed Won'),
        (STATUS_CLOSED_LOST, 'Closed Lost'),
    ]

    company_name = models.CharField(max_length=255)
    contact_name = models.CharField(max_length=255)
    email = models.EmailField()
    phone = models.CharField(max_length=50, blank=True)
    company_size = models.CharField(max_length=20, choices=COMPANY_SIZE_CHOICES)
    industry = models.CharField(max_length=255)
    project_description = models.TextField()
    budget_range = models.CharField(max_length=20, choices=BUDGET_CHOICES)
    timeline = models.CharField(max_length=20, choices=TIMELINE_CHOICES)
    how_heard_about_us = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_NEW)

    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = 'inquiries'

    def __str__(self):
        return f"{self.company_name} – {self.contact_name}"
