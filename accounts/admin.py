from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import CustomUser


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    list_display = ["email", "username", "company_name", "plan", "is_staff", "created_at"]
    list_filter = ["plan", "is_staff", "is_active"]
    search_fields = ["email", "username", "company_name"]
    fieldsets = UserAdmin.fieldsets + (
        ("TARS Profile", {"fields": ("company_name", "plan")}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ("TARS Profile", {"fields": ("email", "company_name", "plan")}),
    )
