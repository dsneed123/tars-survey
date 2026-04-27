from django.contrib import admin
from django.db.models import Count

from .models import Project


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("name", "github_repo", "owner", "language", "task_count", "is_active", "created_at")
    list_filter = ("language", "is_active")
    search_fields = ("name", "github_repo", "owner__email")
    raw_id_fields = ("owner",)

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_task_count=Count("tasks", distinct=True))

    @admin.display(description="Tasks", ordering="_task_count")
    def task_count(self, obj):
        return obj._task_count
