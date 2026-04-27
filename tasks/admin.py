from django.contrib import admin

from .models import Task, TaskAttachment


class TaskAttachmentInline(admin.TabularInline):
    model = TaskAttachment
    extra = 0
    readonly_fields = ("filename", "uploaded_at")


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ("title", "project", "created_by", "status", "pr_url", "priority", "created_at")
    list_filter = ("status",)
    search_fields = ("title", "description", "created_by__email", "project__name")
    raw_id_fields = ("created_by", "project")
    readonly_fields = ("created_at", "started_at", "completed_at")
    inlines = [TaskAttachmentInline]


@admin.register(TaskAttachment)
class TaskAttachmentAdmin(admin.ModelAdmin):
    list_display = ("filename", "task", "uploaded_at")
    search_fields = ("filename", "task__title")
    raw_id_fields = ("task",)
