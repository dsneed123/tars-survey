from django.contrib import admin

from .models import Worker


@admin.register(Worker)
class WorkerAdmin(admin.ModelAdmin):
    list_display = ("hostname", "ip_address", "status", "capacity", "current_load", "last_heartbeat", "registered_at")
    list_filter = ("status",)
    search_fields = ("hostname", "ip_address")
    readonly_fields = ("api_key", "registered_at", "last_heartbeat")
