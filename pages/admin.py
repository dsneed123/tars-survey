from django.contrib import admin

from .models import Inquiry


@admin.register(Inquiry)
class InquiryAdmin(admin.ModelAdmin):
    list_display = ("name", "email", "company", "team_size", "created_at")
    list_filter = ("team_size", "created_at")
    search_fields = ("name", "email", "company")
    readonly_fields = ("created_at",)
    ordering = ("-created_at",)
