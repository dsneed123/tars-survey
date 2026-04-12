from django.contrib import admin

from .models import Project


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("name", "github_repo", "owner", "language", "is_active", "created_at")
    list_filter = ("language", "is_active")
    search_fields = ("name", "github_repo", "owner__email")
    raw_id_fields = ("owner",)
