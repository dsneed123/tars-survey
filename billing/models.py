from django.conf import settings
from django.db import models


class Plan(models.Model):
    PLAN_NAMES = [
        ("free", "Free"),
        ("starter", "Starter"),
        ("pro", "Pro"),
        ("enterprise", "Enterprise"),
    ]

    name = models.CharField(max_length=20, choices=PLAN_NAMES, unique=True)
    stripe_price_id = models.CharField(max_length=200, blank=True, help_text="Stripe price ID (e.g. price_xxx)")
    max_projects = models.IntegerField(default=1, help_text="0 = unlimited")
    max_tasks_per_month = models.IntegerField(default=10, help_text="0 = unlimited")
    price_cents = models.IntegerField(default=0, help_text="Price in cents (e.g. 4900 = $49.00)")

    class Meta:
        ordering = ["price_cents"]

    def __str__(self):
        return self.get_name_display()

    @property
    def price_dollars(self):
        return self.price_cents / 100


class Subscription(models.Model):
    STATUS_CHOICES = [
        ("active", "Active"),
        ("canceled", "Canceled"),
        ("past_due", "Past Due"),
        ("trialing", "Trialing"),
        ("incomplete", "Incomplete"),
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="subscription",
    )
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT, related_name="subscriptions")
    stripe_subscription_id = models.CharField(max_length=200, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="active")
    current_period_end = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.email} — {self.plan}"
