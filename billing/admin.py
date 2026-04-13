from django.contrib import admin

from .models import Plan, Subscription


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ["name", "price_cents", "max_projects", "max_tasks_per_month", "stripe_price_id"]
    ordering = ["price_cents"]


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ["user", "plan", "status", "stripe_subscription_id", "current_period_end", "created_at"]
    list_filter = ["plan", "status"]
    search_fields = ["user__email", "stripe_subscription_id"]
    raw_id_fields = ["user"]
    readonly_fields = ["created_at", "updated_at"]
