from django.contrib import admin

from .models import Event, PageView


@admin.register(PageView)
class PageViewAdmin(admin.ModelAdmin):
    list_display = ("path", "user", "ip_address", "created_at")
    list_filter = ("created_at",)
    search_fields = ("path", "ip_address", "user__email")
    readonly_fields = ("created_at",)
    date_hierarchy = "created_at"


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ("name", "user", "created_at")
    list_filter = ("name", "created_at")
    search_fields = ("name", "user__email")
    readonly_fields = ("created_at",)
    date_hierarchy = "created_at"
