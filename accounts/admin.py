from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.db.models import Count

from .models import CustomUser


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    list_display = ["email", "username", "company_name", "plan", "tasks_count", "last_login", "is_staff", "created_at"]
    list_filter = ["plan", "is_staff", "is_active", "is_email_verified"]
    search_fields = ["email", "username", "company_name"]
    fieldsets = UserAdmin.fieldsets + (
        ("TARS Profile", {"fields": ("company_name", "plan", "is_email_verified")}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ("TARS Profile", {"fields": ("email", "company_name", "plan")}),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_tasks_count=Count("tasks", distinct=True))

    @admin.display(description="Tasks", ordering="_tasks_count")
    def tasks_count(self, obj):
        return obj._tasks_count
