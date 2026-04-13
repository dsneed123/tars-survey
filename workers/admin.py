from django.contrib import admin

from .models import TaskAssignment, Worker


@admin.register(Worker)
class WorkerAdmin(admin.ModelAdmin):
    list_display = ("hostname", "ip_address", "status", "capacity", "current_load", "last_heartbeat", "registered_at")
    list_filter = ("status",)
    search_fields = ("hostname", "ip_address")
    readonly_fields = ("api_key", "registered_at", "last_heartbeat")


@admin.register(TaskAssignment)
class TaskAssignmentAdmin(admin.ModelAdmin):
    list_display = ("task", "worker", "result", "assigned_at", "completed_at")
    list_filter = ("result", "worker")
    search_fields = ("task__title", "worker__hostname")
    raw_id_fields = ("task", "worker")
    readonly_fields = ("assigned_at",)
